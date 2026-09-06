"""QSOL-MAP v0.2 multi-resolution deterministic Layer-1 observation."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Sequence

from .analysis import build_percept as build_v01_percept
from .canonical import canonical_bytes, domain_sha256
from .v02_tables import (
    BIT_REVERSED_1024,
    LONG_FRAME_SIZE,
    LONG_HOP_SIZE,
    LONG_TOP_K,
    LONG_WINDOW_WEIGHTS,
    Q15_ONE,
    TWIDDLE_COS_Q15_1024,
    TWIDDLE_SIN_Q15_1024,
)
from .wav import PCM16Wave

PROFILE_ID = "qsol-map-multiresolution-v0.2"
LONG_PROFILE_ID = "qsol-map-fixed-fft-1024-v0.2"
V01_PROFILE_ID = "qsol-map-fixed-fft-v0.1"
IMPLEMENTATION_ID = "qsol-map-python-reference-0.2.0"
PERCEPT_DOMAIN = "QSOL-MAP/PERCEPT/v0.2"
LONG_COMPLEX_MATRIX_DOMAIN = "QSOL-MAP/LONG-COMPLEX-MATRIX/v0.2"
LONG_POWER_MATRIX_DOMAIN = "QSOL-MAP/LONG-POWER-MATRIX/v0.2"
ONSET_RULE_ID = "energy-rise-3-over-2-v0.2"
AUDIBLE_REFERENCE_UPPER_HZ = 20_000
ULTRASONIC_SPLIT_HZ = 40_000
MAX_TRANSIENT_EVENTS = 16
MAX_DECIMAL_DIGITS = 1024

_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_SIGNED_DECIMAL = re.compile(r"(?:0|-?[1-9][0-9]*)\Z", re.ASCII)
_UNSIGNED_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z", re.ASCII)


def _plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _hex_digest(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _decimal_digits(value: str) -> int:
    return len(value) - (1 if value.startswith("-") else 0)


def _signed_decimal(value: object) -> bool:
    return (
        isinstance(value, str)
        and _decimal_digits(value) <= MAX_DECIMAL_DIGITS
        and _SIGNED_DECIMAL.fullmatch(value) is not None
    )


def _unsigned_decimal(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_DECIMAL_DIGITS
        and _UNSIGNED_DECIMAL.fullmatch(value) is not None
    )


def _safe_decimal_int(value: object, *, signed: bool = False) -> int | None:
    validator = _signed_decimal if signed else _unsigned_decimal
    if not validator(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _exact_keys(value: object, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys


def _canonical_equal(left: object, right: object) -> bool:
    try:
        return canonical_bytes(left) == canonical_bytes(right)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return False


def _frame_starts(sample_count: int) -> range:
    if sample_count <= 0:
        raise ValueError("analysis requires at least one sample")
    return range(0, sample_count, LONG_HOP_SIZE)


def _windowed_long_frame(samples: Sequence[int], start: int) -> list[int]:
    frame = [0] * LONG_FRAME_SIZE
    available = min(LONG_FRAME_SIZE, max(0, len(samples) - start))
    for index in range(available):
        frame[index] = samples[start + index] * LONG_WINDOW_WEIGHTS[index]
    return frame


def _fixed_fft_long(windowed: Sequence[int]) -> tuple[tuple[int, int], ...]:
    """Compute the frozen 1024-point Q15-twiddle transform with exact integers."""
    if len(windowed) != LONG_FRAME_SIZE:
        raise ValueError("long fixed FFT requires exactly 1024 windowed samples")

    state = [[windowed[BIT_REVERSED_1024[index]], 0] for index in range(LONG_FRAME_SIZE)]
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
                tr = vr * wr - vi * wi
                ti = vr * wi + vi * wr
                scaled_ur = ur * Q15_ONE
                scaled_ui = ui * Q15_ONE
                state[base + offset] = [scaled_ur + tr, scaled_ui + ti]
                state[base + offset + half] = [scaled_ur - tr, scaled_ui - ti]
        width *= 2
    return tuple((real, imag) for real, imag in state[: LONG_FRAME_SIZE // 2 + 1])


def _update_row_hash(hasher: "hashlib._Hash", row: object) -> None:
    encoded = canonical_bytes(row)
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def _region_index(sample_rate: int, bin_index: int) -> str:
    scaled = bin_index * sample_rate
    if scaled < AUDIBLE_REFERENCE_UPPER_HZ * LONG_FRAME_SIZE:
        return "below_20khz_reference"
    if scaled < ULTRASONIC_SPLIT_HZ * LONG_FRAME_SIZE:
        return "20_to_40khz_reference"
    return "at_or_above_40khz_reference"


def _analyze_long_channel(samples: Sequence[int], sample_rate: int) -> dict:
    bin_count = LONG_FRAME_SIZE // 2 + 1
    aggregate_power = [0] * bin_count
    regions = {
        "below_20khz_reference": 0,
        "20_to_40khz_reference": 0,
        "at_or_above_40khz_reference": 0,
    }

    complex_hash = hashlib.sha256()
    complex_hash.update(LONG_COMPLEX_MATRIX_DOMAIN.encode("utf-8") + b"\x00")
    power_hash = hashlib.sha256()
    power_hash.update(LONG_POWER_MATRIX_DOMAIN.encode("utf-8") + b"\x00")

    events = []
    for frame_index, start in enumerate(_frame_starts(len(samples))):
        windowed = _windowed_long_frame(samples, start)
        coefficients = _fixed_fft_long(windowed)
        powers = [real * real + imag * imag for real, imag in coefficients]

        for bin_index, power in enumerate(powers):
            aggregate_power[bin_index] += power
            regions[_region_index(sample_rate, bin_index)] += power

        _update_row_hash(
            complex_hash,
            [[str(real), str(imag)] for real, imag in coefficients],
        )
        _update_row_hash(power_hash, [str(power) for power in powers])

        ranked = sorted(range(bin_count), key=lambda k: (-powers[k], k))[:LONG_TOP_K]
        non_dc_bin = max(range(1, bin_count), key=lambda k: (powers[k], -k))
        centroid_den = sum(powers)
        centroid_num = sum(index * power for index, power in enumerate(powers))
        frame_energy = sum(value * value for value in windowed)
        events.append(
            {
                "frame_index": frame_index,
                "sample_start": start,
                "windowed_energy": str(frame_energy),
                "spectral_centroid_bin": {
                    "numerator": str(centroid_num),
                    "denominator": str(centroid_den),
                },
                "dominant_non_dc_bin": non_dc_bin,
                "top_components": [
                    {
                        "bin": bin_index,
                        "real": str(coefficients[bin_index][0]),
                        "imag": str(coefficients[bin_index][1]),
                        "power": str(powers[bin_index]),
                    }
                    for bin_index in ranked
                ],
            }
        )

    return {
        "aggregate_power_by_bin": [str(value) for value in aggregate_power],
        "aggregate_power_by_frequency_region": {
            key: str(value) for key, value in regions.items()
        },
        "complex_matrix_sha256": complex_hash.hexdigest(),
        "power_matrix_sha256": power_hash.hexdigest(),
        "events": events,
    }


def _transient_observation(v01_channel: dict) -> dict:
    candidates = []
    positive_delta_sum = 0
    maximum_positive_delta = 0
    previous_energy = None

    for event in v01_channel["events"]:
        current = int(event["windowed_energy"])
        if previous_energy is not None:
            delta = current - previous_energy
            positive = max(0, delta)
            positive_delta_sum += positive
            maximum_positive_delta = max(maximum_positive_delta, positive)
            if current > previous_energy and current * 2 >= previous_energy * 3:
                rise_ratio = None
                if previous_energy != 0:
                    rise_ratio = {
                        "numerator": str(current),
                        "denominator": str(previous_energy),
                    }
                candidates.append(
                    {
                        "frame_index": event["frame_index"],
                        "sample_start": event["sample_start"],
                        "previous_energy": str(previous_energy),
                        "current_energy": str(current),
                        "positive_delta": str(positive),
                        "rise_ratio": rise_ratio,
                    }
                )
        previous_energy = current

    strongest = sorted(
        candidates,
        key=lambda item: (-int(item["positive_delta"]), item["frame_index"]),
    )[:MAX_TRANSIENT_EVENTS]
    return {
        "rule_id": ONSET_RULE_ID,
        "candidate_count": len(candidates),
        "positive_delta_sum": str(positive_delta_sum),
        "maximum_positive_delta": str(maximum_positive_delta),
        "strongest_candidates": strongest,
    }


def _channel_relationships(wave: PCM16Wave) -> list[dict]:
    relationships = []
    for left_index in range(wave.channels):
        left = wave.samples_by_channel[left_index]
        for right_index in range(left_index + 1, wave.channels):
            right = wave.samples_by_channel[right_index]
            dot = 0
            left_energy = 0
            right_energy = 0
            difference_energy = 0
            sum_energy = 0
            for left_sample, right_sample in zip(left, right):
                dot += left_sample * right_sample
                left_energy += left_sample * left_sample
                right_energy += right_sample * right_sample
                delta = left_sample - right_sample
                total = left_sample + right_sample
                difference_energy += delta * delta
                sum_energy += total * total

            denominator = left_energy * right_energy
            correlation_squared = None
            if denominator:
                correlation_squared = {
                    "numerator": str(dot * dot),
                    "denominator": str(denominator),
                }
            relationships.append(
                {
                    "left_channel": left_index,
                    "right_channel": right_index,
                    "dot_product": str(dot),
                    "dot_product_sign": 1 if dot > 0 else -1 if dot < 0 else 0,
                    "left_sum_squares": str(left_energy),
                    "right_sum_squares": str(right_energy),
                    "difference_sum_squares": str(difference_energy),
                    "sum_sum_squares": str(sum_energy),
                    "zero_lag_correlation_squared": correlation_squared,
                }
            )
    return relationships


def _frequency_support(sample_rate: int) -> dict:
    highest_bin = LONG_FRAME_SIZE // 2
    return {
        "nyquist_hz": {"numerator": sample_rate, "denominator": 2},
        "highest_retained_bin": highest_bin,
        "highest_retained_frequency_hz": {
            "numerator": highest_bin * sample_rate,
            "denominator": LONG_FRAME_SIZE,
        },
        "audible_reference_upper_hz": AUDIBLE_REFERENCE_UPPER_HZ,
        "ultrasonic_reference_split_hz": ULTRASONIC_SPLIT_HZ,
        "bins_at_or_above_20khz_retained": (
            highest_bin * sample_rate >= AUDIBLE_REFERENCE_UPPER_HZ * LONG_FRAME_SIZE
        ),
        "psychoacoustic_low_pass_applied": False,
    }


def build_multiresolution_percept(wave: PCM16Wave) -> dict:
    """Build the v0.2 compact multi-resolution Layer-1 percept envelope."""
    v01 = build_v01_percept(wave)
    v01_channels = v01["percept"]["channels"]
    long_channels = [
        _analyze_long_channel(samples, wave.sample_rate_hz)
        for samples in wave.samples_by_channel
    ]

    percept = {
        "schema": "qsol-map-percept-core-v0.2",
        "layer": "L1_deterministic_acoustic_observation",
        "implementation": IMPLEMENTATION_ID,
        "source": {
            "wav_sha256": wave.source_sha256,
            "pcm_s16le_sha256": wave.pcm_s16le_sha256,
            "sample_rate_hz": wave.sample_rate_hz,
            "channels": wave.channels,
            "frame_count": wave.frame_count,
            "bits_per_sample": 16,
        },
        "profile": {
            "id": PROFILE_ID,
            "short_reference_profile_id": V01_PROFILE_ID,
            "long_reference_profile_id": LONG_PROFILE_ID,
            "long_frame_size_samples": LONG_FRAME_SIZE,
            "long_hop_size_samples": LONG_HOP_SIZE,
            "long_window": "symmetric-integer-triangular-1024-v0.2",
            "long_twiddle": "frozen-exp-minus-i-2pi-k-over-1024-q15-v0.2",
            "q15_one": Q15_ONE,
            "long_top_components_per_frame": LONG_TOP_K,
            "tail_policy": "zero_pad_each_hop_start_below_frame_count",
            "numeric_contract": "exact_unbounded_integer_reference",
            "onset_rule": {
                "id": ONSET_RULE_ID,
                "candidate_condition": "current > previous and 2*current >= 3*previous",
                "source_profile": V01_PROFILE_ID,
                "maximum_reported_candidates": MAX_TRANSIENT_EVENTS,
            },
            "frequency_regions_hz": {
                "below_20khz_reference": {"lower_inclusive": 0, "upper_exclusive": 20_000},
                "20_to_40khz_reference": {"lower_inclusive": 20_000, "upper_exclusive": 40_000},
                "at_or_above_40khz_reference": {"lower_inclusive": 40_000, "upper_exclusive": None},
            },
            "sidecar_schema": "qsol-map-spectral-sidecar-v0.2",
        },
        "short_reference": {
            "percept_sha256": v01["percept_sha256"],
            "channels": [
                {
                    "channel_index": channel["channel_index"],
                    "complex_matrix_sha256": channel["complex_matrix_sha256"],
                    "power_matrix_sha256": channel["power_matrix_sha256"],
                }
                for channel in v01_channels
            ],
        },
        "frequency_support": _frequency_support(wave.sample_rate_hz),
        "channels": [
            {
                "channel_index": channel_index,
                "long_spectral": long_channels[channel_index],
                "transient": _transient_observation(v01_channels[channel_index]),
            }
            for channel_index in range(wave.channels)
        ],
        "channel_relationships": _channel_relationships(wave),
        "interpretation": {
            "learned_tokenization_present": False,
            "semantic_inference_present": False,
            "human_subjective_report_present": False,
        },
    }
    digest = domain_sha256(PERCEPT_DOMAIN, canonical_bytes(percept))
    return {
        "schema": "qsol-map-percept-envelope-v0.2",
        "percept_sha256": digest,
        "percept": percept,
    }


def _validate_top_components(components: object) -> bool:
    if not isinstance(components, list) or len(components) != LONG_TOP_K:
        return False
    bins: set[int] = set()
    previous_power: int | None = None
    previous_bin: int | None = None
    for component in components:
        if not _exact_keys(component, {"bin", "real", "imag", "power"}):
            return False
        bin_index = component["bin"]
        if not _plain_int(bin_index) or not 0 <= bin_index <= LONG_FRAME_SIZE // 2:
            return False
        if bin_index in bins:
            return False
        bins.add(bin_index)
        real = _safe_decimal_int(component["real"], signed=True)
        imag = _safe_decimal_int(component["imag"], signed=True)
        power = _safe_decimal_int(component["power"])
        if real is None or imag is None or power is None:
            return False
        if power != real * real + imag * imag:
            return False
        if previous_power is not None:
            if power > previous_power:
                return False
            if power == previous_power and previous_bin is not None and bin_index < previous_bin:
                return False
        previous_power = power
        previous_bin = bin_index
    return True


def _validate_long_event(event: object, index: int) -> bool:
    if not _exact_keys(
        event,
        {
            "frame_index",
            "sample_start",
            "windowed_energy",
            "spectral_centroid_bin",
            "dominant_non_dc_bin",
            "top_components",
        },
    ):
        return False
    if not _plain_int(event["frame_index"]) or not _plain_int(event["sample_start"]):
        return False
    if event["frame_index"] != index or event["sample_start"] != index * LONG_HOP_SIZE:
        return False
    if not _unsigned_decimal(event["windowed_energy"]):
        return False
    centroid = event["spectral_centroid_bin"]
    if not _exact_keys(centroid, {"numerator", "denominator"}):
        return False
    numerator = _safe_decimal_int(centroid["numerator"])
    denominator = _safe_decimal_int(centroid["denominator"])
    if numerator is None or denominator is None:
        return False
    if numerator > (LONG_FRAME_SIZE // 2) * denominator:
        return False
    dominant = event["dominant_non_dc_bin"]
    if not _plain_int(dominant) or not 1 <= dominant <= LONG_FRAME_SIZE // 2:
        return False
    components = event["top_components"]
    if not _validate_top_components(components):
        return False
    strongest_non_dc = next(
        (component["bin"] for component in components if component["bin"] != 0),
        None,
    )
    return strongest_non_dc is not None and dominant == strongest_non_dc


def _validate_transient(value: object, short_event_count: int) -> bool:
    if not _exact_keys(
        value,
        {"rule_id", "candidate_count", "positive_delta_sum", "maximum_positive_delta", "strongest_candidates"},
    ):
        return False
    if value["rule_id"] != ONSET_RULE_ID:
        return False
    count = value["candidate_count"]
    if not _plain_int(count) or not 0 <= count <= max(0, short_event_count - 1):
        return False
    positive_delta_sum = _safe_decimal_int(value["positive_delta_sum"])
    maximum_positive_delta = _safe_decimal_int(value["maximum_positive_delta"])
    if positive_delta_sum is None or maximum_positive_delta is None:
        return False
    if maximum_positive_delta > positive_delta_sum:
        return False
    candidates = value["strongest_candidates"]
    if not isinstance(candidates, list) or len(candidates) != min(MAX_TRANSIENT_EVENTS, count):
        return False

    seen: set[int] = set()
    previous_strength: int | None = None
    previous_index_for_tie: int | None = None
    for candidate in candidates:
        if not _exact_keys(
            candidate,
            {"frame_index", "sample_start", "previous_energy", "current_energy", "positive_delta", "rise_ratio"},
        ):
            return False
        frame_index = candidate["frame_index"]
        sample_start = candidate["sample_start"]
        if not _plain_int(frame_index) or not 1 <= frame_index < short_event_count:
            return False
        if not _plain_int(sample_start) or sample_start != frame_index * 128:
            return False
        if frame_index in seen:
            return False
        seen.add(frame_index)

        previous_energy = _safe_decimal_int(candidate["previous_energy"])
        current_energy = _safe_decimal_int(candidate["current_energy"])
        positive_delta = _safe_decimal_int(candidate["positive_delta"])
        if previous_energy is None or current_energy is None or positive_delta is None:
            return False
        if current_energy <= previous_energy or current_energy * 2 < previous_energy * 3:
            return False
        if positive_delta != current_energy - previous_energy:
            return False
        if positive_delta > maximum_positive_delta or positive_delta > positive_delta_sum:
            return False

        ratio = candidate["rise_ratio"]
        if previous_energy == 0:
            if ratio is not None:
                return False
        else:
            if not _exact_keys(ratio, {"numerator", "denominator"}):
                return False
            ratio_numerator = _safe_decimal_int(ratio["numerator"])
            ratio_denominator = _safe_decimal_int(ratio["denominator"])
            if ratio_numerator != current_energy or ratio_denominator != previous_energy or ratio_denominator == 0:
                return False

        if previous_strength is not None:
            if positive_delta > previous_strength:
                return False
            if positive_delta == previous_strength and previous_index_for_tie is not None and frame_index < previous_index_for_tie:
                return False
        previous_strength = positive_delta
        previous_index_for_tie = frame_index
    return True


def _validate_long_channel(channel: object, index: int, frame_count: int, sample_rate: int) -> bool:
    if not _exact_keys(channel, {"channel_index", "long_spectral", "transient"}):
        return False
    if not _plain_int(channel["channel_index"]) or channel["channel_index"] != index:
        return False
    spectral = channel["long_spectral"]
    if not _exact_keys(
        spectral,
        {"aggregate_power_by_bin", "aggregate_power_by_frequency_region", "complex_matrix_sha256", "power_matrix_sha256", "events"},
    ):
        return False
    aggregate = spectral["aggregate_power_by_bin"]
    if not isinstance(aggregate, list) or len(aggregate) != LONG_FRAME_SIZE // 2 + 1:
        return False
    aggregate_values = [_safe_decimal_int(value) for value in aggregate]
    if any(value is None for value in aggregate_values):
        return False

    regions = spectral["aggregate_power_by_frequency_region"]
    region_names = {
        "below_20khz_reference",
        "20_to_40khz_reference",
        "at_or_above_40khz_reference",
    }
    if not _exact_keys(regions, region_names):
        return False
    region_values = {key: _safe_decimal_int(regions[key]) for key in region_names}
    if any(value is None for value in region_values.values()):
        return False
    expected_regions = {key: 0 for key in region_names}
    for bin_index, power in enumerate(aggregate_values):
        expected_regions[_region_index(sample_rate, bin_index)] += power
    if region_values != expected_regions:
        return False
    if not _hex_digest(spectral["complex_matrix_sha256"]) or not _hex_digest(spectral["power_matrix_sha256"]):
        return False

    events = spectral["events"]
    expected = (frame_count + LONG_HOP_SIZE - 1) // LONG_HOP_SIZE
    if not isinstance(events, list) or len(events) != expected:
        return False
    if not all(_validate_long_event(event, event_index) for event_index, event in enumerate(events)):
        return False
    centroid_denominator_total = 0
    for event in events:
        denominator = _safe_decimal_int(event["spectral_centroid_bin"]["denominator"])
        if denominator is None:
            return False
        centroid_denominator_total += denominator
    if centroid_denominator_total != sum(aggregate_values):
        return False
    short_event_count = (frame_count + 128 - 1) // 128
    return _validate_transient(channel["transient"], short_event_count)


def _validate_relationships(value: object, channel_count: int) -> bool:
    expected_pairs = channel_count * (channel_count - 1) // 2
    if not isinstance(value, list) or len(value) != expected_pairs:
        return False
    expected = [(i, j) for i in range(channel_count) for j in range(i + 1, channel_count)]
    channel_energies: dict[int, int] = {}
    for relation, (left, right) in zip(value, expected):
        if not _exact_keys(
            relation,
            {
                "left_channel",
                "right_channel",
                "dot_product",
                "dot_product_sign",
                "left_sum_squares",
                "right_sum_squares",
                "difference_sum_squares",
                "sum_sum_squares",
                "zero_lag_correlation_squared",
            },
        ):
            return False
        if not _plain_int(relation["left_channel"]) or not _plain_int(relation["right_channel"]):
            return False
        if relation["left_channel"] != left or relation["right_channel"] != right:
            return False
        if not _plain_int(relation["dot_product_sign"]) or relation["dot_product_sign"] not in (-1, 0, 1):
            return False

        dot = _safe_decimal_int(relation["dot_product"], signed=True)
        left_energy = _safe_decimal_int(relation["left_sum_squares"])
        right_energy = _safe_decimal_int(relation["right_sum_squares"])
        difference_energy = _safe_decimal_int(relation["difference_sum_squares"])
        sum_energy = _safe_decimal_int(relation["sum_sum_squares"])
        if None in (dot, left_energy, right_energy, difference_energy, sum_energy):
            return False
        for channel_index, energy in ((left, left_energy), (right, right_energy)):
            if channel_index in channel_energies and channel_energies[channel_index] != energy:
                return False
            channel_energies[channel_index] = energy
        expected_sign = 1 if dot > 0 else -1 if dot < 0 else 0
        if relation["dot_product_sign"] != expected_sign:
            return False
        if difference_energy != left_energy + right_energy - 2 * dot:
            return False
        if sum_energy != left_energy + right_energy + 2 * dot:
            return False

        corr = relation["zero_lag_correlation_squared"]
        denominator_value = left_energy * right_energy
        numerator_value = dot * dot
        if numerator_value > denominator_value:
            return False
        if denominator_value == 0:
            if corr is not None:
                return False
        else:
            if not _exact_keys(corr, {"numerator", "denominator"}):
                return False
            corr_numerator = _safe_decimal_int(corr["numerator"])
            corr_denominator = _safe_decimal_int(corr["denominator"])
            if corr_numerator != numerator_value or corr_denominator != denominator_value or corr_denominator == 0:
                return False
    return True


def _validate_percept_core(percept: object) -> bool:
    if not _exact_keys(
        percept,
        {
            "schema", "layer", "implementation", "source", "profile", "short_reference",
            "frequency_support", "channels", "channel_relationships", "interpretation",
        },
    ):
        return False
    if percept["schema"] != "qsol-map-percept-core-v0.2" or percept["layer"] != "L1_deterministic_acoustic_observation":
        return False
    if percept["implementation"] != IMPLEMENTATION_ID:
        return False

    source = percept["source"]
    if not _exact_keys(source, {"wav_sha256", "pcm_s16le_sha256", "sample_rate_hz", "channels", "frame_count", "bits_per_sample"}):
        return False
    if not _hex_digest(source["wav_sha256"]) or not _hex_digest(source["pcm_s16le_sha256"]):
        return False
    sample_rate = source["sample_rate_hz"]
    channel_count = source["channels"]
    frame_count = source["frame_count"]
    if not _plain_int(sample_rate) or not 1 <= sample_rate <= 768_000:
        return False
    if not _plain_int(channel_count) or not 1 <= channel_count <= 8:
        return False
    if not _plain_int(frame_count) or frame_count <= 0:
        return False
    if not _plain_int(source["bits_per_sample"]) or source["bits_per_sample"] != 16:
        return False

    expected_profile = {
        "id": PROFILE_ID,
        "short_reference_profile_id": V01_PROFILE_ID,
        "long_reference_profile_id": LONG_PROFILE_ID,
        "long_frame_size_samples": LONG_FRAME_SIZE,
        "long_hop_size_samples": LONG_HOP_SIZE,
        "long_window": "symmetric-integer-triangular-1024-v0.2",
        "long_twiddle": "frozen-exp-minus-i-2pi-k-over-1024-q15-v0.2",
        "q15_one": Q15_ONE,
        "long_top_components_per_frame": LONG_TOP_K,
        "tail_policy": "zero_pad_each_hop_start_below_frame_count",
        "numeric_contract": "exact_unbounded_integer_reference",
        "onset_rule": {
            "id": ONSET_RULE_ID,
            "candidate_condition": "current > previous and 2*current >= 3*previous",
            "source_profile": V01_PROFILE_ID,
            "maximum_reported_candidates": MAX_TRANSIENT_EVENTS,
        },
        "frequency_regions_hz": {
            "below_20khz_reference": {"lower_inclusive": 0, "upper_exclusive": 20_000},
            "20_to_40khz_reference": {"lower_inclusive": 20_000, "upper_exclusive": 40_000},
            "at_or_above_40khz_reference": {"lower_inclusive": 40_000, "upper_exclusive": None},
        },
        "sidecar_schema": "qsol-map-spectral-sidecar-v0.2",
    }
    if not _canonical_equal(percept["profile"], expected_profile):
        return False

    short = percept["short_reference"]
    if not _exact_keys(short, {"percept_sha256", "channels"}) or not _hex_digest(short["percept_sha256"]):
        return False
    if not isinstance(short["channels"], list) or len(short["channels"]) != channel_count:
        return False
    for index, channel in enumerate(short["channels"]):
        if not _exact_keys(channel, {"channel_index", "complex_matrix_sha256", "power_matrix_sha256"}):
            return False
        if not _plain_int(channel["channel_index"]) or channel["channel_index"] != index:
            return False
        if not _hex_digest(channel["complex_matrix_sha256"]) or not _hex_digest(channel["power_matrix_sha256"]):
            return False

    expected_support = _frequency_support(sample_rate)
    if not _canonical_equal(percept["frequency_support"], expected_support):
        return False

    channels = percept["channels"]
    if not isinstance(channels, list) or len(channels) != channel_count:
        return False
    if not all(
        _validate_long_channel(channel, index, frame_count, sample_rate)
        for index, channel in enumerate(channels)
    ):
        return False
    if not _validate_relationships(percept["channel_relationships"], channel_count):
        return False

    interpretation = percept["interpretation"]
    if not _exact_keys(
        interpretation,
        {"learned_tokenization_present", "semantic_inference_present", "human_subjective_report_present"},
    ):
        return False
    return (
        interpretation["learned_tokenization_present"] is False
        and interpretation["semantic_inference_present"] is False
        and interpretation["human_subjective_report_present"] is False
    )


def verify_multiresolution_envelope(envelope: dict) -> bool:
    if not _exact_keys(envelope, {"schema", "percept_sha256", "percept"}):
        return False
    if envelope["schema"] != "qsol-map-percept-envelope-v0.2":
        return False
    digest = envelope["percept_sha256"]
    if not _hex_digest(digest):
        return False
    try:
        percept = envelope["percept"]
        if not _validate_percept_core(percept):
            return False
        expected = domain_sha256(PERCEPT_DOMAIN, canonical_bytes(percept))
    except (KeyError, TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        return False
    return hmac.compare_digest(expected, digest)
