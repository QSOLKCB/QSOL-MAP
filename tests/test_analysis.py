import copy
import struct
import unittest

from qsol_map.analysis import (
    PERCEPT_DOMAIN,
    build_percept,
    verify_percept_envelope,
)
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.tables import FRAME_SIZE
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


class AnalysisTests(unittest.TestCase):
    def test_repeated_analysis_is_byte_identical(self):
        samples = [1000 if (index // 16) % 2 == 0 else -1000 for index in range(512)]
        wave = parse_pcm16_wav(make_wav(samples))
        first = canonical_bytes(build_percept(wave))
        second = canonical_bytes(build_percept(wave))
        self.assertEqual(first, second)

    def test_constant_signal_has_dc_as_top_component(self):
        wave = parse_pcm16_wav(make_wav([1000] * FRAME_SIZE))
        envelope = build_percept(wave)
        first_event = envelope["percept"]["channels"][0]["events"][0]
        self.assertEqual(first_event["top_components"][0]["bin"], 0)

    def test_zero_signal_has_zero_power_and_stable_tie_break(self):
        wave = parse_pcm16_wav(make_wav([0] * 300))
        envelope = build_percept(wave)
        channel = envelope["percept"]["channels"][0]
        self.assertTrue(all(value == "0" for value in channel["aggregate_power_by_bin"]))
        self.assertEqual(channel["events"][0]["top_components"][0]["bin"], 0)
        self.assertEqual(channel["events"][0]["dominant_non_dc_bin"], 1)

    def test_golden_percept_vector(self):
        samples = [((index * 37) % 2001) - 1000 for index in range(384)]
        wave = parse_pcm16_wav(make_wav(samples, sample_rate=48000))
        envelope = build_percept(wave)
        channel = envelope["percept"]["channels"][0]
        self.assertEqual(
            envelope["percept_sha256"],
            "e7ec380529d01790981e819bf5f33f8c251a6c89caafe19458b9053ae573b49c",
        )
        self.assertEqual(
            channel["power_matrix_sha256"],
            "6eb7ebeb2730da6ed111e6207dfc148217f89bb5272084a079b96f39fb487291",
        )
        self.assertEqual(
            channel["complex_matrix_sha256"],
            "cf4033b613f024f67e0a61938958599b1e09c3178b8bb618fd13c14e940ecc27",
        )

    def test_tamper_rejected(self):
        wave = parse_pcm16_wav(make_wav([0, 1, 2, 3] * 80))
        envelope = build_percept(wave)
        self.assertTrue(verify_percept_envelope(envelope))
        changed = copy.deepcopy(envelope)
        changed["percept"]["source"]["sample_rate_hz"] = 44100
        self.assertFalse(verify_percept_envelope(changed))

    def test_non_ascii_digest_is_rejected_without_exception(self):
        wave = parse_pcm16_wav(make_wav([0, 1, 2, 3] * 80))
        envelope = build_percept(wave)
        envelope["percept_sha256"] = "é" * 64
        self.assertFalse(verify_percept_envelope(envelope))

    def test_structurally_invalid_core_is_rejected_even_with_matching_hash(self):
        percept = {
            "schema": "qsol-map-percept-core-v0.1",
            "layer": "L3_semantic_interpretation",
        }
        envelope = {
            "schema": "qsol-map-percept-envelope-v0.1",
            "percept": percept,
            "percept_sha256": domain_sha256(PERCEPT_DOMAIN, canonical_bytes(percept)),
        }
        self.assertFalse(verify_percept_envelope(envelope))

    def test_stereo_channels_are_not_collapsed(self):
        interleaved = []
        for index in range(300):
            interleaved.extend((1000, -1000 if index % 2 else 1000))
        wave = parse_pcm16_wav(make_wav(interleaved, channels=2))
        envelope = build_percept(wave)
        channels = envelope["percept"]["channels"]
        self.assertEqual(len(channels), 2)
        self.assertNotEqual(
            channels[0]["power_matrix_sha256"],
            channels[1]["power_matrix_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
