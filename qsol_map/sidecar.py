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


def verify_spectral_sidecar(envelope: dict, lines) -> bool:
    """Verify while preserving the public configurable sidecar line bound."""
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
            return _receipts_module.verify_spectral_sidecar(envelope, lines)
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
    exact_stream = _ExactUTF8TextSink(stream)
    return _receipts_module.write_spectral_sidecar(wave, envelope, exact_stream)
