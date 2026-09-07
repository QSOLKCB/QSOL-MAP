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

## Implemented canonical profiles

Two L1 profiles are implemented.

### Frozen v0.1 short reference

`qsol-map-fixed-fft-v0.1`

- strict RIFF/WAVE PCM format 1;
- PCM16 little endian;
- 1 to 8 channels;
- 256-sample frame, 128-sample hop;
- exact integer triangular window;
- frozen Q15 twiddles;
- exact unbounded-integer Python FFT;
- independent source, PCM, complex-matrix, power-matrix and percept commitments.

The v0.1 profile is frozen and must remain byte-identical to its published golden vector.

### v0.2 multi-resolution reference

`qsol-map-multiresolution-v0.2`

The v0.2 profile imports the frozen v0.1 result and adds:

- a deterministic 1024-sample / 512-hop long spectral reference;
- an exact published normative quarter-wave Q15 table plus deterministic full-table reconstruction rule;
- the complete normative long FFT algorithm in specification section 4.1: ten-bit input reversal, ten radix-2 stage widths, twiddle-index schedule, exact scaled butterflies, and ascending retained bins 0..512;
- independent long complex/power matrix commitments;
- explicit represented-frequency support and 20 kHz / 40 kHz reference regions;
- no psychoacoustic low-pass filtering;
- deterministic short-frame energy-rise transient candidates;
- exact pairwise channel relationships without downmixing;
- optional canonical NDJSON full-spectral sidecars;
- strict sidecar ordering, arithmetic, matrix and receipt verification;
- exact sidecar reconstruction of PCM16 from both spectral profiles, requiring identical recovered waveforms;
- reconstructed PCM SHA-256 binding, frozen-v0.1 percept rebuild, transient rebuild, and channel-relationship rebuild before sidecar acceptance.

For a transition from zero previous energy, the transient candidate's `rise_ratio` is `null`; finite rational ratios are emitted only when the denominator is non-zero. Candidate energies and summary totals are bounded by the source-sized frozen short-window PCM16 maxima. If fewer than two short frames exist, both transient summary totals are zero. When more than 16 candidates exist, omitted candidates still contribute at least one positive integer unit each to `positive_delta_sum`.

The compact verifier also requires the complete channel Gram matrix to be positive semidefinite with rank no greater than the source frame count, applies short-source integer realizability checks, and for two- and three-frame multichannel sources requires one joint PCM16 vector assignment to reproduce every Gram entry and each declared long-window energy. For three frames, source energy is `x^2 + y^2 + z^2` and windowed energy is `x^2 + 4*y^2 + 9*z^2`; separate pairwise witnesses are insufficient.

One- and two-sample long windows, including mono sources and source tails, require exact energies `x^2` and `x^2 + 4*y^2` respectively for PCM16 integers. The same rule applies independently to previous/current short frames reported by transient candidates. Bounds for longer windows are not a complete proof of integer realizability; full sidecar verification reconstructs actual PCM evidence.

A three-frame mono source must admit a signed PCM16 triple with energy `x^2 + 4*y^2 + 9*z^2` and the same DC/Nyquist aggregate powers. The endpoint magnitudes must be exact multiples of `32768^10`; after removing that scale, exact square/divisibility checks recover at most eight candidate triples. This check applies to the complete three-frame mono source, not three-sample tails of longer recordings, and does not certify the remaining spectrum or source commitments. See specification section 8.1.

When there is exactly one long event, all aggregate bin powers, including omitted interior bins, receive bounded necessary two-square checks: nonzero odd part 1 modulo 4 and even valuations of primes `{3, 7, 11, 19, 23, 31}`. In addition, the committed butterfly schedule defines **per-bin coefficient divisors** for every retained bin: start each input real divisor at 1 and each identically-zero input imaginary divisor at 0, multiply a divisor by the absolute integer Q15 factor on multiplication, and take the gcd on every exact sum or difference. A reported real/imag component must be divisible by the derived divisor for that bin, with divisor 0 requiring exact zero. A single-event power must be divisible by `gcd(D_real[k]^2, D_imag[k]^2)`. DC/Nyquist retain their stronger perfect-square and `32768^10` real-endpoint rules. This general rule subsumes the earlier bin-256 special case and also constrains bins such as bin 8. It applies only to a single-event row, not to aggregates summed across multiple events. See specification section 5.

For each channel and bin, sum the reported component powers and count the long events selecting that bin, including zero-power selections. The subtotal cannot exceed the aggregate. If the selection count equals the number of long events, the subtotal must equal the aggregate exactly; only partially selected bins can have unreported contributions.

### Compact verifier conformance details

The following rejection rules are identity-bearing parts of the v0.2 compact verification contract, not implementation conveniences:

- the single-event **per-bin coefficient divisors** are derived from the frozen long FFT itself by integer-divisor propagation through all ten butterfly stages; reported coefficient components and their single-event powers must satisfy those divisors;
- after removing the exact `32768^10` scale from a one-event DC/Nyquist pair, any **reported** endpoint component keeps its signed `real` value; the signed values must satisfy the source-tail window congruences `D+N = 2*sum(even-index w*x)` and `D-N = 2*sum(odd-index w*x)`. An endpoint omitted from `top_components` remains sign-unspecified and either sign may witness the magnitude;
- for a complete two-sample source, each channel must additionally satisfy `D^2 + N^2 = 2*windowed_energy`, so an independently realizable energy cannot contradict the exact endpoint powers;
- for a complete three-sample mono source, the bounded PCM16 witness used by section 8.1 must match the signed value of every reported DC/Nyquist component, not merely the two endpoint magnitudes;
- for a one-sample multichannel source, signed DC coefficients recover the signed PCM sample in each channel, so each relationship dot product must equal the product of those signed samples rather than merely matching the product of their magnitudes;
- an omitted long bin may equal the weakest selected top-component power only when its larger bin index keeps it behind that selected cutoff. If its bin index is smaller than the weakest selected bin, its integer power must be strictly lower;
- every event centroid obeys both `selected_weighted_power <= numerator` and `numerator <= selected_weighted_power + 512*(denominator-selected_power_total)`;
- if all covering long-event `windowed_energy` values for a channel are zero, the strictly positive long-window weights establish an all-zero source channel, so its transient candidate count/list, positive-delta sum and maximum must all be zero;
- if `maximum_positive_delta` exceeds the strongest reported candidate delta, that maximum must be attainable by an actually non-candidate transition, and the positive-delta mass outside the reported candidate set must be at least that maximum;
- when more than 16 candidates exist, the 16 reported candidates are the deterministic descending-delta/ascending-frame prefix. An omitted candidate may tie the weakest reported delta only at a later frame; an earlier frame with the same delta would displace the reported cutoff. If every transition is a candidate, exact adjacent reported short-frame energies also constrain an omitted candidate: known previous energy `P` requires delta at least `ceil(P/2)`, known current energy `C` requires delta at least `C-floor(2C/3)`, and when both are known the exact delta is `C-P`. These minima must fit both the top-16 cutoff and the exact unreported positive mass. If every transition is a candidate, the summary maximum equals the strongest reported candidate.

Identity-bearing decimal strings are length-bounded before integer conversion so malformed untrusted envelopes fail closed rather than escaping verification.

## Identity path

```text
source bytes
-> source_sha256
-> PCM data bytes
-> pcm_s16le_sha256
-> frozen v0.1 short analysis
-> v0.1 percept + matrix commitments
-> v0.2 long analysis + transient/channel observations
-> v0.2 percept core
-> domain-separated percept_sha256
```

Optional full spectral evidence is a separately verified sidecar receiver. Sidecar verification reconstructs both spectral profiles back to one PCM16 waveform, checks that waveform against `pcm_s16le_sha256`, rebuilds the frozen v0.1 percept identity, and cross-checks transient/channel observations. File-backed verification must inspect exact UTF-8/LF bytes before text newline translation; CRLF is not canonical.

Seekable verifier inputs, including `StringIO`, must start at logical position zero. Reject nonzero positions without consuming or rewinding the stream; synchronize an already-zero text wrapper before exact binary reads. Explicit record iterables are verified as the complete supplied sequence, not as evidence about any data discarded before that sequence.

The public sidecar writer first validates the `PCM16Wave` immutable tuple-of-tuples layout, metadata, sample counts and plain PCM16 integers, and hashes the actual samples in frame-major/channel-order signed little-endian form. The recomputed digest must equal `pcm_s16le_sha256` before rebuilding analysis or touching the destination. It then requires an envelope exactly matching the rebuilt deterministic v0.2 analysis and a provably empty seekable destination positioned at zero. The original RIFF bytes are not retained by this object, so this check does not recompute `source_sha256`.

The writer completes every record and LF terminator by looping over legal partial writes. Non-progress, invalid write counts and destination errors must prevent a successful receipt. Partial output may remain after failure; no transactional rollback or durable-storage guarantee is claimed. The text adapter returns completed character counts while binary-backed writes preserve exact UTF-8 bytes.

## Source lineage

Design references are pinned in `docs/PROVENANCE.md`.

Important sources:
- QSOLKCB/SONIFICATION
- QSOLKCB/SPECTRAL
- QSOLKCB/E8_MUSIC v1.1.0
- QSOLKCB/OPT
- SoundStream, arXiv:2107.03312

No SoundStream code or model weights are vendored.

## Development rules

1. Preserve the L0-L4 layer boundary.
2. Preserve frozen `qsol-map-fixed-fft-v0.1` behavior and golden vectors.
3. Fail closed on unsupported canonical inputs and malformed verification data.
4. Never insert floats into identity-bearing JSON.
5. Large exact integers must be canonical decimal strings; untrusted decimal fields must be bounded before `int()` conversion.
6. Preserve source, PCM, short-matrix, long-matrix, sidecar and percept commitments independently.
7. Sidecar acceptance must bind reconstructed short/long evidence to one PCM waveform, its PCM hash, the frozen v0.1 percept, transient observations, and channel relationships.
8. Never downmix channels implicitly.
9. High sample rate permits analysis of represented bins above conventional human-audible ranges; it does not prove sensor response or physical ultrasonic validity.
10. Learned models must be versioned and hash-bound when L2 is added.
11. Keep a deterministic reference path before optimizing.
12. Consult QSOLKCB/OPT before changing test, DSP, parallel, or Lean CI performance.
13. Do not weaken tests or claim portable speedups without target-repo measurements.
14. Run the complete suite after every behavior change.

## Commands

Frozen v0.1:

```bash
python3 -m qsol_map analyze input.wav -o percept-v01.json
python3 -m qsol_map verify percept-v01.json
```

v0.2:

```bash
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json --sidecar spectral-v02.ndjson
python3 -m qsol_map verify-v0.2 percept-v02.json
python3 -m qsol_map verify-sidecar-v0.2 percept-v02.json spectral-v02.ndjson
```

Output collisions are rejected before writing, including case-equivalent and Unicode-normalization-equivalent initially nonexistent names when the target filesystem aliases those names.

Benchmark from a checkout:

```bash
python3 scripts/benchmark_v02.py
```

The benchmark is environment-scoped evidence only, not a portable speed claim or CI performance gate.

Tests:

```bash
python3 -m unittest discover -s tests -v
```

## Next major phase

See `ROADMAP.md`. The next major protocol addition is v0.3 L2 learned-token reception: exact model/weights/codebook/preprocessing identities, separately committed token streams, and comparisons against independently preserved L1 evidence.
