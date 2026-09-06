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
- represented discrete-time bandwidth implied by the sampling process.

L0 answers: **what bytes and sampled signal were supplied?**

It does not answer what the signal means.

### L1 - deterministic acoustic observation

Implemented examples:
- waveform statistics;
- exact windowed spectral coefficients;
- spectral power;
- phase-bearing complex coefficients;
- short- and long-window frame events;
- deterministic transient candidates;
- exact channel-pair relationships;
- represented-frequency support metadata;
- optional full-spectral sidecar evidence.

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

## 4. Frozen v0.1 data flow

The published `qsol-map-fixed-fft-v0.1` profile remains unchanged:

```text
WAV bytes
  |
  +-- SHA256 -------------------------------> L0 source identity
  |
  +-- strict RIFF/WAVE parser
          |
          +-- PCM16 payload SHA256 ----------> L0 sample-payload identity
          |
          +-- per-channel 256 / 128 analysis
                  |
                  +-- waveform observations
                  +-- exact integer triangular window
                  +-- frozen-Q15 exact-integer FFT
                  +-- complex matrix commitment
                  +-- power matrix commitment
                  +-- aggregate power
                  +-- sparse frame events
                          |
                          v
                     v0.1 L1 percept
```

No resampling and no downmix occur in the frozen canonical path.

## 5. v0.2 multi-resolution data flow

v0.2 extends L1 without mutating the v0.1 reference:

```text
                           PCM16 source
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
       frozen v0.1 short path        v0.2 long path
          256 / 128 frames           1024 / 512 frames
                 |                           |
                 |                    exact integer FFT
                 |                           |
                 |                    long matrix hashes
                 |                    long frame events
                 |                    frequency regions
                 |                           |
                 +-------------+-------------+
                               |
                      deterministic transient
                       candidates from v0.1
                               |
                      pairwise channel metrics
                               |
                    represented-frequency support
                               |
                               v
                  qsol-map-multiresolution-v0.2
                               |
                  canonical percept SHA-256
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
          compact L1 envelope       optional NDJSON sidecar
                                     full short+long spectra
```

The aggregate profile binds the frozen v0.1 percept hash and per-channel v0.1 matrix commitments, then adds the v0.2 long-window evidence.

## 6. Two deterministic spectral resolutions

### Short reference

`qsol-map-fixed-fft-v0.1`

- frame size: 256 samples;
- hop: 128 samples;
- bins: 0..128;
- frozen Q15 twiddles;
- exact unbounded-integer Python reference arithmetic.

### Long reference

`qsol-map-fixed-fft-1024-v0.2`

- frame size: 1024 samples;
- hop: 512 samples;
- bins: 0..512;
- exact symmetric integer triangular window;
- frozen Q15 1024-point twiddles;
- exact unbounded-integer Python reference arithmetic.

The long profile provides finer frequency-bin spacing while the short profile preserves finer temporal sampling. QSOL-MAP does not claim that either resolution is a complete perceptual model.

## 7. High-sample-rate treatment

For sample rate `f_s`, long bin `k` represents the exact rational frequency:

```text
k * f_s / 1024
```

v0.2 retains all represented bins up to Nyquist and does not apply a psychoacoustic low-pass filter.

The packet groups aggregate long-window power into authored reference regions:

```text
[0, 20 kHz)
[20 kHz, 40 kHz)
[40 kHz, Nyquist]
```

These labels do not establish sensor bandwidth, physical ultrasonic validity, or a universal biological hearing limit. They describe represented digital-signal regions under the declared observation contract.

## 8. Deterministic transient candidates

Transient candidates are derived from consecutive frozen v0.1 short-window energies using:

```text
current > previous
and
2 * current >= 3 * previous
```

The rule is explicitly authored and versioned as `energy-rise-3-over-2-v0.2`.

For a transition from zero previous energy, `rise_ratio` is `null` rather than a rational value with a zero denominator. For non-zero previous energy, the packet stores the exact finite ratio `current / previous` as decimal-string numerator and denominator.

This is a deterministic L1 event rule, not a validated model of human onset perception.

## 9. Channel relationships

Channels remain independent and are never implicitly downmixed.

For each pair `i < j`, v0.2 records exact full-source integer quantities including:

- dot product and sign;
- left/right sum of squares;
- difference and sum signal energies;
- zero-lag correlation squared when both channel energies are non-zero.

These are signal relationships. They do not infer speaker geometry, source direction, or perceived stereo width.

## 10. Compact packet and complete sidecar evidence

The compact v0.2 packet contains aggregate and selected observations plus commitments to the complete short and long complex/power matrices.

The optional sidecar schema is:

```text
qsol-map-spectral-sidecar-v0.2
```

It is canonical NDJSON containing:

1. one header;
2. every v0.1 short spectral row in deterministic channel/frame order;
3. every v0.2 long spectral row in deterministic channel/frame order;
4. one receipt trailer.

Each coefficient entry is `["real","imag","power"]`, with canonical bounded decimal strings and exact `power = real^2 + imag^2` verification.

The sidecar verifier checks:
- canonical line encoding;
- exact header identity;
- plain non-Boolean integer position fields;
- deterministic row order;
- coefficient arithmetic;
- row/record receipts;
- reconstructed short and long matrix commitments;
- no missing or extra records.

The sidecar is a receiver of committed L1 evidence. It does not replace the compact percept identity.

## 11. Verification boundary

v0.2 verifiers are fail-closed on malformed untrusted input.

Identity-bearing decimal strings are bounded before conversion to Python integers. This prevents interpreter integer-string limits from turning malformed input into uncaught verifier exceptions and also bounds verification work on attacker-controlled numeric strings.

Boolean values are not accepted where schema fields require integers, even though Python considers `False == 0` and `True == 1` in ordinary equality.

Canonical byte comparison is used where exact typed structure matters.

## 12. SoundStream relationship

SoundStream uses a learned encoder, residual vector quantizer and decoder to map waveforms into compact quantized embeddings and reconstruct perceptually similar audio.

QSOL-MAP keeps a different authority structure:

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

The future neural codec path is a receiver of the source and/or L1 evidence. It is not allowed to erase the independently inspectable L1 reference path.

## 13. Cross-modal receivers

Visual and haptic mappings belong downstream of committed evidence.

A future visual receiver may map frequency, power and phase into authored visual variables. A future haptic receiver may map selected temporal or spectral bands to actuators.

Those mappings are authored receivers. Their outputs are not intrinsic physical properties of the source.

## 14. Optimization

QSOL-MAP treats the deterministic Python implementation as the reference path.

Optimization work follows QSOLKCB/OPT:
- precompute static structures;
- batch/vectorize only behind conformance tests;
- reuse computation only when an exact invariant permits it;
- use bounded parallelism only after target measurements;
- preserve complete semantic test coverage;
- keep benchmark claims local to the measured environment.

The v0.2 benchmark is directly runnable from a repository checkout with:

```bash
python3 scripts/benchmark_v02.py
```

It is not a CI performance gate and makes no portable speed claim.

See `docs/OPTIMIZATION.md`.
