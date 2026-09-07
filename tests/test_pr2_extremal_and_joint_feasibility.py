"""Regressions for endpoint extremals, shared witnesses, and joint allocations."""

import copy
import unittest

from qsol_map import multiresolution as mr
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


class ExtremalEndpointTests(unittest.TestCase):
    def test_cauchy_equality_requires_weight_divisible_constant_vector(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([1, 0, 0, 0]))
        )
        channel = copy.deepcopy(envelope["percept"]["channels"][0])
        spectral = channel["long_spectral"]
        event = spectral["events"][0]
        scale = mr._LONG_FFT_ENDPOINT_SCALE

        event["windowed_energy"] = "4"
        spectral["aggregate_power_by_bin"][0] = str((4 * scale) ** 2)
        spectral["aggregate_power_by_bin"][mr.LONG_FRAME_SIZE // 2] = "0"
        event["top_components"] = [
            {
                "bin": 0,
                "real": str(4 * scale),
                "imag": "0",
                "power": str((4 * scale) ** 2),
            },
            *[
                {"bin": index, "real": "0", "imag": "0", "power": "0"}
                for index in range(1, mr.LONG_TOP_K)
            ],
        ]

        # Equality |D|^2 = A*W forces all four windowed samples to equal 1.
        # That cannot equal (x0, 2*x1, 3*x2, 4*x3) for integer PCM samples.
        self.assertFalse(
            mr._single_event_endpoint_energy_bounds_are_valid(channel, 4)
        )

    def test_two_sample_endpoint_signs_use_same_pcm16_witness(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([0, 0]))
        )
        percept = copy.deepcopy(envelope["percept"])
        spectral = percept["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        scale = mr._LONG_FFT_ENDPOINT_SCALE
        endpoint_power = (40000 * scale) ** 2

        event["windowed_energy"] = "1600000000"
        spectral["aggregate_power_by_bin"][0] = str(endpoint_power)
        spectral["aggregate_power_by_bin"][mr.LONG_FRAME_SIZE // 2] = str(endpoint_power)
        event["top_components"] = [
            {
                "bin": 0,
                "real": str(40000 * scale),
                "imag": "0",
                "power": str(endpoint_power),
            },
            {
                "bin": mr.LONG_FRAME_SIZE // 2,
                "real": str(40000 * scale),
                "imag": "0",
                "power": str(endpoint_power),
            },
            *[
                {"bin": index, "real": "0", "imag": "0", "power": "0"}
                for index in range(1, 7)
            ],
        ]

        # Signed D=N=40000 implies x=40000,y=0, outside signed PCM16.
        self.assertFalse(mr._two_sample_endpoint_witnesses_are_valid(percept))


class TransformDivisibilityTests(unittest.TestCase):
    def test_multi_event_components_and_aggregates_keep_bin_divisors(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([0] * 513))
        )
        channel = copy.deepcopy(envelope["percept"]["channels"][0])
        spectral = channel["long_spectral"]
        self.assertEqual(len(spectral["events"]), 2)

        spectral["events"][0]["top_components"][0] = {
            "bin": 0,
            "real": "1",
            "imag": "0",
            "power": "1",
        }
        spectral["aggregate_power_by_bin"][0] = "1"
        self.assertFalse(mr._transform_divisibility_is_valid(channel))


class JointResidualAllocationTests(unittest.TestCase):
    def test_aggregate_residuals_require_one_event_bin_allocation(self):
        scale = mr._LONG_FFT_ENDPOINT_SCALE
        g = scale * scale
        q = 100 * g
        aggregate = [0] * (mr.LONG_FRAME_SIZE // 2 + 1)

        def event(selected_bins, residual):
            components = [
                {"bin": bin_index, "real": "0", "imag": "0", "power": str(q)}
                for bin_index in selected_bins
            ]
            for bin_index in selected_bins:
                aggregate[bin_index] += q
            return {
                "sample_start": 0,
                "windowed_energy": "1",
                "spectral_centroid_bin": {
                    "numerator": "0",
                    "denominator": str(len(selected_bins) * q + residual),
                },
                "dominant_non_dc_bin": 1,
                "top_components": components,
            }

        event0 = event(range(0, 8), 9 * g)
        event1 = event(range(8, 16), 1 * g)
        # Residual at bin 0 cannot come from event 0 because it selects bin 0
        # exactly. Event 1 therefore must supply all 5G, but it owns only G of
        # row residual. The symmetric bin-8 residual does not repair that.
        aggregate[0] += 5 * g
        aggregate[8] += 5 * g
        channel = {
            "long_spectral": {
                "events": [event0, event1],
                "aggregate_power_by_bin": [str(value) for value in aggregate],
            }
        }
        self.assertFalse(mr._aggregate_residual_allocation_is_feasible(channel))


class TransientMassCapacityTests(unittest.TestCase):
    def test_total_noncandidate_mass_cannot_exceed_transition_caps(self):
        envelope = mr.build_multiresolution_percept(
            parse_pcm16_wav(make_wav([1] + [0] * 256))
        )
        changed = copy.deepcopy(envelope)
        transient = changed["percept"]["channels"][0]["transient"]
        transient.update(
            {
                "candidate_count": 0,
                "strongest_candidates": [],
                "maximum_positive_delta": "259003707817983",
                "positive_delta_sum": "259004065731925",
            }
        )
        rehash(changed)

        # The two authored non-candidate caps sum to one less than the forged
        # positive total, so no classification-compatible transition set exists.
        self.assertFalse(
            mr._transient_unreported_mass_is_feasible(changed["percept"])
        )
        self.assertFalse(mr.verify_multiresolution_envelope(changed))


if __name__ == "__main__":
    unittest.main()
