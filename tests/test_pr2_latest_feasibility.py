import copy
import io
import struct
import tempfile
import threading
import unittest
from pathlib import Path

import qsol_map.__main__ as cli_module
import qsol_map.sidecar as sidecar_module
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
)
from qsol_map.sidecar import write_spectral_sidecar
from qsol_map.wav import parse_pcm16_wav


def make_wav(samples, sample_rate=48000, channels=1):
    payload = struct.pack("<" + "h" * len(samples), *samples)
    block_align = channels * 2
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        16,
    )
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def rehash(envelope):
    envelope["percept_sha256"] = domain_sha256(
        PERCEPT_DOMAIN,
        canonical_bytes(envelope["percept"]),
    )


class LatestFeasibilityTests(unittest.TestCase):
    def test_case_insensitive_output_alias_is_rejected_before_writing(self):
        wav_bytes = make_wav([1, -1] * 200)
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.wav"
            output_path = Path(directory) / "Percept.json"
            sidecar_path = Path(directory) / "percept.json"
            input_path.write_bytes(wav_bytes)
            original_probe = cli_module._filesystem_case_insensitive
            cli_module._filesystem_case_insensitive = lambda directory: True
            try:
                with self.assertRaises(ValueError):
                    cli_module._analyze_v02(input_path, output_path, sidecar_path)
            finally:
                cli_module._filesystem_case_insensitive = original_probe
            self.assertFalse(output_path.exists())
            self.assertFalse(sidecar_path.exists())

    def test_sidecar_writer_rejects_rebound_matrix_commitment(self):
        wave = parse_pcm16_wav(make_wav([3, -2, 1, -4] * 200))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        changed["percept"]["short_reference"]["channels"][0][
            "complex_matrix_sha256"
        ] = "0" * 64
        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))
        stream = io.StringIO()
        with self.assertRaises(ValueError):
            write_spectral_sidecar(wave, changed, stream)
        self.assertEqual(stream.getvalue(), "")

    def test_channel_gram_rank_cannot_exceed_frame_count(self):
        wave = parse_pcm16_wav(make_wav([1, 1, 1], channels=3))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        for relation in changed["percept"]["channel_relationships"]:
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
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_single_short_frame_requires_zero_transient_totals(self):
        wave = parse_pcm16_wav(make_wav([7] * 64))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        self.assertEqual(transient["candidate_count"], 0)
        transient["positive_delta_sum"] = "1"
        transient["maximum_positive_delta"] = "1"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_transient_candidate_energies_obey_short_pcm_window_bounds(self):
        wave = parse_pcm16_wav(make_wav([0] * 128 + [12000] * 256))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        candidate = changed["percept"]["channels"][0]["transient"][
            "strongest_candidates"
        ][0]
        huge_previous = 10**50
        huge_current = 2 * huge_previous
        candidate["previous_energy"] = str(huge_previous)
        candidate["current_energy"] = str(huge_current)
        candidate["positive_delta"] = str(huge_previous)
        candidate["rise_ratio"] = {
            "numerator": str(huge_current),
            "denominator": str(huge_previous),
        }
        transient = changed["percept"]["channels"][0]["transient"]
        transient["positive_delta_sum"] = str(huge_previous)
        transient["maximum_positive_delta"] = str(huge_previous)
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_single_long_event_ranking_must_match_aggregate_row(self):
        wave = parse_pcm16_wav(make_wav([3, -2, 5, -1] * 50, sample_rate=1000))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        self.assertEqual(len(spectral["events"]), 1)
        event = spectral["events"][0]
        reported_bins = {component["bin"] for component in event["top_components"]}
        target_bin = next(
            bin_index
            for bin_index in range(1, len(spectral["aggregate_power_by_bin"]))
            if bin_index not in reported_bins
        )
        strongest_power = max(int(component["power"]) for component in event["top_components"])
        old_power = int(spectral["aggregate_power_by_bin"][target_bin])
        new_power = strongest_power + 1
        delta = new_power - old_power
        self.assertGreater(delta, 0)
        spectral["aggregate_power_by_bin"][target_bin] = str(new_power)
        regions = spectral["aggregate_power_by_frequency_region"]
        regions["below_20khz_reference"] = str(
            int(regions["below_20khz_reference"]) + delta
        )
        centroid = event["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) + delta)
        centroid["numerator"] = str(
            int(centroid["numerator"]) + target_bin * delta
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_single_sample_relationships_require_integer_pcm_realization(self):
        wave = parse_pcm16_wav(make_wav([1, 1], channels=2))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        relation = changed["percept"]["channel_relationships"][0]
        relation.update(
            {
                "dot_product": "2",
                "dot_product_sign": 1,
                "left_sum_squares": "2",
                "right_sum_squares": "2",
                "difference_sum_squares": "0",
                "sum_sum_squares": "8",
                "zero_lag_correlation_squared": {
                    "numerator": "4",
                    "denominator": "4",
                },
            }
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_one_transition_requires_equal_positive_sum_and_maximum(self):
        wave = parse_pcm16_wav(make_wav([0] * 200))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        self.assertEqual(transient["candidate_count"], 0)
        transient["positive_delta_sum"] = "2"
        transient["maximum_positive_delta"] = "1"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_single_event_endpoint_aggregate_power_must_be_square(self):
        wave = parse_pcm16_wav(make_wav([100] * 200, sample_rate=1000))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        self.assertEqual(len(spectral["events"]), 1)
        event = spectral["events"][0]
        endpoint = len(spectral["aggregate_power_by_bin"]) - 1
        reported_bins = {component["bin"] for component in event["top_components"]}
        self.assertNotIn(endpoint, reported_bins)

        old_power = int(spectral["aggregate_power_by_bin"][endpoint])
        new_power = old_power + 1
        while int(new_power**0.5) ** 2 == new_power:
            new_power += 1
        weakest_reported = min(int(component["power"]) for component in event["top_components"])
        self.assertLess(new_power, weakest_reported)
        delta = new_power - old_power
        spectral["aggregate_power_by_bin"][endpoint] = str(new_power)
        regions = spectral["aggregate_power_by_frequency_region"]
        regions["below_20khz_reference"] = str(
            int(regions["below_20khz_reference"]) + delta
        )
        centroid = event["spectral_centroid_bin"]
        centroid["denominator"] = str(int(centroid["denominator"]) + delta)
        centroid["numerator"] = str(
            int(centroid["numerator"]) + endpoint * delta
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_each_event_centroid_covers_reported_component_weight(self):
        samples = [((index * 7919) % 30001) - 15000 for index in range(1600)]
        wave = parse_pcm16_wav(make_wav(samples))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        events = changed["percept"]["channels"][0]["long_spectral"]["events"]
        self.assertGreaterEqual(len(events), 2)

        chosen = None
        for source_index, source_event in enumerate(events):
            selected_weight = sum(
                component["bin"] * int(component["power"])
                for component in source_event["top_components"]
            )
            if selected_weight <= 0:
                continue
            source_numerator = int(source_event["spectral_centroid_bin"]["numerator"])
            shift = source_numerator - selected_weight + 1
            if shift <= 0:
                continue
            for target_index, target_event in enumerate(events):
                if target_index == source_index:
                    continue
                target_centroid = target_event["spectral_centroid_bin"]
                target_numerator = int(target_centroid["numerator"])
                target_denominator = int(target_centroid["denominator"])
                capacity = 512 * target_denominator - target_numerator
                if capacity >= shift:
                    chosen = (source_event, target_event, selected_weight, shift)
                    break
            if chosen is not None:
                break
        self.assertIsNotNone(chosen)
        source_event, target_event, selected_weight, shift = chosen
        source_centroid = source_event["spectral_centroid_bin"]
        target_centroid = target_event["spectral_centroid_bin"]
        source_centroid["numerator"] = str(selected_weight - 1)
        target_centroid["numerator"] = str(int(target_centroid["numerator"]) + shift)
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_concurrent_sidecar_line_limit_overrides_are_serialized(self):
        wave = parse_pcm16_wav(make_wav([3, -2, 1, -4] * 200))
        envelope = build_multiresolution_percept(wave)
        sidecar_stream = io.StringIO()
        sidecar_module.write_spectral_sidecar(wave, envelope, sidecar_stream)
        sidecar_text = sidecar_stream.getvalue()
        self.assertGreater(max(map(len, sidecar_text.splitlines(True))), 1000)

        class BlockingReader:
            def __init__(self, text, entered, release):
                self._stream = io.StringIO(text)
                self._entered = entered
                self._release = release
                self._first = True

            def readline(self, size=-1):
                if self._first:
                    self._first = False
                    self._entered.set()
                    if not self._release.wait(5):
                        raise RuntimeError("timed out waiting to release blocked sidecar read")
                return self._stream.readline(size)

        old_limit = sidecar_module.MAX_SIDECAR_LINE_CHARS
        entered_a = threading.Event()
        entered_b = threading.Event()
        release_a = threading.Event()
        release_b = threading.Event()
        results = {}
        threads = []

        def run(name, reader):
            results[name] = sidecar_module.verify_spectral_sidecar(envelope, reader)

        try:
            sidecar_module.MAX_SIDECAR_LINE_CHARS = 1000
            thread_a = threading.Thread(
                target=run,
                args=("a", BlockingReader(sidecar_text, entered_a, release_a)),
                daemon=True,
            )
            thread_b = threading.Thread(
                target=run,
                args=("b", BlockingReader(sidecar_text, entered_b, release_b)),
                daemon=True,
            )
            threads = [thread_a, thread_b]
            thread_a.start()
            self.assertTrue(entered_a.wait(2))
            thread_b.start()

            # The second verifier must not reach its first read while the first
            # call still owns the temporary module-global override.
            self.assertFalse(entered_b.wait(0.5))
            release_a.set()
            thread_a.join(5)
            self.assertFalse(thread_a.is_alive())
            self.assertTrue(entered_b.wait(2))
            release_b.set()
            thread_b.join(5)
            self.assertFalse(thread_b.is_alive())
            self.assertFalse(results["a"])
            self.assertFalse(results["b"])
        finally:
            release_a.set()
            release_b.set()
            for thread in threads:
                thread.join(1)
            sidecar_module.MAX_SIDECAR_LINE_CHARS = old_limit


if __name__ == "__main__":
    unittest.main()
