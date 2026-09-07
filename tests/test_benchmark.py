import json
from pathlib import Path
import subprocess
import sys
import unittest


class BenchmarkHarnessTests(unittest.TestCase):
    def test_benchmark_runs_from_repository_checkout(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/benchmark_v02.py",
                "--frames",
                "64",
                "--repeats",
                "1",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["benchmark"], "qsol-map-v0.2-reference-compact-percept")
        self.assertEqual(payload["frames"], 64)
        self.assertEqual(payload["repeats"], 1)
        self.assertEqual(
            payload["claim_boundary"],
            "environment-scoped observation; not a portable performance claim",
        )


if __name__ == "__main__":
    unittest.main()
