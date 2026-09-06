import copy
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

import qsol_map.sidecar as sidecar
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
    LONG_COMPLEX_MATRIX_DOMAIN,
    PERCEPT_DOMAIN,
    build_multiresolution_percept,
    verify_multiresolution_envelope,
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


def rewrite_sidecar(envelope, text, mutator=None, update_long_complex=False):
    records = [json.loads(line) for line in text.splitlines()]
    header = records[0]
    trailer = records[-1]
    frames = records[1:-1]

    long_hashers = None
    if update_long_complex:
        channel_count = envelope["percept"]["source"]["channels"]
        long_hashers = [
            sidecar._matrix_hasher(LONG_COMPLEX_MATRIX_DOMAIN)
            for _ in range(channel_count)
        ]

    records_hasher = sidecar._matrix_hasher(sidecar.SIDECAR_RECORDS_DOMAIN)
    for record in frames:
        if mutator is not None:
            mutator(record)
        if (
            long_hashers is not None
            and record["record_type"] == "spectral_frame"
            and record["profile_id"] == sidecar.LONG_PROFILE_ID
        ):
            complex_row = [[item[0], item[1]] for item in record["coefficients"]]
            sidecar._update_matrix_hash(
                long_hashers[record["channel_index"]],
                complex_row,
            )
        sidecar._update_records_hash(records_hasher, record)

    if long_hashers is not None:
        for channel_index, hasher in enumerate(long_hashers):
            envelope["percept"]["channels"][channel_index]["long_spectral"][
                "complex_matrix_sha256"
            ] = hasher.hexdigest()

    rehash(envelope)
    header["percept_sha256"] = envelope["percept_sha256"]
    header_sha256 = domain_sha256(
        sidecar.SIDECAR_HEADER_DOMAIN,
        canonical_bytes(header),
    )
    trailer["header_sha256"] = header_sha256
    trailer["records_sha256"] = records_hasher.hexdigest()
    receipt_core = {
        "header_sha256": trailer["header_sha256"],
        "records_sha256": trailer["records_sha256"],
        "record_count": trailer["record_count"],
    }
    trailer["receipt_sha256"] = domain_sha256(
        sidecar.SIDECAR_RECEIPT_DOMAIN,
        canonical_bytes(receipt_core),
    )

    return "".join(
        canonical_bytes(record).decode("utf-8") + "\n"
        for record in [header, *frames, trailer]
    )


class LatestSidecarConsistencyTests(unittest.TestCase):
    def test_transients_are_derived_from_short_sidecar_rows(self):
        wave = parse_pcm16_wav(make_wav([0] * 512 + [12000] * 512))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        sidecar.write_spectral_sidecar(wave, envelope, stream)

        changed = copy.deepcopy(envelope)
        transient = changed["percept"]["channels"][0]["transient"]
        transient["positive_delta_sum"] = str(int(transient["positive_delta_sum"]) * 2)
        transient["maximum_positive_delta"] = str(
            int(transient["maximum_positive_delta"]) * 2
        )
        for candidate in transient["strongest_candidates"]:
            candidate["previous_energy"] = str(int(candidate["previous_energy"]) * 2)
            candidate["current_energy"] = str(int(candidate["current_energy"]) * 2)
            candidate["positive_delta"] = str(int(candidate["positive_delta"]) * 2)
            if candidate["rise_ratio"] is not None:
                candidate["rise_ratio"]["numerator"] = str(
                    int(candidate["rise_ratio"]["numerator"]) * 2
                )
                candidate["rise_ratio"]["denominator"] = str(
                    int(candidate["rise_ratio"]["denominator"]) * 2
                )

        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))
        rebound = rewrite_sidecar(changed, stream.getvalue())
        self.assertFalse(sidecar.verify_spectral_sidecar(changed, io.StringIO(rebound)))

    def test_short_and_long_profiles_must_reconstruct_same_pcm_waveform(self):
        samples = [((index * 31) % 2003) - 1001 for index in range(900)]
        wave = parse_pcm16_wav(make_wav(samples))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        sidecar.write_spectral_sidecar(wave, envelope, stream)

        changed = copy.deepcopy(envelope)
        for event in changed["percept"]["channels"][0]["long_spectral"]["events"]:
            for component in event["top_components"]:
                component["real"] = str(-int(component["real"]))
                component["imag"] = str(-int(component["imag"]))

        def negate_long(record):
            if record.get("profile_id") != sidecar.LONG_PROFILE_ID:
                return
            for coefficient in record["coefficients"]:
                coefficient[0] = str(-int(coefficient[0]))
                coefficient[1] = str(-int(coefficient[1]))

        rebound = rewrite_sidecar(
            changed,
            stream.getvalue(),
            mutator=negate_long,
            update_long_complex=True,
        )
        self.assertTrue(verify_multiresolution_envelope(changed))
        self.assertFalse(sidecar.verify_spectral_sidecar(changed, io.StringIO(rebound)))

    def test_channel_relationships_are_derived_from_reconstructed_pcm(self):
        interleaved = []
        for index in range(700):
            value = ((index * 97) % 20001) - 10000
            interleaved.extend((value, -value))
        wave = parse_pcm16_wav(make_wav(interleaved, channels=2))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        sidecar.write_spectral_sidecar(wave, envelope, stream)

        changed = copy.deepcopy(envelope)
        relation = changed["percept"]["channel_relationships"][0]
        left_energy = int(relation["left_sum_squares"])
        right_energy = int(relation["right_sum_squares"])
        self.assertGreater(left_energy, 0)
        self.assertEqual(left_energy, right_energy)
        relation.update(
            {
                "dot_product": "0",
                "dot_product_sign": 0,
                "difference_sum_squares": str(left_energy + right_energy),
                "sum_sum_squares": str(left_energy + right_energy),
                "zero_lag_correlation_squared": {
                    "numerator": "0",
                    "denominator": str(left_energy * right_energy),
                },
            }
        )
        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))
        rebound = rewrite_sidecar(changed, stream.getvalue())
        self.assertFalse(sidecar.verify_spectral_sidecar(changed, io.StringIO(rebound)))

    def test_invalid_utf8_file_backed_sidecar_fails_closed(self):
        wave = parse_pcm16_wav(make_wav([1, -1] * 300))
        envelope = build_multiresolution_percept(wave)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.ndjson"
            path.write_bytes(b"\xff\n")
            with path.open("r", encoding="utf-8", newline="") as stream:
                self.assertFalse(sidecar.verify_spectral_sidecar(envelope, stream))


if __name__ == "__main__":
    unittest.main()
