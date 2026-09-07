import copy
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from qsol_map import __main__ as cli_module
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
)
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


class OverlapAndOutputRaceTests(unittest.TestCase):
    def test_single_event_energy_parity_matches_endpoint_magnitudes(self):
        wave = parse_pcm16_wav(make_wav([1, 0, 0, 0]))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        self.assertEqual(event["windowed_energy"], "1")
        event["windowed_energy"] = "4"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_one_sample_transient_tail_is_coupled_to_previous_overlap(self):
        wave = parse_pcm16_wav(make_wav([0] * 129))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        transient.update(
            {
                "candidate_count": 1,
                "positive_delta_sum": "1",
                "maximum_positive_delta": "1",
                "strongest_candidates": [
                    {
                        "frame_index": 1,
                        "sample_start": 128,
                        "previous_energy": "0",
                        "current_energy": "1",
                        "positive_delta": "1",
                        "rise_ratio": None,
                    }
                ],
            }
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_one_sample_long_tail_is_coupled_to_previous_overlap(self):
        wave = parse_pcm16_wav(make_wav([0] * 512 + [1]))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        events = changed["percept"]["channels"][0]["long_spectral"]["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["windowed_energy"], str(512 * 512))
        self.assertEqual(events[1]["windowed_energy"], "1")
        events[0]["windowed_energy"] = "131283"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_v02_output_path_swap_during_analysis_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.wav"
            output_path = root / "percept.json"
            sidecar_path = root / "spectral.ndjson"
            source_bytes = make_wav([index % 23 - 11 for index in range(600)])
            input_path.write_bytes(source_bytes)

            real_build = cli_module.build_multiresolution_percept

            def swap_reserved_output(wave):
                self.assertTrue(output_path.exists())
                output_path.unlink()
                os.symlink(input_path, output_path)
                return real_build(wave)

            with mock.patch.object(
                cli_module,
                "build_multiresolution_percept",
                side_effect=swap_reserved_output,
            ):
                result = cli_module.main(
                    [
                        "analyze-v0.2",
                        str(input_path),
                        "-o",
                        str(output_path),
                        "--sidecar",
                        str(sidecar_path),
                    ]
                )

            self.assertEqual(result, 2)
            self.assertEqual(input_path.read_bytes(), source_bytes)
            self.assertTrue(output_path.is_symlink())
            self.assertEqual(output_path.resolve(), input_path.resolve())
            self.assertEqual(sidecar_path.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
