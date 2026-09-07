"""Regression coverage for short PCM windows, writer input, and the FFT spec."""

import copy
from dataclasses import replace
import hashlib
import io
from pathlib import Path
import struct
import unittest
from unittest import mock

import qsol_map.multiresolution as multiresolution
import qsol_map.sidecar as sidecar
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.pcm_constraints import (
    _small_window_energy_is_realizable,
    _validate_wave_pcm_commitment,
)
from qsol_map.v02_tables import TWIDDLE_COS_QUARTER_Q15_1024
from qsol_map.wav import PCM16Wave, parse_pcm16_wav


def make_wav(samples, channels=1, sample_rate=48000):
    payload = struct.pack("<" + "h" * len(samples), *samples)
    block_align = channels * 2
    fmt = struct.pack(
        "<HHIIHH", 1, channels, sample_rate,
        sample_rate * block_align, block_align, 16,
    )
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def rehash(envelope):
    envelope["percept_sha256"] = domain_sha256(
        multiresolution.PERCEPT_DOMAIN, canonical_bytes(envelope["percept"])
    )


class SmallWindowFeasibilityTests(unittest.TestCase):
    def test_two_sample_mono_rejects_unattainable_energy_after_rehash(self):
        wave = parse_pcm16_wav(make_wav([1, 0]))
        envelope = multiresolution.build_multiresolution_percept(wave)
        self.assertTrue(multiresolution.verify_multiresolution_envelope(envelope))
        changed = copy.deepcopy(envelope)
        changed["percept"]["channels"][0]["long_spectral"]["events"][0][
            "windowed_energy"
        ] = "2"
        rehash(changed)
        self.assertFalse(multiresolution.verify_multiresolution_envelope(changed))

    def test_valid_one_and_two_sample_mono_sources_remain_valid(self):
        for samples in (
            [0], [1], [-32768], [0, 0], [1, 0], [0, 1],
            [1, -1], [-32768, 32767], [-32768, -32768],
        ):
            with self.subTest(samples=samples):
                wave = parse_pcm16_wav(make_wav(samples))
                envelope = multiresolution.build_multiresolution_percept(wave)
                self.assertTrue(multiresolution.verify_multiresolution_envelope(envelope))

    def test_long_tail_requires_one_or_two_sample_integer_energy(self):
        for frame_count in (513, 514):
            with self.subTest(frame_count=frame_count):
                samples = [0] * frame_count
                samples[512] = 1
                wave = parse_pcm16_wav(make_wav(samples))
                envelope = multiresolution.build_multiresolution_percept(wave)
                self.assertTrue(multiresolution.verify_multiresolution_envelope(envelope))
                changed = copy.deepcopy(envelope)
                events = changed["percept"]["channels"][0]["long_spectral"]["events"]
                self.assertEqual(events[-1]["windowed_energy"], "1")
                events[-1]["windowed_energy"] = "2"
                rehash(changed)
                self.assertFalse(multiresolution.verify_multiresolution_envelope(changed))

    def test_short_tail_rejects_impossible_candidate_energy(self):
        for frame_count in (129, 130):
            with self.subTest(frame_count=frame_count):
                wave = parse_pcm16_wav(make_wav([0] * frame_count))
                changed = multiresolution.build_multiresolution_percept(wave)
                transient = changed["percept"]["channels"][0]["transient"]
                transient.update({
                    "candidate_count": 1,
                    "positive_delta_sum": "2",
                    "maximum_positive_delta": "2",
                    "strongest_candidates": [{
                        "frame_index": 1,
                        "sample_start": 128,
                        "previous_energy": "0",
                        "current_energy": "2",
                        "positive_delta": "2",
                        "rise_ratio": None,
                    }],
                })
                rehash(changed)
                self.assertFalse(multiresolution.verify_multiresolution_envelope(changed))

    def test_valid_short_tails_at_pcm16_limits_remain_valid(self):
        for tail in ([-32768], [32767], [-32768, 32767], [1, -2]):
            with self.subTest(tail=tail):
                wave = parse_pcm16_wav(make_wav([0] * 128 + tail))
                envelope = multiresolution.build_multiresolution_percept(wave)
                self.assertTrue(multiresolution.verify_multiresolution_envelope(envelope))

    def test_two_sample_energy_check_matches_exhaustive_small_domain(self):
        attainable = {
            first * first + 4 * second * second
            for first in range(33) for second in range(17)
        }
        for energy in range(1025):
            with self.subTest(energy=energy):
                self.assertEqual(
                    _small_window_energy_is_realizable(energy, 2),
                    energy in attainable,
                )

    def test_energy_check_covers_zero_and_pcm16_boundaries(self):
        square_max = 32768 ** 2
        for energy, available, expected in (
            (0, 0, True), (1, 0, False), (-1, 1, False),
            (0, 1, True), (square_max, 1, True), (square_max + 1, 1, False),
            (2, 1, False), (0, 2, True), (2, 2, False), (12, 2, False),
            (5 * square_max, 2, True), (5 * square_max + 1, 2, False),
        ):
            with self.subTest(energy=energy, available=available):
                self.assertEqual(
                    _small_window_energy_is_realizable(energy, available), expected
                )


class WriterPCMCommitmentTests(unittest.TestCase):
    def test_stale_pcm_digest_is_rejected_before_any_output_or_rebuild(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4, 5, -6], channels=2))
        stale = replace(wave, pcm_s16le_sha256="0" * 64)
        envelope = multiresolution.build_multiresolution_percept(stale)
        self.assertTrue(multiresolution.verify_multiresolution_envelope(envelope))
        for initial in ("", "existing\n"):
            with self.subTest(initial=initial):
                stream = io.StringIO(initial)
                with mock.patch.object(
                    sidecar._mr, "build_multiresolution_percept",
                    side_effect=AssertionError("must validate PCM before rebuilding"),
                ):
                    with self.assertRaisesRegex(ValueError, "PCM commitment"):
                        sidecar.write_spectral_sidecar(stale, envelope, stream)
                self.assertEqual(stream.getvalue(), initial)
                self.assertEqual(stream.tell(), 0)

    def test_stale_sample_content_is_rejected(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4]))
        stale = replace(wave, samples_by_channel=((1, -2, 3, -5),))
        envelope = multiresolution.build_multiresolution_percept(stale)
        stream = io.StringIO()
        with self.assertRaisesRegex(ValueError, "PCM commitment"):
            sidecar.write_spectral_sidecar(stale, envelope, stream)
        self.assertEqual(stream.getvalue(), "")

    def test_invalid_direct_wave_shapes_and_samples_fail_before_output(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4]))
        envelope = multiresolution.build_multiresolution_percept(wave)
        invalid_fields = (
            {"channels": 2}, {"channels": True}, {"frame_count": 3},
            {"frame_count": 0}, {"sample_rate_hz": 0},
            {"samples_by_channel": ((1, -2, 3),)},
            {"samples_by_channel": ((True, -2, 3, -4),)},
            {"samples_by_channel": ((32768, -2, 3, -4),)},
            {"samples_by_channel": ((1.0, -2, 3, -4),)},
            {"samples_by_channel": [[1, -2, 3, -4]]},
            {"pcm_s16le_sha256": "not-a-digest"},
        )
        for fields in invalid_fields:
            with self.subTest(fields=fields):
                stream = io.StringIO()
                with self.assertRaises(ValueError):
                    sidecar.write_spectral_sidecar(replace(wave, **fields), envelope, stream)
                self.assertEqual(stream.getvalue(), "")

    def test_stale_hash_does_not_flush_or_write_binary_backed_destination(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3]))
        stale = replace(wave, pcm_s16le_sha256="f" * 64)
        envelope = multiresolution.build_multiresolution_percept(stale)
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="utf-8")
        try:
            stream.write("pending sentinel")
            self.assertEqual(raw.getvalue(), b"")
            with self.assertRaisesRegex(ValueError, "PCM commitment"):
                sidecar.write_spectral_sidecar(stale, envelope, stream)
            self.assertEqual(raw.getvalue(), b"")
            stream.flush()
            self.assertEqual(raw.getvalue(), b"pending sentinel")
        finally:
            stream.detach()

    def test_valid_direct_wave_preserves_exact_channel_interleaving(self):
        flat = [-32768, 1, 32767, 0, -2, 3, 4, -5, 6]
        payload = struct.pack("<9h", *flat)
        parsed = parse_pcm16_wav(make_wav(flat, channels=3))
        direct = PCM16Wave(
            source_sha256=parsed.source_sha256,
            pcm_s16le_sha256=hashlib.sha256(payload).hexdigest(),
            sample_rate_hz=48000, channels=3, frame_count=3,
            samples_by_channel=tuple(tuple(flat[c::3]) for c in range(3)),
        )
        envelope = multiresolution.build_multiresolution_percept(direct)
        stream = io.StringIO()
        receipt = sidecar.write_spectral_sidecar(direct, envelope, stream)
        self.assertIsNotNone(receipt)
        self.assertTrue(sidecar.verify_spectral_sidecar(envelope, io.StringIO(stream.getvalue())))

    def test_pcm_hash_matches_independent_payload_across_chunk_boundary(self):
        flat = [((index * 97) % 65536) - 32768 for index in range(5001)]
        wave = parse_pcm16_wav(make_wav(flat, channels=3))
        self.assertIsNone(_validate_wave_pcm_commitment(wave))
        with self.assertRaisesRegex(ValueError, "PCM commitment"):
            _validate_wave_pcm_commitment(replace(wave, pcm_s16le_sha256="0" * 64))


class NormativeLongFFTTests(unittest.TestCase):
    def test_published_algorithm_reproduces_complete_reference_rows(self):
        path = Path(__file__).resolve().parents[1] / "spec" / "QSOL-MAP-MULTIRES-v0.2.md"
        specification = path.read_text(encoding="utf-8")
        section = specification.split("## 4. Frozen long-window twiddles\n", 1)[1]
        table_text = section.split("```text\n", 1)[1].split("```", 1)[0]
        quarter = tuple(int(value.strip()) for value in table_text.split(",") if value.strip())
        self.assertEqual(quarter, TWIDDLE_COS_QUARTER_Q15_1024)
        code = specification.split("<!-- BEGIN NORMATIVE LONG FFT -->\n```python\n", 1)[1]
        code = code.split("\n```\n<!-- END NORMATIVE LONG FFT -->", 1)[0]
        namespace = {}
        exec(compile(code, str(path), "exec"), namespace)
        reference = namespace["long_fft_reference"]

        frames = [[0] * 1024]
        for position in (0, 1, 511, 512, 1023):
            frame = [0] * 1024
            frame[position] = -32768
            frames.append(frame)
        frames.append([((index * 137) % 65536) - 32768 for index in range(1024)])
        for index, frame in enumerate(frames):
            with self.subTest(frame=index):
                self.assertEqual(reference(frame, quarter), multiresolution._fixed_fft_long(frame))
        impulse = [1] + [0] * 1023
        self.assertEqual(reference(impulse, quarter), ((32768 ** 10, 0),) * 513)


if __name__ == "__main__":
    unittest.main()
