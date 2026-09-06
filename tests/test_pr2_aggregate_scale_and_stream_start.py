"""Compact evidence completeness and whole-stream sidecar regressions."""

import copy
import io
from math import isqrt
import tempfile
import unittest

from qsol_map import multiresolution as mr
from qsol_map import sidecar
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


def change_aggregate(spectral, bin_index, new_power, event_index=0):
    """Rebind totals so rejection cannot rely on a stale digest or subtotal."""
    old_power = int(spectral["aggregate_power_by_bin"][bin_index])
    delta = new_power - old_power
    spectral["aggregate_power_by_bin"][bin_index] = str(new_power)
    region = mr._region_index(48000, bin_index)
    regions = spectral["aggregate_power_by_frequency_region"]
    regions[region] = str(int(regions[region]) + delta)
    centroid = spectral["events"][event_index]["spectral_centroid_bin"]
    centroid["denominator"] = str(int(centroid["denominator"]) + delta)
    centroid["numerator"] = str(int(centroid["numerator"]) + bin_index * delta)


class AggregateCompletenessTests(unittest.TestCase):
    def test_fully_selected_bin_requires_exact_aggregate_after_rehash(self):
        envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([1] * 513)))
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        spectral = envelope["percept"]["channels"][0]["long_spectral"]
        self.assertEqual(len(spectral["events"]), 2)
        selected = [
            {component["bin"]: int(component["power"]) for component in event["top_components"]}
            for event in spectral["events"]
        ]
        self.assertTrue(all(0 in row for row in selected))
        for bin_index in sorted(set(selected[0]) & set(selected[1])):
            with self.subTest(bin_index=bin_index):
                total = sum(row[bin_index] for row in selected)
                self.assertEqual(total, int(spectral["aggregate_power_by_bin"][bin_index]))
                changed = copy.deepcopy(envelope)
                change_aggregate(changed["percept"]["channels"][0]["long_spectral"], bin_index, total + 1)
                rehash(changed)
                self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_partially_selected_bins_keep_valid_unreported_contributions(self):
        samples = [1 if index % 2 == 0 else -1 for index in range(513)]
        envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
        spectral = envelope["percept"]["channels"][0]["long_spectral"]
        rows = [
            {component["bin"]: int(component["power"]) for component in event["top_components"]}
            for event in spectral["events"]
        ]
        self.assertTrue(any(
            sum(bin_index in row for row in rows) == 1
            and sum(row.get(bin_index, 0) for row in rows) < int(power)
            for bin_index, power in enumerate(spectral["aggregate_power_by_bin"])
        ))
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))


class EndpointScaleTests(unittest.TestCase):
    def test_selected_unit_endpoint_is_rejected_for_four_sample_mono(self):
        for endpoint in (0, 512):
            with self.subTest(endpoint=endpoint):
                envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([1, 0, 0, 0])))
                spectral = envelope["percept"]["channels"][0]["long_spectral"]
                powers = [0] * 513
                powers[endpoint] = 1
                spectral["aggregate_power_by_bin"] = [str(power) for power in powers]
                spectral["aggregate_power_by_frequency_region"] = {
                    "below_20khz_reference": 0,
                    "20_to_40khz_reference": 0,
                    "at_or_above_40khz_reference": 0,
                }
                region = mr._region_index(48000, endpoint)
                spectral["aggregate_power_by_frequency_region"][region] = 1
                spectral["aggregate_power_by_frequency_region"] = {
                    name: str(value) for name, value in spectral["aggregate_power_by_frequency_region"].items()
                }
                event = spectral["events"][0]
                event["spectral_centroid_bin"] = {"numerator": str(endpoint), "denominator": "1"}
                event["dominant_non_dc_bin"] = endpoint or 1
                ranked = sorted(range(513), key=lambda index: (-powers[index], index))[:8]
                event["top_components"] = [
                    {"bin": index, "real": str(powers[index]), "imag": "0", "power": str(powers[index])}
                    for index in ranked
                ]
                rehash(envelope)
                self.assertFalse(mr.verify_multiresolution_envelope(envelope))

    def test_omitted_endpoint_square_requires_frozen_scale(self):
        for samples, endpoint in (([1, 0, 0, 0], 512), ([1, -1, 1, -1], 0)):
            with self.subTest(endpoint=endpoint):
                envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples)))
                self.assertTrue(mr.verify_multiresolution_envelope(envelope))
                spectral = envelope["percept"]["channels"][0]["long_spectral"]
                self.assertNotIn(endpoint, {component["bin"] for component in spectral["events"][0]["top_components"]})
                magnitude = isqrt(int(spectral["aggregate_power_by_bin"][endpoint]))
                self.assertGreater(magnitude, 0)
                self.assertEqual(magnitude % (32768 ** 10), 0)
                change_aggregate(spectral, endpoint, (magnitude - 1) ** 2)
                rehash(envelope)
                self.assertFalse(mr.verify_multiresolution_envelope(envelope))

    def test_valid_single_event_endpoints_across_lengths_and_channels(self):
        for frame_count in (1, 2, 3, 4, 128, 512):
            for channels in (1, 2):
                with self.subTest(frame_count=frame_count, channels=channels):
                    samples = [(-32768 if channel == 0 else 32767) if frame == 0 else 0
                               for frame in range(frame_count) for channel in range(channels)]
                    envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav(samples, channels=channels)))
                    self.assertTrue(mr.verify_multiresolution_envelope(envelope))
        silent = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([0] * 4)))
        self.assertTrue(mr.verify_multiresolution_envelope(silent))

    def test_multi_event_endpoint_aggregate_need_not_be_square(self):
        envelope = mr.build_multiresolution_percept(parse_pcm16_wav(make_wav([1] + [0] * 511 + [2])))
        spectral = envelope["percept"]["channels"][0]["long_spectral"]
        power = int(spectral["aggregate_power_by_bin"][0])
        self.assertNotEqual(isqrt(power) ** 2, power)
        self.assertTrue(mr.verify_multiresolution_envelope(envelope))


class WholeStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wave = parse_pcm16_wav(make_wav([1, 0, 0, 0]))
        cls.envelope = mr.build_multiresolution_percept(wave)
        destination = io.StringIO()
        sidecar.write_spectral_sidecar(wave, cls.envelope, destination)
        cls.text = destination.getvalue()

    def test_stringio_cannot_skip_a_prefix(self):
        stream = io.StringIO("junk\n" + self.text)
        stream.readline()
        position = stream.tell()
        self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, stream))
        self.assertEqual(stream.tell(), position)

    def test_regular_text_file_cannot_skip_a_prefix(self):
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", newline="") as stream:
            stream.write("junk\n" + self.text)
            stream.seek(0)
            stream.readline()
            position = stream.tell()
            self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, stream))
            self.assertEqual(stream.tell(), position)

    def test_text_wrapper_read_ahead_does_not_hide_prefix(self):
        with io.TextIOWrapper(io.BytesIO(("junk\n" + self.text).encode("utf-8")), encoding="utf-8", newline=None) as stream:
            stream.readline()
            position = stream.tell()
            self.assertGreater(position, 0)
            self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, stream))
            self.assertEqual(stream.tell(), position)

    def test_zero_position_and_explicit_record_iterables_remain_supported(self):
        self.assertTrue(sidecar.verify_spectral_sidecar(self.envelope, io.StringIO(self.text)))
        self.assertTrue(sidecar.verify_spectral_sidecar(self.envelope, iter(self.text.splitlines(keepends=True))))
        with io.TextIOWrapper(io.BytesIO(self.text.encode("utf-8")), encoding="utf-8", newline=None) as stream:
            stream.read(1)
            stream.seek(0)
            self.assertTrue(sidecar.verify_spectral_sidecar(self.envelope, stream))

    def test_whole_prefixed_stream_and_crlf_still_fail(self):
        self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, io.StringIO("junk\n" + self.text)))
        with io.TextIOWrapper(io.BytesIO(self.text.replace("\n", "\r\n").encode("utf-8")), encoding="utf-8", newline=None) as stream:
            self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, stream))

    def test_closed_seekable_input_fails_without_raising(self):
        stream = io.StringIO(self.text)
        stream.close()
        self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, stream))


if __name__ == "__main__":
    unittest.main()
