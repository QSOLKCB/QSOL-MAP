import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

import qsol_map
from qsol_map.__main__ import main


def make_wav(samples):
    payload = struct.pack("<" + "h" * len(samples), *samples)
    fmt = struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


class CliTests(unittest.TestCase):
    def test_package_version_matches_v02(self):
        self.assertEqual(qsol_map.__version__, "0.2.0")

    def test_analyze_writes_exact_envelope_file(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.wav"
            output = directory / "percept.json"
            source.write_bytes(make_wav([0, 100, -100, 50] * 80))

            self.assertEqual(main(["analyze", str(source), "-o", str(output)]), 0)
            envelope = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(envelope["schema"], "qsol-map-percept-envelope-v0.1")
            self.assertEqual(main(["verify", str(output)]), 0)

    def test_v02_analyze_verify_and_sidecar_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.wav"
            output = directory / "percept-v02.json"
            sidecar = directory / "spectral-v02.ndjson"
            source.write_bytes(make_wav([0, 1000, -500, 250] * 300))

            self.assertEqual(
                main([
                    "analyze-v0.2",
                    str(source),
                    "-o",
                    str(output),
                    "--sidecar",
                    str(sidecar),
                ]),
                0,
            )
            envelope = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(envelope["schema"], "qsol-map-percept-envelope-v0.2")
            self.assertEqual(main(["verify-v0.2", str(output)]), 0)
            self.assertEqual(
                main(["verify-sidecar-v0.2", str(output), str(sidecar)]),
                0,
            )

    def test_v02_rejects_same_percept_and_sidecar_path_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.wav"
            collision = directory / "same-output"
            source.write_bytes(make_wav([1, -1, 2, -2] * 100))

            self.assertEqual(
                main([
                    "analyze-v0.2",
                    str(source),
                    "-o",
                    str(collision),
                    "--sidecar",
                    str(collision),
                ]),
                2,
            )
            self.assertFalse(collision.exists())

    def test_v02_rejects_hardlinked_output_collision_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.wav"
            output = directory / "percept-v02.json"
            sidecar = directory / "spectral-v02.ndjson"
            source.write_bytes(make_wav([1, -1, 2, -2] * 100))
            output.write_text("sentinel", encoding="utf-8")
            try:
                os.link(output, sidecar)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            self.assertTrue(output.samefile(sidecar))

            self.assertEqual(
                main([
                    "analyze-v0.2",
                    str(source),
                    "-o",
                    str(output),
                    "--sidecar",
                    str(sidecar),
                ]),
                2,
            )
            self.assertEqual(output.read_text(encoding="utf-8"), "sentinel")
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "sentinel")


if __name__ == "__main__":
    unittest.main()
