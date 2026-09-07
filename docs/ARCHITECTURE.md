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

The complete quarter-wave Q15 table, quadrant/sine reconstruction and long FFT are normative in `spec/QSOL-MAP-MULTIRES-v0.2.md`. Section 4.1 specifies ten-bit input reversal, widths 2 through 1024, `offset*(1024/width)` twiddle indices and exact scaled butterflies. Each butterfly scales the upper input by 32768 and combines it with the lower input times the committed twiddle. There is no per-stage division or final normalization. Bins 0..512 are retained in natural order. Conformance tests execute the published algorithm against complete coefficient rows.

The same graph derives **per-bin coefficient divisors** for every long event. Input real divisors start at 1 and imaginary divisors at 0 (identically zero). Multiplication scales by the absolute Q15 factor; sums/differences take the gcd. Every reported event component obeys the resulting `D_real[k]` and `D_imag[k]`, with divisor zero requiring zero. Every aggregate bin, including multi-event sums, obeys `g[k]=gcd(D_real[k]^2,D_imag[k]^2)` because each summand does. Each event denominator obeys `gcd(g[k])=2^64`; each numerator obeys `gcd(k*g[k])`. These rules include bin 256 and ordinary bins such as bin 8. Section 4.2 defines them normatively.

Single-row endpoint-square and two-square restrictions are different: sums of powers need not remain squares or sums of two squares. Those restrictions remain single-event-only; divisibility applies to all events and their aggregate sums. The transform does not depend on unstated rounding, runtime trigonometry or an ad hoc list of bins.

The long profile provides finer frequency-bin spacing while the short profile preserves finer temporal sampling. Neither is claimed to be a complete perceptual model.

## 7. High-sample-rate treatment

For sample rate `f_s`, long bin `k` represents `k*f_s/1024` exactly as a rational frequency. v0.2 retains represented bins to Nyquist without a psychoacoustic low-pass filter.

Aggregate power is grouped into authored regions:

```text
[0, 20 kHz)
[20 kHz, 40 kHz)
[40 kHz, Nyquist]
```

These labels do not establish sensor bandwidth, physical ultrasonic validity or a universal biological hearing limit. They describe represented digital-signal regions under the observation contract.

## 8. Deterministic transient candidates

Candidates derive from consecutive frozen v0.1 short-window energies:

```text
current > previous
and
2 * current >= 3 * previous
```

The authored rule is `energy-rise-3-over-2-v0.2`. A zero previous energy gives `rise_ratio: null`; otherwise the finite ratio is stored as exact decimal-string numerator/denominator.

Energies and summaries obey source-sized PCM16 short-window maxima. Fewer than two short frames give zero totals. Positive delta sums fit transition multiplicity, and every omitted candidate contributes at least one unit.

The reported 16 candidates form the descending-delta/ascending-frame prefix. Earlier omitted frames cannot tie the weakest reported delta. Known neighboring energies constrain candidate eligibility in both mixed and all-candidate sets: P implies `d>=ceil(P/2)`, C implies `d>=C-floor(2C/3)`, and two known energies require exact `d=C-P` and the onset predicate. Enough eligible omitted frames and positive mass must exist.

A maximum stronger than the reported candidate maximum must be realized by an unreported non-candidate, respecting known adjacent energies, source bounds and the strict non-candidate threshold `2*C<3*P`. With no fixed neighbor this gives `d<=min((Pmax-1)//2,(Cmax-1)//3)`. Its unreported mass must be sufficient. Total unreported mass also fits the sum of non-candidate caps after exactly the omitted-candidate count of feasible candidate-cap replacements, choosing the largest candidate-minus-noncandidate gains. Specification sections 7 and 7.1 define the exact necessary capacity rules; they do not reconstruct the entire short-energy chain.

One/two-sample short tails require energies `x^2` or `x^2+4*y^2` for PCM16 integers. Exact squared-tail witnesses also constrain shared contributions to the preceding overlapping short frame, including bounded non-overlap residual feasibility. The same tiny-window rules apply to long events.

If every covering long-event energy in a channel is zero, strictly positive window weights prove the source samples are zero. Candidate count/list and both transient summaries must then be zero/empty.

This is a deterministic L1 rule, not a validated model of human onset perception.

## 9. Channel relationships

Channels remain independent and are never implicitly downmixed. Each pair `i<j` records exact source dot product/sign, left/right energies, sum/difference energies and zero-lag correlation squared when both energies are nonzero.

The complete Gram matrix must be positive semidefinite with rank no greater than source frame count. This is real-vector feasibility, not by itself PCM16 integer realizability.

One-frame sources bind sample energy and signed pair products to DC coefficients divided by `32768^10`. Two-frame sources derive exact `x=(D+N)/2`, `y=(D-N)/4` from permitted endpoint signs, enforce signed PCM16 range and `x^2+4*y^2=W`, and use those same candidates for a joint Gram assignment when multichannel. Mono still requires the endpoint/energy witness. Tiny tails of longer sources receive the separate weighted-energy rules, not complete-source endpoint reconstruction.

Complete three- and four-frame multichannel sources require one joint endpoint-compatible PCM16 assignment matching every Gram entry, source energy and long-window energy. Specification section 8.2 and `short_source_witnesses.py` define the bounded solver:

```text
E = x^2+y^2+z^2+t^2
W = x^2+4*y^2+9*z^2+16*t^2
A = (D+N)/2 = x+3*z
B = (D-N)/4 = y+2*t
y = B-2*t
(x-3*z)^2 = 2*(W-4*y^2-16*t^2)-A^2
```

For three frames t=0; four-frame candidates enumerate at most 65536 signed PCM16 t values for each of at most four endpoint sign pairs. Exact square/divisibility checks recover x and z. Every candidate must reproduce E, W and the observed endpoint magnitudes/signs, including the asymmetric -32768/+32767 limits. One common assignment must satisfy all channel dot products. Separate per-pair or energy-only witnesses cannot override reported endpoint signs. The existing three-frame Gram/window checks remain necessary; the public verifier further filters by endpoint evidence.

Three-frame mono has no Gram diagonal, so section 8.1 uses W and endpoint powers/signs to derive at most eight PCM16 triples by the same t=0 algebra without an E constraint. Only omitted endpoints permit a choice of sign.

These exact short-source feasibility checks do not verify unreported coefficients, matrix commitments or source hashes, and are not applied to three/four-sample tails of longer sources. They do not infer speaker geometry, source direction or perceived stereo width.

## 10. Compact packet and complete sidecar evidence

The compact packet contains aggregate/selected observations and commitments to full short/long matrices. The separately verified sidecar schema is `qsol-map-spectral-sidecar-v0.2`: one header, every short row, every long row, then a receipt trailer, in deterministic channel/frame order.

Every record is exact UTF-8 terminated by LF; CRLF is noncanonical even if text translation could hide it. Each coefficient is `["real","imag","power"]`, with bounded canonical decimals and exact `power=real^2+imag^2`.

Seekable verifier inputs, including StringIO, begin at logical zero; nonzero positions are rejected without consumption or rewinding. Already-zero binary-backed text wrappers are synchronized before exact reads. Non-seekable binary-backed inputs bypass tell/seek. Explicit iterables are the complete supplied sequence, not proof of previously discarded content. StringIO newline=None is rejected at verification because it may already have erased CRLF; explicit newline="" and newline="\n" inputs remain supported.

The sidecar verifier checks:
- canonical UTF-8/LF encoding and bounded reads;
- exact header identity and plain non-Boolean positions;
- deterministic order, coefficient arithmetic and receipts;
- reconstructed short/long matrix commitments;
- exact inverse PCM16 reconstruction with overlap, window divisibility, ranges and tails;
- equality of reconstructed profiles and interleaved PCM SHA-256;
- rebuilt frozen-v0.1 percept, long events, transients and channel relationships;
- no missing, extra or decode-failed records, including failures after a valid trailer.

Before rebuilding analysis or touching output, the writer validates PCM16Wave metadata, immutable tuple-of-tuples dimensions and plain signed PCM16 samples. It recomputes the frame-major/channel-order signed little-endian PCM digest in bounded chunks and requires equality. It then rebuilds v0.2 and requires exact canonical-envelope equality, including matrix and observation commitments. The destination must be empty, seekable and at zero.

Binary-backed text output writes exact UTF-8; translating StringIO destinations are rejected. Legal short writes are completed; invalid/stalled counts raise OSError, and destination exceptions propagate without a successful receipt. Partial output can remain; no rollback or durable-storage guarantee is implied. PCM16Wave does not retain original RIFF bytes, so this check cannot recompute `source_sha256` or authenticate the recording.

The verifier validates compact input before allocating channel spools and uses bounded temporary spools rather than full in-memory matrices/waveforms. The sidecar receives committed L1 evidence; it does not replace compact identity.

## 11. Verification boundary

v0.2 verification fails closed on malformed untrusted input. Decimal strings are bounded before integer conversion, Boolean/int aliases are rejected, and canonical-byte comparison is used where exact typed structure matters.

Long/transient energies obey source/window maxima and finite-transform bounds. Short-source joint feasibility has the precise scope in sections 8.1 and 8.2 of the specification; it is not a general arbitrary-length waveform proof.

For one long event, aggregates are exact row powers and receive the bounded two-square filter: odd part 1 modulo 4 and even valuations at `{3,7,11,19,23,31}`. Endpoints require exact squares with roots divisible by `32768^10`. These square restrictions do not apply to multi-event sums. In contrast, **per-bin coefficient divisors**, aggregate power divisors and each event denominator/numerator gcd divisor apply regardless of event count, as described in section 6.

Reported single-event endpoint signs obey source-tail even/odd window congruences and energy parity. Endpoint magnitude M obeys `M^2<=a*W`; equality forces a constant or alternating-constant windowed vector, which must divide by every weight into PCM16 samples and reproduce W and both endpoint observations. This is an exact equality witness, not merely another inequality.

Selected power subtotals cannot exceed aggregate bins; fully selected bins require equality, including zero selections. Omitted-bin caps honor ascending-bin ties. One joint nonnegative integer residual allocation must also match each event denominator and aggregate bin, exclude selected cells and respect those cutoff capacities. Integer max-flow decides this necessary allocation condition. It does not prove per-cell transform realizability or simultaneous event centroid moments.

Each event centroid separately obeys `K<=N<=K+512*(D-S)`, with selected total S and selected weighted total K. Summed event denominators/numerators equal the aggregate total/weighted total. Rehashing does not waive arithmetic, divisibility or joint-allocation checks.

Transient validation preserves deterministic cutoff, adjacency, exact complete summaries, attainable maxima and classification-aware total capacity. The zero long state forces zero transients. Full sidecar reconstruction remains the complete evidence check.

Output collisions use open-file identities and filesystem case/normalization equivalence. The CLI reserves nontruncating regular output handles before analysis, revalidates reserved paths, and writes through held descriptors instead of following replacements. This is not an atomic multi-file transaction.

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
