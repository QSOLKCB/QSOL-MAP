"""Deterministic Layer-1 acoustic observation reference for QSOL-MAP."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Sequence

from .canonical import canonical_bytes, domain_sha256
from .tables import (
    FRAME_SIZE,
    WINDOW_WEIGHTS,
    HOP_SIZE,
    Q15_ONE,
    TOP_K,
    TWIDDLE_COS_Q15,
    TWIDDLE_SIN_Q15,
)
from .wav import PCM16Wave

PROFILE_ID = "qsol-map-fixed-fft-v0.1"
IMPLEMENTATION_ID = "qsol-map-python-reference-0.1.0"
PERCEPT_DOMAIN = "QSOL-MAP/PERCEPT/v0.1"
COMPLEX_MATRIX_DOMAIN = "QSOL-MAP/COMPLEX-MATRIX/v0.1"
POWER_MATRIX_DOMAIN = "QSOL-MAP/POWER-MATRIX/v0.1"

_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_SIGNED_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)\Z", re.ASCII)
_UNSIGNED_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z", re.ASCII)

_BIT_REVERSED = tuple(
    int(f"{index:08b}"[::-1], 2)
    for index in range(FRAME_SIZE)
)


def _frame_starts(sample_count: int) -> range:
    if sample_count <= 0:
        raise ValueError("analysis requires at least one sample")
    return range(0, sample_count, HOP_SIZE)


def _windowed_frame(samples: Sequence[int], start: int) -> list[int]:
    frame = [0] * FRAME_SIZE
    available = min(FRAME_SIZE, max(0, len(samples) - start))
    for index in range(available):
        frame[index] = samples[start + index] * WINDOW_WEIGHTS[index]
    return frame


def _fixed_fft_real(windowed: Sequence[int]) -> tuple[tuple[int, int], ...]:
    """Compute the frozen 256-point complex transform using exact integers.

    No right-shift or floating-point rounding occurs. Each FFT stage multiplies
    both butterfly paths by Q15_ONE, so the common scale grows uniformly and
    remains exactly comparable within the profile.
    """
    if len(windowed) != FRAME_SIZE:
        raise ValueError("fixed FFT requires exactly 256 windowed samples")

    state = [[windowed[_BIT_REVERSED[index]], 0] for index in range(FRAME_SIZE)]
    width = 2
    while width <= FRAME_SIZE:
        half = width // 2
        twiddle_step = FRAME_SIZE // width
        for base in range(0, FRAME_SIZE, width):
            for offset in range(half):
                twiddle_index = offset * twiddle_step
                wr = TWIDDLE_COS_Q15[twiddle_index]
                wi = TWIDDLE_SIN_Q15[twiddle_index]

                ur, ui = state[base + offset]
                vr, vi = state[base + offset + half]
                tr = vr * wr - vi * wi
                ti = vr * wi + vi * wr
                scaled_ur = ur * Q15_ONE
                scaled_ui = ui * Q15_ONE

                state[base + offset] = [scaled_ur + tr, scaled_ui + ti]
                state[base + offset + half] = [scaled_ur - tr, scaled_ui - ti]
        width *= 2

    return tuple((real, imag) for real, imag in state[: FRAME_SIZE // 2 + 1])


def _update_row_hash(hasher: "hashlib._Hash", row: object) -> None:
    encoded = canonical_bytes(row)
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def _waveform_observations(samples: Sequence[int]) -> dict:
    peak_abs = 0
    sum_squares = 0
    zero_crossings = 0
    previous_sign = 0
    for sample in samples:
        magnitude = abs(sample)
        if magnitude > peak_abs:
            peak_abs = magnitude
        sum_squares += sample * sample
        sign = 1 if sample > 0 else -1 if sample < 0 else 0
        if sign:
            if previous_sign and sign != previous_sign:
                zero_crossings += 1
            previous_sign = sign
    return {
        "sample_count": len(samples),
        "peak_abs": peak_abs,
        "sum_squares": str(sum_squares),
        "zero_crossings": zero_crossings,
    }


def _analyze_channel(samples: Sequence[int]) -> dict:
    bin_count = FRAME_SIZE // 2 + 1
    aggregate_power = [0] * bin_count

    complex_hash = hashlib.sha256()
    complex_hash.update(COMPLEX_MATRIX_DOMAIN.encode("utf-8") + b"\x00")
    power_hash = hashlib.sha256()
    power_hash.update(POWER_MATRIX_DOMAIN.encode("utf-8") + b"\x00")

    events = []
    for frame_index, start in enumerate(_frame_starts(len(samples))):
        windowed = _windowed_frame(samples, start)
        coefficients = _fixed_fft_real(windowed)
        powers = [real * real + imag * imag for real, imag in coefficients]

        for bin_index, power in enumerate(powers):
            aggregate_power[bin_index] += power

        _update_row_hash(
            complex_hash,
            [[str(real), str(imag)] for real, imag in coefficients],
        )
        _update_row_hash(power_hash, [str(power) for power in powers])

        ranked = sorted(range(bin_count), key=lambda k: (-powers[k], k))[:TOP_K]
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
        "waveform": _waveform_observations(samples),
        "aggregate_power_by_bin": [str(value) for value in aggregate_power],
        "complex_matrix_sha256": complex_hash.hexdigest(),
        "power_matrix_sha256": power_hash.hexdigest(),
        "events": events,
    }


def build_percept(wave: PCM16Wave) -> dict:
    """Build a deterministic Layer-1 percept envelope from parsed PCM16 audio."""
    percept = {
        "schema": "qsol-map-percept-core-v0.1",
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
            "frame_size_samples": FRAME_SIZE,
            "hop_size_samples": HOP_SIZE,
            "window": "symmetric-integer-triangular-v1",
            "twiddle": "frozen-exp-minus-i-2pi-k-over-256-q15-v1",
            "q15_one": Q15_ONE,
            "top_components_per_frame": TOP_K,
            "frequency_bin_rule": {
                "numerator": "bin_index * sample_rate_hz",
                "denominator": FRAME_SIZE,
            },
            "tail_policy": "zero_pad_each_hop_start_below_frame_count",
            "numeric_contract": "exact_unbounded_integer_reference",
        },
        "channels": [
            {
                "channel_index": channel_index,
                **_analyze_channel(samples),
            }
            for channel_index, samples in enumerate(wave.samples_by_channel)
        ],
        "interpretation": {
            "learned_tokenization_present": False,
            "semantic_inference_present": False,
            "human_subjective_report_present": False,
        },
    }

    digest = domain_sha256(PERCEPT_DOMAIN, canonical_bytes(percept))
    return {
        "schema": "qsol-map-percept-envelope-v0.1",
        "percept_sha256": digest,
        "percept": percept,
    }


def _plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _hex_digest(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _signed_decimal(value: object) -> bool:
    return isinstance(value, str) and _SIGNED_DECIMAL.fullmatch(value) is not None


def _unsigned_decimal(value: object) -> bool:
    return isinstance(value, str) and _UNSIGNED_DECIMAL.fullmatch(value) is not None


def _exact_keys(value: object, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys


def _validate_frame_event(event: object, frame_index: int) -> bool:
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
    if event["frame_index"] != frame_index or event["sample_start"] != frame_index * HOP_SIZE:
        return False
    if not _plain_int(event["frame_index"]) or not _plain_int(event["sample_start"]):
        return False
    if not _unsigned_decimal(event["windowed_energy"]):
        return False

    centroid = event["spectral_centroid_bin"]
    if not _exact_keys(centroid, {"numerator", "denominator"}):
        return False
    if not _unsigned_decimal(centroid["numerator"]) or not _unsigned_decimal(centroid["denominator"]):
        return False

    dominant = event["dominant_non_dc_bin"]
    if not _plain_int(dominant) or not 1 <= dominant <= FRAME_SIZE // 2:
        return False

    components = event["top_components"]
    if not isinstance(components, list) or len(components) != TOP_K:
        return False
    bins: set[int] = set()
    for component in components:
        if not _exact_keys(component, {"bin", "real", "imag", "power"}):
            return False
        bin_index = component["bin"]
        if not _plain_int(bin_index) or not 0 <= bin_index <= FRAME_SIZE // 2:
            return False
        if bin_index in bins:
            return False
        bins.add(bin_index)
        if not _signed_decimal(component["real"]) or not _signed_decimal(component["imag"]):
            return False
        if not _unsigned_decimal(component["power"]):
            return False
    return True


def _validate_channel(channel: object, channel_index: int, frame_count: int) -> bool:
    if not _exact_keys(
        channel,
        {
            "channel_index",
            "waveform",
            "aggregate_power_by_bin",
            "complex_matrix_sha256",
            "power_matrix_sha256",
            "events",
        },
    ):
        return False
    if channel["channel_index"] != channel_index or not _plain_int(channel["channel_index"]):
        return False

    waveform = channel["waveform"]
    if not _exact_keys(waveform, {"sample_count", "peak_abs", "sum_squares", "zero_crossings"}):
        return False
    if waveform["sample_count"] != frame_count or not _plain_int(waveform["sample_count"]):
        return False
    peak_abs = waveform["peak_abs"]
    zero_crossings = waveform["zero_crossings"]
    if not _plain_int(peak_abs) or not 0 <= peak_abs <= 32768:
        return False
    if not _plain_int(zero_crossings) or not 0 <= zero_crossings <= max(0, frame_count - 1):
        return False
    if not _unsigned_decimal(waveform["sum_squares"]):
        return False

    aggregate = channel["aggregate_power_by_bin"]
    if not isinstance(aggregate, list) or len(aggregate) != FRAME_SIZE // 2 + 1:
        return False
    if not all(_unsigned_decimal(value) for value in aggregate):
        return False
    if not _hex_digest(channel["complex_matrix_sha256"]) or not _hex_digest(channel["power_matrix_sha256"]):
        return False

    events = channel["events"]
    expected_events = (frame_count + HOP_SIZE - 1) // HOP_SIZE
    if not isinstance(events, list) or len(events) != expected_events:
        return False
    return all(_validate_frame_event(event, index) for index, event in enumerate(events))


def _validate_percept_core(percept: object) -> bool:
    if not _exact_keys(
        percept,
        {"schema", "layer", "implementation", "source", "profile", "channels", "interpretation"},
    ):
        return False
    if percept["schema"] != "qsol-map-percept-core-v0.1":
        return False
    if percept["layer"] != "L1_deterministic_acoustic_observation":
        return False
    if percept["implementation"] != IMPLEMENTATION_ID:
        return False

    source = percept["source"]
    if not _exact_keys(
        source,
        {"wav_sha256", "pcm_s16le_sha256", "sample_rate_hz", "channels", "frame_count", "bits_per_sample"},
    ):
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
    if source["bits_per_sample"] != 16 or not _plain_int(source["bits_per_sample"]):
        return False

    profile = percept["profile"]
    if not _exact_keys(
        profile,
        {
            "id",
            "frame_size_samples",
            "hop_size_samples",
            "window",
            "twiddle",
            "q15_one",
            "top_components_per_frame",
            "frequency_bin_rule",
            "tail_policy",
            "numeric_contract",
        },
    ):
        return False
    if profile["id"] != PROFILE_ID:
        return False
    if profile["frame_size_samples"] != FRAME_SIZE or profile["hop_size_samples"] != HOP_SIZE:
        return False
    if profile["window"] != "symmetric-integer-triangular-v1":
        return False
    if profile["twiddle"] != "frozen-exp-minus-i-2pi-k-over-256-q15-v1":
        return False
    if profile["q15_one"] != Q15_ONE or profile["top_components_per_frame"] != TOP_K:
        return False
    if profile["tail_policy"] != "zero_pad_each_hop_start_below_frame_count":
        return False
    if profile["numeric_contract"] != "exact_unbounded_integer_reference":
        return False
    if profile["frequency_bin_rule"] != {
        "numerator": "bin_index * sample_rate_hz",
        "denominator": FRAME_SIZE,
    }:
        return False

    channels = percept["channels"]
    if not isinstance(channels, list) or len(channels) != channel_count:
        return False
    if not all(_validate_channel(channel, index, frame_count) for index, channel in enumerate(channels)):
        return False

    interpretation = percept["interpretation"]
    if not _exact_keys(
        interpretation,
        {"learned_tokenization_present", "semantic_inference_present", "human_subjective_report_present"},
    ):
        return False
    return interpretation == {
        "learned_tokenization_present": False,
        "semantic_inference_present": False,
        "human_subjective_report_present": False,
    }


def verify_percept_envelope(envelope: dict) -> bool:
    if not _exact_keys(envelope, {"schema", "percept_sha256", "percept"}):
        return False
    if envelope["schema"] != "qsol-map-percept-envelope-v0.1":
        return False

    percept = envelope["percept"]
    digest = envelope["percept_sha256"]
    if not _hex_digest(digest) or not _validate_percept_core(percept):
        return False

    try:
        expected = domain_sha256(PERCEPT_DOMAIN, canonical_bytes(percept))
    except (TypeError, ValueError, UnicodeError):
        return False
    return hmac.compare_digest(expected, digest)
