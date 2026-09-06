"""QSOL-MAP v0.2 multi-resolution reference with verifier hardening."""

from __future__ import annotations

from fractions import Fraction
from math import isqrt

from . import multiresolution_core as _core
from .pcm_constraints import _small_window_energy_is_realizable
from .tables import (
    FRAME_SIZE as SHORT_FRAME_SIZE,
    HOP_SIZE as SHORT_HOP_SIZE,
    WINDOW_WEIGHTS as SHORT_WINDOW_WEIGHTS,
)
from .v02_tables import (
    LONG_FRAME_SIZE,
    LONG_TOP_K,
    LONG_WINDOW_WEIGHTS,
    Q15_ONE,
    TWIDDLE_COS_Q15_1024,
    TWIDDLE_SIN_Q15_1024,
)


_ORIGINAL_VALIDATOR_ATTR = "_qsol_map_v02_original_validate_percept_core"
if not hasattr(_core, _ORIGINAL_VALIDATOR_ATTR):
    setattr(_core, _ORIGINAL_VALIDATOR_ATTR, _core._validate_percept_core)
_original_validate_percept_core = getattr(_core, _ORIGINAL_VALIDATOR_ATTR)
_LONG_WINDOW_SQUARE_PREFIX = [0]
for _weight in LONG_WINDOW_WEIGHTS:
    _LONG_WINDOW_SQUARE_PREFIX.append(
        _LONG_WINDOW_SQUARE_PREFIX[-1] + _weight * _weight
    )
_SHORT_WINDOW_SQUARE_PREFIX = [0]
for _weight in SHORT_WINDOW_WEIGHTS:
    _SHORT_WINDOW_SQUARE_PREFIX.append(
        _SHORT_WINDOW_SQUARE_PREFIX[-1] + _weight * _weight
    )
_PCM16_SQUARE_MAX = (1 << 15) ** 2
_LONG_WINDOW_WEIGHT_SQUARE_MAX = max(weight * weight for weight in LONG_WINDOW_WEIGHTS)
_LONG_FFT_STAGE_COUNT = LONG_FRAME_SIZE.bit_length() - 1
_LONG_FFT_TWIDDLE_NORM_MAX = max(
    real * real + imag * imag
    for real, imag in zip(TWIDDLE_COS_Q15_1024, TWIDDLE_SIN_Q15_1024)
)
_LONG_FFT_STAGE_NORM_BOUND = max(Q15_ONE * Q15_ONE, _LONG_FFT_TWIDDLE_NORM_MAX)
_LONG_FFT_POWER_GAIN_BOUND = (
    2 * _LONG_FFT_STAGE_NORM_BOUND
) ** _LONG_FFT_STAGE_COUNT


def _matrix_rank(matrix: list[list[int]]) -> int:
    """Return exact matrix rank using rational Gaussian elimination."""
    if not matrix:
        return 0
    work = [[Fraction(value) for value in row] for row in matrix]
    row_count = len(work)
    column_count = len(work[0])
    rank = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(rank, row_count) if work[row][column] != 0),
            None,
        )
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        for entry in range(column, column_count):
            work[rank][entry] /= pivot_value
        for row in range(row_count):
            if row == rank or work[row][column] == 0:
                continue
            factor = work[row][column]
            for entry in range(column, column_count):
                work[row][entry] -= factor * work[rank][entry]
        rank += 1
        if rank == row_count:
            break
    return rank


def _relationship_gram_matrix(percept: dict) -> list[list[int]] | None:
    channel_count = percept["source"]["channels"]
    if channel_count <= 1:
        return []
    gram = [[0] * channel_count for _ in range(channel_count)]
    energies: dict[int, int] = {}
    for relation in percept["channel_relationships"]:
        left = relation["left_channel"]
        right = relation["right_channel"]
        dot = _core._safe_decimal_int(relation["dot_product"], signed=True)
        left_energy = _core._safe_decimal_int(relation["left_sum_squares"])
        right_energy = _core._safe_decimal_int(relation["right_sum_squares"])
        if dot is None or left_energy is None or right_energy is None:
            return None
        for channel_index, energy in ((left, left_energy), (right, right_energy)):
            if channel_index in energies and energies[channel_index] != energy:
                return None
            energies[channel_index] = energy
        gram[left][right] = dot
        gram[right][left] = dot
    if len(energies) != channel_count:
        return None
    for channel_index, energy in energies.items():
        gram[channel_index][channel_index] = energy
    return gram


def _relationship_gram_rank(percept: dict) -> int | None:
    gram = _relationship_gram_matrix(percept)
    if gram is None:
        return None
    return _matrix_rank(gram)


def _relationship_channel_energies(percept: dict) -> dict[int, int] | None:
    channel_count = percept["source"]["channels"]
    if channel_count <= 1:
        return {}
    energies: dict[int, int] = {}
    for relation in percept["channel_relationships"]:
        left = relation["left_channel"]
        right = relation["right_channel"]
        left_energy = _core._safe_decimal_int(relation["left_sum_squares"])
        right_energy = _core._safe_decimal_int(relation["right_sum_squares"])
        if left_energy is None or right_energy is None:
            return None
        for channel_index, energy in ((left, left_energy), (right, right_energy)):
            if channel_index in energies and energies[channel_index] != energy:
                return None
            energies[channel_index] = energy
    return energies if len(energies) == channel_count else None


def _short_frame_energy_bound(frame_count: int, frame_index: int) -> int:
    sample_start = frame_index * SHORT_HOP_SIZE
    available = min(SHORT_FRAME_SIZE, max(0, frame_count - sample_start))
    return _PCM16_SQUARE_MAX * _SHORT_WINDOW_SQUARE_PREFIX[available]


def _one_long_event_matches_aggregate(channel: dict) -> bool:
    spectral = channel["long_spectral"]
    events = spectral["events"]
    if len(events) != 1:
        return True
    aggregate: list[int] = []
    for value in spectral["aggregate_power_by_bin"]:
        parsed = _core._safe_decimal_int(value)
        if parsed is None:
            return False
        aggregate.append(parsed)

    # For a real-input FFT, DC and Nyquist have zero imaginary part. With one
    # long event the aggregate row is the exact frame-power row, so endpoint
    # powers must be perfect squares even when those bins are omitted from the
    # compact top-component list.
    for endpoint in (0, len(aggregate) - 1):
        magnitude = isqrt(aggregate[endpoint])
        if magnitude * magnitude != aggregate[endpoint]:
            return False

    event = events[0]
    expected_bins = sorted(
        range(len(aggregate)),
        key=lambda bin_index: (-aggregate[bin_index], bin_index),
    )[:LONG_TOP_K]
    components = event["top_components"]
    if [component["bin"] for component in components] != expected_bins:
        return False
    for component in components:
        power = _core._safe_decimal_int(component["power"])
        if power is None or power != aggregate[component["bin"]]:
            return False
    expected_dominant = max(
        range(1, len(aggregate)),
        key=lambda bin_index: (aggregate[bin_index], -bin_index),
    )
    return event["dominant_non_dc_bin"] == expected_dominant


def _single_sample_relationships_are_integer_realizable(percept: dict) -> bool:
    if percept["source"]["frame_count"] != 1:
        return True

    channels = percept["channels"]
    event_energies: list[int] = []
    magnitudes: list[int] = []
    for channel in channels:
        events = channel["long_spectral"]["events"]
        if len(events) != 1:
            return False
        energy = _core._safe_decimal_int(events[0]["windowed_energy"])
        if energy is None:
            return False
        magnitude = isqrt(energy)
        if magnitude * magnitude != energy or magnitude >= (1 << 15) + 1:
            return False
        event_energies.append(energy)
        magnitudes.append(magnitude)

    channel_count = percept["source"]["channels"]
    if channel_count <= 1:
        return True
    relationship_energies = _relationship_channel_energies(percept)
    if relationship_energies is None:
        return False
    if any(
        relationship_energies[channel_index] != event_energies[channel_index]
        for channel_index in range(channel_count)
    ):
        return False

    for relation in percept["channel_relationships"]:
        left = relation["left_channel"]
        right = relation["right_channel"]
        dot = _core._safe_decimal_int(relation["dot_product"], signed=True)
        if dot is None or abs(dot) != magnitudes[left] * magnitudes[right]:
            return False
    return True


def _two_sample_vectors(energy: int) -> list[tuple[int, int]]:
    """Enumerate exact PCM16 vectors with the requested two-sample energy."""
    if energy < 0 or energy > 2 * _PCM16_SQUARE_MAX:
        return []
    lower = -(1 << 15)
    upper = (1 << 15) - 1
    limit = min(isqrt(energy), 1 << 15)
    vectors: list[tuple[int, int]] = []
    for first in range(max(lower, -limit), min(upper, limit) + 1):
        remainder = energy - first * first
        second_magnitude = isqrt(remainder)
        if second_magnitude * second_magnitude != remainder:
            continue
        if second_magnitude == 0:
            second_values = (0,)
        else:
            second_values = (-second_magnitude, second_magnitude)
        for second in second_values:
            if lower <= second <= upper:
                vectors.append((first, second))
    return vectors


def _two_sample_relationships_are_integer_realizable(percept: dict) -> bool:
    """Require PCM16 long-energy feasibility, plus joint Gram data when present."""
    if percept["source"]["frame_count"] != 2:
        return True
    channel_count = percept["source"]["channels"]
    if channel_count == 1:
        events = percept["channels"][0]["long_spectral"]["events"]
        if len(events) != 1:
            return False
        energy = _core._safe_decimal_int(events[0]["windowed_energy"])
        return energy is not None and _small_window_energy_is_realizable(energy, 2)
    gram = _relationship_gram_matrix(percept)
    if gram is None:
        return False

    first_weight_square = LONG_WINDOW_WEIGHTS[0] * LONG_WINDOW_WEIGHTS[0]
    second_weight_square = LONG_WINDOW_WEIGHTS[1] * LONG_WINDOW_WEIGHTS[1]
    by_energy: dict[int, list[tuple[int, int]]] = {}
    candidates: list[list[tuple[int, int]]] = []
    for channel_index in range(channel_count):
        energy = gram[channel_index][channel_index]
        if energy not in by_energy:
            by_energy[energy] = _two_sample_vectors(energy)
        events = percept["channels"][channel_index]["long_spectral"]["events"]
        if len(events) != 1:
            return False
        long_energy = _core._safe_decimal_int(events[0]["windowed_energy"])
        if long_energy is None:
            return False
        channel_candidates = [
            vector
            for vector in by_energy[energy]
            if (
                vector[0] * vector[0] * first_weight_square
                + vector[1] * vector[1] * second_weight_square
            )
            == long_energy
        ]
        if not channel_candidates:
            return False
        candidates.append(channel_candidates)

    order = sorted(range(channel_count), key=lambda index: len(candidates[index]))
    assigned: dict[int, tuple[int, int]] = {}

    def search(position: int) -> bool:
        if position == len(order):
            return True
        channel_index = order[position]
        for vector in candidates[channel_index]:
            compatible = True
            for other_index, other_vector in assigned.items():
                dot = vector[0] * other_vector[0] + vector[1] * other_vector[1]
                if dot != gram[channel_index][other_index]:
                    compatible = False
                    break
            if not compatible:
                continue
            assigned[channel_index] = vector
            if search(position + 1):
                return True
            del assigned[channel_index]
        return False

    return search(0)


def _sum_of_three_squares_possible(energy: int) -> bool:
    """Apply Legendre's exact three-square obstruction to a channel energy."""
    if energy < 0:
        return False
    reduced = energy
    while reduced and reduced % 4 == 0:
        reduced //= 4
    return reduced % 8 != 7


def _three_sample_relationships_are_integer_realizable(percept: dict) -> bool:
    """Reject three-frame Gram diagonals that no integer PCM vector can realize."""
    if percept["source"]["frame_count"] != 3:
        return True
    channel_count = percept["source"]["channels"]
    if channel_count <= 1:
        return True
    gram = _relationship_gram_matrix(percept)
    if gram is None:
        return False
    return all(
        _sum_of_three_squares_possible(gram[index][index])
        for index in range(channel_count)
    )


def _validate_percept_core(percept: object) -> bool:
    """Run core validation plus source-sized feasibility and energy bounds."""
    if not _original_validate_percept_core(percept):
        return False

    source = percept["source"]
    frame_count = source["frame_count"]
    channel_count = source["channels"]
    max_channel_energy = frame_count * _PCM16_SQUARE_MAX
    for relation in percept["channel_relationships"]:
        left_energy = _core._safe_decimal_int(relation["left_sum_squares"])
        right_energy = _core._safe_decimal_int(relation["right_sum_squares"])
        if left_energy is None or right_energy is None:
            return False
        if left_energy > max_channel_energy or right_energy > max_channel_energy:
            return False

    gram_rank = _relationship_gram_rank(percept)
    if gram_rank is None or gram_rank > frame_count:
        return False
    if not _single_sample_relationships_are_integer_realizable(percept):
        return False
    if not _two_sample_relationships_are_integer_realizable(percept):
        return False
    if not _three_sample_relationships_are_integer_realizable(percept):
        return False

    relationship_energies = None
    if channel_count > 1:
        relationship_energies = _relationship_channel_energies(percept)
        if relationship_energies is None:
            return False

    for channel_index, channel in enumerate(percept["channels"]):
        if not _one_long_event_matches_aggregate(channel):
            return False
        for event in channel["long_spectral"]["events"]:
            sample_start = event["sample_start"]
            available = min(LONG_FRAME_SIZE, max(0, frame_count - sample_start))
            windowed_energy = _core._safe_decimal_int(event["windowed_energy"])
            if windowed_energy is None:
                return False
            max_windowed_energy = (
                _PCM16_SQUARE_MAX * _LONG_WINDOW_SQUARE_PREFIX[available]
            )
            if windowed_energy > max_windowed_energy:
                return False
            if not _small_window_energy_is_realizable(windowed_energy, available):
                return False
            if relationship_energies is not None:
                source_energy = relationship_energies[channel_index]
                if windowed_energy > source_energy * _LONG_WINDOW_WEIGHT_SQUARE_MAX:
                    return False

            centroid = event["spectral_centroid_bin"]
            numerator = _core._safe_decimal_int(centroid["numerator"])
            denominator = _core._safe_decimal_int(centroid["denominator"])
            if numerator is None or denominator is None:
                return False
            if denominator > windowed_energy * _LONG_FFT_POWER_GAIN_BOUND:
                return False

            selected_weighted_power = 0
            selected_power_total = 0
            component_powers: list[int] = []
            for component in event["top_components"]:
                power = _core._safe_decimal_int(component["power"])
                if power is None:
                    return False
                component_powers.append(power)
                selected_power_total += power
                selected_weighted_power += component["bin"] * power
            if numerator < selected_weighted_power:
                return False

            # The compact list claims to contain the strongest LONG_TOP_K bins.
            # Therefore every omitted bin is bounded by the weakest selected
            # power. This supplies a necessary total-power capacity bound even
            # when multiple events prevent reconstructing an individual row
            # from aggregate powers alone.
            omitted_count = LONG_FRAME_SIZE // 2 + 1 - len(component_powers)
            weakest_selected_power = component_powers[-1]
            if denominator > (
                selected_power_total + omitted_count * weakest_selected_power
            ):
                return False

    short_event_count = (frame_count + SHORT_HOP_SIZE - 1) // SHORT_HOP_SIZE
    transition_bounds = [
        _short_frame_energy_bound(frame_count, frame_index)
        for frame_index in range(1, short_event_count)
    ]
    positive_delta_sum_bound = sum(transition_bounds)
    maximum_positive_delta_bound = max(transition_bounds, default=0)

    for channel in percept["channels"]:
        transient = channel["transient"]
        positive_delta_sum = _core._safe_decimal_int(transient["positive_delta_sum"])
        maximum_positive_delta = _core._safe_decimal_int(
            transient["maximum_positive_delta"]
        )
        if positive_delta_sum is None or maximum_positive_delta is None:
            return False
        if positive_delta_sum > positive_delta_sum_bound:
            return False
        if maximum_positive_delta > maximum_positive_delta_bound:
            return False
        if positive_delta_sum > max(0, short_event_count - 1) * maximum_positive_delta:
            return False
        if maximum_positive_delta == 0 and positive_delta_sum != 0:
            return False
        if short_event_count < 2 and (
            positive_delta_sum != 0 or maximum_positive_delta != 0
        ):
            return False
        if short_event_count == 2 and positive_delta_sum != maximum_positive_delta:
            return False

        reported_delta_sum = 0
        for candidate in transient["strongest_candidates"]:
            positive_delta = _core._safe_decimal_int(candidate["positive_delta"])
            if positive_delta is None:
                return False
            reported_delta_sum += positive_delta
        omitted_candidate_count = transient["candidate_count"] - len(
            transient["strongest_candidates"]
        )
        if reported_delta_sum + omitted_candidate_count > positive_delta_sum:
            return False

        for candidate in transient["strongest_candidates"]:
            frame_index = candidate["frame_index"]
            previous_energy = _core._safe_decimal_int(candidate["previous_energy"])
            current_energy = _core._safe_decimal_int(candidate["current_energy"])
            if previous_energy is None or current_energy is None:
                return False
            if previous_energy > _short_frame_energy_bound(
                frame_count, frame_index - 1
            ):
                return False
            if current_energy > _short_frame_energy_bound(frame_count, frame_index):
                return False
            for index, energy in (
                (frame_index - 1, previous_energy),
                (frame_index, current_energy),
            ):
                available = min(
                    SHORT_FRAME_SIZE, max(0, frame_count - index * SHORT_HOP_SIZE)
                )
                if not _small_window_energy_is_realizable(energy, available):
                    return False
    return True


# The core verifier resolves this global at call time, so patch the validation
# boundary before re-exporting the established public/private module surface.
_core._validate_percept_core = _validate_percept_core
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)
