"""Command-line interface for the dependency-free QSOL-MAP reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .analysis import build_percept, verify_percept_envelope
from .canonical import canonical_bytes
from .wav import parse_pcm16_wav


def _analyze(input_path: Path, output_path: Path | None) -> int:
    wave = parse_pcm16_wav(input_path.read_bytes())
    envelope = build_percept(wave)
    encoded = canonical_bytes(envelope)
    if output_path is None:
        sys.stdout.buffer.write(encoded + b"\n")
    else:
        output_path.write_bytes(encoded)
    return 0


def _verify(input_path: Path) -> int:
    envelope = json.loads(input_path.read_text(encoding="utf-8"))
    if not verify_percept_envelope(envelope):
        print("invalid QSOL-MAP percept envelope", file=sys.stderr)
        return 1
    print(envelope["percept_sha256"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m qsol_map",
        description="QSOL-MAP deterministic machine-audio observation reference",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="analyze a strict PCM16 RIFF/WAVE file")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("-o", "--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify a percept envelope hash")
    verify.add_argument("input", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            return _analyze(args.input, args.output)
        if args.command == "verify":
            return _verify(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
