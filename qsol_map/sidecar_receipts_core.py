"""QSOL-MAP v0.2 sidecar API with final reconstructed-evidence bindings."""

from __future__ import annotations

import hashlib
import struct
import tempfile
from typing import Iterable

from . import analysis as _v01
from . import multiresolution as _mr
from . import sidecar_consistency_core as _consistency
from . import sidecar_core as _base
from .canonical import canonical_bytes
from .tables import FRAME_SIZE as _SHORT_FRAME_SIZE, TOP_K as _SHORT_TOP_K


# Preserve the established writer, constants, and reconstruction helper surface.
for _name in dir(_consistency):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_consistency, _name)


_DECODE_FAILURE_SENTINEL = "__qsol_map_invalid_decode__\n"


def _preserving_bounded_lines(lines: Iterable[str]):
    """Bound file-backed reads and preserve decode failures as invalid evidence."""
    readline = getattr(lines, "readline", None)
    if callable(readline):
        while True:
            try:
                line = readline(MAX_SIDECAR_LINE_CHARS + 1)
            except UnicodeDecodeError:
                yield _DECODE_FAILURE_SENTINEL
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
            yield _DECODE_FAILURE_SENTINEL


class _EvidenceCapture(_consistency._EvidenceCapture):
    """Extend waveform reconstruction with PCM and frozen-v0.1 commitments."""

    def __init__(self, envelope: dict):
        super().__init__(envelope)
        self.short_aggregate = [
            [0] * (_SHORT_FRAME_SIZE // 2 + 1)
            for _ in range(self.channel_count)
        ]
        self.short_event_streams = [
            tempfile.TemporaryFile() for _ in range(self.channel_count)
        ]
        self.short_event_counts = [0] * self.channel_count

    def close(self) -> None:
        for stream in getattr(self, "short_event_streams", []):
            stream.close()
        super().close()

    def feed(self, line: str) -> None:
        record = _base._canonical_line(line)
        super().feed(line)
        if self.invalid or record is None:
            return
        if (
            record.get("record_type") != "spectral_frame"
            or record.get("profile_id") != _mr.V01_PROFILE_ID
        ):
            return

        channel_index = record.get("channel_index")
        if not _base._plain_int(channel_index) or not 0 <= channel_index < self.channel_count:
            self.invalid = True
            return
        parsed = self._parse_coefficients(record)
        if parsed is None or len(parsed) != _SHORT_FRAME_SIZE // 2 + 1:
            self.invalid = True
            return

        powers = [real * real + imag * imag for real, imag in parsed]
        for bin_index, power in enumerate(powers):
            self.short_aggregate[channel_index][bin_index] += power

        energy = self.transients[channel_index].previous_energy
        if energy is None:
            self.invalid = True
            return
        ranked = sorted(
            range(len(powers)),
            key=lambda bin_index: (-powers[bin_index], bin_index),
        )[:_SHORT_TOP_K]
        dominant = max(
            range(1, len(powers)),
            key=lambda bin_index: (powers[bin_index], -bin_index),
        )
        event = {
            "frame_index": record["frame_index"],
            "sample_start": record["sample_start"],
            "windowed_energy": str(energy),
            "spectral_centroid_bin": {
                "numerator": str(
                    sum(bin_index * power for bin_index, power in enumerate(powers))
                ),
                "denominator": str(sum(powers)),
            },
            "dominant_non_dc_bin": dominant,
            "top_components": [
                {
                    "bin": bin_index,
                    "real": str(parsed[bin_index][0]),
                    "imag": str(parsed[bin_index][1]),
                    "power": str(powers[bin_index]),
                }
                for bin_index in ranked
            ],
        }
        stream = self.short_event_streams[channel_index]
        if self.short_event_counts[channel_index]:
            stream.write(b",")
        stream.write(canonical_bytes(event))
        self.short_event_counts[channel_index] += 1

    def _pcm_sha256(self) -> str | None:
        for spool in self.short:
            spool.rewind()
        hasher = hashlib.sha256()
        frame_format = "<" + "h" * self.channel_count
        while True:
            chunks = [spool.stream.read(8192) for spool in self.short]
            lengths = {len(chunk) for chunk in chunks}
            if len(lengths) != 1:
                return None
            chunk_length = lengths.pop()
            if chunk_length == 0:
                return hasher.hexdigest()
            if chunk_length % 2:
                return None
            channel_values = [
                [value for (value,) in struct.iter_unpack("<h", chunk)]
                for chunk in chunks
            ]
            if len({len(values) for values in channel_values}) != 1:
                return None
            interleaved = bytearray()
            for frame in zip(*channel_values):
                interleaved.extend(struct.pack(frame_format, *frame))
            hasher.update(interleaved)

    @staticmethod
    def _waveform_observation(spool) -> dict | None:
        spool.rewind()
        peak_abs = 0
        zero_crossings = 0
        previous_sign = 0
        sample_count = 0
        while True:
            chunk = spool.stream.read(8192)
            if not chunk:
                break
            if len(chunk) % 2:
                return None
            for (sample,) in struct.iter_unpack("<h", chunk):
                sample_count += 1
                peak_abs = max(peak_abs, abs(sample))
                sign = 1 if sample > 0 else -1 if sample < 0 else 0
                if sign:
                    if previous_sign and sign != previous_sign:
                        zero_crossings += 1
                    previous_sign = sign
        if sample_count != spool.frame_count:
            return None
        return {
            "sample_count": sample_count,
            "peak_abs": peak_abs,
            "sum_squares": str(spool.sum_squares),
            "zero_crossings": zero_crossings,
        }

    def _v01_percept_sha256(self) -> str | None:
        """Stream the canonical frozen-v0.1 percept into its domain hash."""
        waveforms = [self._waveform_observation(spool) for spool in self.short]
        if any(waveform is None for waveform in waveforms):
            return None

        hasher = hashlib.sha256()
        hasher.update(_v01.PERCEPT_DOMAIN.encode("utf-8") + b"\x00")
        write = hasher.update
        write(b'{"channels":[')
        short_reference = self.envelope["percept"]["short_reference"]["channels"]
        for channel_index in range(self.channel_count):
            if channel_index:
                write(b",")
            write(b'{"aggregate_power_by_bin":')
            write(canonical_bytes([
                str(value) for value in self.short_aggregate[channel_index]
            ]))
            write(b',"channel_index":')
            write(str(channel_index).encode("ascii"))
            write(b',"complex_matrix_sha256":')
            write(canonical_bytes(short_reference[channel_index]["complex_matrix_sha256"]))
            write(b',"events":[')
            event_stream = self.short_event_streams[channel_index]
            event_stream.seek(0)
            while True:
                chunk = event_stream.read(8192)
                if not chunk:
                    break
                write(chunk)
            write(b'],"power_matrix_sha256":')
            write(canonical_bytes(short_reference[channel_index]["power_matrix_sha256"]))
            write(b',"waveform":')
            write(canonical_bytes(waveforms[channel_index]))
            write(b"}")

        profile = {
            "id": _v01.PROFILE_ID,
            "frame_size_samples": _SHORT_FRAME_SIZE,
            "hop_size_samples": _v01.HOP_SIZE,
            "window": "symmetric-integer-triangular-v1",
            "twiddle": "frozen-exp-minus-i-2pi-k-over-256-q15-v1",
            "q15_one": _v01.Q15_ONE,
            "top_components_per_frame": _SHORT_TOP_K,
            "frequency_bin_rule": {
                "numerator": "bin_index * sample_rate_hz",
                "denominator": _SHORT_FRAME_SIZE,
            },
            "tail_policy": "zero_pad_each_hop_start_below_frame_count",
            "numeric_contract": "exact_unbounded_integer_reference",
        }
        interpretation = {
            "learned_tokenization_present": False,
            "semantic_inference_present": False,
            "human_subjective_report_present": False,
        }
        write(b'],"implementation":')
        write(canonical_bytes(_v01.IMPLEMENTATION_ID))
        write(b',"interpretation":')
        write(canonical_bytes(interpretation))
        write(b',"layer":')
        write(canonical_bytes("L1_deterministic_acoustic_observation"))
        write(b',"profile":')
        write(canonical_bytes(profile))
        write(b',"schema":')
        write(canonical_bytes("qsol-map-percept-core-v0.1"))
        write(b',"source":')
        write(canonical_bytes(self.envelope["percept"]["source"]))
        write(b"}")
        return hasher.hexdigest()

    def validate(self) -> bool:
        if not super().validate():
            return False
        reconstructed_pcm_sha256 = self._pcm_sha256()
        if reconstructed_pcm_sha256 is None:
            return False
        source = self.envelope["percept"]["source"]
        if reconstructed_pcm_sha256 != source["pcm_s16le_sha256"]:
            return False
        reconstructed_v01 = self._v01_percept_sha256()
        if reconstructed_v01 is None:
            return False
        return (
            reconstructed_v01
            == self.envelope["percept"]["short_reference"]["percept_sha256"]
        )


def verify_spectral_sidecar(envelope: dict, lines: Iterable[str]) -> bool:
    """Verify sidecar commitments before allocating reconstruction resources."""
    if not _mr.verify_multiresolution_envelope(envelope):
        return False

    capture: _EvidenceCapture | None = None
    try:
        capture = _EvidenceCapture(envelope)

        def instrumented():
            for line in _preserving_bounded_lines(lines):
                capture.feed(line)
                yield line

        if not _base.verify_spectral_sidecar(envelope, instrumented()):
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
