"""Exact PCM16 feasibility checks used by the v0.2 validation boundaries."""

from __future__ import annotations

import hashlib
from math import isqrt
import struct

from .wav import PCM16Wave


_PCM16_MAGNITUDE_MAX = 1 << 15
_PCM16_SQUARE_MAX = _PCM16_MAGNITUDE_MAX ** 2


def _small_window_energy_is_realizable(energy: int, available: int) -> bool:
    """Check exact energy feasibility for zero-, one-, and two-sample tails.

    Both frozen triangular windows start with weights 1 and 2. Magnitudes up
    to 32768 are allowed because their negative signs are representable PCM16
    samples. Longer windows retain their separate source-sized bounds; this
    helper makes no claim to solve their full integer feasibility problem.
    """
    if energy < 0 or available < 0:
        return False
    if available == 0:
        return energy == 0
    if available == 1:
        magnitude = isqrt(energy)
        return magnitude <= _PCM16_MAGNITUDE_MAX and magnitude * magnitude == energy
    if available == 2:
        if energy > 5 * _PCM16_SQUARE_MAX or energy % 4 not in (0, 1):
            return False
        for second in range(min(_PCM16_MAGNITUDE_MAX, isqrt(energy // 4)) + 1):
            first_square = energy - 4 * second * second
            first = isqrt(first_square)
            if first <= _PCM16_MAGNITUDE_MAX and first * first == first_square:
                return True
        return False
    return True


def _validate_wave_pcm_commitment(wave: PCM16Wave) -> None:
    """Validate the immutable sample layout and its exact interleaved digest.

    Hash at most 8192 payload bytes at a time. The original RIFF container is
    not retained by PCM16Wave, so source_sha256 is not recomputed here.
    """
    if not isinstance(wave, PCM16Wave):
        raise ValueError("sidecar requires a PCM16Wave")
    for value, lower, upper, name in (
        (wave.channels, 1, 8, "channels"),
        (wave.sample_rate_hz, 1, 768_000, "sample_rate_hz"),
    ):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"invalid PCM16Wave {name}")
    if type(wave.frame_count) is not int or wave.frame_count < 1:
        raise ValueError("invalid PCM16Wave frame_count")
    channels = wave.samples_by_channel
    if type(channels) is not tuple or len(channels) != wave.channels:
        raise ValueError("PCM16Wave samples must match the declared channel count")
    if any(type(samples) is not tuple or len(samples) != wave.frame_count for samples in channels):
        raise ValueError("PCM16Wave samples must be immutable tuples matching frame_count")

    digest = wave.pcm_s16le_sha256
    if not isinstance(digest, str) or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError("invalid PCM16Wave PCM commitment")
    hasher = hashlib.sha256()
    payload = bytearray()
    for frame_index in range(wave.frame_count):
        for samples in channels:
            sample = samples[frame_index]
            if type(sample) is not int or not -32768 <= sample <= 32767:
                raise ValueError("PCM16Wave samples must be plain signed PCM16 integers")
            payload.extend(struct.pack("<h", sample))
            if len(payload) == 8192:
                hasher.update(payload)
                payload.clear()
    hasher.update(payload)
    if hasher.hexdigest() != digest:
        raise ValueError("PCM16Wave PCM commitment does not match interleaved samples")
