"""Regressions for the latest PR #2 compact-verifier review findings."""

import copy
import unittest

from qsol_map import multiresolution as mr
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


class LatestCompactVerifierFixes(unittest.TestCase):
    def test_reported_endpoint_signs_obey_tail_window_congruence(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([-19, 0, -16, 0]))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        nyquist = next(
            component for component in event["top_components"] if component["bin"] == 512
        )
        scale = 32768 ** 10
        dc = next(
            component for component in event["top_components"] if component["bin"] == 0
        )
        self.assertEqual(int(dc["real"]) // scale, -67)
        self.assertEqual(int(nyquist["real"]) // scale, -67)

        # Powers remain unchanged, but D=-67 and N=67 imply D-N=-134.
        # With four available weights 1,2,3,4, D-N must be divisible by 4.
        nyquist["real"] = str(-int(nyquist["real"]))
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_unreported_positive_mass_can_realize_declared_maximum(self):
        samples = [0] * 256 + [1]
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        )
        transient = changed["percept"]["channels"][0]["transient"]
        candidates = transient["strongest_candidates"]
        self.assertEqual(transient["candidate_count"], 1)
        self.assertEqual(len(candidates), 1)
        reported = int(candidates[0]["positive_delta"])
        self.assertEqual(reported, 16384)

        # The only unreported transition has positive mass 2, so it cannot be
        # the declared maximum 16385 even though the coarse sum/max bounds hold.
        transient["positive_delta_sum"] = str(reported + 2)
        transient["maximum_positive_delta"] = str(reported + 1)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_omitted_bin_before_cutoff_uses_strict_tie_bound(self):
        samples = [1 if index % 2 == 0 else -1 for index in range(513)]
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        )
        percept = changed["percept"]
        spectral = percept["channels"][0]["long_spectral"]
        first, tail = spectral["events"]
        self.assertEqual(
            [component["bin"] for component in first["top_components"]],
            list(range(512, 504, -1)),
        )
        self.assertEqual(
            [component["bin"] for component in tail["top_components"]],
            list(range(8)),
        )

        weakest = int(first["top_components"][-1]["power"])
        tail_bin_zero = next(
            int(component["power"])
            for component in tail["top_components"]
            if component["bin"] == 0
        )
        aggregate = spectral["aggregate_power_by_bin"]
        original = int(aggregate[0])
        target = tail_bin_zero + weakest
        delta = target - original
        self.assertGreater(delta, 0)

        # Saturating the first event's cutoff at bin 0 would tie its selected
        # bin 505, but ascending-bin tie-breaking would have selected bin 0.
        aggregate[0] = str(target)
        region = mr._region_index(percept["source"]["sample_rate_hz"], 0)
        regions = spectral["aggregate_power_by_frequency_region"]
        regions[region] = str(int(regions[region]) + delta)
        centroid = first["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) + delta)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))


if __name__ == "__main__":
    unittest.main()
