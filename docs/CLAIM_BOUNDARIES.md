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

1. the frozen v0.1 percept identity and per-channel v0.1 matrix commitments are carried forward as the short-window reference;
2. a separate deterministic 1024-sample / 512-hop long-window spectral reference is computed using the exact normative frozen Q15 table and complete long FFT algorithm published in `spec/QSOL-MAP-MULTIRES-v0.2.md`, with exact unbounded-integer Python arithmetic;
3. complete long complex and power matrices receive independent cryptographic commitments;
4. represented long-window bins are retained up to source Nyquist without a psychoacoustic low-pass filter;
5. aggregate power is reported in authored `[0,20 kHz)`, `[20,40 kHz)`, and `[40 kHz,Nyquist]` reference regions when such represented bins exist;
6. deterministic transient candidates are produced by the exact `energy-rise-3-over-2-v0.2` rule applied to frozen v0.1 short-frame energies;
7. a transition from zero previous energy is represented with `rise_ratio: null`, never a zero-denominator rational value;
8. transient energies and summary totals are bounded by source-sized PCM16/frozen-window maxima, obey transition-multiplicity bounds, and include a minimum positive contribution from candidates omitted beyond the 16 reported strongest events;
9. exact pairwise channel signal relationships are recorded without downmixing, the complete Gram matrix is jointly feasible with rank no greater than the source frame count, and short sources receive additional integer-realizability checks;
10. for two- and three-frame multichannel sources, accepted compact observations admit one joint PCM16 vector assignment that matches all declared Gram products and the exact committed long-window weighted energy; mono two-frame sources and one/two-sample long or reported short tails also require exact weighted-energy realizability;
11. an optional canonical NDJSON sidecar can carry every short and long complex spectral row while remaining separately verified against compact matrix commitments;
12. accepted sidecars reconstruct exact PCM16 from both profiles, require one shared waveform, bind that waveform to `pcm_s16le_sha256`, rebuild the frozen v0.1 percept identity, and reconstruct transient/channel observations;
13. sidecar ordering, exact UTF-8/LF line bytes, coefficient arithmetic, receipt hashes and exact typed position fields are checked fail-closed before text newline translation can hide non-canonical CRLF bytes;
14. the sidecar writer validates immutable PCM16 sample layout and the recomputed interleaved sample digest before rebuilding the exact v0.2 envelope or touching its provably empty, seekable destination at position zero;
15. malformed oversized decimal strings are rejected before untrusted integer conversion can escape the verifier contract;
16. output collisions are rejected before writing, including filesystem aliases created by case folding or Unicode normalization equivalence on target filesystems that treat such spellings as identical;
17. the v0.2 golden vector protects the current multi-resolution reference behavior;
18. single-event aggregate powers, including omitted interior bins, satisfy the bounded necessary two-square checks in specification section 5, without claiming complete large-integer factorization;
19. the writer completes legal partial writes and cannot return a successful receipt after invalid write progress or a destination exception;
20. reported single-event DC/Nyquist signs are preserved and checked against the committed source-tail window congruences, while omitted endpoints remain sign-unspecified;
21. a complete two-sample channel binds its exact long energy to its scaled endpoint powers by `D^2 + N^2 = 2*windowed_energy`;
22. a complete three-sample mono witness must reproduce the sign of every reported endpoint component, not only its aggregate magnitude;
23. per-event top-component omissions respect the authored descending-power/ascending-bin tie break, and per-event centroid numerators are bounded by both selected and omitted power;
24. transient summaries with more than 16 candidates preserve the deterministic top-16 cutoff, including ascending-frame ties, and a maximum stronger than the strongest reported candidate must be realizable by a non-candidate transition with sufficient unreported positive mass;
25. for every retained bin in a single long event, the compact verifier enforces **per-bin coefficient divisors** derived directly from the frozen ten-stage integer butterfly schedule, and the single-event power obeys the corresponding squared-gcd divisor; this generalizes the former bin-256 special rule;
26. if an omitted candidate borders reported short-frame energy evidence, that known previous/current energy imposes the exact or minimum feasible candidate delta before the top-16 cutoff and omitted-mass checks are accepted;
27. if every covering long-event `windowed_energy` value for one channel is zero, the strictly positive long-window weights establish an all-zero source channel and its transient candidate count/list/sum/maximum are all zero;
28. for a one-frame multichannel source, the signed DC coefficients recover the signed sole PCM samples and each relationship dot product equals the product of those signed samples, not merely the product of their magnitudes.

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

For a digital signal sampled at `f_s`, the represented discrete-time band is bounded by the sampling process and its Nyquist frequency `f_s / 2`.

QSOL-MAP may analyze bins above conventional human-audible ranges when the source sample rate supports those represented frequencies. This means only that the supplied digital recording contains values in those represented bins under the declared transform.

It does **not** establish that:
- the original physical source contained corresponding ultrasonic energy;
- the microphone, ADC or previous processing chain preserved it accurately;
- 20 kHz is a universal biological cutoff;
- energy above 20 kHz is perceptually meaningful to humans.

## Twiddle and deterministic-transform boundary

The long transform identity is not defined by an informal phrase such as “Q15 approximation of an exponential.” The versioned v0.2 specification publishes the complete 257-entry normative quarter-wave cosine table and the exact quadrant/sine reconstruction rule that yields every long-transform integer twiddle pair.

Section 4.1 defines the full transform schedule: ten-bit input reversal, ten radix-2 stages with widths 2 through 1024, the exact twiddle-index schedule and butterfly equations, per-stage upper-input scaling by 32768, no division or final normalization, and natural-order retained bins 0..512. An executable specification test compares complete coefficient rows with the implementation. A transform using the same twiddles but different scaling or stage arithmetic is not the same profile.

Independent producers must use those exact committed integers and that algorithm. No unstated floating-point rounding, truncation, tie-breaking, library trigonometry, or runtime table generation rule is part of the canonical v0.2 identity.

For compact single-event verification, that exact butterfly graph also defines guaranteed **per-bin coefficient divisors**. Each arbitrary input real starts with divisor 1 and each identically-zero input imaginary starts with divisor 0. Multiplication by an integer Q15 factor multiplies a nonzero divisor by the factor's absolute value, while every exact sum/difference takes the gcd of the term divisors. Propagating those rules through all ten stages yields `D_real[k]` and `D_imag[k]` for every retained bin. A reported real/imag coefficient must be divisible by its derived divisor, with divisor 0 requiring exact zero. The corresponding single-event power must be divisible by `gcd(D_real[k]^2, D_imag[k]^2)`. This subsumes the earlier bin-256 `32768^20` power rule and constrains ordinary bins such as bin 8 as well. These are necessary divisibility constraints of one transform row and are not imposed on aggregate sums over multiple long events.

For a single long event, every aggregate bin equals one integer complex power, including bins omitted from the compact components. The compact verifier additionally requires each nonzero power's odd part to be 1 modulo 4 and its valuations at primes `{3, 7, 11, 19, 23, 31}` to be even; endpoint powers require exact squares whose square roots are divisible by `32768^10`. This scale requirement applies to every single-event channel, not only three-frame mono sources, and permits zero. These bounded necessary checks reject impossible values without unbounded factorization. Passing is not a complete two-square existence proof or proof that the entire FFT row arises from the declared samples. The single-row condition is not imposed on sums across multiple events. Full sidecar verification checks actual coefficients and reconstructed PCM.

For a one-event endpoint pair, a DC or Nyquist component present in `top_components` retains its signed `real` coefficient after division by `32768^10`. The signed values must satisfy `D+N = 2*sum(even-index w*x)` and `D-N = 2*sum(odd-index w*x)` for the samples actually available in that source tail. The reference enforces the corresponding exact divisibility constraints from the committed integer window weights. An omitted endpoint supplies only its power magnitude and may use either sign as a compact witness.

For every channel, a bin selected in every long event has a fully known aggregate: it must equal the sum of those reported powers. Zero-power selections count toward completeness. Bins omitted from at least one event may have additional unreported power, but their aggregate must still be at least the selected subtotal. Per-event upper caps also preserve the top-K ordering: an omitted bin with an index smaller than the weakest selected bin must have strictly lower integer power; a later omitted bin may tie the weakest selected power.

For each event, selected components constrain the centroid from both sides. If `S` is selected power, `K` selected weighted power, `D` the centroid denominator and `N` the numerator, compact acceptance requires:

```text
K <= N <= K + 512 * (D - S)
```

The upper bound is necessary because all omitted retained bins have indices at most 512. These checks are consistency constraints on compact observations, not reconstruction of the omitted spectrum.

## Transient boundary

The v0.2 transient candidate rule is deterministic and exact:

```text
current > previous
and
2 * current >= 3 * previous
```

It is an authored Layer-1 observation rule. Candidate count and strongest-candidate selection are protocol outputs, not empirical claims about human onset perception.

When `previous == 0`, the ratio is not finite. The canonical representation uses `rise_ratio: null` rather than encoding an invalid denominator of zero.

Candidate energies and summary totals must remain within the maximum possible values implied by PCM16 input, the frozen short triangular window and the source tail. If fewer than two short frames exist, there is no transition and both summary totals are zero. Across `T` transitions, `positive_delta_sum` cannot exceed `T * maximum_positive_delta`. When `candidate_count` exceeds the 16 reported strongest candidates, every omitted candidate is still a strict positive integer rise and contributes at least one unit to the minimum feasible positive-delta sum.

The 16 reported entries are the actual deterministic prefix ordered by descending `positive_delta` and then ascending `frame_index`. An omitted candidate can equal the weakest reported delta only at a later frame. An earlier equal-delta candidate would rank into the reported set and is therefore inconsistent. If every transition is a candidate, the exact positive mass outside the 16 reported entries must fit the per-frame cutoff allowances. If an omitted candidate borders reported short-frame energy evidence, that evidence strengthens the lower bound: known previous energy `P` requires `d >= ceil(P/2)` to satisfy the 3/2 candidate rule; known current energy `C` requires `d >= C-floor(2C/3)`; if both are known then `d=C-P` exactly and the candidate predicate must hold. These minima must also fit the deterministic top-16 cutoff and exact unreported positive mass. `maximum_positive_delta` equals the strongest reported candidate delta when every transition is a candidate.

If `maximum_positive_delta` is larger than the strongest reported candidate, that maximum cannot be an omitted stronger candidate because it would have ranked into the reported set. Compact acceptance therefore requires at least one non-candidate transition and enough positive-delta mass outside the reported candidate set for one such transition to attain the declared maximum.

Each reported previous/current short frame with one available sample requires energy `x^2`, and with two available samples requires `x^2 + 4*y^2`, for signed PCM16 integers. These tail-specific checks apply independently of channel count and reject unattainable energies even below the generic upper bound.

The two resolutions share an exact zero state. Because the committed long triangular window uses strictly positive integer weights over every available source sample and the long-event schedule covers the source, zero `windowed_energy` for every covering long event proves every source sample in that channel is zero. A compact packet in that state must report `candidate_count=0`, an empty strongest-candidate list, `positive_delta_sum=0`, and `maximum_positive_delta=0`.

## Channel boundary

Channels are never implicitly mixed in the canonical v0.1 or v0.2 paths.

Pairwise v0.2 quantities such as dot product, difference energy, sum energy and zero-lag correlation squared are exact signal relationships. The complete Gram matrix must be positive semidefinite and have rank at most `frame_count`, so accepted relationships can arise from real vectors in the declared sample space; that alone does not establish PCM16 integer realizability.

For a one-frame multichannel source, the compact signed endpoint evidence is stronger than a magnitude-only Gram check. Each channel's reported DC coefficient is purely real and divisible by `32768^10`; removing that scale gives the signed sole PCM sample. Every relationship dot product must equal the product of the corresponding signed samples. Thus two positive reported DC coefficients cannot coexist with a negative dot product merely because the dot-product magnitude is feasible.

Short sources receive additional integer-realizability constraints. In particular, a two-frame multichannel compact percept must admit one joint set of PCM16 integer vectors satisfying the complete Gram data, and those same feasible vectors must reproduce each channel's declared long-window energy under the committed first two long-window weights. A two-frame mono source must still admit PCM16 integers realizing that weighted energy, despite having no channel-pair records. All one/two-sample long tails receive the same exact energy checks. For a complete two-sample channel, the scaled endpoint magnitudes additionally satisfy `D^2 + N^2 = 2*windowed_energy`; a merely feasible energy that contradicts the sole spectral row is invalid.

For three-frame multichannel sources, the verifier requires one common assignment of signed PCM16 triples satisfying every channel dot product and both source energy `E = x^2 + y^2 + z^2` and long energy `W = x^2 + 4*y^2 + 9*z^2`. The search derives candidates from `W-E = 3*y^2 + 8*z^2`, preserving the asymmetric signed range at -32768. It rejects jointly impossible triples even when each pair has a separate witness. This is exact feasibility for these Gram and weighted-energy quantities, not verification of the full matrix commitments.

For a complete three-frame mono source, absence of Gram records does not waive weighted-energy feasibility. The verifier requires a signed PCM16 triple matching `W = x^2 + 4*y^2 + 9*z^2` and both DC/Nyquist aggregate powers with exact endpoint coefficient scale `32768^10`. Square and divisibility checks recover at most eight candidates, preserving -32768 while excluding +32768. If an endpoint is present in `top_components`, the accepted triple must reproduce that endpoint's reported signed scaled `real` coefficient; only an omitted endpoint remains sign-unspecified. This is exact for those observations only: it does not certify remaining spectral coefficients, matrix commitments or source digests, and does not apply that endpoint-aggregate rule to three-sample tails of longer sources. See specification section 8.1.

These compact checks are necessary constraints, not a complete proof that every arbitrary-length compact observation has an integer waveform realization. Full sidecar verification separately reconstructs and binds actual PCM samples.

They do not by themselves establish acoustic scene geometry or spatial perception.

## Sidecar boundary

The optional `qsol-map-spectral-sidecar-v0.2` is complete spectral evidence for the declared short and long transforms, not a replacement audio format.

Its verifier checks deterministic ordering, typed integer position fields, coefficient arithmetic, receipt identity and reconstruction of the compact packet's matrix commitments. It additionally inverts both profiles to exact PCM16, checks overlap/tail/window constraints, requires both profiles to reconstruct the same waveform, binds reconstructed interleaved PCM to `pcm_s16le_sha256`, rebuilds the frozen v0.1 percept identity, and cross-checks transient/channel observations against recovered samples.

Canonical sidecar records are exact UTF-8 bytes terminated by one LF byte. CRLF is invalid canonical NDJSON even if a normal `TextIOWrapper(newline=None)` would translate it to `\n`; file-backed verification therefore inspects the underlying bytes before newline translation.

Seekable verifier inputs, including `StringIO`, must begin at logical position zero. A nonzero position is rejected without consuming or rewinding the input, so a valid suffix after a skipped junk prefix is not accepted as a whole file. Explicit record iterables remain scoped to the complete sequence supplied by the caller; acceptance makes no claim about content discarded before creating that sequence.

A decode failure is invalid evidence even if it occurs after an otherwise valid trailer. Verification uses bounded reads and bounded temporary spools.

The public writer independently validates `PCM16Wave` metadata, immutable tuple-of-tuples dimensions and plain signed PCM16 values, then recomputes `pcm_s16le_sha256` from frame-major/channel-order signed little-endian sample bytes in bounded chunks. A stale or directly constructed inconsistent wave is rejected before rebuilding analysis or touching the destination. It then rebuilds deterministic v0.2 analysis and refuses to emit a sidecar when the supplied envelope differs, including a rebound matrix commitment with a recomputed outer digest. It also refuses append-positioned or stale-tail destinations by requiring a provably empty seekable stream positioned at zero.

The writer must complete legal partial writes of every payload and LF before returning its receipt. Zero, `None`, negative, Boolean, non-integer or oversized write counts fail with `OSError`; destination exceptions propagate. Failed output can remain partial, but no successful receipt is returned. This does not guarantee transactional rollback, a final filesystem flush, or durable storage.

The original RIFF bytes are not retained by `PCM16Wave`. Recomputing its sample digest therefore does not recompute the separate `source_sha256` container hash or establish source authenticity.

A valid sidecar proves conformance to the declared serialization/commitment/reconstruction relationship. It does not prove that the source recording is authentic or scientifically meaningful.

## Determinism boundary

The current profiles are versioned Python references. They use exact integer signal arithmetic after parsing. The v0.2 long twiddle integers, reconstruction rule and full FFT algorithm are published as identity-bearing protocol data. Executing the normative algorithm in conformance tests guards against documentation/implementation drift; it does not establish universal correctness of every independent implementation.

A future implementation may claim conformance only after passing frozen vectors for the relevant profile, including:
- input parsing;
- windowing;
- transform coefficients;
- matrix commitments;
- packet serialization;
- percept identity;
- sidecar identity/verification where applicable.

## Verification boundary

Verification is designed to fail closed on malformed untrusted documents.

Important rules include:
- Boolean values are not accepted where integer fields are required;
- identity-bearing decimal strings are canonical and length-bounded before integer conversion;
- exact typed structures use canonical-byte comparison where ordinary Python equality would blur `False` with `0` or `True` with `1`;
- long and short-frame authored energies are bounded by the source/PCM/window contract and additional exact short-source feasibility constraints, including one/two-sample mono windows and tails;
- single-event long coefficients and powers obey the frozen transform's **per-bin coefficient divisors**, derived by exact integer-divisor propagation through the ten-stage butterfly schedule;
- complete two-sample channels bind weighted energy to endpoint powers with `D^2 + N^2 = 2W`, and complete three-sample mono witnesses preserve any reported endpoint signs;
- one-frame multichannel relationship dots are bound to the signed DC-derived PCM samples;
- reported one-event endpoint signs obey the committed source-tail window congruences;
- long spectral power and top-component claims must fit finite transform/ranking bounds, including strict tie-aware omitted-bin cutoffs and bounded necessary two-square checks for single-event aggregates;
- every event centroid is bounded both below and above by its selected/omitted power split;
- transient summaries must account for transition multiplicity, omitted candidates, adjacent reported-energy constraints on omitted candidates, the deterministic top-16 cutoff, frame-index tie ordering, and feasibility of any maximum stronger than the strongest reported candidate;
- a channel proven all-zero by zero covering long-event energies must have zero/empty transient observations;
- channel relationships must be jointly feasible in the declared sample dimension, including one shared PCM16 assignment for three-frame Gram and weighted-energy data;
- invalid structural data is rejected even when an attacker recomputes outer hashes;
- writer-side sample commitments are recomputed rather than trusted from the input object;
- partial writes are completed or fail without a successful receipt;
- file-backed sidecar verification preserves exact line bytes rather than accepting CRLF hidden by newline translation;
- output destinations are checked by filesystem identity, including case-equivalent and Unicode-normalization-equivalent initially nonexistent names on target filesystems that alias those spellings.

These checks establish protocol validity within the stated verification boundary, not trust in the origin of the data or complete arbitrary-length integer feasibility from a compact packet alone.

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
