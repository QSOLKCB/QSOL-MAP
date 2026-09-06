import copy
import io
import json
import struct
import unittest
from unittest import mock

import qsol_map.sidecar as sidecar_module
from qsol_map.canonical import canonical_bytes, domain_sha256
from qsol_map.multiresolution import (
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
    header["source"] = envelope["percept"]["source"]
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


class FinalReceiptHardeningTests(unittest.TestCase):
    def _fixture(self, *, channels=1):
        if channels == 1:
            samples = [((index * 37) % 2003) - 1001 for index in range(900)]
        else:
            samples = []
            for index in range(700):
                left = ((index * 31) % 1601) - 800
                right = ((index * 47) % 1801) - 900
                samples.extend((left, right))
        wave = parse_pcm16_wav(make_wav(samples, channels=channels))
        envelope = build_multiresolution_percept(wave)
        stream = io.StringIO()
        write_spectral_sidecar(wave, envelope, stream)
        return wave, envelope, stream.getvalue()

    def test_reconstructed_pcm_must_match_declared_pcm_digest(self):
        _, envelope, sidecar = self._fixture()
        changed = copy.deepcopy(envelope)
        original = changed["percept"]["source"]["pcm_s16le_sha256"]
        changed["percept"]["source"]["pcm_s16le_sha256"] = (
            "0" * 64 if original != "0" * 64 else "1" * 64
        )
        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))
        rebound = rebind_sidecar(changed, sidecar)
        self.assertFalse(verify_spectral_sidecar(changed, io.StringIO(rebound)))

    def test_short_reference_digest_is_rebuilt_from_sidecar_evidence(self):
        _, envelope, sidecar = self._fixture()
        changed = copy.deepcopy(envelope)
        original = changed["percept"]["short_reference"]["percept_sha256"]
        changed["percept"]["short_reference"]["percept_sha256"] = (
            "0" * 64 if original != "0" * 64 else "1" * 64
        )
        rehash(changed)
        self.assertTrue(verify_multiresolution_envelope(changed))
        rebound = rebind_sidecar(changed, sidecar)
        self.assertFalse(verify_spectral_sidecar(changed, io.StringIO(rebound)))

    def test_compact_long_window_energy_is_bounded_by_pcm16_window(self):
        _, envelope, _ = self._fixture()
        changed = copy.deepcopy(envelope)
        event = changed["percept"]["channels"][0]["long_spectral"]["events"][0]
        event["windowed_energy"] = "1" + "0" * 100
        rehash(changed)
        self.assertFalse(verify_multiresolution_envelope(changed))

    def test_decode_failure_after_valid_trailer_is_not_clean_eof(self):
        _, envelope, sidecar = self._fixture()

        class LateDecodeFailure:
            def __init__(self, text):
                self.stream = io.StringIO(text)
                self.raised = False

            def readline(self, size=-1):
                line = self.stream.readline(size)
                if line:
                    return line
                if not self.raised:
                    self.raised = True
                    raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
                return ""

        self.assertFalse(verify_spectral_sidecar(envelope, LateDecodeFailure(sidecar)))

    def test_invalid_envelope_is_rejected_before_spool_allocation(self):
        _, envelope, _ = self._fixture()
        changed = copy.deepcopy(envelope)
        changed["percept"]["source"]["channels"] = 1_000_000
        rehash(changed)

        def forbidden_tempfile(*args, **kwargs):
            raise AssertionError("temporary spool allocated before compact validation")

        with mock.patch.object(sidecar_module.tempfile, "TemporaryFile", forbidden_tempfile):
            self.assertFalse(verify_spectral_sidecar(changed, io.StringIO("")))


if __name__ == "__main__":
    unittest.main()
