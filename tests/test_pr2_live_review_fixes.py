import copy
import importlib
import io
import struct
import unittest

import qsol_map.multiresolution as multiresolution_module
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
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

    def test_zero_maximum_positive_delta_requires_zero_positive_sum(self):
        wave = parse_pcm16_wav(make_wav([0] * 384))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        transient = changed["percept"]["channels"][0]["transient"]
        transient["positive_delta_sum"] = "1"
        transient["maximum_positive_delta"] = "0"
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


if __name__ == "__main__":
    unittest.main()
