"""Regressions for omitted powers, joint three-sample Gram data, and short writes."""

from collections import defaultdict
import copy
import io
from itertools import product
from math import isqrt
from types import SimpleNamespace
import unittest

from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.integer_checks import (
    _joint_vectors_match_gram,
    _sum_of_two_squares_residues_possible,
    _three_sample_vectors,
)
from qsol_map import multiresolution as mr
from qsol_map import sidecar
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav


def rehash(envelope):
    envelope["percept_sha256"] = domain_sha256(
        mr.PERCEPT_DOMAIN, canonical_bytes(envelope["percept"])
    )


def set_dot(relation, dot):
    left = int(relation["left_sum_squares"])
    right = int(relation["right_sum_squares"])
    relation["dot_product"] = str(dot)
    relation["dot_product_sign"] = (dot > 0) - (dot < 0)
    relation["difference_sum_squares"] = str(left + right - 2 * dot)
    relation["sum_sum_squares"] = str(left + right + 2 * dot)
    relation["zero_lag_correlation_squared"] = (
        {"numerator": str(dot * dot), "denominator": str(left * right)}
        if left and right else None
    )


class OmittedPowerTests(unittest.TestCase):
    def test_rehashed_single_event_rejects_impossible_omitted_interior_power(self):
        wave = parse_pcm16_wav(make_wav([((i * 37) % 2001) - 1000 for i in range(300)]))
        original = mr.build_multiresolution_percept(wave)
        self.assertTrue(mr.verify_multiresolution_envelope(original))
        for power in (3, 6, 12, 21, 33, 3 << 200):
            with self.subTest(power=power):
                changed = copy.deepcopy(original)
                spectral = changed["percept"]["channels"][0]["long_spectral"]
                event = spectral["events"][0]
                selected = {component["bin"] for component in event["top_components"]}
                bin_index = next(index for index in range(1, 512) if index not in selected)
                self.assertLess(power, int(event["top_components"][-1]["power"]))
                difference = power - int(spectral["aggregate_power_by_bin"][bin_index])
                spectral["aggregate_power_by_bin"][bin_index] = str(power)
                region = mr._region_index(wave.sample_rate_hz, bin_index)
                regions = spectral["aggregate_power_by_frequency_region"]
                regions[region] = str(int(regions[region]) + difference)
                centroid = event["spectral_centroid_bin"]
                centroid["denominator"] = str(int(centroid["denominator"]) + difference)
                centroid["numerator"] = str(int(centroid["numerator"]) + bin_index * difference)
                rehash(changed)
                self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_two_square_checks_match_small_exhaustive_reference(self):
        possible = {x * x + y * y for x in range(33) for y in range(33)}
        for power in range(1025):
            self.assertEqual(_sum_of_two_squares_residues_possible(power), power in possible, power)

    def test_two_square_checks_preserve_large_genuine_integer_powers(self):
        for x, y in product((0, 1, -7, (1 << 400) + 19), repeat=2):
            self.assertTrue(_sum_of_two_squares_residues_possible(x * x + y * y))
        self.assertFalse(_sum_of_two_squares_residues_possible(-1))
        self.assertFalse(_sum_of_two_squares_residues_possible(3 << 3000))
        self.assertFalse(_sum_of_two_squares_residues_possible(3 ** 101 * 7))

    def test_single_row_constraint_is_not_applied_to_multi_event_aggregates(self):
        # A multi-event aggregate is a sum of more than two integer squares.
        channel = {"long_spectral": {"events": [{}, {}], "aggregate_power_by_bin": ["3"]}}
        self.assertTrue(mr._one_long_event_matches_aggregate(channel))
        wave = parse_pcm16_wav(make_wav([((i * 29) % 503) - 251 for i in range(700)]))
        self.assertTrue(mr.verify_multiresolution_envelope(mr.build_multiresolution_percept(wave)))


class ThreeSampleGramTests(unittest.TestCase):
    def test_rehashed_orthogonal_energy_one_and_three_channels_are_rejected(self):
        wave = parse_pcm16_wav(make_wav([1, 1, 0, 1, 0, 1], channels=2))
        changed = mr.build_multiresolution_percept(wave)
        self.assertTrue(mr.verify_multiresolution_envelope(changed))
        set_dot(changed["percept"]["channel_relationships"][0], 0)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_pairwise_witnesses_do_not_replace_one_joint_assignment(self):
        # All channels have E=6, W=17 and vectors (+/-2, +/-1, +/-1).
        # Every pair below has a witness and the Gram determinant is 56 > 0,
        # but there is no one triple of vectors realizing all three pairs.
        gram = [[6, -4, -4], [-4, 6, 4], [-4, 4, 6]]
        candidates = _three_sample_vectors(6, 17)
        for left, right in ((0, 1), (0, 2), (1, 2)):
            self.assertTrue(any(
                sum(x * y for x, y in zip(a, b)) == gram[left][right]
                for a in candidates for b in candidates
            ))
        self.assertFalse(_joint_vectors_match_gram(gram, [candidates] * 3))
        wave = parse_pcm16_wav(make_wav([2, 2, 2, 1, 1, 1, 1, 1, 1], channels=3))
        changed = mr.build_multiresolution_percept(wave)
        for relation in changed["percept"]["channel_relationships"]:
            set_dot(relation, gram[relation["left_channel"]][relation["right_channel"]])
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_three_sample_assignment_binds_exact_long_energy(self):
        wave = parse_pcm16_wav(make_wav([1, 1, 0, 0, 0, 0], channels=2))
        changed = mr.build_multiresolution_percept(wave)
        for channel in changed["percept"]["channels"]:
            channel["long_spectral"]["events"][0]["windowed_energy"] = "2"
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_three_sample_vectors_match_exhaustive_energy_pairs(self):
        expected = defaultdict(set)
        for vector in product(range(-6, 7), repeat=3):
            energy = sum(sample * sample for sample in vector)
            if energy <= 36:
                weighted = sum((index + 1) ** 2 * sample * sample for index, sample in enumerate(vector))
                expected[energy, weighted].add(vector)
        for energy in range(37):
            for weighted in range(9 * energy + 1):
                actual = _three_sample_vectors(energy, weighted)
                self.assertEqual(set(actual), expected.get((energy, weighted), set()), (energy, weighted))
                self.assertEqual(len(actual), len(set(actual)))

    def test_three_sample_vectors_handle_pcm16_limits_and_impossible_bounds(self):
        for vector in ((-32768, 0, 32767), (-32768,) * 3, (32767,) * 3, (0, 0, 0)):
            energy = sum(sample * sample for sample in vector)
            weighted = sum((index + 1) ** 2 * sample * sample for index, sample in enumerate(vector))
            actual = _three_sample_vectors(energy, weighted)
            self.assertIn(vector, actual)
            self.assertTrue(all(-32768 <= sample <= 32767 for item in actual for sample in item))
        for energy, weighted in ((-1, 0), (1, 0), (1, 10), (3 * 32768 ** 2 + 1, 0), (1, 10 ** 100)):
            self.assertEqual(_three_sample_vectors(energy, weighted), [])

    def test_valid_three_sample_multichannel_sources_remain_valid(self):
        vectors = ((-32768, 0, 32767), (32767, 1, -32768), (0, 0, 0), (1, 2, 3),
                   (-1, -2, -3), (2, 1, 1), (1, 1, 1), (-32768, -32768, -32768))
        for count in (2, 3, 8):
            with self.subTest(channels=count):
                samples = [vectors[channel][frame] for frame in range(3) for channel in range(count)]
                wave = parse_pcm16_wav(make_wav(samples, channels=count))
                self.assertTrue(mr.verify_multiresolution_envelope(mr.build_multiresolution_percept(wave)))
        wave = parse_pcm16_wav(make_wav([0] * 9, channels=3))
        self.assertTrue(mr.verify_multiresolution_envelope(mr.build_multiresolution_percept(wave)))


class ShortWriteBuffer(io.BytesIO):
    def __init__(self, maximum):
        super().__init__()
        self.maximum = maximum
        self.calls = 0

    def write(self, payload):
        self.calls += 1
        return super().write(payload[:self.maximum])


class ShortWriteStringIO(io.StringIO):
    def write(self, text):
        return super().write(text[:1])


class ShortWriteTests(unittest.TestCase):
    def test_short_binary_writes_preserve_entire_sidecar_and_receipt(self):
        wave = parse_pcm16_wav(make_wav([0]))
        envelope = mr.build_multiresolution_percept(wave)
        reference = io.StringIO()
        expected_receipt = sidecar.write_spectral_sidecar(wave, envelope, reference)
        for maximum in (1, 7, 4096):
            with self.subTest(maximum=maximum):
                binary = ShortWriteBuffer(maximum)
                stream = SimpleNamespace(buffer=binary, flush=lambda: None)
                receipt = sidecar.write_spectral_sidecar(wave, envelope, stream)
                self.assertEqual(receipt, expected_receipt)
                self.assertEqual(binary.getvalue(), reference.getvalue().encode("utf-8"))
                self.assertTrue(sidecar.verify_spectral_sidecar(envelope, io.StringIO(binary.getvalue().decode("utf-8"))))
                self.assertGreater(binary.calls, 1)

    def test_short_string_writes_preserve_entire_sidecar_and_receipt(self):
        wave = parse_pcm16_wav(make_wav([0]))
        envelope = mr.build_multiresolution_percept(wave)
        stream = ShortWriteStringIO()
        reference = io.StringIO()
        expected = sidecar.write_spectral_sidecar(wave, envelope, reference)
        self.assertEqual(sidecar.write_spectral_sidecar(wave, envelope, stream), expected)
        self.assertEqual(stream.getvalue(), reference.getvalue())

    def test_utf8_short_writes_return_character_count_and_preserve_empty_write(self):
        binary = ShortWriteBuffer(1)
        sink = sidecar._ExactUTF8TextSink(SimpleNamespace(buffer=binary))
        self.assertEqual(sink.write("é\n"), 2)
        self.assertEqual(binary.getvalue(), "é\n".encode("utf-8"))
        self.assertEqual(binary.calls, 3)
        self.assertEqual(sink.write(""), 0)
        self.assertEqual(binary.calls, 3)

    def test_invalid_write_progress_cannot_return_a_receipt(self):
        wave = parse_pcm16_wav(make_wav([0]))
        envelope = mr.build_multiresolution_percept(wave)
        for result in (0, None, -1, True, 1.0, "oversized"):
            with self.subTest(result=result):
                class InvalidBuffer(ShortWriteBuffer):
                    def write(self, payload):
                        if not self.calls:
                            return super().write(payload)
                        self.calls += 1
                        return len(payload) + 1 if result == "oversized" else result
                binary = InvalidBuffer(1)
                with self.assertRaises(OSError):
                    sidecar.write_spectral_sidecar(wave, envelope, SimpleNamespace(buffer=binary))
                self.assertEqual(binary.calls, 2)
                self.assertEqual(len(binary.getvalue()), 1)

    def test_write_failure_after_partial_progress_is_propagated(self):
        class FailingBuffer(ShortWriteBuffer):
            def write(self, payload):
                if self.calls:
                    raise OSError("simulated destination failure")
                return super().write(payload)
        wave = parse_pcm16_wav(make_wav([0]))
        envelope = mr.build_multiresolution_percept(wave)
        binary = FailingBuffer(3)
        with self.assertRaisesRegex(OSError, "simulated destination failure"):
            sidecar.write_spectral_sidecar(wave, envelope, SimpleNamespace(buffer=binary))
        self.assertEqual(len(binary.getvalue()), 3)


if __name__ == "__main__":
    unittest.main()
