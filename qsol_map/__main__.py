"""Command-line interface for the dependency-free QSOL-MAP reference."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unicodedata

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


def _write_all(fd: int, payload: bytes) -> None:
    """Write the complete byte payload to an already validated file handle."""
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if type(written) is not int or written <= 0 or written > len(view):
            raise OSError("output write made invalid progress")
        view = view[written:]


def _reserve_output_file(path: Path) -> int:
    """Open or create a regular output without truncating or following a symlink."""
    flags = os.O_WRONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        try:
            fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("v0.2 output destination must be a regular file")
        return fd
    except Exception:
        os.close(fd)
        raise


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _reserved_path_matches(path: Path, fd: int) -> bool:
    """Check that a reserved pathname still names the already-open file."""
    try:
        path_stat = os.stat(path, follow_symlinks=False)
        fd_stat = os.fstat(fd)
    except OSError:
        return False
    return stat.S_ISREG(path_stat.st_mode) and _same_stat(path_stat, fd_stat)


def _stdout_stat():
    try:
        return os.fstat(sys.stdout.fileno())
    except (AttributeError, OSError, ValueError):
        return None


def _validate_reserved_outputs(
    input_stat: os.stat_result,
    output_path: Path | None,
    output_fd: int | None,
    sidecar_path: Path | None,
    sidecar_fd: int | None,
    *,
    require_paths_unchanged: bool,
) -> None:
    """Validate reserved destination identities before any truncating write."""
    output_stat = os.fstat(output_fd) if output_fd is not None else None
    sidecar_stat = os.fstat(sidecar_fd) if sidecar_fd is not None else None
    stdout_stat = _stdout_stat()

    if output_stat is not None and _same_stat(input_stat, output_stat):
        raise ValueError("percept output must not overwrite the input WAV")
    if output_stat is None and stdout_stat is not None and _same_stat(input_stat, stdout_stat):
        raise ValueError("stdout percept output must not alias the input WAV")
    if sidecar_stat is not None and _same_stat(input_stat, sidecar_stat):
        raise ValueError("sidecar output must not overwrite the input WAV")
    if output_stat is not None and sidecar_stat is not None and _same_stat(output_stat, sidecar_stat):
        raise ValueError("percept output and sidecar output must be different paths")
    if output_stat is None and sidecar_stat is not None and stdout_stat is not None:
        if _same_stat(sidecar_stat, stdout_stat):
            raise ValueError("sidecar output must not alias stdout when the percept is written to stdout")

    if require_paths_unchanged:
        if output_fd is not None and output_path is not None:
            if not _reserved_path_matches(output_path, output_fd):
                raise ValueError("percept output path changed after reservation")
        if sidecar_fd is not None and sidecar_path is not None:
            if not _reserved_path_matches(sidecar_path, sidecar_fd):
                raise ValueError("sidecar output path changed after reservation")


def _filesystem_case_insensitive(directory: Path) -> bool:
    """Probe whether an existing output directory aliases case variants."""
    probe_path: Path | None = None
    try:
        directory = directory.resolve(strict=True)
        with tempfile.NamedTemporaryFile(
            prefix="QsolMapCaseProbeAa",
            dir=directory,
            delete=False,
        ) as probe:
            probe_path = Path(probe.name)
        alternate = probe_path.with_name(probe_path.name.swapcase())
        if alternate == probe_path or not alternate.exists():
            return False
        return probe_path.samefile(alternate)
    except OSError:
        return False
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink()
            except OSError:
                pass


def _filesystem_normalization_insensitive(directory: Path) -> bool:
    """Probe whether an existing output directory aliases NFC/NFD names."""
    probe_path: Path | None = None
    try:
        directory = directory.resolve(strict=True)
        with tempfile.NamedTemporaryFile(
            prefix="QsolMapNormProbe-é-",
            dir=directory,
            delete=False,
        ) as probe:
            probe_path = Path(probe.name)
        alternate_name = unicodedata.normalize("NFD", probe_path.name)
        alternate = probe_path.with_name(alternate_name)
        if alternate == probe_path or not alternate.exists():
            return False
        return probe_path.samefile(alternate)
    except OSError:
        return False
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink()
            except OSError:
                pass


def _same_path(left: Path, right: Path) -> bool:
    """Return whether two paths designate the same filesystem object or name.

    Existing paths are compared by filesystem identity first so distinct hard
    links to one inode cannot bypass the collision guard. For paths that do not
    exist yet, exact resolved names are compared and then case/Unicode
    normalization equivalence is checked against the behavior of the shared
    target filesystem before either destination is created.
    """
    try:
        if left.exists() and right.exists() and left.samefile(right):
            return True
    except OSError:
        pass

    left_resolved = left.resolve(strict=False)
    right_resolved = right.resolve(strict=False)
    if left_resolved == right_resolved:
        return True

    left_name = left_resolved.name
    right_name = right_resolved.name
    left_nfc = unicodedata.normalize("NFC", left_name)
    right_nfc = unicodedata.normalize("NFC", right_name)
    case_equivalent = left_name.casefold() == right_name.casefold()
    normalization_equivalent = left_nfc == right_nfc
    normalized_case_equivalent = left_nfc.casefold() == right_nfc.casefold()
    if not normalized_case_equivalent:
        return False

    try:
        left_parent = left_resolved.parent.resolve(strict=True)
        right_parent = right_resolved.parent.resolve(strict=True)
        if not left_parent.samefile(right_parent):
            return False
    except OSError:
        return False

    if case_equivalent:
        return _filesystem_case_insensitive(left_parent)
    if normalization_equivalent:
        return _filesystem_normalization_insensitive(left_parent)
    return (
        _filesystem_case_insensitive(left_parent)
        and _filesystem_normalization_insensitive(left_parent)
    )


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
    # Keep the cheap name/filesystem preflight for clear errors, but do not
    # trust it as the write authority. The actual v0.2 destinations are opened
    # and validated below before the potentially expensive analysis begins.
    if output_path is not None and _same_path(input_path, output_path):
        raise ValueError("percept output must not overwrite the input WAV")
    if output_path is None and _same_as_stream(input_path, sys.stdout):
        raise ValueError("stdout percept output must not alias the input WAV")
    if sidecar_path is not None and _same_path(input_path, sidecar_path):
        raise ValueError("sidecar output must not overwrite the input WAV")
    if output_path is not None and sidecar_path is not None and _same_path(output_path, sidecar_path):
        raise ValueError("percept output and sidecar output must be different paths")
    if output_path is None and sidecar_path is not None and _same_as_stream(sidecar_path, sys.stdout):
        raise ValueError("sidecar output must not alias stdout when the percept is written to stdout")

    output_fd: int | None = None
    sidecar_fd: int | None = None
    with input_path.open("rb") as input_stream:
        input_stat = os.fstat(input_stream.fileno())
        try:
            if output_path is not None:
                output_fd = _reserve_output_file(output_path)
            if sidecar_path is not None:
                sidecar_fd = _reserve_output_file(sidecar_path)

            _validate_reserved_outputs(
                input_stat,
                output_path,
                output_fd,
                sidecar_path,
                sidecar_fd,
                require_paths_unchanged=True,
            )

            wave = parse_pcm16_wav(input_stream.read())
            envelope = build_multiresolution_percept(wave)

            # Re-check the reserved names after analysis. If another process
            # replaced either directory entry, fail before truncating either
            # already-open output. Writes themselves use only the reserved fds.
            _validate_reserved_outputs(
                input_stat,
                output_path,
                output_fd,
                sidecar_path,
                sidecar_fd,
                require_paths_unchanged=True,
            )

            encoded = canonical_bytes(envelope)
            if output_fd is None:
                sys.stdout.buffer.write(encoded + b"\n")
            else:
                os.ftruncate(output_fd, 0)
                os.lseek(output_fd, 0, os.SEEK_SET)
                _write_all(output_fd, encoded)

            if sidecar_fd is not None:
                os.ftruncate(sidecar_fd, 0)
                os.lseek(sidecar_fd, 0, os.SEEK_SET)
                with os.fdopen(
                    os.dup(sidecar_fd),
                    "w",
                    encoding="utf-8",
                    newline="",
                ) as stream:
                    write_spectral_sidecar(wave, envelope, stream)

            _validate_reserved_outputs(
                input_stat,
                output_path,
                output_fd,
                sidecar_path,
                sidecar_fd,
                require_paths_unchanged=True,
            )
            return 0
        finally:
            if output_fd is not None:
                os.close(output_fd)
            if sidecar_fd is not None:
                os.close(sidecar_fd)


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
