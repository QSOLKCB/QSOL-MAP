import copy
import io
import struct
import tempfile
import unittest
from pathlib import Path

import qsol_map.__main__ as cli_module
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
)
from qsol_map.sidecar import write_spectral_sidecar
from qsol_map.wav import parse_pcm16_wav


def make_wav(samples, sample_rate=48000, channels=1):
    payload = struct.pack("<" + "h" * len(samples), *samples)
    block_align = channels * 2
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        16,
    )
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def rehash(envelope):
    envelope["percept_sha256"] = domain_sha256(
        PERCEPT_DOMAIN,
        canonical_bytes(envelope["percept"]),
    )


class LatestFeasibilityTests(unittest.TestCase):
    def test_case_insensitive_output_alias_is_rejected_before_writing(self):
        wav_bytes = make_wav([1, -1] * 200)
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.wav"
            output_path = Path(directory) / "Percept.json"
            sidecar_path = Path(directory) / "percept.json"
            input_path.write_bytes(wav_bytes)
            original_probe = cli_module._filesystem_case_insensitive
            cli_module._filesystem_case_insensitive = lambda directory: True
            try:
                with self.assertRaises(ValueError):
                    cli_module._analyze_v02(input_path, output_path, sidecar_path)
            finally:
                cli_module._filesystem_case_insensitive = original_probe
            self.assertFalse(output_path.exists())
            self.assertFalse(sidecar_path.exists())

    def test_sidecar_writer_rejects_rebound_matrix_commitment(self):
        wave = parse_pcm16_wav(make_wav([3, -2, 1, -4] * 200))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        changed["percept"]["short_reference"]["channels"][0][
            "complex_matrix_sha256"
        ] = "0" * 64
        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))
        stream = io.StringIO()
        with self.assertRaises(ValueError):
            write_spectral_sidecar(wave, changed, stream)
        self.assertEqual(stream.getvalue(), "")

    def test_channel_gram_rank_cannot_exceed_frame_count(self):
        wave = parse_pcm16_wav(make_wav([1, 1, 1], channels=3))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        for relation in changed["percept"]["channel_relationships"]:
            relation.update(
                {
                    "dot_product": "0",
                    "dot_product_sign": 0,
                    "left_sum_squares": "1",
                    "right_sum_squares": "1",
                    "difference_sum_squares": "2",
                    "sum_sum_squares": "2",
                    "zero_lag_correlation_squared": {
                        "numerator": "0",
                        "denominator": "1",
                    },
                }
            )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_single_short_frame_requires_zero_transient_totals(self):
        wave = parse_pcm16_wav(make_wav([7] * 64))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        self.assertEqual(transient["candidate_count"], 0)
        transient["positive_delta_sum"] = "1"
        transient["maximum_positive_delta"] = "1"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_transient_candidate_energies_obey_short_pcm_window_bounds(self):
        wave = parse_pcm16_wav(make_wav([0] * 128 + [12000] * 256))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        candidate = changed["percept"]["channels"][0]["transient"][
            "strongest_candidates"
        ][0]
        huge_previous = 10**50
        huge_current = 2 * huge_previous
        candidate["previous_energy"] = str(huge_previous)
        candidate["current_energy"] = str(huge_current)
        candidate["positive_delta"] = str(huge_previous)
        candidate["rise_ratio"] = {
            "numerator": str(huge_current),
            "denominator": str(huge_previous),
        }
        transient = changed["percept"]["channels"][0]["transient"]
        transient["positive_delta_sum"] = str(huge_previous)
        transient["maximum_positive_delta"] = str(huge_previous)
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))


if __name__ == "__main__":
    unittest.main()
