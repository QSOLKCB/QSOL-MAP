"""Command-line interface for the dependency-free QSOL-MAP reference."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .analysis import build_percept, verify_percept_envelope
from .canonical import canonical_bytes
from .multiresolution import build_multiresolution_percept, verify_multiresolution_envelope
from .sidecar import verify_spectral_sidecar, write_spectral_sidecar
from .wav import parse_pcm16_wav


def _write_envelope(envelope: dict, output_path: Path | None) -> None:
    encoded = canonical_bytes(envelope)
    if output_path is None:
        sys.stdout.buffer.write(encoded + b"\n")
    else:
        output_path.write_bytes(encoded)


def _same_path(left: Path, right: Path) -> bool:
    """Return whether two paths designate the same filesystem object.

    Existing paths are compared by filesystem identity first so distinct hard
    links to one inode cannot bypass the collision guard. The resolved-string
    comparison remains the fallback for paths that do not exist yet.
    """
    try:
        if left.exists() and right.exists() and left.samefile(right):
            return True
    except OSError:
        pass
    return left.resolve(strict=False) == right.resolve(strict=False)


def _same_as_stream(path: Path, stream) -> bool:
    """Return whether an existing path aliases the stream's open file object."""
    try:
        path_stat = path.stat()
        stream_stat = os.fstat(stream.fileno())
    except (AttributeError, OSError, ValueError):
        return False
    return (
        path_stat.st_dev == stream_stat.st_dev
        and path_stat.st_ino == stream_stat.st_ino
    )


def _analyze(input_path: Path, output_path: Path | None) -> int:
    wave = parse_pcm16_wav(input_path.read_bytes())
    _write_envelope(build_percept(wave), output_path)
    return 0


def _analyze_v02(input_path: Path, output_path: Path | None, sidecar_path: Path | None) -> int:
    if output_path is not None and _same_path(input_path, output_path):
        raise ValueError("percept output must not overwrite the input WAV")
    if sidecar_path is not None and _same_path(input_path, sidecar_path):
        raise ValueError("sidecar output must not overwrite the input WAV")
    if output_path is not None and sidecar_path is not None and _same_path(output_path, sidecar_path):
        raise ValueError("percept output and sidecar output must be different paths")
    if output_path is None and sidecar_path is not None and _same_as_stream(sidecar_path, sys.stdout):
        raise ValueError("sidecar output must not alias stdout when the percept is written to stdout")

    wave = parse_pcm16_wav(input_path.read_bytes())
    envelope = build_multiresolution_percept(wave)
    _write_envelope(envelope, output_path)
    if sidecar_path is not None:
        with sidecar_path.open("w", encoding="utf-8", newline="") as stream:
            write_spectral_sidecar(wave, envelope, stream)
    return 0


def _verify(input_path: Path) -> int:
    envelope = json.loads(input_path.read_text(encoding="utf-8"))
    if not verify_percept_envelope(envelope):
        print("invalid QSOL-MAP percept envelope", file=sys.stderr)
        return 1
    print(envelope["percept_sha256"])
    return 0


def _verify_v02(input_path: Path) -> int:
    envelope = json.loads(input_path.read_text(encoding="utf-8"))
    if not verify_multiresolution_envelope(envelope):
        print("invalid QSOL-MAP v0.2 percept envelope", file=sys.stderr)
        return 1
    print(envelope["percept_sha256"])
    return 0


def _verify_sidecar(percept_path: Path, sidecar_path: Path) -> int:
    envelope = json.loads(percept_path.read_text(encoding="utf-8"))
    with sidecar_path.open("r", encoding="utf-8", newline="") as stream:
        valid = verify_spectral_sidecar(envelope, stream)
    if not valid:
        print("invalid QSOL-MAP v0.2 spectral sidecar", file=sys.stderr)
        return 1
    print(envelope["percept_sha256"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m qsol_map",
        description="QSOL-MAP deterministic machine-audio observation reference",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="analyze with frozen v0.1 profile")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("-o", "--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify a frozen v0.1 percept envelope")
    verify.add_argument("input", type=Path)

    analyze_v02 = subparsers.add_parser(
        "analyze-v0.2",
        help="analyze with v0.2 multi-resolution deterministic observation",
    )
    analyze_v02.add_argument("input", type=Path)
    analyze_v02.add_argument("-o", "--output", type=Path)
    analyze_v02.add_argument(
        "--sidecar",
        type=Path,
        help="optionally stream the full short+long complex spectral evidence as canonical NDJSON",
    )

    verify_v02 = subparsers.add_parser("verify-v0.2", help="verify a v0.2 percept envelope")
    verify_v02.add_argument("input", type=Path)

    verify_sidecar = subparsers.add_parser(
        "verify-sidecar-v0.2",
        help="verify a v0.2 spectral sidecar against its compact percept",
    )
    verify_sidecar.add_argument("percept", type=Path)
    verify_sidecar.add_argument("sidecar", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            return _analyze(args.input, args.output)
        if args.command == "verify":
            return _verify(args.input)
        if args.command == "analyze-v0.2":
            return _analyze_v02(args.input, args.output, args.sidecar)
        if args.command == "verify-v0.2":
            return _verify_v02(args.input)
        if args.command == "verify-sidecar-v0.2":
            return _verify_sidecar(args.percept, args.sidecar)
    except (OSError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())