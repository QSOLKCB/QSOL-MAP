"""QSOL-MAP v0.2 sidecar API with writer and verifier hardening."""

from __future__ import annotations

import io
import threading

from . import multiresolution as _mr
from . import sidecar_receipts_core as _receipts_module
from .canonical import canonical_bytes


_LINE_LIMIT_LOCK = threading.RLock()


def _reexport(module) -> None:
    for name in dir(module):
        if not name.startswith("__"):
            globals()[name] = getattr(module, name)


_reexport(_receipts_module)


def _line_limit_modules():
    """Return verifier modules that consume the public sidecar line limit."""
    modules = [_receipts_module]
    for name in ("_base", "_consistency"):
        module = getattr(_receipts_module, name, None)
        if module is not None:
            modules.append(module)
            nested = getattr(module, "_core", None)
            if nested is not None:
                modules.append(nested)
    unique = []
    seen = set()
    for module in modules:
        identity = id(module)
        if identity not in seen:
            seen.add(identity)
            unique.append(module)
    return unique


def _ensure_empty_destination(stream) -> None:
    """Require a provably empty sidecar destination before emitting a header.

    A canonical sidecar is a complete stream beginning with exactly one header.
    Appending to prior content, or overwriting only a prefix while leaving stale
    trailing bytes, can return a receipt for a stream the verifier must reject.
    Seekable destinations are therefore accepted only when both the current
    position and total length are zero. Non-seekable destinations cannot prove
    that property and fail closed.
    """
    if isinstance(stream, io.StringIO):
        try:
            position = stream.tell()
            stream.seek(0, io.SEEK_END)
            end = stream.tell()
            stream.seek(position)
        except (OSError, ValueError) as exc:
            raise ValueError("sidecar destination must be seekable and empty") from exc
        if position != 0 or end != 0:
            raise ValueError("sidecar destination must be empty and positioned at zero")
        return

    binary = getattr(stream, "buffer", None)
    if binary is None:
        raise ValueError(
            "sidecar text stream must be StringIO or expose a writable binary buffer"
        )
    flush = getattr(stream, "flush", None)
    if callable(flush):
        flush()
    try:
        position = binary.tell()
        binary.seek(0, io.SEEK_END)
        end = binary.tell()
        binary.seek(position)
    except (AttributeError, OSError, ValueError) as exc:
        raise ValueError("sidecar destination must be seekable and empty") from exc
    if position != 0 or end != 0:
        raise ValueError("sidecar destination must be empty and positioned at zero")


class _ExactUTF8TextSink:
    """Present a text ``write`` API while preserving canonical UTF-8 bytes.

    ``TextIOWrapper`` may translate ``\n`` on write, notably to CRLF on
    Windows when opened with ``newline=None``. For binary-backed text streams
    we therefore flush any pending text and write encoded bytes directly to
    the underlying buffer. ``StringIO`` is safe because it performs no newline
    translation. Other opaque text sinks cannot prove byte-exact behavior and
    are rejected rather than silently emitting non-canonical NDJSON.
    """

    def __init__(self, stream):
        self._stream = stream
        self._binary = getattr(stream, "buffer", None)
        if self._binary is not None and callable(getattr(self._binary, "write", None)):
            flush = getattr(stream, "flush", None)
            if callable(flush):
                flush()
        elif isinstance(stream, io.StringIO):
            self._binary = None
        else:
            raise ValueError(
                "sidecar text stream must be StringIO or expose a writable binary buffer"
            )

    def write(self, text: str):
        if not isinstance(text, str):
            raise TypeError("sidecar writer accepts text records only")
        if self._binary is not None:
            return self._binary.write(text.encode("utf-8"))
        return self._stream.write(text)


class _ExactUTF8LineReader:
    """Read exact UTF-8 bytes without ``TextIOWrapper`` newline translation."""

    def __init__(self, binary):
        self._binary = binary

    def readline(self, size: int = -1) -> str:
        if size is None or size < 0:
            size = MAX_SIDECAR_LINE_CHARS + 1
        payload = self._binary.readline(size)
        if payload == b"":
            return ""
        return payload.decode("utf-8")


def _exact_verification_lines(lines):
    """Return a line source that preserves the sidecar's underlying bytes.

    A normal ``TextIOWrapper`` opened with ``newline=None`` translates CRLF to
    LF before callers can inspect it. When a binary buffer is available, sync
    the wrapper to its logical position and verify from that buffer directly so
    canonical LF delimiters are checked before any text newline translation.
    ``StringIO`` and explicit string iterables have no hidden byte translation
    layer and are passed through unchanged.
    """
    binary = getattr(lines, "buffer", None)
    if binary is None:
        return lines
    try:
        cookie = lines.tell()
        lines.seek(cookie)
    except (AttributeError, OSError, ValueError):
        return None
    if not callable(getattr(binary, "readline", None)):
        return None
    return _ExactUTF8LineReader(binary)


def verify_spectral_sidecar(envelope: dict, lines) -> bool:
    """Verify while preserving line bounds and exact canonical sidecar bytes."""
    exact_lines = _exact_verification_lines(lines)
    if exact_lines is None:
        return False

    # Nested verifier modules expose the same legacy module-global limit. Keep
    # the complete override/verification/restore interval serialized so one
    # concurrent call cannot restore a larger previous value while another is
    # still consuming untrusted records.
    with _LINE_LIMIT_LOCK:
        limit = MAX_SIDECAR_LINE_CHARS
        previous = []
        try:
            for module in _line_limit_modules():
                if hasattr(module, "MAX_SIDECAR_LINE_CHARS"):
                    previous.append((module, module.MAX_SIDECAR_LINE_CHARS))
                    module.MAX_SIDECAR_LINE_CHARS = limit
            return _receipts_module.verify_spectral_sidecar(envelope, exact_lines)
        finally:
            for module, old_limit in reversed(previous):
                module.MAX_SIDECAR_LINE_CHARS = old_limit


def write_spectral_sidecar(wave, envelope: dict, stream):
    """Write only evidence that exactly matches the supplied PCM16 waveform."""
    if not _mr.verify_multiresolution_envelope(envelope):
        raise ValueError("sidecar requires a valid v0.2 percept envelope")
    expected = _mr.build_multiresolution_percept(wave)
    try:
        matches = canonical_bytes(envelope) == canonical_bytes(expected)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        matches = False
    if not matches:
        raise ValueError(
            "sidecar percept observations and commitments must match the input WAV"
        )
    _ensure_empty_destination(stream)
    exact_stream = _ExactUTF8TextSink(stream)
    return _receipts_module.write_spectral_sidecar(wave, envelope, exact_stream)
