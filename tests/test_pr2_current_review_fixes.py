"""Regressions for the current PR #2 review findings."""

import copy
import io
import unittest

from qsol_map import multiresolution as mr
from qsol_map import sidecar
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


class CurrentCompactReviewFixes(unittest.TestCase):
    def test_single_event_endpoint_magnitudes_require_matching_parity(self):
        wave = parse_pcm16_wav(make_wav([1, 0, 0, 0]))
        changed = copy.deepcopy(mr.build_multiresolution_percept(wave))
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        scale = 32768 ** 10
        power = scale * scale

        self.assertEqual(int(spectral["aggregate_power_by_bin"][0]), power)
        self.assertEqual(int(spectral["aggregate_power_by_bin"][512]), power)

        # Keep a valid one-frame ranking and all aggregate identities while
        # making the scaled DC/Nyquist magnitudes 0 and 1 respectively.
        spectral["aggregate_power_by_bin"][0] = "0"
        region = mr._region_index(48000, 0)
        regions = spectral["aggregate_power_by_frequency_region"]
        regions[region] = str(int(regions[region]) - power)
        centroid = event["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) - power)
        event["top_components"] = [
            {
                "bin": bin_index,
                "real": str(scale),
                "imag": "0",
                "power": str(power),
            }
            for bin_index in range(1, 9)
        ]
        event["dominant_non_dc_bin"] = 1
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_single_sample_energy_matches_exact_endpoint_power(self):
        envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([1])))
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))

        changed = copy.deepcopy(envelope)
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        self.assertEqual(event["windowed_energy"], "1")
        event["windowed_energy"] = "4"
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

        for sample in (0, -1, 1, 32767, -32768):
            with self.subTest(sample=sample):
                valid = mr.build_multiresolution_percept(
                    parse_pcm16_wav(make_wav([sample]))
                )
                self.assertTrue(mr.verify_multiresolution_envelope(valid))

    def test_all_candidate_transitions_require_exact_positive_delta_sum(self):
        # The two impulses land at opposite ends of successive triangular
        # windows, producing two consecutive rises among exactly three short
        # frames. Both transitions therefore appear as authored candidates.
        samples = [0] * 384
        samples[255] = 1000
        samples[383] = 2000
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        )
        transient = changed["percept"]["channels"][0]["transient"]
        self.assertEqual(transient["candidate_count"], 2)
        self.assertEqual(len(transient["strongest_candidates"]), 2)
        reported_sum = sum(
            int(candidate["positive_delta"])
            for candidate in transient["strongest_candidates"]
        )
        self.assertEqual(int(transient["positive_delta_sum"]), reported_sum)

        transient["positive_delta_sum"] = str(reported_sum + 1)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_all_candidate_transitions_require_exact_maximum_positive_delta(self):
        samples = [0] * 384
        samples[255] = 1000
        samples[383] = 2000
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        )
        transient = changed["percept"]["channels"][0]["transient"]
        candidates = transient["strongest_candidates"]
        self.assertEqual(transient["candidate_count"], 2)
        self.assertEqual(len(candidates), 2)
        strongest = int(candidates[0]["positive_delta"])
        total = int(transient["positive_delta_sum"])
        self.assertEqual(int(transient["maximum_positive_delta"]), strongest)
        self.assertGreater(total, strongest)

        transient["maximum_positive_delta"] = str(total)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_aggregate_bin_is_capped_by_omitted_event_rankings(self):
        # One shared impulse appears in both long events. A one-sample row has
        # flat power across bins, so both events author bins 0..7 as their
        # deterministic top-K and every omitted bin starts at its exact cap.
        samples = [0] * 512 + [1]
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        )
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        self.assertEqual(len(spectral["events"]), 2)
        for event in spectral["events"]:
            self.assertEqual(
                [component["bin"] for component in event["top_components"]],
                list(range(8)),
            )

        aggregate = spectral["aggregate_power_by_bin"]
        aggregate[8] = str(int(aggregate[8]) - 1)
        aggregate[9] = str(int(aggregate[9]) + 2)
        aggregate[10] = str(int(aggregate[10]) - 1)
        # The three bins share a frequency region and the mutation preserves
        # both total power and weighted centroid: -8 + 18 - 10 == 0.
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))


class CurrentSidecarReviewFixes(unittest.TestCase):
    def test_nonseekable_binary_backed_text_stream_is_supported(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4] * 100))
        envelope = mr.build_multiresolution_percept(wave)
        destination = io.StringIO()
        sidecar.write_spectral_sidecar(wave, envelope, destination)
        payload = destination.getvalue().encode("utf-8")

        class NonSeekableBytes(io.BytesIO):
            def seekable(self):
                return False

            def seek(self, *args, **kwargs):
                raise OSError("non-seekable")

            def tell(self):
                raise OSError("non-seekable")

        binary = NonSeekableBytes(payload)
        stream = io.TextIOWrapper(binary, encoding="utf-8", newline=None)
        try:
            self.assertFalse(stream.seekable())
            self.assertTrue(sidecar.verify_spectral_sidecar(envelope, stream))
        finally:
            stream.detach()

    def test_translating_stringio_sidecar_destination_is_rejected_before_write(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4] * 100))
        envelope = mr.build_multiresolution_percept(wave)

        for newline in ("\r", "\r\n"):
            with self.subTest(newline=newline):
                destination = io.StringIO(newline=newline)
                with self.assertRaises(ValueError):
                    sidecar.write_spectral_sidecar(wave, envelope, destination)
                self.assertEqual(destination.getvalue(), "")

        for newline in (None, "", "\n"):
            with self.subTest(safe_newline=newline):
                destination = io.StringIO(newline=newline)
                sidecar.write_spectral_sidecar(wave, envelope, destination)
                text = destination.getvalue()
                self.assertNotIn("\r", text)
                self.assertTrue(text.endswith("\n"))
                self.assertTrue(
                    sidecar.verify_spectral_sidecar(envelope, io.StringIO(text))
                )


if __name__ == "__main__":
    unittest.main()
