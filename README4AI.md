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

## Current implementation

`qsol-map-fixed-fft-v0.1` is the only implemented canonical analysis profile.

Input:
- strict RIFF/WAVE PCM format 1;
- PCM16 little endian;
- 1 to 8 channels;
- no implicit resampling or downmix.

Identity path:
```text
source bytes
-> source_sha256
-> PCM data bytes
-> pcm_s16le_sha256
-> exact per-channel fixed-integer analysis
-> percept core
-> domain-separated percept_sha256
```

The FFT reference uses an exact integer triangular-window rule and frozen Q15 twiddle tables with exact unbounded integer arithmetic. Runtime trigonometric floating point is forbidden from the profile.

## Source lineage

Design references are pinned in `docs/PROVENANCE.md`.

Important sources:
- QSOLKCB/SONIFICATION
- QSOLKCB/SPECTRAL
- QSOLKCB/E8_MUSIC v1.1.0
- QSOLKCB/OPT
- SoundStream, arXiv:2107.03312

No code from SoundStream is vendored.

## Development rules

1. Preserve the layer boundary.
2. Fail closed on unsupported canonical inputs.
3. Never insert floats into identity-bearing JSON.
4. Large exact integers must be decimal strings.
5. Preserve source and PCM hashes independently.
6. Learned models must be versioned and hash-bound when L2 is added.
7. Keep a deterministic reference path before optimizing.
8. Consult QSOLKCB/OPT before changing test, DSP, parallel, or Lean CI performance.
9. Do not weaken tests or claim portable speedups without target-repo measurements.
10. Run the complete suite after every behavior change.

## Commands

```bash
python3 -m unittest discover -s tests -v
python3 -m qsol_map analyze input.wav -o percept.json
python3 -m qsol_map verify percept.json
```

## Near-term work

See `ROADMAP.md`. The next major additions are multi-resolution deterministic spectral evidence and an L2 learned-token receiver that is explicitly derivative of, and separately committed from, L1.
