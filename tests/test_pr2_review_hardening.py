import copy
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from qsol_map.__main__ import _analyze_v02
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    LONG_FRAME_SIZE,
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
)
from qsol_map.sidecar import (
    SIDECAR_HEADER_DOMAIN,
    SIDECAR_RECEIPT_DOMAIN,
    verify_spectral_sidecar,
    write_spectral_sidecar,
)
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


def rebind_sidecar(envelope, text):
    lines = text.splitlines(keepends=True)
    header = json.loads(lines[0])
    header["percept_sha256"] = envelope["percept_sha256"]
    lines[0] = canonical_bytes(header).decode("utf-8") + "\n"

    trailer = json.loads(lines[-1])
    trailer["header_sha256"] = domain_sha256(
        SIDECAR_HEADER_DOMAIN,
        canonical_bytes(header),
    )
    receipt_core = {
        "header_sha256": trailer["header_sha256"],
        "records_sha256": trailer["records_sha256"],
        "record_count": trailer["record_count"],
    }
    trailer["receipt_sha256"] = domain_sha256(
        SIDECAR_RECEIPT_DOMAIN,
        canonical_bytes(receipt_core),
    )
    lines[-1] = canonical_bytes(trailer).decode("utf-8") + "\n"
    return "".join(lines)


class PR2ReviewHardeningTests(unittest.TestCase):
    def test_reported_transient_deltas_cannot_exceed_summary(self):
        wave = parse_pcm16_wav(make_wav([0] * 512 + [12000] * 512))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        candidates = transient["strongest_candidates"]
        self.assertGreaterEqual(len(candidates), 2)
        transient["positive_delta_sum"] = str(
            max(int(candidate["positive_delta"]) for candidate in candidates)
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_top_components_fit_inside_frame_total_power(self):
        wave = parse_pcm16_wav(make_wav([0] * LONG_FRAME_SIZE))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        component = changed["percept"]["channels"][0]["long_spectral"]["events"][0]["top_components"][0]
        component.update({"real": "1", "imag": "0", "power": "1"})
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_centroid_numerator_totals_match_bin_aggregates(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4] * 300))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        centroid = changed["percept"]["channels"][0]["long_spectral"]["events"][0]["spectral_centroid_bin"]
        centroid["numerator"] = str(int(centroid["numerator"]) + 1)
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_sidecar_rows_bind_selected_long_event_observations(self):
        samples = [((index * 19) % 1001) - 500 for index in range(700)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        write_spectral_sidecar(wave, envelope, stream)

        changed = copy.deepcopy(envelope)
        events = changed["percept"]["channels"][0]["long_spectral"]["events"]
        selected = None
        for event in events:
            for component in event["top_components"]:
                if component["bin"] not in (0, LONG_FRAME_SIZE // 2) and int(component["real"]) != 0:
                    selected = component
                    break
            if selected is not None:
                break
        self.assertIsNotNone(selected)
        selected["real"] = str(-int(selected["real"]))
        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))

        rebound = rebind_sidecar(changed, stream.getvalue())
        self.assertFalse(verify_spectral_sidecar(changed, io.StringIO(rebound)))

    def test_sidecar_cannot_alias_implicit_stdout(self):
        wav_bytes = make_wav([1, -1] * 300)
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.wav"
            stdout_path = Path(directory) / "stdout.bin"
            input_path.write_bytes(wav_bytes)
            with stdout_path.open("w", encoding="utf-8") as stdout_stream:
                old_stdout = sys.stdout
                sys.stdout = stdout_stream
                try:
                    alias = Path(f"/proc/self/fd/{stdout_stream.fileno()}")
                    with self.assertRaises(ValueError):
                        _analyze_v02(input_path, None, alias)
                finally:
                    sys.stdout = old_stdout
            self.assertEqual(stdout_path.read_bytes(), b"")

    def test_multichannel_relationship_gram_matrix_must_be_psd(self):
        interleaved = []
        for index in range(64):
            value = (index % 11) - 5
            interleaved.extend((value, value, value))
        wave = parse_pcm16_wav(make_wav(interleaved, channels=3))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        dots = [1, 1, -1]
        for relation, dot in zip(changed["percept"]["channel_relationships"], dots):
            relation["dot_product"] = str(dot)
            relation["dot_product_sign"] = 1 if dot > 0 else -1
            relation["left_sum_squares"] = "1"
            relation["right_sum_squares"] = "1"
            relation["difference_sum_squares"] = str(2 - 2 * dot)
            relation["sum_sum_squares"] = str(2 + 2 * dot)
            relation["zero_lag_correlation_squared"] = {
                "numerator": "1",
                "denominator": "1",
            }
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_sidecar_cannot_overwrite_input_even_through_hardlink(self):
        wav_bytes = make_wav([1, -1] * 300)
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.wav"
            alias_path = Path(directory) / "sidecar.ndjson"
            output_path = Path(directory) / "percept.json"
            input_path.write_bytes(wav_bytes)
            os.link(input_path, alias_path)
            with self.assertRaises(ValueError):
                _analyze_v02(input_path, output_path, alias_path)
            self.assertEqual(input_path.read_bytes(), wav_bytes)
            self.assertFalse(output_path.exists())

    def test_window_energy_zero_state_matches_spectral_power_zero_state(self):
        wave = parse_pcm16_wav(make_wav([0] * LONG_FRAME_SIZE))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        event["windowed_energy"] = "1"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_adjacent_transient_candidates_share_frame_energy(self):
        wave = parse_pcm16_wav(make_wav([0] * 512 + [12000] * 512))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        candidates = changed["percept"]["channels"][0]["transient"]["strongest_candidates"]
        by_frame = {candidate["frame_index"]: candidate for candidate in candidates}
        pair = next(
            (
                (by_frame[index], by_frame[index + 1])
                for index in sorted(by_frame)
                if index + 1 in by_frame
            ),
            None,
        )
        self.assertIsNotNone(pair)
        _, later = pair
        previous_energy = int(later["previous_energy"]) + 1
        current_energy = int(later["current_energy"]) + 1
        later["previous_energy"] = str(previous_energy)
        later["current_energy"] = str(current_energy)
        later["positive_delta"] = str(current_energy - previous_energy)
        later["rise_ratio"] = None if previous_energy == 0 else {
            "numerator": str(current_energy),
            "denominator": str(previous_energy),
        }
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_selected_component_power_is_bounded_by_declared_bin_aggregate(self):
        wave = parse_pcm16_wav(make_wav([1200] * LONG_FRAME_SIZE))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        component = event["top_components"][0]
        occupied = {item["bin"] for item in event["top_components"]}
        target = next(
            bin_index
            for bin_index, aggregate in enumerate(spectral["aggregate_power_by_bin"])
            if bin_index not in occupied
            and bin_index not in (0, LONG_FRAME_SIZE // 2)
            and int(aggregate) < int(component["power"])
        )
        component["bin"] = target
        event["dominant_non_dc_bin"] = next(
            item["bin"] for item in event["top_components"] if item["bin"] != 0
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_real_fft_endpoint_components_have_zero_imaginary_part(self):
        wave = parse_pcm16_wav(make_wav([1200] * LONG_FRAME_SIZE))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        component = next(item for item in event["top_components"] if item["bin"] == 0)
        old_power = int(component["power"])
        component["imag"] = "1"
        component["power"] = str(old_power + 1)
        event["spectral_centroid_bin"]["denominator"] = str(
            int(event["spectral_centroid_bin"]["denominator"]) + 1
        )
        spectral["aggregate_power_by_bin"][0] = str(
            int(spectral["aggregate_power_by_bin"][0]) + 1
        )
        region = spectral["aggregate_power_by_frequency_region"]
        region["below_20khz_reference"] = str(int(region["below_20khz_reference"]) + 1)
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_sidecar_receipt_is_frozen_for_fixed_fixture(self):
        samples = [((index * 19) % 1001) - 500 for index in range(700)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        trailer = write_spectral_sidecar(wave, envelope, stream)
        self.assertEqual(
            trailer["records_sha256"],
            "__RECORDS_SHA256__",
        )
        self.assertEqual(
            trailer["receipt_sha256"],
            "__RECEIPT_SHA256__",
        )


if __name__ == "__main__":
    unittest.main()
