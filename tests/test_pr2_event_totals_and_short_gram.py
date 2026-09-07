"""Public-verifier regressions for event totals and shared short PCM evidence."""

import copy
import unittest

from qsol_map import multiresolution as mr
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


def envelope_for(*channels):
    interleaved = [value for frame in zip(*channels) for value in frame]
    wave = parse_pcm16_wav(make_wav(interleaved, channels=len(channels)))
    return mr.build_multiresolution_percept(wave)


def set_dot(relation, dot):
    left = int(relation["left_sum_squares"])
    right = int(relation["right_sum_squares"])
    relation.update(
        dot_product=str(dot),
        dot_product_sign=(dot > 0) - (dot < 0),
        difference_sum_squares=str(left + right - 2 * dot),
        sum_sum_squares=str(left + right + 2 * dot),
        zero_lag_correlation_squared=(
            {"numerator": str(dot * dot), "denominator": str(left * right)}
            if left and right else None
        ),
    )


class EventTotalsAndShortGramTests(unittest.TestCase):
    def test_rehashed_event_total_transfer_requires_transform_divisibility(self):
        envelope = envelope_for([1] * 513)
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                changed = copy.deepcopy(envelope)
                first, second = changed["percept"]["channels"][0]["long_spectral"]["events"]
                first["spectral_centroid_bin"]["denominator"] = str(
                    int(first["spectral_centroid_bin"]["denominator"]) + direction
                )
                second["spectral_centroid_bin"]["denominator"] = str(
                    int(second["spectral_centroid_bin"]["denominator"]) - direction
                )
                rehash(changed)
                self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_four_frame_gram_cannot_claim_orthogonal_norms_one_and_seven(self):
        envelope = envelope_for([1, 0, 0, 0], [2, 1, 1, 1])
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        changed = copy.deepcopy(envelope)
        set_dot(changed["percept"]["channel_relationships"][0], 0)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_three_frame_gram_witness_preserves_reported_dc_sign(self):
        envelope = envelope_for([1, 2, 3], [1, 2, 3])
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        changed = copy.deepcopy(envelope)
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        dc = next(item for item in event["top_components"] if item["bin"] == 0)
        dc["real"] = str(-int(dc["real"]))
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))


if __name__ == "__main__":
    unittest.main()
