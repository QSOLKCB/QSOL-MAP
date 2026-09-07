"""Independent conformance checks for row divisors and short signed witnesses."""

import copy
import io
import itertools
from pathlib import Path
import unittest

from qsol_map import multiresolution as mr
from qsol_map.short_source_witnesses import short_source_vectors, vectors_have_joint_gram
from qsol_map.sidecar import write_spectral_sidecar, verify_spectral_sidecar
from qsol_map.wav import parse_pcm16_wav
from test_pr2_event_totals_and_short_gram import envelope_for
from test_pr2_live_review_fixes import make_wav, rehash


def observations(vector):
    windowed = [(index + 1) * value for index, value in enumerate(vector)]
    return (
        sum(value * value for value in vector),
        sum(value * value for value in windowed),
        sum(windowed),
        sum(value if index % 2 == 0 else -value for index, value in enumerate(windowed)),
    )


class ExactSignedWitnessTests(unittest.TestCase):
    def test_exhaustive_small_signed_energy_endpoint_domain(self):
        for count in (3, 4):
            reference = {}
            for vector in itertools.product(range(-3, 4), repeat=count):
                key = observations(vector)
                if key[0] <= 9:
                    reference.setdefault(key, set()).add(vector)
            for (energy, windowed, dc, nyquist), expected in reference.items():
                self.assertEqual(
                    set(short_source_vectors(count, energy, windowed, (dc,), (nyquist,))),
                    expected,
                )
                # Keep E <= 9, so the cube above also contains every possible
                # witness for these independently perturbed observations.
                for delta in (-1, 1):
                    self.assertEqual(
                        set(short_source_vectors(count, energy, windowed + delta, (dc,), (nyquist,))),
                        reference.get((energy, windowed + delta, dc, nyquist), set()),
                    )

    def test_omitted_endpoints_allow_only_their_observed_magnitudes(self):
        for vector in ((1, 2, 3), (1, 2, 3, 4), (0, 0, 0, 0)):
            energy, windowed, dc, nyquist = observations(vector)
            all_signs = short_source_vectors(
                len(vector), energy, windowed, tuple(sorted({dc, -dc})),
                tuple(sorted({nyquist, -nyquist})),
            )
            self.assertIn(vector, all_signs)
            self.assertIn(tuple(-value for value in vector), all_signs)
            for witness in all_signs:
                e, w, d, n = observations(witness)
                self.assertEqual((e, w, abs(d), abs(n)), (energy, windowed, abs(dc), abs(nyquist)))

    def test_pcm16_asymmetric_limits_and_zero(self):
        for count in (3, 4):
            for vector in ((0,) * count, (-32768,) * count, (32767,) * count,
                           tuple((-32768, 32767, 0, 1)[:count])):
                e, w, d, n = observations(vector)
                self.assertIn(vector, short_source_vectors(count, e, w, (d,), (n,)))
            impossible = (32768,) + (0,) * (count - 1)
            e, w, d, n = observations(impossible)
            self.assertEqual(short_source_vectors(count, e, w, (d,), (n,)), [])
        self.assertEqual(short_source_vectors(4, -1, 0, (0,), (0,)), [])
        self.assertEqual(short_source_vectors(4, 1, -1, (0,), (0,)), [])
        self.assertEqual(short_source_vectors(4, 1, 1, (1,), (0,)), [])

    def test_joint_assignment_does_not_replace_signed_candidates(self):
        self.assertTrue(vectors_have_joint_gram([[(1, 0, 0)], [(1, 0, 0)]], [[1, 1], [1, 1]]))
        self.assertFalse(vectors_have_joint_gram([[(-1, 0, 0)], [(1, 0, 0)]], [[1, 1], [1, 1]]))
        # Every pair has a separate witness in this set, but three mutually
        # orthogonal unit vectors cannot all come from its two coordinate axes.
        choices = [(1, 0, 0, 0), (0, 1, 0, 0)]
        self.assertFalse(vectors_have_joint_gram([choices] * 3, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]))

    def test_valid_multichannel_three_and_four_frame_sources(self):
        for count in (3, 4):
            channels = [tuple(values[:count]) for values in (
                (1, 2, 3, 4), (-1, -2, -3, -4), (0, 0, 0, 0),
                (-32768, 0, 0, 0), (32767, 0, 1, -1), (4, 3, 2, 1),
                (0, 1, 0, 1), (0, -1, 0, -1),
            )]
            envelope = envelope_for(*channels)
            self.assertTrue(mr.verify_multiresolution_envelope(envelope))
            self.assertTrue(mr._short_multichannel_endpoint_witnesses_are_valid(envelope["percept"]))

    def test_three_and_four_frame_signed_nyquist_and_dc_tampering(self):
        for vector, endpoint in (((-1, 2, -3), 512), ((1, 2, 3, 4), 0)):
            envelope = envelope_for(vector, vector)
            self.assertTrue(mr.verify_multiresolution_envelope(envelope))
            changed = copy.deepcopy(envelope)
            event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
            component = next(item for item in event["top_components"] if item["bin"] == endpoint)
            component["real"] = str(-int(component["real"]))
            rehash(changed)
            self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_valid_four_frame_sidecar_round_trip(self):
        channels = ([1, 0, 0, 0], [2, 1, 1, 1])
        samples = [value for frame in zip(*channels) for value in frame]
        wave = parse_pcm16_wav(make_wav(samples, channels=2))
        envelope = mr.build_multiresolution_percept(wave)
        stream = io.StringIO()
        write_spectral_sidecar(wave, envelope, stream)
        stream.seek(0)
        self.assertTrue(verify_spectral_sidecar(envelope, stream))


class DivisorScopeTests(unittest.TestCase):
    def test_event_denominator_and_numerator_divisors_come_from_bins(self):
        from math import gcd
        divisors = tuple(gcd(r*r, i*i) for r, i in zip(mr._LONG_BIN_REAL_DIVISORS, mr._LONG_BIN_IMAG_DIVISORS))
        self.assertEqual(mr._LONG_BIN_POWER_DIVISORS, divisors)
        self.assertEqual(mr._LONG_POWER_TOTAL_DIVISOR, gcd(*divisors))
        self.assertEqual(mr._LONG_POWER_TOTAL_DIVISOR, 2**64)
        self.assertEqual(mr._LONG_POWER_MOMENT_DIVISOR, gcd(*(k*d for k, d in enumerate(divisors))))
        for length in (4, 513, 1025):
            envelope = envelope_for([1] * length)
            channel = envelope["percept"]["channels"][0]
            self.assertTrue(mr._transform_divisibility_is_valid(channel))
            self.assertTrue(mr.verify_multiresolution_envelope(envelope))

    def test_aggregate_preserving_event_numerator_transfer_is_rejected(self):
        changed = envelope_for([1] * 513)
        first, second = changed["percept"]["channels"][0]["long_spectral"]["events"]
        first["spectral_centroid_bin"]["numerator"] = str(int(first["spectral_centroid_bin"]["numerator"]) + 1)
        second["spectral_centroid_bin"]["numerator"] = str(int(second["spectral_centroid_bin"]["numerator"]) - 1)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_required_docs_state_multi_event_and_short_signed_witness_scope(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("README.md", "README4AI.md", "ROADMAP.md", "docs/ARCHITECTURE.md",
                     "docs/CLAIM_BOUNDARIES.md", "spec/QSOL-MAP-MULTIRES-v0.2.md"):
            text = (root / name).read_text(encoding="utf-8")
            with self.subTest(document=name):
                for marker in ("per-bin coefficient divisors", "multi-event", "2^64", "four-frame", "8.2"):
                    self.assertIn(marker, text)
                for obsolete in (
                    "It applies only to a single-event row, not to aggregates summed across multiple events",
                    "These single-row divisors are not imposed on sums across multiple long events",
                    "do not impose single-row divisibility on multi-event sums",
                ):
                    self.assertNotIn(obsolete, text)


if __name__ == "__main__":
    unittest.main()
