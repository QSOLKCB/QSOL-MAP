"""Regressions for mono three-sample weighted energy without Gram records."""

from collections import defaultdict
import copy
import io
from itertools import product
from math import isqrt
import unittest

from qsol_map import multiresolution as mr
from qsol_map import sidecar
from qsol_map.mono_constraints import _three_sample_window_vectors
from qsol_map.wav import parse_pcm16_wav
from test_pr2_integer_and_write_checks import rehash
from test_pr2_live_review_fixes import make_wav


class MonoThreeSampleTests(unittest.TestCase):
    def test_rehashed_mono_energy_two_is_rejected(self):
        wave = parse_pcm16_wav(make_wav([1, 0, 0]))
        original = mr.build_multiresolution_percept(wave)
        self.assertTrue(mr.verify_multiresolution_envelope(original))
        self.assertEqual(original["percept"]["channel_relationships"], [])
        for energy in (2, 3, 6, 7):
            with self.subTest(energy=energy):
                changed = copy.deepcopy(original)
                changed["percept"]["channels"][0]["long_spectral"]["events"][0]["windowed_energy"] = str(energy)
                rehash(changed)
                self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_weighted_energy_must_share_its_endpoint_evidence(self):
        wave = parse_pcm16_wav(make_wav([1, 0, 0]))
        changed = mr.build_multiresolution_percept(wave)
        # Four is realizable in isolation, but not with this frame's endpoints.
        changed["percept"]["channels"][0]["long_spectral"]["events"][0]["windowed_energy"] = "4"
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_omitted_endpoint_requires_exact_fft_scale(self):
        wave = parse_pcm16_wav(make_wav([1, 0, 0]))
        changed = mr.build_multiresolution_percept(wave)
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        endpoint = 512
        self.assertNotIn(endpoint, {item["bin"] for item in event["top_components"]})
        old_power = int(spectral["aggregate_power_by_bin"][endpoint])
        new_power = (isqrt(old_power) - 1) ** 2
        difference = new_power - old_power
        spectral["aggregate_power_by_bin"][endpoint] = str(new_power)
        region = mr._region_index(wave.sample_rate_hz, endpoint)
        regions = spectral["aggregate_power_by_frequency_region"]
        regions[region] = str(int(regions[region]) + difference)
        centroid = event["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) + difference)
        centroid["numerator"] = str(int(centroid["numerator"]) + endpoint * difference)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_solver_matches_exhaustive_small_energy_and_endpoint_domain(self):
        expected = defaultdict(set)
        for x, y, z in product(range(-8, 9), repeat=3):
            energy = x * x + 4 * y * y + 9 * z * z
            if energy <= 64:
                expected[energy, abs(x + 2 * y + 3 * z), abs(x - 2 * y + 3 * z)].add((x, y, z))
        # Every endpoint magnitude for energy <= 64 is <= sqrt(3*64) < 14.
        for key in product(range(65), range(15), range(15)):
            actual = _three_sample_window_vectors(*key)
            self.assertEqual(set(actual), expected.get(key, set()), key)
            self.assertEqual(len(actual), len(set(actual)))
            self.assertLessEqual(len(actual), 8)

    def test_solver_preserves_pcm16_limits_and_rejects_invalid_bounds(self):
        for x, y, z in product((-32768, 0, 32767), repeat=3):
            energy = x * x + 4 * y * y + 9 * z * z
            dc, nyquist = abs(x + 2 * y + 3 * z), abs(x - 2 * y + 3 * z)
            actual = _three_sample_window_vectors(energy, dc, nyquist)
            self.assertIn((x, y, z), actual)
            self.assertLessEqual(len(actual), 8)
            for a, b, c in actual:
                self.assertTrue(all(-32768 <= sample <= 32767 for sample in (a, b, c)))
                self.assertEqual(a * a + 4 * b * b + 9 * c * c, energy)
                self.assertEqual(abs(a + 2 * b + 3 * c), dc)
                self.assertEqual(abs(a - 2 * b + 3 * c), nyquist)
        for key in ((-1, 0, 0), (14 * 32768 ** 2 + 1, 0, 0),
                    (0, -1, 0), (0, 0, -1), (0, 6 * 32768 + 1, 0),
                    (0, 0, 6 * 32768 + 1), (2, 1, 1), (1, 1, 0)):
            self.assertEqual(_three_sample_window_vectors(*key), [], key)

    def test_valid_mono_triples_and_exact_endpoint_scaling(self):
        vectors = list(product((-1, 0, 1), repeat=3))
        vectors.extend(product((-32768, 0, 32767), repeat=3))
        vectors.extend(((1, 2, 3), (-7, 11, -13), (300, -500, 700)))
        scale = 32768 ** 10
        for x, y, z in vectors:
            with self.subTest(samples=(x, y, z)):
                wave = parse_pcm16_wav(make_wav([x, y, z]))
                envelope = mr.build_multiresolution_percept(wave)
                spectral = envelope["percept"]["channels"][0]["long_spectral"]
                self.assertEqual(int(spectral["aggregate_power_by_bin"][0]), ((x + 2 * y + 3 * z) * scale) ** 2)
                self.assertEqual(int(spectral["aggregate_power_by_bin"][512]), ((x - 2 * y + 3 * z) * scale) ** 2)
                self.assertTrue(mr.verify_multiresolution_envelope(envelope))

    def test_valid_mono_sidecar_round_trip(self):
        wave = parse_pcm16_wav(make_wav([-32768, 1, 32767]))
        envelope = mr.build_multiresolution_percept(wave)
        stream = io.StringIO()
        receipt = sidecar.write_spectral_sidecar(wave, envelope, stream)
        self.assertTrue(receipt)
        self.assertTrue(sidecar.verify_spectral_sidecar(envelope, io.StringIO(stream.getvalue())))

    def test_other_source_lengths_remain_accepted(self):
        for samples in ([1], [1, -2], [1, -2, 3, -4], [0] * 512 + [1, -2, 3]):
            with self.subTest(frame_count=len(samples)):
                wave = parse_pcm16_wav(make_wav(samples))
                self.assertTrue(mr.verify_multiresolution_envelope(mr.build_multiresolution_percept(wave)))


if __name__ == "__main__":
    unittest.main()
