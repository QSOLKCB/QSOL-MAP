# Claim Boundaries

## What QSOL-MAP v0.1.0 may claim

For an accepted PCM16 RIFF/WAVE input and the frozen `qsol-map-fixed-fft-v0.1` profile, the reference implementation may claim that:

1. the complete input bytes are identified by SHA-256;
2. the PCM data chunk is independently identified by SHA-256;
3. channels are analyzed independently without hidden downmixing;
4. the exact triangular-window rule and committed Q15 twiddle constants are used;
5. the transform is computed with deterministic exact integer operations in the Python reference;
6. aggregate power and compact frame observations are derived from that transform;
7. complete complex and power matrices are cryptographically committed;
8. the canonical percept core receives a domain-separated SHA-256 identity;
9. the published golden vector protects the frozen reference behavior.

The v0.1 profile remains unchanged by v0.2.

## What QSOL-MAP v0.2.0 additionally may claim

For an accepted source and `qsol-map-multiresolution-v0.2`, the reference implementation may additionally claim that:

1. the frozen v0.1 percept and per-channel matrix identities are carried forward as the short reference;
2. a separate deterministic 1024-sample / 512-hop long reference uses the exact normative table and FFT algorithm in `spec/QSOL-MAP-MULTIRES-v0.2.md`, with exact unbounded-integer arithmetic;
3. long complex/power matrices have independent commitments, represented bins are retained to Nyquist without psychoacoustic filtering, and the authored 20/40 kHz region subtotals are derived from those bins;
4. the versioned `energy-rise-3-over-2-v0.2` rule produces deterministic candidates from frozen short energies, with null ratios for zero previous energy;
5. energies and summaries obey source/window bounds, transition multiplicity, deterministic top-16 ordering, omitted-candidate adjacency and classification-aware mass capacities;
6. channel relationships preserve channels independently, require exact identities, consistent energies, PSD and rank bounds, with additional integer checks for short sources;
7. complete two-, three- and four-frame multichannel observations require one joint signed PCM16 assignment matching Gram products, long energies and endpoint evidence; mono two/three-frame sources retain their own exact endpoint/energy witnesses;
8. one/two-sample long and reported short tails require exact weighted-energy feasibility and the stated overlap constraints;
9. optional canonical NDJSON sidecars carry every short/long complex row and independently verify ordering, typed positions, arithmetic, receipts and matrix commitments;
10. sidecars reconstruct both profiles to one PCM16 waveform, bind the PCM digest, rebuild frozen-v0.1 identity and cross-check long events, transients and relationships;
11. writers validate immutable sample layout and recomputed PCM digest before rebuilding the envelope or touching an empty seekable destination at zero;
12. legal partial writes are completed and invalid progress/errors prevent a successful receipt;
13. exact UTF-8/LF verification rejects noncanonical CRLF hidden by translating inputs, and seekable inputs cannot skip prefixes;
14. malformed bounded-decimal/type/recursion cases fail closed;
15. output collisions are rejected before writes, including case/Unicode-equivalent filesystem aliases; writes use reserved handles rather than replacement pathnames;
16. frozen v0.1, v0.2 and sidecar golden identities remain protected;
17. single-event aggregate powers receive bounded necessary two-square checks and exact endpoint squares/scale, without claiming complete large-integer factorization;
18. **per-bin coefficient divisors** derived from the frozen butterfly graph constrain every event's reported components and every aggregate power, including multi-event sums; event denominators/numerators retain the gcd divisors of their summed terms, including the `2^64` denominator divisor;
19. reported endpoint signs obey window congruences and single-event Cauchy equality requires a weight-divisible PCM16 witness reproducing both endpoints and energy;
20. selected/omitted powers obey exact fully-selected-bin totals, tie-aware cutoffs, one joint residual allocation and per-event centroid bounds;
21. zero energies in all covering long events force zero/empty transients;
22. one-frame signed DC samples fix relationship dot-product signs.

These are implementation conformance claims within the boundaries below, not a blanket proof of arbitrary-length compact waveform realizability.

## What QSOL-MAP v0.2.0 does not claim

It does not claim:

- that an AI subjectively hears or experiences music;
- that L1 is equivalent to a human auditory system;
- that the packet is a complete psychoacoustic model;
- that the packet or sidecar is a lossless representation of the waveform;
- that two percept packets with similar features necessarily sound similar to humans;
- that spectral power alone captures timbre, rhythm, harmony or musical meaning;
- that the transient rule is equivalent to a human auditory onset percept or a validated MIR onset detector;
- that channel-pair observations infer speaker geometry, source direction or perceived stereo width;
- that the current transforms are optimal, real-time, or compression-efficient;
- that a learned neural codec has already been implemented;
- that SoundStream code, weights or codebooks are included;
- that any E8, qutrit, quantum, cosmological or other symbolic interpretation is intrinsic to the audio;
- that frequencies above conventional human hearing are present unless the source capture and sampling chain actually preserved represented energy there;
- that a high sample rate proves the microphone or recording hardware had usable response all the way to Nyquist;
- that a cryptographic hash proves scientific validity or authenticity of the original physical event;
- that the benchmark harness establishes portable performance.

## Nyquist and high-sample-rate boundary

For a signal sampled at `f_s`, the represented band is bounded by the sampling process and Nyquist `f_s/2`. Analysis above conventional human-audible ranges describes supplied digital values under the declared transform.

It does not establish original physical ultrasonic energy, accurate preservation by microphone/ADC/processing, a universal 20 kHz biological cutoff, or perceptual significance to humans.

## Twiddle and deterministic-transform boundary

The versioned specification publishes all 257 normative quarter-wave integers and the exact quadrant/sine reconstruction. Section 4.1 specifies ten-bit input reversal, ten radix-2 stages, twiddle schedule, exact butterflies with upper-input scaling by 32768, no division/normalization and retained natural-order bins 0..512. An executable specification test compares complete rows. Using the same table with different arithmetic is not conformance. No unstated floating-point rounding or runtime trigonometric generation is permitted.

The graph derives **per-bin coefficient divisors**: input real divisor 1, input imaginary divisor 0; multiplication scales by the absolute integer factor and addition/subtraction takes the gcd. Every event's reported components satisfy `D_real[k]` and `D_imag[k]`, with zero divisor requiring zero. Define `g[k]=gcd(D_real[k]^2,D_imag[k]^2)`. Every aggregate bin, including multi-event sums, is divisible by g[k] because every individual event power is. Each event denominator is divisible by `gcd(g[k])=2^64`; each numerator by `gcd(k*g[k])`. Section 4.2 is normative.

Divisibility survives summation; single-row square restrictions do not. Only single-event aggregates receive the odd-part/two-square filter at primes `{3,7,11,19,23,31}` and endpoint perfect-square checks with roots divisible by `32768^10`. Multi-event endpoint sums need not be squares, but still obey their power divisor. The bounded filter is not a complete two-square existence proof, nor does passing all divisibility checks prove a complete transform row or source waveform.

A reported one-event DC/Nyquist component preserves its signed scaled real value. The pair obeys source-tail congruences `D+N=2*sum(even w*x)` and `D-N=2*sum(odd w*x)` using available window-coefficient gcds. Only omitted endpoints permit either sign. Endpoint and energy parity agree, and each magnitude M satisfies `M^2<=a*W`. Equality fixes a constant or alternating-constant windowed vector; it must divide by every weight into signed PCM16 samples and reproduce W and both endpoint observations. This is exact equality-case evidence, not just a loose upper bound.

A bin selected in every event has aggregate equal to its selected subtotal, counting zeros. Other bins may contain unreported power within each event's cutoff. Earlier omitted bins must be strictly below the weakest selected power; later omitted bins may tie. Event row residuals and aggregate column residuals must admit one nonnegative integer allocation, excluding selected cells and obeying those capacities. Max-flow verifies this necessary condition. It does not prove per-cell coefficient/power feasibility, per-cell transform divisibility, or a shared waveform.

Each event centroid separately satisfies `K<=N<=K+512*(D-S)`, where S/K are selected total/weighted power and D/N are denominator/numerator. Global event totals agree with aggregate total/weighted power. These bounds do not assert that the residual allocation simultaneously realizes each event's exact moment.

## Transient boundary

The exact authored rule is:

```text
current > previous
and
2 * current >= 3 * previous
```

Candidate count and selection are deterministic L1 output, not claims about human onset perception. A zero previous energy has null ratio. Source/tail maxima, exact tiny-tail energies, transition-count bounds, shared reported-energy consistency and overlap constraints remain mandatory.

The reported list is the descending-delta/ascending-frame top 16. Omitted ties are allowed only at later frames. In mixed and all-candidate sets, known previous/current energies constrain which omitted frames can be candidates and their minimum or exact delta. Sufficient eligible frames and positive mass must exist. Complete reported candidate sets fix both summary statistics exactly; when all transitions are candidates, omitted mass fits their cutoff allowances and the maximum is the strongest candidate.

A maximum stronger than the strongest reported candidate requires a non-candidate transition compatible with known neighbors and source bounds, with enough unreported mass. For positive delta d, non-candidate status requires `P>=2*d+1`, `C>=3*d+1`; with no fixed energy this yields `d<=min((Pmax-1)//2,(Cmax-1)//3)`.

Total unreported mass also fits the sum of non-candidate caps after exactly the declared omitted-candidate count of feasible cap replacements, choosing the largest candidate-minus-noncandidate gains. Specification section 7.1 defines this necessary classification-aware upper bound. It is not exact feasibility of the complete shared short-energy chain.

One/two-sample tails require PCM16 energies `x^2` or `x^2+4*y^2`; shared squared-tail witnesses constrain preceding overlap and bounded residual feasibility. Zero energy in all covering long events proves zero samples under positive weights, requiring zero candidate count, empty candidates and zero summaries.

## Channel boundary

Channels are never implicitly mixed. Pairwise dot products, sum/difference energies and correlation are exact signal quantities. PSD and rank at most frame_count establish real-vector dimensional feasibility, not integer PCM16 feasibility by themselves.

For one frame, signed DC coefficients divided by `32768^10` fix the sole samples; energies and every dot product must match those signed samples. Magnitude-only agreement is insufficient.

For complete two-frame sources, exact `x=(D+N)/2`, `y=(D-N)/4` must produce signed PCM16 samples reproducing W and reported endpoint signs. Multichannel Gram assignments must use these same candidates. Mono sources have no Gram records but still require endpoint-compatible energy. The weaker `D^2+N^2=2W` identity alone is not enough.

Complete three- and four-frame multichannel sources use the exact shared witness in specification section 8.2. Each candidate matches its Gram diagonal E, weighted energy W and both endpoint magnitudes plus reported signs:

```text
E = x^2+y^2+z^2+t^2
W = x^2+4*y^2+9*z^2+16*t^2
D = x+2*y+3*z+4*t
N = x-2*y+3*z-4*t
```

Three frames use t=0. Four-frame enumeration ranges over bounded signed PCM16 t; A=(D+N)/2 and B=(D-N)/4 give y=B-2t and `(x-3z)^2=2*(W-4*y^2-16*t^2)-A^2`. Exact square/divisibility and range checks recover every candidate, preserving -32768 and excluding +32768. One common assignment must match all Gram products; energy-only or separate pairwise witnesses cannot contradict signed endpoint evidence. This rejects orthogonal norms 1 and 7 in four frames, and opposite DC signs for three-frame channels whose Gram data forces identical vectors.

Three-frame mono retains section 8.1's at-most-eight endpoint/weighted-energy candidates with all reported signs preserved. One/two-sample tails of longer sources retain separate energy/overlap checks. The complete-source three/four-frame endpoint witness is not imposed on tails whose aggregate endpoints sum multiple events.

These checks are exact for the specified short-source Gram/energy/endpoint evidence, not unreported coefficients, full matrix commitments or source digests. Arbitrary-length compact acceptance remains a collection of necessary constraints rather than a complete waveform existence proof. Full sidecar verification separately reconstructs and binds actual PCM. None of this establishes acoustic scene geometry or spatial perception.

## Sidecar boundary

The optional `qsol-map-spectral-sidecar-v0.2` is complete spectral evidence for the declared transforms, not a replacement audio format.

Verification checks deterministic order, typed positions, arithmetic, receipts and matrix commitments. It inverts both profiles to PCM16, validates overlap/window/tail constraints, requires identical waveforms, checks interleaved PCM SHA-256, rebuilds frozen-v0.1 identity and cross-checks long events, transients and relationships.

Records are exact UTF-8/LF; CRLF is noncanonical before any translation. Seekable inputs start at logical zero, with nonzero positions rejected without consumption or rewinding. Explicit iterables represent the complete supplied sequence, not previously discarded data. StringIO newline=None verification is rejected because it may already have normalized CRLF. A late decode failure is still invalid evidence. Reads and temporary reconstruction spools are bounded.

The writer validates PCM16Wave metadata, immutable dimensions and plain PCM16 samples, then recomputes the actual interleaved digest before analysis rebuild or output. The rebuilt envelope must match exactly. Destinations must be empty, seekable and at zero. Legal partial writes are completed; invalid/stalled counts and destination errors prevent a successful receipt. Partial output may remain; no rollback, final filesystem flush or durable-storage guarantee is claimed.

PCM16Wave does not retain original RIFF bytes, so checking its sample digest cannot recompute `source_sha256` or authenticate the recording. A valid sidecar establishes the declared serialization/commitment/reconstruction relationship, not scientific meaning or authenticity.

## Determinism boundary

The profiles are versioned exact-integer Python references. Twiddle data and the full long FFT algorithm are published as identity-bearing protocol material. Executable specification tests guard against drift, not universal correctness of independent implementations.

A future implementation claims conformance only after passing frozen vectors for parsing, windowing, coefficients, matrix commitments, serialization, percept identity and applicable sidecar identity/verification.

## Verification boundary

Verification fails closed on malformed untrusted documents. It requires bounded canonical decimals, exact types, source/window bounds, transform divisibility at component/bin/event-sum levels, signed endpoint congruence/equality witnesses, tiny-tail feasibility, joint short-source PCM assignments, selected/omitted power and centroid constraints, and deterministic transient arithmetic/adjacency/capacity rules.

Recomputing outer hashes does not waive these constraints. Writer sample commitments are recomputed, short writes are completed or fail, canonical bytes are checked before translation, and output aliases are rejected using filesystem identity and reserved handles.

These checks establish protocol validity within the stated scope, not origin trust or complete arbitrary-length integer realizability from compact evidence alone.

## Learned-model boundary

When L2 is introduced, the following must remain separately identified:

```text
L1 percept hash
model/weights/codebook hash
L2 token hash
runtime/inference identity where required
```

A model update creates a new learned representation context even if the source audio is unchanged.

## Human-data boundary

Human ratings belong at L4. Any statistical mapping from L1 or L2 to human ratings belongs at L3.

The correct form is:

```text
model predicts that participants under protocol P tend to report X
```

not:

```text
the waveform objectively is X
```

unless X is separately defined as a physical measurement.
