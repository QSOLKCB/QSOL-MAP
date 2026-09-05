import json
from pathlib import Path
import struct
import tempfile
import unittest

from qsol_map.__main__ import main


def make_wav(samples):
    payload = struct.pack("<" + "h" * len(samples), *samples)
    fmt = struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
