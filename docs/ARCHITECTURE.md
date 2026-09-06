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

The complete identity-bearing quarter-wave Q15 table and the exact quadrant/sine reconstruction rule are normative in `spec/QSOL-MAP-MULTIRES-v0.2.md`. Section 4.1 also defines the entire long FFT: ten-bit input reversal, stage widths 2 through 1024, `offset * (1024 / width)` twiddle indices, and exact radix-2 butterfly equations. Each butterfly multiplies the upper input by 32768 and combines it with the lower input times the committed twiddle. There is no per-stage division or final normalization. The output retains bins 0..512 in ascending natural order. The conformance suite executes the published algorithm and checks complete coefficient rows against the implementation.

The long transform does not depend on an unstated rounding, stage schedule, or runtime trigonometric convention.

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

Candidate energies and summary totals must fit the source-sized PCM16 maximum induced by the frozen 256-sample triangular window. If fewer than two short frames exist, no transition can be formed and both transient summary totals are zero. The total positive delta is bounded by transition multiplicity, and candidates omitted beyond the 16 reported strongest entries still contribute at least one positive integer unit each to the summary.

Each reported previous/current short frame is also checked against its own source-tail availability. One available sample requires energy `x^2`; two require `x^2 + 4*y^2`, with signed PCM16 integers. The shared exact small-window check is used for long windows as well, so mono sources and tails do not bypass energy feasibility.

This is a deterministic L1 event rule, not a validated model of human onset perception.

## 9. Channel relationships

Channels remain independent and are never implicitly downmixed.

For each pair `i < j`, v0.2 records exact full-source integer quantities including:

- dot product and sign;
- left/right sum of squares;
- difference and sum signal energies;
- zero-lag correlation squared when both channel energies are non-zero.

The complete channel Gram matrix must be positive semidefinite and its exact rank must not exceed the source frame count. This preserves joint feasibility in the actual sample-dimensional space, rather than validating only pairwise arithmetic.

Short sources have additional integer-realizability checks. For two-frame multichannel sources, one joint feasible PCM16 vector assignment must satisfy all Gram products and reproduce each channel's exact long-window weighted energy under the committed weights. Two-frame mono sources have no Gram records but must still admit PCM16 samples with that weighted energy. Exact one/two-sample long-tail checks apply independently of total source length and channel count.

Three-frame multichannel sources likewise require one common assignment of PCM16 triples satisfying every Gram entry and each long energy. With source energy `E` and long energy `W`, the exact equations are `E = x^2 + y^2 + z^2` and `W = x^2 + 4*y^2 + 9*z^2`. The helper uses `W-E = 3*y^2 + 8*z^2` to enumerate at most 32769 third-coordinate magnitudes, derives the other squares and valid signed samples, then checks joint compatibility across all channels. Diagonal three-square checks and separate pairwise witnesses alone cannot establish this joint assignment. See specification section 8.

The three-frame mono path has no Gram energy to use, so it binds `W = x^2 + 4*y^2 + 9*z^2` to the sole long event's DC/Nyquist aggregate powers instead. Their coefficient magnitudes must be exactly divisible by `32768^10`. Enumerating the two endpoint signs gives `y = (D-N)/4` and `A = (D+N)/2`; the square `(x-3*z)^2 = 2*(W-4*y^2)-A^2` then yields at most eight signed PCM16 triples. At least one must exist. This is exact for the weighted energy and endpoint powers only, not the remaining spectral/source commitments, and is not applied to three-sample tails of longer sources. See specification section 8.1.

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

Each record is exact UTF-8 terminated by one LF byte. CRLF is non-canonical even when a text wrapper would otherwise translate it to `\n`; file-backed verification inspects the underlying bytes before newline translation.

Each coefficient entry is `["real","imag","power"]`, with canonical bounded decimal strings and exact `power = real^2 + imag^2` verification.

The sidecar verifier checks:
- canonical UTF-8/LF line encoding and bounded reads;
- exact header identity;
- plain non-Boolean integer position fields;
- deterministic row order;
- coefficient arithmetic;
- row/record receipts;
- reconstructed short and long matrix commitments;
- exact inverse reconstruction of PCM16 from both profiles with overlap, tail and window-divisibility checks;
- equality of the short- and long-profile reconstructed waveforms;
- reconstructed interleaved PCM SHA-256 against `source.pcm_s16le_sha256`;
- frozen v0.1 percept identity rebuilt from short-profile evidence;
- transient observations rebuilt from short rows;
- channel relationships rebuilt from recovered PCM;
- no missing, extra or decode-failed records.

Before rebuilding analysis or touching output, the public sidecar writer validates the supplied `PCM16Wave` immutable tuple-of-tuples layout, metadata, channel/frame counts and plain signed PCM16 samples. It hashes the actual sample payload in frame-major order with ascending channels within each frame and signed 16-bit little-endian encoding. The recomputed digest must match `pcm_s16le_sha256`; a stale digest cannot become trusted merely by rebuilding an envelope that copies it. This hash pass uses bounded payload chunks.

The writer then rebuilds the deterministic v0.2 percept from those validated samples and requires exact canonical equality with the envelope it was given. It therefore cannot issue a receipt for sidecar rows that contradict declared matrix or observation commitments. It also requires an empty seekable destination at position zero, preventing appended or stale-tail sidecars from receiving a successful receipt. Since `PCM16Wave` does not retain original RIFF bytes, this check does not recompute the separate `source_sha256` container commitment.

The exact output adapter loops until each record and LF terminator has been accepted. Binary writes use views of the remaining UTF-8 payload; text writes return character counts. Legal short writes are completed, invalid or stalled progress raises `OSError`, and destination exceptions propagate without a successful receipt. Partial output can remain on failure; no rollback or durable-storage guarantee is implied.

The verifier uses bounded temporary spools for reconstructed PCM instead of materializing complete spectral matrices or an unbounded waveform in memory.

The sidecar is a receiver of committed L1 evidence. It does not replace the compact percept identity.

## 11. Verification boundary

v0.2 verifiers are fail-closed on malformed untrusted input.

Identity-bearing decimal strings are bounded before conversion to Python integers. This prevents interpreter integer-string limits from turning malformed input into uncaught verifier exceptions and also bounds verification work on attacker-controlled numeric strings.

Boolean values are not accepted where schema fields require integers, even though Python considers `False == 0` and `True == 1` in ordinary equality.

Long-frame and transient energies are bounded by source-sized PCM16/window maxima, transform-power and ranking constraints are enforced, and short-source integer feasibility is checked where exact compact constraints are available. The channel Gram matrix must be jointly feasible in no more than `frame_count` dimensions. The one/two-sample energy checks and joint three-frame Gram/window-energy check do not claim a complete compact-only integer feasibility proof for arbitrary longer windows or full spectral commitments; full sidecar verification reconstructs the actual PCM evidence.

For a single long event, aggregate entries are exact single-row powers. A bounded two-square filter checks all bins, including omitted interior bins: each nonzero power has odd part 1 modulo 4 and even valuations of the fixed primes `{3, 7, 11, 19, 23, 31}`. DC and Nyquist additionally require exact squares. This rejects necessary-condition violations without unbounded factorization of large powers. It is not a complete two-square existence proof, and is not applied to multi-event sums. The full sidecar checks actual coefficient arithmetic separately.

Canonical byte comparison is used where exact typed structure matters.

Output-path collision checks use filesystem identity for existing paths and probe both case folding and Unicode normalization equivalence for initially nonexistent names in a shared output directory when the target filesystem aliases those spellings.

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
