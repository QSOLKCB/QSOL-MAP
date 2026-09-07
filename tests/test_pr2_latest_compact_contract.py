"""Regressions for the latest compact-verifier contract review."""

import copy
import unittest

from qsol_map import multiresolution as mr
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


class LatestCompactContractTests(unittest.TestCase):
    def test_two_sample_mono_energy_is_bound_to_endpoint_powers(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([1, 0]))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        changed = copy.deepcopy(envelope)
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        self.assertEqual(event["windowed_energy"], "1")
        event["windowed_energy"] = "4"
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_three_sample_mono_witness_preserves_reported_endpoint_signs(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([1, 0, 1]))
        )
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        changed = copy.deepcopy(envelope)
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        nyquist = next(
            component for component in event["top_components"] if component["bin"] == 512
        )
        self.assertNotEqual(nyquist["real"], "0")
        nyquist["real"] = str(-int(nyquist["real"]))
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_omitted_candidate_must_rank_below_reported_top16_cutoff(self):
        # E_i = 4^i makes all 17 transitions candidates with deltas
        # 3*4^(i-1). The authored top 16 are therefore frames 17..2.
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(
                parse_pcm16_wav(make_wav([0] * 2304))
            )
        )
        transient = changed["percept"]["channels"][0]["transient"]
        candidates = []
        previous = 1
        all_deltas = []
        for frame_index in range(1, 18):
            current = 4 ** frame_index
            delta = current - previous
            all_deltas.append(delta)
            candidates.append(
                {
                    "frame_index": frame_index,
                    "sample_start": frame_index * 128,
                    "previous_energy": str(previous),
                    "current_energy": str(current),
                    "positive_delta": str(delta),
                    "rise_ratio": {
                        "numerator": str(current),
                        "denominator": str(previous),
                    },
                }
            )
            previous = current

        transient["candidate_count"] = 17
        transient["positive_delta_sum"] = str(sum(all_deltas))
        transient["maximum_positive_delta"] = str(all_deltas[-1])
        transient["strongest_candidates"] = list(reversed(candidates[1:]))
        rehash(changed)
        self.assertTrue(mr.verify_multiresolution_envelope(changed))

        # Keep the exact summary but report frame 1 instead of stronger frame 2.
        transient["strongest_candidates"] = [
            *list(reversed(candidates[2:])),
            candidates[0],
        ]
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_each_event_centroid_has_an_omitted_power_upper_bound(self):
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(
                parse_pcm16_wav(make_wav([1] * 513))
            )
        )
        events = changed["percept"]["channels"][0]["long_spectral"]["events"]
        self.assertEqual(len(events), 2)
        first, tail = events

        def selected_totals(event):
            power = sum(int(component["power"]) for component in event["top_components"])
            weighted = sum(
                component["bin"] * int(component["power"])
                for component in event["top_components"]
            )
            return power, weighted

        tail_power, tail_weighted = selected_totals(tail)
        tail_centroid = tail["spectral_centroid_bin"]
        tail_denominator = int(tail_centroid["denominator"])
        tail_numerator = int(tail_centroid["numerator"])
        upper = tail_weighted + 512 * (tail_denominator - tail_power)
        self.assertLessEqual(tail_numerator, upper)
        shift = upper - tail_numerator + 1

        first_power, first_weighted = selected_totals(first)
        first_centroid = first["spectral_centroid_bin"]
        self.assertGreaterEqual(int(first_centroid["numerator"]) - shift, first_weighted)
        self.assertLessEqual(first_power, int(first_centroid["denominator"]))

        tail_centroid["numerator"] = str(tail_numerator + shift)
        first_centroid["numerator"] = str(int(first_centroid["numerator"]) - shift)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))


if __name__ == "__main__":
    unittest.main()
