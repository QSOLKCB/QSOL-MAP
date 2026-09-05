"""Deterministic Layer-1 acoustic observation reference for QSOL-MAP."""

from __future__ import annotations

import hashlib
import hmac
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


def verify_percept_envelope(envelope: dict) -> bool:
    if not isinstance(envelope, dict):
        return False
    if envelope.get("schema") != "qsol-map-percept-envelope-v0.1":
        return False
    percept = envelope.get("percept")
    digest = envelope.get("percept_sha256")
    if not isinstance(percept, dict) or not isinstance(digest, str):
        return False
    expected = domain_sha256(PERCEPT_DOMAIN, canonical_bytes(percept))
    return hmac.compare_digest(expected, digest)
