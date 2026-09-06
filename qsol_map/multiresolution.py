"""QSOL-MAP v0.2 multi-resolution reference with verifier hardening."""

from __future__ import annotations

from . import multiresolution_core as _core


_original_validate_percept_core = _core._validate_percept_core


def _validate_percept_core(percept: object) -> bool:
    """Run the frozen core validation plus source-sized PCM16 energy bounds."""
    if not _original_validate_percept_core(percept):
        return False

    source = percept["source"]
    frame_count = source["frame_count"]
    max_channel_energy = frame_count * (1 << 15) ** 2
    for relation in percept["channel_relationships"]:
        left_energy = _core._safe_decimal_int(relation["left_sum_squares"])
        right_energy = _core._safe_decimal_int(relation["right_sum_squares"])
        if left_energy is None or right_energy is None:
            return False
        if left_energy > max_channel_energy or right_energy > max_channel_energy:
            return False
    return True


# The core verifier resolves this global at call time, so patch the validation
# boundary before re-exporting the established public/private module surface.
_core._validate_percept_core = _validate_percept_core
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)
