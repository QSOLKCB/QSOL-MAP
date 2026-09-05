# AGENTS.md

Machine-oriented repository rules for QSOL-MAP.

## Authority order

1. Preserve correctness and declared scientific/epistemic boundaries.
2. Preserve canonical identity and replay behavior.
3. Preserve tests and golden vectors.
4. Optimize only after the above are protected.

## Layer firewall

The repository uses five distinct layers:

- L0: source / physical signal encoding
- L1: deterministic acoustic observation
- L2: learned tokenization
- L3: semantic interpretation
- L4: human subjective or experimental report

Never collapse these layers in code, schema, documentation, tests, or user-facing claims.

Forbidden examples:
- calling an L2 token a measured frequency;
- calling an L3 label an objective property of the waveform;
- claiming L1 equals human hearing;
- claiming an AI has subjective auditory experience because it can classify or compare percept packets.

## Canonical profile rules

For `qsol-map-fixed-fft-v0.1`:

- no runtime random input;
- no runtime trigonometric functions;
- no float in identity-bearing JSON;
- no hidden resampling or channel collapse;
- no timestamps, filenames, paths, UI state, playback state, or environment observations in percept identity;
- unsupported WAV structures fail closed;
- large exact integer observations are decimal strings;
- source, PCM, complex-matrix, power-matrix, and percept hashes remain distinct commitments.

Changing any identity-bearing rule requires a new profile/version identifier and new golden vectors.

## Optimization rules

Consult QSOLKCB/OPT before performance work.

Apply these principles:
- correctness outranks speed;
- keep the deterministic reference path;
- use minimal fixtures that still exercise the invariant;
- reuse computations only behind explicit equality/invariant gates;
- precompute static DSP structures;
- do not cargo-cult worker counts, block sizes, tolerances, or benchmark numbers;
- benchmark the target repository before making a speedup claim;
- never skip semantic coverage merely to reduce CI time.

Current CI intentionally avoids dependency installation and duplicate runtime matrices. Do not add expensive lanes without a contract reason.

## Testing

Required before proposing a behavior change:

```bash
python3 -m unittest discover -s tests -v
```

Golden-vector changes require an explicit explanation of why canonical identity changed.

## Learned models

L2 is not implemented yet. When it is introduced:
- store or identify the exact architecture/version;
- bind model weights and codebooks by cryptographic hash;
- keep token hashes separate from L1 hashes;
- never make the learned path the sole authority for L1 reconstruction or measurement;
- document nondeterministic accelerator/runtime behavior honestly.

## Documentation

Keep `README.md` human-readable and `README4AI.md` compact and machine-oriented. Update `ROADMAP.md`, `docs/ARCHITECTURE.md`, and `docs/CLAIM_BOUNDARIES.md` when protocol boundaries change.
