#!/usr/bin/env python3
"""Environment-scoped benchmark harness for QSOL-MAP v0.2.

This script is intentionally not a CI performance gate. It records enough
runtime context to make a local timing observation useful without promoting it
into a portable speed claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import struct
import sys
import time

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from qsol_map.multiresolution import build_multiresolution_percept
from qsol_map.wav import parse_pcm16_wav


def make_fixture(frame_count: int, sample_rate: int) -> bytes:
    samples = [((index * 257 + 31) % 32749) - 16374 for index in range(frame_count)]
    payload = struct.pack("<" + "h" * len(samples), *samples)
    block_align = 2
    fmt = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * block_align, block_align, 16)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=48_000)
    parser.add_argument("--sample-rate", type=int, default=48_000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.frames <= 0 or args.repeats <= 0 or not 1 <= args.sample_rate <= 768_000:
        parser.error("frames/repeats must be positive and sample-rate must be within the adapter bounds")

    wave = parse_pcm16_wav(make_fixture(args.frames, args.sample_rate))
    elapsed_ns = []
    hashes = []
    for _ in range(args.repeats):
        start = time.perf_counter_ns()
        envelope = build_multiresolution_percept(wave)
        elapsed_ns.append(time.perf_counter_ns() - start)
        hashes.append(envelope["percept_sha256"])

    if len(set(hashes)) != 1:
        raise RuntimeError("deterministic benchmark fixture produced different percept hashes")

    result = {
        "benchmark": "qsol-map-v0.2-reference-compact-percept",
        "frames": args.frames,
        "sample_rate_hz": args.sample_rate,
        "repeats": args.repeats,
        "elapsed_ns": elapsed_ns,
        "median_elapsed_ns": int(statistics.median(elapsed_ns)),
        "percept_sha256": hashes[0],
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "claim_boundary": "environment-scoped observation; not a portable performance claim",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
