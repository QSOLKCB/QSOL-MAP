"""QSOL-MAP v0.2 sidecar API with writer and verifier hardening."""

from __future__ import annotations

from . import multiresolution as _mr
from . import sidecar_receipts_core as _core
from .canonical import canonical_bytes


for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)


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
    return _core.write_spectral_sidecar(wave, envelope, stream)
