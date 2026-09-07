"""QSOL-MAP v0.2 verifier surface with latest compact hardening."""

from __future__ import annotations

from math import isqrt

from . import multiresolution_base as _base


# Preserve the established public/private surface. The base module contains the
# frozen transform implementation and the accumulated v0.2 verifier. This thin
# layer adds review-derived necessary constraints without duplicating that code.
for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

_BASE_VALIDATOR = _base._validate_percept_core
_BIN_256 = LONG_FRAME_SIZE // 4
_SCALE_SQUARED = _LONG_FFT_ENDPOINT_SCALE * _LONG_FFT_ENDPOINT_SCALE


def _single_event_special_bin_scale_is_valid(channel: dict) -> bool:
    """Bind bin 256 to the exact ten-stage Q15 coefficient scale."""
    spectral = channel["long_spectral"]
    events = spectral["events"]
    if len(events) != 1:
        return True

    power = _core._safe_decimal_int(spectral["aggregate_power_by_bin"][_BIN_256])
    if power is None or power % _SCALE_SQUARED:
        return False

    component = next(
        (
            item
            for item in events[0]["top_components"]
            if item["bin"] == _BIN_256
        ),
        None,
    )
    if component is None:
        return True
    real = _core._safe_decimal_int(component["real"], signed=True)
    imag = _core._safe_decimal_int(component["imag"], signed=True)
    return (
        real is not None
        and imag is not None
        and real % _LONG_FFT_ENDPOINT_SCALE == 0
        and imag % _LONG_FFT_ENDPOINT_SCALE == 0
    )


def _single_event_endpoint_energy_bounds_are_valid(
    channel: dict, frame_count: int
) -> bool:
    """Apply Cauchy bounds between endpoint magnitudes and window energy."""
    spectral = channel["long_spectral"]
    events = spectral["events"]
    if len(events) != 1:
        return True
    event = events[0]
    energy = _core._safe_decimal_int(event["windowed_energy"])
    if energy is None:
        return False
    available = min(
        LONG_FRAME_SIZE,
        max(0, frame_count - event["sample_start"]),
    )
    for endpoint in (0, LONG_FRAME_SIZE // 2):
        power = _core._safe_decimal_int(spectral["aggregate_power_by_bin"][endpoint])
        if power is None:
            return False
        root = isqrt(power)
        magnitude, remainder = divmod(root, _LONG_FFT_ENDPOINT_SCALE)
        if root * root != power or remainder:
            return False
        if magnitude * magnitude > available * energy:
            return False
    return True


def _long_energy_covers_relationship_energy(percept: dict) -> bool:
    """Require long-event weighted energies to cover full-source channel energy."""
    if percept["source"]["channels"] <= 1:
        return True
    source_energies = _base._relationship_channel_energies(percept)
    if source_energies is None:
        return False
    for channel_index, channel in enumerate(percept["channels"]):
        total = 0
        for event in channel["long_spectral"]["events"]:
            energy = _core._safe_decimal_int(event["windowed_energy"])
            if energy is None:
                return False
            total += energy
        if total < source_energies[channel_index]:
            return False
    return True


def _noncandidate_positive_delta_bound(frame_count: int, frame_index: int) -> int:
    """Return a necessary maximum delta for a transition that is not a candidate.

    For d=C-P>0, failing the authored candidate threshold means 2C < 3P.
    With C=P+d and integer energies this requires P >= 2d+1 and C >= 3d+1.
    Source-sized previous/current energy maxima therefore bound d from both
    sides.
    """
    previous_max = _base._short_frame_energy_bound(frame_count, frame_index - 1)
    current_max = _base._short_frame_energy_bound(frame_count, frame_index)
    if previous_max <= 0 or current_max <= 0:
        return 0
    return min((previous_max - 1) // 2, (current_max - 1) // 3)


def _transient_noncandidate_maximum_is_feasible(percept: dict) -> bool:
    frame_count = percept["source"]["frame_count"]
    short_event_count = (
        frame_count + SHORT_HOP_SIZE - 1
    ) // SHORT_HOP_SIZE
    transition_count = max(0, short_event_count - 1)

    for channel in percept["channels"]:
        transient = channel["transient"]
        maximum = _core._safe_decimal_int(transient["maximum_positive_delta"])
        if maximum is None:
            return False
        reported = transient["strongest_candidates"]
        strongest_reported = 0
        reported_frames: set[int] = set()
        if reported:
            strongest_reported = _core._safe_decimal_int(
                reported[0]["positive_delta"]
            )
            if strongest_reported is None:
                return False
            reported_frames = {item["frame_index"] for item in reported}

        if maximum <= strongest_reported:
            continue
        noncandidate_count = transition_count - transient["candidate_count"]
        if noncandidate_count <= 0:
            return False

        # The compact packet does not identify which unreported transitions are
        # omitted candidates versus non-candidates. A necessary condition is
        # that at least one unreported frame has enough source-sized energy
        # capacity to realize the declared non-candidate maximum while still
        # failing the 3/2 onset threshold.
        if not any(
            frame_index not in reported_frames
            and _noncandidate_positive_delta_bound(frame_count, frame_index)
            >= maximum
            for frame_index in range(1, transition_count + 1)
        ):
            return False
    return True


def _validate_percept_core(percept: object) -> bool:
    """Run the accumulated verifier plus the latest necessary constraints."""
    if not _BASE_VALIDATOR(percept):
        return False

    frame_count = percept["source"]["frame_count"]
    for channel in percept["channels"]:
        if not _single_event_special_bin_scale_is_valid(channel):
            return False
        if not _single_event_endpoint_energy_bounds_are_valid(channel, frame_count):
            return False
    if not _long_energy_covers_relationship_energy(percept):
        return False
    if not _transient_noncandidate_maximum_is_feasible(percept):
        return False
    return True


# Public verification resolves this core hook at call time. The base module is
# intentionally left intact so reloads keep a stable validator underneath this
# thin hardening layer.
_core._validate_percept_core = _validate_percept_core
