import copy
import io
import json
import struct
import unittest

from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    LONG_FRAME_SIZE,
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
)
from qsol_map.sidecar import (
    SIDECAR_RECEIPT_DOMAIN,
    SIDECAR_RECORDS_DOMAIN,
    _matrix_hasher,
    _update_records_hash,
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


class MultiResolutionTests(unittest.TestCase):
    def test_v01_reference_remains_frozen(self):
        samples = [((index * 37) % 2001) - 1000 for index in range(384)]
        wave = parse_pcm16_wav(make_wav(samples, sample_rate=48000))
        envelope = build_multiresolution_percept(wave)
        self.assertEqual(
            envelope["percept"]["short_reference"]["percept_sha256"],
            "e7ec380529d01790981e819bf5f33f8c251a6c89caafe19458b9053ae573b49c",
        )

    def test_v02_repeated_analysis_is_byte_identical_and_valid(self):
        samples = [1000 if (index // 31) % 2 == 0 else -700 for index in range(1536)]
        wave = parse_pcm16_wav(make_wav(samples))
        first = build_multiresolution_percept(wave)
        second = build_multiresolution_percept(wave)
        self.assertTrue(verify_multiresolution_envelope(first))
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))

    def test_v02_golden_percept_vector(self):
        samples = [((index * 53 + 17) % 4093) - 2046 for index in range(1408)]
        wave = parse_pcm16_wav(make_wav(samples, sample_rate=96000))
        envelope = build_multiresolution_percept(wave)
        self.assertEqual(
            envelope["percept_sha256"],
            "c167694d60661ceac1d01d6504cbd8b5db77286ce09b28a342629b03046735d7",
        )

    def test_long_constant_signal_keeps_dc_dominant(self):
        wave = parse_pcm16_wav(make_wav([1200] * LONG_FRAME_SIZE))
        envelope = build_multiresolution_percept(wave)
        first = envelope["percept"]["channels"][0]["long_spectral"]["events"][0]
        self.assertEqual(first["top_components"][0]["bin"], 0)

    def test_high_sample_rate_retains_ultrasonic_reference_bins(self):
        samples = [16000 if index % 2 == 0 else -16000 for index in range(LONG_FRAME_SIZE)]
        wave = parse_pcm16_wav(make_wav(samples, sample_rate=192000))
        envelope = build_multiresolution_percept(wave)
        support = envelope["percept"]["frequency_support"]
        regions = envelope["percept"]["channels"][0]["long_spectral"]["aggregate_power_by_frequency_region"]
        self.assertTrue(support["bins_at_or_above_20khz_retained"])
        self.assertFalse(support["psychoacoustic_low_pass_applied"])
        self.assertGreater(int(regions["at_or_above_40khz_reference"]), 0)

    def test_energy_rise_emits_transient_candidate_and_silence_ratio_is_null(self):
        samples = [0] * 512 + [12000] * 512
        wave = parse_pcm16_wav(make_wav(samples))
        transient = build_multiresolution_percept(wave)["percept"]["channels"][0]["transient"]
        self.assertGreater(transient["candidate_count"], 0)
        self.assertGreater(int(transient["maximum_positive_delta"]), 0)
        silence_candidates = [
            candidate
            for candidate in transient["strongest_candidates"]
            if candidate["previous_energy"] == "0"
        ]
        self.assertTrue(silence_candidates)
        self.assertIsNone(silence_candidates[0]["rise_ratio"])

    def test_channel_relationships_preserve_sign_and_difference(self):
        interleaved = []
        for index in range(600):
            value = ((index * 97) % 20001) - 10000
            interleaved.extend((value, -value))
        wave = parse_pcm16_wav(make_wav(interleaved, channels=2))
        relation = build_multiresolution_percept(wave)["percept"]["channel_relationships"][0]
        self.assertEqual(relation["dot_product_sign"], -1)
        self.assertGreater(int(relation["difference_sum_squares"]), 0)
        corr = relation["zero_lag_correlation_squared"]
        self.assertEqual(corr["numerator"], corr["denominator"])

    def test_structurally_tampered_v02_envelope_is_rejected(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4] * 300))
        envelope = build_multiresolution_percept(wave)
        changed = copy.deepcopy(envelope)
        changed["percept"]["layer"] = "L3_semantic_interpretation"
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_oversized_decimal_string_fails_closed_without_exception(self):
        wave = parse_pcm16_wav(make_wav([1, -2, 3, -4] * 300))
        changed = copy.deepcopy(build_multiresolution_percept(wave))
        changed["percept"]["channels"][0]["long_spectral"]["aggregate_power_by_bin"][0] = "9" * 5000
        changed["percept_sha256"] = domain_sha256(
            PERCEPT_DOMAIN,
            canonical_bytes(changed["percept"]),
        )
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_streaming_sidecar_round_trip_and_tamper_rejection(self):
        samples = [((index * 19) % 1001) - 500 for index in range(700)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        trailer = write_spectral_sidecar(wave, envelope, stream)
        self.assertGreater(trailer["record_count"], 0)
        self.assertTrue(verify_spectral_sidecar(envelope, io.StringIO(stream.getvalue())))

        lines = stream.getvalue().splitlines(keepends=True)
        record = json.loads(lines[1])
        record["coefficients"][0][2] = str(int(record["coefficients"][0][2]) + 1)
        lines[1] = canonical_bytes(record).decode("utf-8") + "\n"
        self.assertFalse(verify_spectral_sidecar(envelope, lines))

    def test_sidecar_boolean_position_rejected_even_with_recomputed_receipt(self):
        samples = [((index * 11) % 701) - 350 for index in range(700)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        write_spectral_sidecar(wave, envelope, stream)
        records = [json.loads(line) for line in stream.getvalue().splitlines()]

        records[1]["channel_index"] = False
        records_hasher = _matrix_hasher(SIDECAR_RECORDS_DOMAIN)
        for record in records[1:-1]:
            _update_records_hash(records_hasher, record)
        trailer = records[-1]
        trailer["records_sha256"] = records_hasher.hexdigest()
        receipt_core = {
            "header_sha256": trailer["header_sha256"],
            "records_sha256": trailer["records_sha256"],
            "record_count": trailer["record_count"],
        }
        trailer["receipt_sha256"] = domain_sha256(
            SIDECAR_RECEIPT_DOMAIN,
            canonical_bytes(receipt_core),
        )
        rewritten = "".join(
            canonical_bytes(record).decode("utf-8") + "\n"
            for record in records
        )
        self.assertFalse(verify_spectral_sidecar(envelope, io.StringIO(rewritten)))


if __name__ == "__main__":
    unittest.main()
