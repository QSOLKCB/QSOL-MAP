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

### Frozen v0.1

For `qsol-map-fixed-fft-v0.1`:

- no runtime random input;
- no runtime trigonometric functions;
- no float in identity-bearing JSON;
- no hidden resampling or channel collapse;
- no timestamps, filenames, paths, UI state, playback state, or environment observations in percept identity;
- unsupported WAV structures fail closed;
- large exact integer observations are decimal strings;
- source, PCM, complex-matrix, power-matrix, and percept hashes remain distinct commitments.

The published v0.1 behavior and golden vectors are frozen. v0.2 must not alter them.

### v0.2 multi-resolution L1

For `qsol-map-multiresolution-v0.2` and `qsol-map-fixed-fft-1024-v0.2`:

- preserve the frozen v0.1 short reference unchanged;
- use the committed 1024-point Q15 twiddle/window contract for the long reference;
- retain represented bins up to source Nyquist without psychoacoustic low-pass filtering;
- do not infer microphone/sensor bandwidth from sample rate alone;
- keep channels independent and never downmix implicitly;
- transient candidates are authored deterministic L1 events, not human-onset claims;
- a rise from zero previous energy uses `rise_ratio: null`, never a zero denominator;
- sidecar records must be canonical NDJSON in exact deterministic order;
- sidecar integer position fields must be plain non-Boolean integers;
- untrusted decimal strings must be canonical and bounded before integer conversion;
- compact percept, short matrices, long matrices, sidecar records, sidecar receipt, source and PCM commitments remain separately identified;
- output-path collisions that would destroy a percept or sidecar must fail before writing.

Changing any identity-bearing rule requires a new profile/version identifier and new golden vectors unless correcting a demonstrated implementation error before the profile is released.

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

The v0.2 benchmark is an environment-scoped observation tool, not a CI performance gate. It must remain runnable from an ordinary repository checkout.

Current CI intentionally avoids dependency installation and duplicate runtime matrices. Do not add expensive lanes without a contract reason.

## Testing

Required before proposing a behavior change:

```bash
python3 -m unittest discover -s tests -v
```

Golden-vector changes require an explicit explanation of why canonical identity changed.

v0.2 changes must also preserve the frozen v0.1 golden hash.

## Learned models

L2 is not implemented yet. When it is introduced:
- store or identify the exact architecture/version;
- bind model weights and codebooks by cryptographic hash;
- keep token hashes separate from L1 hashes;
- never make the learned path the sole authority for L1 reconstruction or measurement;
- document nondeterministic accelerator/runtime behavior honestly.

## Documentation

Keep `README.md` human-readable and `README4AI.md` compact and machine-oriented.

When protocol boundaries change, update at minimum:
- `README.md`;
- `README4AI.md`;
- `ROADMAP.md`;
- `docs/ARCHITECTURE.md`;
- `docs/CLAIM_BOUNDARIES.md`;
- the relevant versioned specification.
