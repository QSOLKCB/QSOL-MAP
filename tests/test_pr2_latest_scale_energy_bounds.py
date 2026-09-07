"""Regressions for the latest PR #2 scale/energy review findings."""

import copy
import unittest

from qsol_map import multiresolution as mr
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


class LatestScaleEnergyBoundsTests(unittest.TestCase):
    def test_single_event_bin_256_requires_frozen_q15_scale(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([1] + [0] * 99))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        percept = changed["percept"]
        spectral = percept["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        self.assertNotIn(256, [item["bin"] for item in event["top_components"]])

        aggregate = spectral["aggregate_power_by_bin"]
        original = int(aggregate[256])
        self.assertGreater(original, 1)
        delta = 1 - original
        aggregate[256] = "1"

        region = mr._region_index(percept["source"]["sample_rate_hz"], 256)
        regions = spectral["aggregate_power_by_frequency_region"]
        regions[region] = str(int(regions[region]) + delta)
        centroid = event["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) + delta)
        centroid["numerator"] = str(int(centroid["numerator"]) + 256 * delta)
        rehash(changed)

        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_overlap_remainder_two_is_not_realizable(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([0] * 512 + [1]))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        events = changed["percept"]["channels"][0]["long_spectral"]["events"]
        self.assertEqual([event["windowed_energy"] for event in events], ["262144", "1"])
        events[0]["windowed_energy"] = "262146"
        rehash(changed)

        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_long_event_energy_sum_covers_relationship_source_energy(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([0] * 8, channels=2))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        relation = changed["percept"]["channel_relationships"][0]
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
        for channel in changed["percept"]["channels"]:
            self.assertEqual(
                [event["windowed_energy"] for event in channel["long_spectral"]["events"]],
                ["0"],
            )
        rehash(changed)

        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_non_candidate_max_obeys_onset_threshold_energy_bounds(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([0] * 129))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        transient = changed["percept"]["channels"][0]["transient"]
        transient.update(
            {
                "candidate_count": 0,
                "positive_delta_sum": "500000000",
                "maximum_positive_delta": "500000000",
                "strongest_candidates": [],
            }
        )
        rehash(changed)

        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_single_event_endpoint_magnitude_obeys_cauchy_energy_bound(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([1, 0, 0, 0]))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        percept = changed["percept"]
        spectral = percept["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        self.assertEqual(event["windowed_energy"], "1")

        scale = 32768 ** 10
        original_power = scale * scale
        target_power = 9 * original_power
        delta = target_power - original_power
        aggregate = spectral["aggregate_power_by_bin"]
        self.assertEqual(int(aggregate[0]), original_power)
        self.assertEqual(int(aggregate[512]), original_power)
        aggregate[0] = str(target_power)
        aggregate[512] = str(target_power)

        regions = spectral["aggregate_power_by_frequency_region"]
        for bin_index in (0, 512):
            region = mr._region_index(percept["source"]["sample_rate_hz"], bin_index)
            regions[region] = str(int(regions[region]) + delta)

        centroid = event["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) + 2 * delta)
        centroid["numerator"] = str(int(centroid["numerator"]) + 512 * delta)

        original_by_bin = {item["bin"]: item for item in event["top_components"]}
        event["top_components"] = [
            {"bin": 0, "real": str(3 * scale), "imag": "0", "power": str(target_power)},
            {"bin": 512, "real": str(3 * scale), "imag": "0", "power": str(target_power)},
            *[copy.deepcopy(original_by_bin[index]) for index in range(1, 7)],
        ]
        event["dominant_non_dc_bin"] = 512
        rehash(changed)

        self.assertFalse(mr.verify_multiresolution_envelope(changed))


if __name__ == "__main__":
    unittest.main()
