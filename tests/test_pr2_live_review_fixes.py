import copy
import importlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import qsol_map.multiresolution as multiresolution_module
from qsol_map import __main__ as cli_module
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    LONG_FRAME_SIZE,
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
)
from qsol_map.sidecar import verify_spectral_sidecar, write_spectral_sidecar
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


class PR2LiveReviewFixes(unittest.TestCase):
    def test_two_frame_relationship_gram_requires_integer_pcm16_realization(self):
        wave = parse_pcm16_wav(make_wav([1, 0, 0, 1], channels=2))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        relation = changed["percept"]["channel_relationships"][0]
        relation.update(
            {
                "dot_product": "0",
                "dot_product_sign": 0,
                "left_sum_squares": "3",
                "right_sum_squares": "3",
                "difference_sum_squares": "6",
                "sum_sum_squares": "6",
                "zero_lag_correlation_squared": {
                    "numerator": "0",
                    "denominator": "9",
                },
            }
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_two_frame_long_energy_must_match_a_feasible_pcm_assignment(self):
        wave = parse_pcm16_wav(make_wav([1, 1, 0, 0], channels=2))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        for channel in changed["percept"]["channels"]:
            event = channel["long_spectral"]["events"][0]
            self.assertEqual(event["windowed_energy"], "1")
            event["windowed_energy"] = "2"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_zero_maximum_positive_delta_requires_zero_positive_sum(self):
        wave = parse_pcm16_wav(make_wav([0] * 384))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        transient["positive_delta_sum"] = "1"
        transient["maximum_positive_delta"] = "0"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_omitted_transient_candidates_contribute_to_positive_sum(self):
        wave = parse_pcm16_wav(make_wav([0] * 2177))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        transient["candidate_count"] = 17
        transient["positive_delta_sum"] = "16"
        transient["maximum_positive_delta"] = "1"
        transient["strongest_candidates"] = [
            {
                "frame_index": frame_index,
                "sample_start": frame_index * 128,
                "previous_energy": "0",
                "current_energy": "1",
                "positive_delta": "1",
                "rise_ratio": None,
            }
            for frame_index in range(1, 17)
        ]
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_multiresolution_reload_preserves_valid_verifier(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4] * 100))
        envelope = build_multiresolution_percept(wave)
        reloaded = importlib.reload(multiresolution_module)
        self.assertTrue(reloaded.verify_multiresolution_envelope(envelope))

    def test_sidecar_writer_bypasses_text_newline_translation(self):
        samples = [((index * 19) % 1001) - 500 for index in range(300)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="utf-8", newline="\r\n")
        write_spectral_sidecar(wave, envelope, stream)
        stream.flush()
        payload = raw.getvalue()
        self.assertNotIn(b"\r\n", payload)
        self.assertTrue(payload.endswith(b"\n"))
        self.assertTrue(
            verify_spectral_sidecar(envelope, io.StringIO(payload.decode("utf-8")))
        )
        stream.detach()

    def test_sidecar_verifier_rejects_crlf_before_text_translation(self):
        samples = [((index * 17) % 701) - 350 for index in range(300)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        canonical_stream = io.StringIO()
        write_spectral_sidecar(wave, envelope, canonical_stream)
        canonical_bytes_payload = canonical_stream.getvalue().encode("utf-8")

        valid_raw = io.BytesIO(canonical_bytes_payload)
        valid_text = io.TextIOWrapper(valid_raw, encoding="utf-8", newline=None)
        self.assertTrue(verify_spectral_sidecar(envelope, valid_text))
        valid_text.detach()

        crlf_raw = io.BytesIO(canonical_bytes_payload.replace(b"\n", b"\r\n"))
        crlf_text = io.TextIOWrapper(crlf_raw, encoding="utf-8", newline=None)
        self.assertFalse(verify_spectral_sidecar(envelope, crlf_text))
        crlf_text.detach()

    def test_multi_event_top_components_must_have_capacity_for_total_power(self):
        samples = [((index * 37) % 2001) - 1000 for index in range(700)]
        wave = parse_pcm16_wav(make_wav(samples))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        events = changed["percept"]["channels"][0]["long_spectral"]["events"]
        self.assertGreaterEqual(len(events), 2)
        event = next(
            item
            for item in events
            if int(item["spectral_centroid_bin"]["denominator"]) > 0
        )
        event["top_components"] = [
            {"bin": index, "real": "0", "imag": "0", "power": "0"}
            for index in range(8)
        ]
        event["dominant_non_dc_bin"] = 1
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_positive_delta_sum_is_bounded_by_transition_multiplicity(self):
        wave = parse_pcm16_wav(make_wav([0] * 257))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        transient["positive_delta_sum"] = "3"
        transient["maximum_positive_delta"] = "1"
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_three_frame_channel_energy_obeys_three_square_constraint(self):
        wave = parse_pcm16_wav(make_wav([0, 0, 0, 0, 0, 0], channels=2))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        relation = changed["percept"]["channel_relationships"][0]
        relation.update(
            {
                "dot_product": "0",
                "dot_product_sign": 0,
                "left_sum_squares": "7",
                "right_sum_squares": "7",
                "difference_sum_squares": "14",
                "sum_sum_squares": "14",
                "zero_lag_correlation_squared": {
                    "numerator": "0",
                    "denominator": "49",
                },
            }
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_spectral_power_is_bounded_by_windowed_energy_and_fft_gain(self):
        wave = parse_pcm16_wav(make_wav([1]))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        spectral = changed["percept"]["channels"][0]["long_spectral"]
        event = spectral["events"][0]
        magnitude = 10**100
        power = magnitude * magnitude
        bin_count = LONG_FRAME_SIZE // 2 + 1
        spectral["aggregate_power_by_bin"] = [str(power)] * bin_count

        region_totals = {
            "below_20khz_reference": 0,
            "20_to_40khz_reference": 0,
            "at_or_above_40khz_reference": 0,
        }
        for bin_index in range(bin_count):
            region = multiresolution_module._region_index(48000, bin_index)
            region_totals[region] += power
        spectral["aggregate_power_by_frequency_region"] = {
            key: str(value) for key, value in region_totals.items()
        }

        event["windowed_energy"] = "1"
        event["spectral_centroid_bin"] = {
            "numerator": str(sum(range(bin_count)) * power),
            "denominator": str(bin_count * power),
        }
        event["dominant_non_dc_bin"] = 1
        event["top_components"] = [
            {
                "bin": bin_index,
                "real": str(magnitude),
                "imag": "0",
                "power": str(power),
            }
            for bin_index in range(8)
        ]
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_zero_channel_energy_forces_zero_long_window_energy(self):
        zero_stereo = parse_pcm16_wav(make_wav([0, 0, 0, 0], channels=2))
        donor_wave = parse_pcm16_wav(make_wav([1, 0]))
        changed = copy.deepcopy(build_multiresolution_percept(zero_stereo))
        donor_spectral = build_multiresolution_percept(donor_wave)["percept"]["channels"][0][
            "long_spectral"
        ]
        changed["percept"]["channels"][0]["long_spectral"] = copy.deepcopy(
            donor_spectral
        )
        changed["percept"]["channels"][1]["long_spectral"] = copy.deepcopy(
            donor_spectral
        )
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_sidecar_writer_rejects_nonempty_destination_streams(self):
        samples = [((index * 13) % 401) - 200 for index in range(300)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)

        append_stream = io.StringIO("existing\n")
        append_stream.seek(0, io.SEEK_END)
        with self.assertRaises(ValueError):
            write_spectral_sidecar(wave, envelope, append_stream)
        self.assertEqual(append_stream.getvalue(), "existing\n")

        stale_tail_stream = io.StringIO("existing\n")
        stale_tail_stream.seek(0)
        with self.assertRaises(ValueError):
            write_spectral_sidecar(wave, envelope, stale_tail_stream)
        self.assertEqual(stale_tail_stream.getvalue(), "existing\n")

    def test_normalization_equivalent_names_use_filesystem_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            precomposed = parent / "é.json"
            decomposed = parent / "e\u0301.json"
            with mock.patch.object(
                cli_module,
                "_filesystem_normalization_insensitive",
                return_value=True,
            ) as probe:
                self.assertTrue(cli_module._same_path(precomposed, decomposed))
                probe.assert_called_once()


if __name__ == "__main__":
    unittest.main()
