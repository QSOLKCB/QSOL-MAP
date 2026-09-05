# Architecture

## 1. Objective

QSOL-MAP defines a machine-native representation stack for audio without pretending that machine analysis and human hearing are the same phenomenon.

The protocol separates source identity, deterministic analysis, learned representation, semantic inference, and human report.

## 2. Layer model

### L0 - source / physical signal encoding

Examples:
- RIFF/WAVE container bytes;
- PCM payload;
- sample rate;
- channel layout;
- captured bandwidth implied by the sampling process.

L0 answers: **what bytes and sampled signal were supplied?**

It does not answer what the signal means.

### L1 - deterministic acoustic observation

Examples:
- waveform statistics;
- exact windowed spectral coefficients;
- spectral power;
- phase-bearing complex coefficients;
- temporal frame events;
- later: transients, harmonic relationships and channel relationships.

L1 answers: **what does the frozen analysis contract deterministically observe in the supplied sampled signal?**

It is not a subjective percept.

### L2 - learned tokenization

Future examples:
- encoder embeddings;
- residual-vector-quantizer indices;
- learned audio codec tokens;
- model-specific latent sequences.

L2 answers: **how did one exact learned model encode the input?**

Every L2 result must bind the model, weights, codebooks, preprocessing and inference contract that produced it.

### L3 - semantic interpretation

Examples:
- "snare";
- "minor harmony";
- "harsh";
- "speech";
- "similar to sample B";
- predicted human perceptual scores.

L3 answers: **what interpretation did an explicit model or rule derive?**

Semantic outputs are not promoted to physical measurements.

### L4 - human subjective or experimental report

Examples:
- groove ratings;
- tension ratings;
- reported brightness;
- similarity judgments;
- accessibility studies.

L4 answers: **what did participating humans report under a defined protocol?**

Human labels may train or evaluate L3 systems, but they remain reports rather than universal signal properties.

## 3. Fundamental invariant

```text
L0 != L1 != L2 != L3 != L4
```

A result may carry explicit lineage to a lower layer, but it may not silently inherit the lower layer's authority.

## 4. Current v0.1 data flow

```text
WAV bytes
  |
  +-- SHA256 -------------------------------> L0 source identity
  |
  +-- strict RIFF/WAVE parser
          |
          +-- PCM16 payload SHA256 ----------> L0 sample-payload identity
          |
          +-- channel 0 samples
          |      |
          |      +-- waveform observations
          |      +-- integer triangular window
          |      +-- fixed integer FFT
          |               |
          |               +-- complex matrix commitment
          |               +-- power matrix commitment
          |               +-- aggregate power
          |               +-- sparse frame events
          |
          +-- channel N samples
                 |
                 +-- same frozen analysis
                          |
                          v
                     L1 percept core
                          |
                    canonical JSON
                          |
              domain-separated SHA256
                          |
                          v
                    percept envelope
```

No resampling and no downmix occur in the current canonical path.

## 5. Why the current transform is integer based

The first profile is designed to establish a simple reproducibility baseline.

Runtime signal analysis uses:
- committed integer PCM samples;
- an exact integer triangular-window rule;
- frozen Q15 complex twiddle tables;
- exact arbitrary-precision integer arithmetic.

The radix-2 transform intentionally performs no right shifts. Both paths through every butterfly receive the same Q15 scale factor at every stage. The resulting coefficient scale is large, but common within the profile and exact.

This is not presented as the fastest implementation. It is the reference path against which optimized implementations can later be checked.

## 6. Compact packet versus complete evidence

The percept packet does not embed every coefficient from every frame. Instead it includes:
- aggregate per-bin power;
- compact top-component frame events;
- selected exact waveform observations;
- a commitment to the complete complex matrix;
- a commitment to the complete power matrix.

A future sidecar format can carry the full matrices while retaining the same commitment model.

The packet is therefore intentionally **non-invertible**. It is not a lossless codec.

## 7. SoundStream relationship

SoundStream uses a learned encoder, residual vector quantizer and decoder to map waveforms into compact quantized embeddings and reconstruct perceptually similar audio.

QSOL-MAP adopts a different authority structure:

```text
L1 deterministic evidence
        |
        +----------------------+
        |                      |
        v                      v
reference analysis       learned encoder
                               |
                               v
                              RVQ
                               |
                               v
                         L2 token stream
```

The future neural codec path is a receiver of the source and/or L1 evidence. It is not allowed to erase the independently inspectable reference path.

## 8. Cross-modal receivers

Visual and haptic mappings belong downstream of committed evidence.

A future visual receiver may map:
- frequency to one visual coordinate;
- amplitude/power to luminance or magnitude;
- complex phase to a cyclic visual variable.

A future haptic receiver may map selected temporal or spectral bands to actuators.

Those mappings are authored receivers. Their outputs are not intrinsic physical properties of the source.

## 9. Optimization

QSOL-MAP treats the deterministic Python implementation as the reference path.

Optimization work should follow QSOLKCB/OPT:
- precompute static structures;
- batch/vectorize only behind conformance tests;
- reuse computation only when an exact invariant permits it;
- use bounded parallelism only after target measurements;
- preserve complete semantic test coverage;
- keep benchmark claims local to the measured environment.

See `docs/OPTIMIZATION.md`.
