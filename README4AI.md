# QSOL-MAP - AI Context

## Mission

QSOL-MAP defines a layered machine-audio observation protocol. Keep physical/source identity, deterministic signal observations, learned tokens, semantic interpretation, and human reports epistemically separate.

## Non-negotiable invariant

```text
L0 source / physical signal encoding
L1 deterministic acoustic observation
L2 learned tokenization
L3 semantic interpretation
L4 human subjective or experimental report

L0 != L1 != L2 != L3 != L4
```

Do not describe L2 or L3 output as direct physical measurement. Do not describe L1 as subjective hearing.

## Implemented canonical profiles

Two L1 profiles are implemented.

### Frozen v0.1 short reference

`qsol-map-fixed-fft-v0.1`

- strict RIFF/WAVE PCM format 1;
- PCM16 little endian;
- 1 to 8 channels;
- 256-sample frame, 128-sample hop;
- exact integer triangular window;
- frozen Q15 twiddles;
- exact unbounded-integer Python FFT;
- independent source, PCM, complex-matrix, power-matrix and percept commitments.

The v0.1 profile is frozen and must remain byte-identical to its published golden vector.

### v0.2 multi-resolution reference

`qsol-map-multiresolution-v0.2`

The v0.2 profile imports the frozen v0.1 result and adds:

- a deterministic 1024-sample / 512-hop long spectral reference;
- independent long complex/power matrix commitments;
- explicit represented-frequency support and 20 kHz / 40 kHz reference regions;
- no psychoacoustic low-pass filtering;
- deterministic short-frame energy-rise transient candidates;
- exact pairwise channel relationships without downmixing;
- optional canonical NDJSON full-spectral sidecars;
- strict sidecar ordering, arithmetic, matrix and receipt verification;
- exact sidecar reconstruction of PCM16 from both spectral profiles, requiring identical recovered waveforms;
- reconstructed PCM SHA-256 binding, frozen-v0.1 percept rebuild, transient rebuild, and channel-relationship rebuild before sidecar acceptance.

For a transition from zero previous energy, the transient candidate's `rise_ratio` is `null`; finite rational ratios are emitted only when the denominator is non-zero. Candidate energies and summary totals are bounded by the source-sized frozen short-window PCM16 maxima. If fewer than two short frames exist, both transient summary totals are zero.

The compact verifier also requires the complete channel Gram matrix to be positive semidefinite with rank no greater than the source frame count, and bounds long-frame energies by the committed PCM16 triangular-window maximum.

Identity-bearing decimal strings are length-bounded before integer conversion so malformed untrusted envelopes fail closed rather than escaping verification.

## Identity path

```text
source bytes
-> source_sha256
-> PCM data bytes
-> pcm_s16le_sha256
-> frozen v0.1 short analysis
-> v0.1 percept + matrix commitments
-> v0.2 long analysis + transient/channel observations
-> v0.2 percept core
-> domain-separated percept_sha256
```

Optional full spectral evidence is a separately verified sidecar receiver. Sidecar verification reconstructs both spectral profiles back to one PCM16 waveform, checks that waveform against `pcm_s16le_sha256`, rebuilds the frozen v0.1 percept identity, and cross-checks transient/channel observations. It does not replace the compact percept identity.

The public sidecar writer only accepts an envelope that exactly matches deterministic v0.2 analysis rebuilt from the supplied WAV.

## Source lineage

Design references are pinned in `docs/PROVENANCE.md`.

Important sources:
- QSOLKCB/SONIFICATION
- QSOLKCB/SPECTRAL
- QSOLKCB/E8_MUSIC v1.1.0
- QSOLKCB/OPT
- SoundStream, arXiv:2107.03312

No SoundStream code or model weights are vendored.

## Development rules

1. Preserve the L0-L4 layer boundary.
2. Preserve frozen `qsol-map-fixed-fft-v0.1` behavior and golden vectors.
3. Fail closed on unsupported canonical inputs and malformed verification data.
4. Never insert floats into identity-bearing JSON.
5. Large exact integers must be canonical decimal strings; untrusted decimal fields must be bounded before `int()` conversion.
6. Preserve source, PCM, short-matrix, long-matrix, sidecar and percept commitments independently.
7. Sidecar acceptance must bind reconstructed short/long evidence to one PCM waveform, its PCM hash, the frozen v0.1 percept, transient observations, and channel relationships.
8. Never downmix channels implicitly.
9. High sample rate permits analysis of represented bins above conventional human-audible ranges; it does not prove sensor response or physical ultrasonic validity.
10. Learned models must be versioned and hash-bound when L2 is added.
11. Keep a deterministic reference path before optimizing.
12. Consult QSOLKCB/OPT before changing test, DSP, parallel, or Lean CI performance.
13. Do not weaken tests or claim portable speedups without target-repo measurements.
14. Run the complete suite after every behavior change.

## Commands

Frozen v0.1:

```bash
python3 -m qsol_map analyze input.wav -o percept-v01.json
python3 -m qsol_map verify percept-v01.json
```

v0.2:

```bash
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json --sidecar spectral-v02.ndjson
python3 -m qsol_map verify-v0.2 percept-v02.json
python3 -m qsol_map verify-sidecar-v0.2 percept-v02.json spectral-v02.ndjson
```

Output collisions are rejected before writing, including case-equivalent nonexistent names when the target filesystem is case-insensitive.

Benchmark from a checkout:

```bash
python3 scripts/benchmark_v02.py
```

The benchmark is environment-scoped evidence only, not a portable speed claim or CI performance gate.

Tests:

```bash
python3 -m unittest discover -s tests -v
```

## Next major phase

See `ROADMAP.md`. The next major protocol addition is v0.3 L2 learned-token reception: exact model/weights/codebook/preprocessing identities, separately committed token streams, and comparisons against independently preserved L1 evidence.
