"""QSOL-MAP v0.2 sidecar API with cross-profile evidence consistency checks."""

from __future__ import annotations

import struct
import tempfile
from typing import Iterable

from . import multiresolution as _mr
from . import sidecar_core as _core
from .tables import (
    FRAME_SIZE as _SHORT_FRAME_SIZE,
    HOP_SIZE as _SHORT_HOP_SIZE,
    Q15_ONE as _SHORT_Q15_ONE,
    TWIDDLE_COS_Q15 as _SHORT_TWIDDLE_COS,
    TWIDDLE_SIN_Q15 as _SHORT_TWIDDLE_SIN,
    WINDOW_WEIGHTS as _SHORT_WINDOW_WEIGHTS,
)
from .v02_tables import (
    LONG_FRAME_SIZE as _LONG_FRAME_SIZE,
    LONG_HOP_SIZE as _LONG_HOP_SIZE,
    Q15_ONE as _LONG_Q15_ONE,
    TWIDDLE_COS_Q15_1024 as _LONG_TWIDDLE_COS,
    TWIDDLE_SIN_Q15_1024 as _LONG_TWIDDLE_SIN,
    LONG_WINDOW_WEIGHTS as _LONG_WINDOW_WEIGHTS,
)


# Preserve the established sidecar writer, constants, and helper surface.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)


def _safe_bounded_lines(lines: Iterable[str]):
    """Yield sidecar lines with bounded file reads and fail-closed decoding."""
    readline = getattr(lines, "readline", None)
    if callable(readline):
        while True:
            try:
                line = readline(MAX_SIDECAR_LINE_CHARS + 1)
            except UnicodeDecodeError:
                return
            if line == "":
                return
            yield line
            if len(line) > MAX_SIDECAR_LINE_CHARS or not line.endswith("\n"):
                return
    else:
        try:
            for line in lines:
                yield line
        except UnicodeDecodeError:
            return


def _bit_reverse(index: int, bits: int) -> int:
    result = 0
    for _ in range(bits):
        result = (result << 1) | (index & 1)
        index >>= 1
    return result


def _recover_pcm_frame(
    coefficients: list[tuple[int, int]],
    *,
    frame_size: int,
    q15_one: int,
    twiddle_cos: tuple[int, ...],
    twiddle_sin: tuple[int, ...],
    window_weights: tuple[int, ...],
    available: int,
) -> tuple[list[int], int] | None:
    """Invert a frozen real-input FFT row into exact PCM samples and frame energy."""
    expected_bins = frame_size // 2 + 1
    if len(coefficients) != expected_bins or not 0 <= available <= frame_size:
        return None
    if coefficients[0][1] != 0 or coefficients[-1][1] != 0:
        return None

    state = [[real, imag] for real, imag in coefficients]
    state.extend([[real, -imag] for real, imag in reversed(coefficients[1:-1])])

    width = frame_size
    while width >= 2:
        half = width // 2
        twiddle_step = frame_size // width
        previous = [[0, 0] for _ in range(frame_size)]
        for base in range(0, frame_size, width):
            for offset in range(half):
                ar, ai = state[base + offset]
                br, bi = state[base + offset + half]

                ur_num = ar + br
                ui_num = ai + bi
                u_den = 2 * q15_one
                if ur_num % u_den or ui_num % u_den:
                    return None
                ur = ur_num // u_den
                ui = ui_num // u_den

                dr = ar - br
                di = ai - bi
                if dr % 2 or di % 2:
                    return None
                tr = dr // 2
                ti = di // 2

                twiddle_index = offset * twiddle_step
                wr = twiddle_cos[twiddle_index]
                wi = twiddle_sin[twiddle_index]
                norm = wr * wr + wi * wi
                if norm == 0:
                    return None
                vr_num = tr * wr + ti * wi
                vi_num = ti * wr - tr * wi
                if vr_num % norm or vi_num % norm:
                    return None
                vr = vr_num // norm
                vi = vi_num // norm

                previous[base + offset] = [ur, ui]
                previous[base + offset + half] = [vr, vi]
        state = previous
        width //= 2

    bits = frame_size.bit_length() - 1
    windowed: list[int] = []
    energy = 0
    for index in range(frame_size):
        real, imag = state[_bit_reverse(index, bits)]
        if imag != 0:
            return None
        windowed.append(real)
        energy += real * real

    samples: list[int] = []
    for index, value in enumerate(windowed):
        if index >= available:
            if value != 0:
                return None
            continue
        weight = window_weights[index]
        if weight <= 0 or value % weight:
            return None
        sample = value // weight
        if not -(1 << 15) <= sample < (1 << 15):
            return None
        samples.append(sample)
    return samples, energy


class _ChannelSpool:
    def __init__(self, frame_count: int):
        self.frame_count = frame_count
        self.stream = tempfile.TemporaryFile()
        self.written = 0
        self.sum_squares = 0

    def merge(self, sample_start: int, samples: list[int]) -> bool:
        if sample_start < 0 or sample_start > self.written:
            return False
        end = sample_start + len(samples)
        if end > self.frame_count:
            return False

        overlap = min(len(samples), max(0, self.written - sample_start))
        if overlap:
            self.stream.seek(sample_start * 2)
            existing = self.stream.read(overlap * 2)
            if len(existing) != overlap * 2:
                return False
            prior = [value for (value,) in struct.iter_unpack("<h", existing)]
            if prior != samples[:overlap]:
                return False

        new_offset = max(0, self.written - sample_start)
        new_samples = samples[new_offset:]
        if new_samples:
            self.stream.seek(self.written * 2)
            self.stream.write(struct.pack("<" + "h" * len(new_samples), *new_samples))
            self.sum_squares += sum(sample * sample for sample in new_samples)
            self.written += len(new_samples)
        return True

    def complete(self) -> bool:
        return self.written == self.frame_count

    def rewind(self) -> None:
        self.stream.seek(0)

    def close(self) -> None:
        self.stream.close()


class _TransientAccumulator:
    def __init__(self):
        self.previous_energy: int | None = None
        self.candidate_count = 0
        self.positive_delta_sum = 0
        self.maximum_positive_delta = 0
        self.strongest: list[dict] = []

    def observe(self, frame_index: int, sample_start: int, current: int) -> None:
        previous = self.previous_energy
        if previous is not None:
            delta = current - previous
            positive = max(0, delta)
            self.positive_delta_sum += positive
            self.maximum_positive_delta = max(self.maximum_positive_delta, positive)
            if current > previous and current * 2 >= previous * 3:
                self.candidate_count += 1
                ratio = None
                if previous != 0:
                    ratio = {
                        "numerator": str(current),
                        "denominator": str(previous),
                    }
                candidate = {
                    "frame_index": frame_index,
                    "sample_start": sample_start,
                    "previous_energy": str(previous),
                    "current_energy": str(current),
                    "positive_delta": str(positive),
                    "rise_ratio": ratio,
                }
                self.strongest.append(candidate)
                self.strongest.sort(
                    key=lambda item: (-int(item["positive_delta"]), item["frame_index"])
                )
                del self.strongest[_mr.MAX_TRANSIENT_EVENTS :]
        self.previous_energy = current

    def observation(self) -> dict:
        return {
            "rule_id": _mr.ONSET_RULE_ID,
            "candidate_count": self.candidate_count,
            "positive_delta_sum": str(self.positive_delta_sum),
            "maximum_positive_delta": str(self.maximum_positive_delta),
            "strongest_candidates": self.strongest,
        }


class _EvidenceCapture:
    def __init__(self, envelope: dict):
        source = envelope["percept"]["source"]
        self.envelope = envelope
        self.frame_count = source["frame_count"]
        self.channel_count = source["channels"]
        self.invalid = False
        self.short = [_ChannelSpool(self.frame_count) for _ in range(self.channel_count)]
        self.long = [_ChannelSpool(self.frame_count) for _ in range(self.channel_count)]
        self.transients = [_TransientAccumulator() for _ in range(self.channel_count)]

    def close(self) -> None:
        for spool in self.short + self.long:
            spool.close()

    def _parse_coefficients(self, record: dict) -> list[tuple[int, int]] | None:
        coefficients = record.get("coefficients")
        if not isinstance(coefficients, list):
            return None
        result: list[tuple[int, int]] = []
        for item in coefficients:
            if not isinstance(item, list) or len(item) != 3:
                return None
            if not _core._signed_decimal(item[0]) or not _core._signed_decimal(item[1]):
                return None
            if not _core._unsigned_decimal(item[2]):
                return None
            try:
                real = int(item[0])
                imag = int(item[1])
                power = int(item[2])
            except (TypeError, ValueError):
                return None
            if real * real + imag * imag != power:
                return None
            result.append((real, imag))
        return result

    def feed(self, line: str) -> None:
        if self.invalid:
            return
        record = _core._canonical_line(line)
        if record is None or record.get("record_type") != "spectral_frame":
            return

        profile_id = record.get("profile_id")
        channel_index = record.get("channel_index")
        frame_index = record.get("frame_index")
        sample_start = record.get("sample_start")
        if (
            not _core._plain_int(channel_index)
            or not _core._plain_int(frame_index)
            or not _core._plain_int(sample_start)
            or not 0 <= channel_index < self.channel_count
        ):
            self.invalid = True
            return

        parsed = self._parse_coefficients(record)
        if parsed is None:
            self.invalid = True
            return

        if profile_id == _mr.V01_PROFILE_ID:
            frame_size = _SHORT_FRAME_SIZE
            q15_one = _SHORT_Q15_ONE
            twiddle_cos = _SHORT_TWIDDLE_COS
            twiddle_sin = _SHORT_TWIDDLE_SIN
            window_weights = _SHORT_WINDOW_WEIGHTS
            spool = self.short[channel_index]
        elif profile_id == _mr.LONG_PROFILE_ID:
            frame_size = _LONG_FRAME_SIZE
            q15_one = _LONG_Q15_ONE
            twiddle_cos = _LONG_TWIDDLE_COS
            twiddle_sin = _LONG_TWIDDLE_SIN
            window_weights = _LONG_WINDOW_WEIGHTS
            spool = self.long[channel_index]
        else:
            return

        available = min(frame_size, max(0, self.frame_count - sample_start))
        recovered = _recover_pcm_frame(
            parsed,
            frame_size=frame_size,
            q15_one=q15_one,
            twiddle_cos=twiddle_cos,
            twiddle_sin=twiddle_sin,
            window_weights=window_weights,
            available=available,
        )
        if recovered is None:
            self.invalid = True
            return
        samples, energy = recovered
        if not spool.merge(sample_start, samples):
            self.invalid = True
            return
        if profile_id == _mr.V01_PROFILE_ID:
            self.transients[channel_index].observe(frame_index, sample_start, energy)

    @staticmethod
    def _same_stream(left: _ChannelSpool, right: _ChannelSpool) -> bool:
        left.rewind()
        right.rewind()
        while True:
            left_chunk = left.stream.read(8192)
            right_chunk = right.stream.read(8192)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True

    @staticmethod
    def _dot(left: _ChannelSpool, right: _ChannelSpool) -> tuple[int, int, int]:
        left.rewind()
        right.rewind()
        dot = 0
        difference_energy = 0
        sum_energy = 0
        while True:
            left_chunk = left.stream.read(8192)
            right_chunk = right.stream.read(8192)
            if len(left_chunk) != len(right_chunk) or len(left_chunk) % 2:
                raise ValueError("inconsistent reconstructed channel spool")
            if not left_chunk:
                return dot, difference_energy, sum_energy
            left_values = struct.iter_unpack("<h", left_chunk)
            right_values = struct.iter_unpack("<h", right_chunk)
            for (left_sample,), (right_sample,) in zip(left_values, right_values):
                dot += left_sample * right_sample
                delta = left_sample - right_sample
                total = left_sample + right_sample
                difference_energy += delta * delta
                sum_energy += total * total

    def _expected_relationships(self) -> list[dict]:
        relationships = []
        for left_index in range(self.channel_count):
            left = self.short[left_index]
            for right_index in range(left_index + 1, self.channel_count):
                right = self.short[right_index]
                dot, difference_energy, sum_energy = self._dot(left, right)
                left_energy = left.sum_squares
                right_energy = right.sum_squares
                denominator = left_energy * right_energy
                correlation = None
                if denominator:
                    correlation = {
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
                        "zero_lag_correlation_squared": correlation,
                    }
                )
        return relationships

    def validate(self) -> bool:
        if self.invalid:
            return False
        if not all(spool.complete() for spool in self.short + self.long):
            return False
        for channel_index in range(self.channel_count):
            if not self._same_stream(self.short[channel_index], self.long[channel_index]):
                return False
            reported_transient = self.envelope["percept"]["channels"][channel_index]["transient"]
            if reported_transient != self.transients[channel_index].observation():
                return False
        return (
            self.envelope["percept"]["channel_relationships"]
            == self._expected_relationships()
        )


def verify_spectral_sidecar(envelope: dict, lines: Iterable[str]) -> bool:
    """Verify canonical sidecar commitments and reconstruct cross-profile L1 evidence."""
    capture: _EvidenceCapture | None = None
    try:
        capture = _EvidenceCapture(envelope)

        def instrumented():
            for line in _safe_bounded_lines(lines):
                capture.feed(line)
                yield line

        if not _core.verify_spectral_sidecar(envelope, instrumented()):
            return False
        return capture.validate()
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeError,
        OverflowError,
        RecursionError,
        OSError,
        struct.error,
    ):
        return False
    finally:
        if capture is not None:
            capture.close()
