"""QSOL-MAP v0.2 verifier surface with latest compact hardening."""

from __future__ import annotations

from math import gcd, isqrt

from . import multiresolution_base as _base


# Preserve the established public/private surface. The base module contains the
# frozen transform implementation and the accumulated v0.2 verifier. This thin
# layer adds review-derived necessary constraints without duplicating that code.
for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

_BASE_VALIDATOR = _base._validate_percept_core
_SCALE_SQUARED = _LONG_FFT_ENDPOINT_SCALE * _LONG_FFT_ENDPOINT_SCALE


def _scaled_divisor(divisor: int, factor: int) -> int:
    """Return a guaranteed divisor after multiplying a component by a factor."""
    if divisor == 0 or factor == 0:
        return 0
    return divisor * abs(factor)


def _compute_long_bin_component_divisors() -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Propagate guaranteed integer divisors through the frozen long FFT.

    Each bit-reversed input real component starts as one arbitrary integer and
    each imaginary component starts identically zero. For every butterfly we
    propagate the gcd of the divisors of the integer terms being added or
    subtracted. The result is a precomputable necessary divisor for every real
    and imaginary output coefficient. It follows the committed twiddle table
    and stage schedule directly, so special bins are not hard-coded.
    """
    state = [(1, 0) for _ in range(LONG_FRAME_SIZE)]
    width = 2
    while width <= LONG_FRAME_SIZE:
        half = width // 2
        twiddle_step = LONG_FRAME_SIZE // width
        for base in range(0, LONG_FRAME_SIZE, width):
            for offset in range(half):
                twiddle_index = offset * twiddle_step
                wr = TWIDDLE_COS_Q15_1024[twiddle_index]
                wi = TWIDDLE_SIN_Q15_1024[twiddle_index]
                ur, ui = state[base + offset]
                vr, vi = state[base + offset + half]

                tr = gcd(_scaled_divisor(vr, wr), _scaled_divisor(vi, wi))
                ti = gcd(_scaled_divisor(vr, wi), _scaled_divisor(vi, wr))
                out_real = gcd(_scaled_divisor(ur, Q15_ONE), tr)
                out_imag = gcd(_scaled_divisor(ui, Q15_ONE), ti)
                state[base + offset] = (out_real, out_imag)
                state[base + offset + half] = (out_real, out_imag)
        width *= 2

    retained = state[: LONG_FRAME_SIZE // 2 + 1]
    return (
        tuple(real for real, _ in retained),
        tuple(imag for _, imag in retained),
    )


_LONG_BIN_REAL_DIVISORS, _LONG_BIN_IMAG_DIVISORS = (
    _compute_long_bin_component_divisors()
)


def _single_event_transform_divisibility_is_valid(channel: dict) -> bool:
    """Apply frozen-transform coefficient divisibility to every retained bin."""
    spectral = channel["long_spectral"]
    events = spectral["events"]
    if len(events) != 1:
        return True

    aggregate = spectral["aggregate_power_by_bin"]
    for bin_index, encoded_power in enumerate(aggregate):
        power = _core._safe_decimal_int(encoded_power)
        if power is None:
            return False
        real_divisor = _LONG_BIN_REAL_DIVISORS[bin_index]
        imag_divisor = _LONG_BIN_IMAG_DIVISORS[bin_index]
        power_divisor = gcd(real_divisor * real_divisor, imag_divisor * imag_divisor)
        if power_divisor:
            if power % power_divisor:
                return False
        elif power != 0:
            return False

    for component in events[0]["top_components"]:
        bin_index = component["bin"]
        real = _core._safe_decimal_int(component["real"], signed=True)
        imag = _core._safe_decimal_int(component["imag"], signed=True)
        if real is None or imag is None:
            return False
        real_divisor = _LONG_BIN_REAL_DIVISORS[bin_index]
        imag_divisor = _LONG_BIN_IMAG_DIVISORS[bin_index]
        if (real_divisor == 0 and real != 0) or (
            real_divisor != 0 and real % real_divisor
        ):
            return False
        if (imag_divisor == 0 and imag != 0) or (
            imag_divisor != 0 and imag % imag_divisor
        ):
            return False
    return True


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


def _zero_long_energy_forces_zero_transient(percept: dict) -> bool:
    """Couple the exact all-zero long state to the short transient summary."""
    for channel in percept["channels"]:
        long_energies: list[int] = []
        for event in channel["long_spectral"]["events"]:
            energy = _core._safe_decimal_int(event["windowed_energy"])
            if energy is None:
                return False
            long_energies.append(energy)
        if not long_energies or any(long_energies):
            continue

        transient = channel["transient"]
        positive_sum = _core._safe_decimal_int(transient["positive_delta_sum"])
        maximum = _core._safe_decimal_int(transient["maximum_positive_delta"])
        if positive_sum is None or maximum is None:
            return False
        if (
            transient["candidate_count"] != 0
            or transient["strongest_candidates"]
            or positive_sum != 0
            or maximum != 0
        ):
            return False
    return True


def _one_sample_relationship_signs_match_endpoints(percept: dict) -> bool:
    """Bind one-sample relationship dots to the signed endpoint-derived PCM."""
    if percept["source"]["frame_count"] != 1:
        return True

    samples: list[int] = []
    for channel in percept["channels"]:
        event = channel["long_spectral"]["events"][0]
        dc = next(
            (item for item in event["top_components"] if item["bin"] == 0),
            None,
        )
        if dc is None:
            return False
        real = _core._safe_decimal_int(dc["real"], signed=True)
        imag = _core._safe_decimal_int(dc["imag"], signed=True)
        if (
            real is None
            or imag != 0
            or real % _LONG_FFT_ENDPOINT_SCALE
        ):
            return False
        samples.append(real // _LONG_FFT_ENDPOINT_SCALE)

    for relation in percept["channel_relationships"]:
        left = relation["left_channel"]
        right = relation["right_channel"]
        dot = _core._safe_decimal_int(relation["dot_product"], signed=True)
        if dot is None or dot != samples[left] * samples[right]:
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

        if not any(
            frame_index not in reported_frames
            and _noncandidate_positive_delta_bound(frame_count, frame_index)
            >= maximum
            for frame_index in range(1, transition_count + 1)
        ):
            return False
    return True


def _omitted_candidate_adjacency_is_feasible(percept: dict) -> bool:
    """Use reported neighboring frame energies to bound omitted candidates."""
    frame_count = percept["source"]["frame_count"]
    short_event_count = (
        frame_count + SHORT_HOP_SIZE - 1
    ) // SHORT_HOP_SIZE
    transition_count = max(0, short_event_count - 1)

    for channel in percept["channels"]:
        transient = channel["transient"]
        reported = transient["strongest_candidates"]
        omitted_count = transient["candidate_count"] - len(reported)
        if omitted_count <= 0 or transient["candidate_count"] != transition_count:
            continue

        known_energy: dict[int, int] = {}
        reported_frames: set[int] = set()
        for candidate in reported:
            frame = candidate["frame_index"]
            previous = _core._safe_decimal_int(candidate["previous_energy"])
            current = _core._safe_decimal_int(candidate["current_energy"])
            if previous is None or current is None:
                return False
            reported_frames.add(frame)
            for energy_frame, value in ((frame - 1, previous), (frame, current)):
                existing = known_energy.get(energy_frame)
                if existing is not None and existing != value:
                    return False
                known_energy[energy_frame] = value

        unreported_frames = [
            frame for frame in range(1, transition_count + 1)
            if frame not in reported_frames
        ]
        if len(unreported_frames) != omitted_count or not reported:
            return False

        weakest_delta = _core._safe_decimal_int(reported[-1]["positive_delta"])
        weakest_frame = reported[-1]["frame_index"]
        positive_sum = _core._safe_decimal_int(transient["positive_delta_sum"])
        reported_sum = sum(
            _core._safe_decimal_int(item["positive_delta"]) or 0
            for item in reported
        )
        if weakest_delta is None or positive_sum is None:
            return False
        unreported_mass = positive_sum - reported_sum

        minimum_mass = 0
        for frame in unreported_frames:
            allowance = weakest_delta - (1 if frame < weakest_frame else 0)
            previous = known_energy.get(frame - 1)
            current = known_energy.get(frame)

            if previous is not None and current is not None:
                if current <= previous or 2 * current < 3 * previous:
                    return False
                minimum = current - previous
            elif previous is not None:
                minimum = (previous + 1) // 2
                if previous + minimum > _base._short_frame_energy_bound(
                    frame_count, frame
                ):
                    return False
            elif current is not None:
                if current <= 0:
                    return False
                minimum = current - (2 * current) // 3
            else:
                minimum = 1

            if minimum < 1 or minimum > allowance:
                return False
            minimum_mass += minimum

        if minimum_mass > unreported_mass:
            return False
    return True


def _validate_percept_core(percept: object) -> bool:
    """Run the accumulated verifier plus the latest necessary constraints."""
    if not _BASE_VALIDATOR(percept):
        return False

    frame_count = percept["source"]["frame_count"]
    for channel in percept["channels"]:
        if not _single_event_transform_divisibility_is_valid(channel):
            return False
        if not _single_event_endpoint_energy_bounds_are_valid(channel, frame_count):
            return False
    if not _long_energy_covers_relationship_energy(percept):
        return False
    if not _zero_long_energy_forces_zero_transient(percept):
        return False
    if not _one_sample_relationship_signs_match_endpoints(percept):
        return False
    if not _transient_noncandidate_maximum_is_feasible(percept):
        return False
    if not _omitted_candidate_adjacency_is_feasible(percept):
        return False
    return True


# Public verification resolves this core hook at call time. The base module is
# intentionally left intact so reloads keep a stable validator underneath this
# thin hardening layer.
_core._validate_percept_core = _validate_percept_core
