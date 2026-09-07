"""Regressions for transform divisibility and cross-evidence compact constraints."""

import copy
import struct
import unittest
from pathlib import Path

from qsol_map import multiresolution as mr
from qsol_map.canonical import canonical_bytes, domain_sha256
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
        mr.PERCEPT_DOMAIN,
        canonical_bytes(envelope["percept"]),
    )


class TransformAndCrossEvidenceTests(unittest.TestCase):
    def test_single_event_bin8_obeys_precomputed_transform_divisor(self):
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([0] * 100)))
        )
        percept = changed["percept"]
        spectral = percept["channels"][0]["long_spectral"]
        event = spectral["events"][0]

        # The frozen butterfly matrix guarantees at least 2^78 divisibility
        # for both coefficient components at bin 8.
        self.assertEqual(mr._LONG_BIN_REAL_DIVISORS[8] % (1 << 78), 0)
        self.assertEqual(mr._LONG_BIN_IMAG_DIVISORS[8] % (1 << 78), 0)

        spectral["aggregate_power_by_bin"] = ["0"] * (mr.LONG_FRAME_SIZE // 2 + 1)
        spectral["aggregate_power_by_bin"][8] = "1"
        spectral["aggregate_power_by_frequency_region"] = {
            "below_20khz_reference": "0",
            "20_to_40khz_reference": "0",
            "at_or_above_40khz_reference": "0",
        }
        region = mr._region_index(percept["source"]["sample_rate_hz"], 8)
        spectral["aggregate_power_by_frequency_region"][region] = "1"
        event["windowed_energy"] = "4"
        event["spectral_centroid_bin"] = {"numerator": "8", "denominator": "1"}
        event["dominant_non_dc_bin"] = 8
        event["top_components"] = [
            {"bin": 8, "real": "1", "imag": "0", "power": "1"},
            *[
                {"bin": bin_index, "real": "0", "imag": "0", "power": "0"}
                for bin_index in range(7)
            ],
        ]
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_omitted_candidate_uses_adjacent_reported_energy_lower_bound(self):
        samples = [1] + [0] * 2176
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        )
        transient = changed["percept"]["channels"][0]["transient"]
        energies = [0, 1, 2, 3, 5, 8, 12, 18, 27, 41, 62, 93, 140, 210, 315, 473, 710]
        candidates = []
        for frame in range(1, 17):
            previous = energies[frame - 1]
            current = energies[frame]
            delta = current - previous
            candidates.append(
                {
                    "frame_index": frame,
                    "sample_start": frame * mr.SHORT_HOP_SIZE,
                    "previous_energy": str(previous),
                    "current_energy": str(current),
                    "positive_delta": str(delta),
                    "rise_ratio": None
                    if previous == 0
                    else {"numerator": str(current), "denominator": str(previous)},
                }
            )
        candidates.sort(key=lambda item: (-int(item["positive_delta"]), item["frame_index"]))

        transient.update(
            {
                "candidate_count": 17,
                "positive_delta_sum": "711",
                "maximum_positive_delta": "237",
                "strongest_candidates": candidates,
            }
        )
        rehash(changed)

        # The omitted frame-17 candidate must start from the reported frame-16
        # energy 710. The 3/2 onset rule therefore requires delta >= 355, not 1.
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_zero_covering_long_energy_forces_zero_transient_summary(self):
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([0] * 384)))
        )
        channel = changed["percept"]["channels"][0]
        self.assertTrue(
            all(int(event["windowed_energy"]) == 0 for event in channel["long_spectral"]["events"])
        )
        channel["transient"].update(
            {
                "candidate_count": 1,
                "positive_delta_sum": "1",
                "maximum_positive_delta": "1",
                "strongest_candidates": [
                    {
                        "frame_index": 1,
                        "sample_start": mr.SHORT_HOP_SIZE,
                        "previous_energy": "0",
                        "current_energy": "1",
                        "positive_delta": "1",
                        "rise_ratio": None,
                    }
                ],
            }
        )
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_one_sample_relationship_dot_matches_signed_dc_samples(self):
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(
                parse_pcm16_wav(make_wav([1, 1], channels=2))
            )
        )
        relation = changed["percept"]["channel_relationships"][0]
        relation.update(
            {
                "dot_product": "-1",
                "dot_product_sign": -1,
                "difference_sum_squares": "4",
                "sum_sum_squares": "0",
                "zero_lag_correlation_squared": {
                    "numerator": "1",
                    "denominator": "1",
                },
            }
        )
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_required_protocol_docs_publish_per_bin_divisibility_rule(self):
        required = (
            "README.md",
            "README4AI.md",
            "ROADMAP.md",
            "docs/ARCHITECTURE.md",
            "docs/CLAIM_BOUNDARIES.md",
            "spec/QSOL-MAP-MULTIRES-v0.2.md",
        )
        marker = "per-bin coefficient divisors"
        for path in required:
            with self.subTest(path=path):
                self.assertIn(marker, Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
