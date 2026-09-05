# QSOL-MAP

**QSOL Machine Perception Audio Protocol**

QSOL-MAP is an experimental protocol and reference implementation for representing audio as a deterministic, machine-readable acoustic observation before any learned tokenization or semantic interpretation is applied.

The project starts from a simple premise:

> Audio information does not have to be represented only as something a human ear can hear.

A machine can inspect waveform structure, complex spectral structure, phase, transients, timing, channel relationships, learned codec tokens, visual projections, haptic projections, and human perceptual reports as separate but related views of the same source.

## Core invariant

QSOL-MAP separates epistemic layers:

```text
L0  source / physical signal encoding
L1  deterministic acoustic observation
L2  learned tokenization
L3  semantic interpretation
L4  human subjective or experimental report
```

The governing rule is:

```text
L0 != L1 != L2 != L3 != L4
```

No layer may silently promote itself into another.

A neural token is not the waveform. A deterministic spectrum is not subjective hearing. A semantic label is not a measured physical property. A human report is not automatically universal perception.

## Current status

The first reference profile implements **L1 deterministic acoustic observation** for strict PCM16 RIFF/WAVE input.

```text
RIFF/WAVE bytes
      |
      +-> source SHA-256
      |
      +-> PCM16 payload SHA-256
      |
      +-> per-channel waveform observations
      |
      +-> exact integer triangular window
      |
      +-> exact-integer 256-point FFT reference
      |
      +-> complex-matrix commitment
      +-> power-matrix commitment
      +-> aggregate power by frequency bin
      +-> compact frame events with dominant components
      |
      +-> canonical percept document
      |
      +-> domain-separated percept SHA-256
```

The implementation deliberately does **not** contain a neural model yet. Learned residual-vector-quantized representations belong at L2 and will be introduced as a receiver of L1 evidence rather than as a replacement for it.

## Why this architecture

The project combines ideas already explored in related QSOL repositories:

- **QSOLKCB/SONIFICATION**: receiver-neutral committed event documents, deterministic ordering, acyclic receipts, and strict claim boundaries.
- **QSOLKCB/SPECTRAL**: deterministic DSP, WAV/PCM handling, spectral views, provenance manifests, fingerprints, and cross-modal signal experiments.
- **QSOLKCB/E8_MUSIC**: explicit separation of canonical observation from interpretive musical rendering, source-to-signal identity chains, executable conformance, and formal-assurance boundaries.
- **QSOLKCB/OPT**: correctness-preserving optimization patterns for tests, DSP, invariant-driven reuse, bounded parallel work, and future Lean CI.

The neural-codec reference point is:

> Neil Zeghidour, Alejandro Luebs, Ahmed Omran, Jan Skoglund, Marco Tagliasacchi, *SoundStream: An End-to-End Neural Audio Codec*, arXiv:2107.03312.

SoundStream demonstrates that general audio can be transformed into learned embeddings and residual-vector-quantized discrete representations. QSOL-MAP uses that as architectural motivation for a future L2 token receiver while preserving an independently inspectable L1 path.

## Quick start

No third-party Python packages are required.

```bash
python3 -m qsol_map analyze input.wav -o percept.json
python3 -m qsol_map verify percept.json
```

The current input adapter accepts:

- RIFF/WAVE;
- uncompressed integer PCM format 1;
- signed 16-bit samples;
- 1 to 8 channels;
- sample rates from 1 Hz through 768 kHz.

Unsupported or malformed inputs fail closed.

## What the packet contains

Each channel records:

- exact sample count;
- peak absolute PCM value;
- sum of squared samples;
- zero-crossing count;
- aggregate spectral power for bins `0..128`;
- a SHA-256 commitment to the complete complex transform matrix;
- a SHA-256 commitment to the complete power matrix;
- per-frame energy;
- exact rational spectral-centroid components;
- deterministic top spectral components including real, imaginary, and power values.

Large integer observations are serialized as decimal strings. Identity-bearing JSON forbids floating-point numbers.

Frequency for bin `k` is represented by the exact rule

```text
f_k = k * sample_rate_hz / 256
```

so no floating-point frequency value has to enter canonical identity.

## Determinism

The current reference profile uses:

- exact integer triangular-window coefficients;
- frozen integer complex twiddle coefficients;
- exact Python integer arithmetic;
- no runtime trigonometric evaluation;
- no random input;
- no learned model;
- canonical JSON with sorted keys;
- domain-separated SHA-256 commitments;
- no timestamps, filenames, filesystem paths, or UI state in percept identity.

The test suite contains a frozen end-to-end golden percept vector.

Cross-language conformance is a future milestone. The current claim is about the versioned Python reference contract, not every possible reimplementation.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

CI intentionally stays small and dependency-free. It follows the QSOLKCB/OPT rule that correctness outranks speed: the complete reference suite runs on every pull request and every push to `main`, while unnecessary environment setup and redundant lanes are avoided.

## Research direction

The intended stack is:

```text
                  canonical audio source
                           |
                           v
              L1 deterministic observation
                           |
             +-------------+-------------+
             |                           |
             v                           v
      exact spectral events       learned audio encoder
                                         |
                                         v
                               residual vector quantizer
                                         |
                                         v
                                  L2 token stream
                                         |
                           +-------------+-------------+
                           |                           |
                           v                           v
                    visual receiver             haptic receiver
                           \                           /
                            \                         /
                             +---------> L3 <---------+
                                      semantics
                                         |
                                         v
                              L4 human-labelled data
```

See [ROADMAP.md](ROADMAP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Claim boundary

QSOL-MAP does not claim that an AI has subjective auditory experience. It does not equate spectral analysis with human hearing, learned tokens with physical truth, or semantic labels with objective properties of music.

The current percept packet is compact and non-invertible. It is an observation record, not a lossless audio codec.

See [docs/CLAIM_BOUNDARIES.md](docs/CLAIM_BOUNDARIES.md).

## Licence

Apache License 2.0. Copyright 2026 Trent Slade / QSOL-IMC.
