# QSOL-MAP

**QSOL Machine Perception Audio Protocol**

QSOL-MAP is an experimental protocol and deterministic reference implementation for representing audio as machine-readable acoustic evidence before learned tokenization, semantic interpretation, or human perceptual reporting is applied.

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

## Current status: v0.2.0 multi-resolution L1

QSOL-MAP currently implements two deterministic Layer-1 profiles.

### Frozen v0.1 short reference

```text
qsol-map-fixed-fft-v0.1
```

This published profile remains unchanged:

- strict PCM16 RIFF/WAVE input;
- 256-sample frames with 128-sample hops;
- exact integer triangular window;
- frozen Q15 complex twiddles;
- exact unbounded-integer Python FFT reference;
- independent source, PCM, complex-matrix, power-matrix, and percept commitments;
- frozen end-to-end golden vector.

### v0.2 multi-resolution reference

```text
qsol-map-multiresolution-v0.2
```

v0.2 imports the frozen v0.1 evidence and adds:

- `qsol-map-fixed-fft-1024-v0.2`, a deterministic 1024-sample / 512-hop long-window reference;
- separate long complex-matrix and power-matrix commitments;
- exact represented-frequency support up to source Nyquist;
- authored `[0,20 kHz)`, `[20,40 kHz)`, and `[40 kHz,Nyquist]` power regions;
- **no psychoacoustic low-pass filter**;
- deterministic short-frame energy-rise transient candidates;
- exact pairwise channel relationships without downmixing;
- optional full short+long canonical NDJSON spectral sidecars;
- strict sidecar ordering, arithmetic, matrix-commitment, receipt, and reconstructed-evidence verification;
- a frozen v0.2 golden percept vector.

The complete identity-bearing quarter-wave Q15 table, full-table reconstruction rule, and long FFT algorithm are published in `spec/QSOL-MAP-MULTIRES-v0.2.md`. Section 4.1 specifies ten-bit input reversal, all ten radix-2 stages, twiddle scheduling, exact scaled butterflies and retained-bin ordering, with no per-stage division or final normalization. An executable specification regression compares complete coefficient rows against the implementation.

The compact verifier bounds long/transient energies by source-sized PCM16/window maxima, checks short-source integer realizability, and requires the complete channel Gram matrix to be positive semidefinite with rank no greater than the source frame count. It derives **per-bin coefficient divisors** from the frozen integer butterfly graph, applying them to every event and to multi-event aggregate power sums. Every event's total and weighted power also retain the appropriate sum divisors.

The v0.2 packet remains Layer 1. It does not introduce neural tokens or semantic music interpretation.

## Why two spectral resolutions?

The v0.1 short transform provides finer temporal sampling:

```text
frame = 256 samples
hop   = 128 samples
bins  = 0..128
```

The v0.2 long transform adds finer frequency-bin spacing:

```text
frame = 1024 samples
hop   = 512 samples
bins  = 0..512
```

Both use exact integer triangular windows, frozen Q15 twiddle tables, and exact Python integer arithmetic in the reference path.

QSOL-MAP deliberately keeps both resolutions rather than pretending one analysis scale captures every relevant structure.

## High-sample-rate observation

For sample rate `f_s`, long bin `k` represents the exact rational frequency:

```text
f_k = k * f_s / 1024
```

v0.2 retains all represented bins through source Nyquist. It does not discard represented content above conventional human-audible ranges merely because a human listener may not hear it.

That does **not** mean a high sample rate proves the microphone, ADC, source medium, or previous processing chain captured physically valid ultrasonic information. QSOL-MAP observes the supplied sampled signal under its declared contract.

## Deterministic transient candidates

v0.2 derives transient candidates from consecutive frozen v0.1 short-frame energies. A frame is a candidate when:

```text
current > previous
and
2 * current >= 3 * previous
```

The rule identifier is `energy-rise-3-over-2-v0.2`. A rise from zero previous energy has `rise_ratio: null`; finite numerator/denominator objects require a nonzero previous energy.

Energies and summaries obey source-sized short-window PCM16 bounds. Fewer than two short frames produce no transition and zero totals. Complete reported candidate sets fix both sum and maximum exactly. Every omitted candidate beyond the 16 reported entries contributes a positive integer delta.

The reported list is the exact descending-delta/ascending-frame top-16 prefix. An omitted candidate may tie the weakest reported delta only at a later frame. Known neighboring reported energies constrain omitted candidate eligibility in mixed and all-candidate sets, including an exact delta when both energies are known. Enough eligible frames and positive mass must exist.

A maximum stronger than the strongest reported candidate must belong to a non-candidate transition, honor known adjacent energies and the strict non-candidate threshold, and fit the unreported positive mass. Total unreported mass also fits the summed transition capacities after exactly the declared omitted-candidate count of feasible candidate-cap replacements. These are necessary compact checks, not complete reconstruction of the shared short-energy chain. Specification sections 7 and 7.1 define the arithmetic.

One/two-sample short tails require energies `x^2` or `x^2+4*y^2` for signed PCM16 integers. The same energy checks apply to long mono/multichannel windows and tails. Shared tail samples also constrain their contribution to the preceding overlapping frame, with bounded exact feasibility checks for small non-overlap remainders.

If every covering long-event energy in a channel is zero, the strictly positive window weights prove all source samples are zero. Its transient count/list and both summary values must then be zero/empty.

This is an authored deterministic signal event, not equivalence to human onset perception.

## Channel relationships

QSOL-MAP never implicitly downmixes canonical input. For every pair `i<j`, v0.2 records exact dot product and sign, channel sums of squares, difference/sum energies, and zero-lag correlation squared when both channel energies are nonzero.

The complete channel Gram matrix must be positive semidefinite and of rank no greater than the source frame count. These real-vector conditions alone do not prove PCM16 integer realizability. Complete two-, three- and four-frame multichannel sources additionally require one shared signed PCM16 assignment reproducing every Gram entry, long-window energy, endpoint power and reported DC/Nyquist sign. Separate pairwise witnesses are insufficient.

For a complete one-sample source, the reported DC coefficient divided by `32768^10` fixes the sole signed sample. Its energy and every relationship dot product must match those signed samples.

For complete two-sample sources, scaled endpoints obey `D=x+2*y`, `N=x-2*y` and `D^2+N^2=2*windowed_energy`. Acceptance additionally requires exact `x=(D+N)/2`, `y=(D-N)/4`, signed PCM16 bounds and the same energy/endpoint-compatible witness for all multichannel Gram products. Mono sources cannot bypass this witness check.

For complete three- and four-frame multichannel sources, specification section **8.2** defines the bounded endpoint-derived solver. With a fourth sample t (zero for three frames), it uses:

```text
E = x^2+y^2+z^2+t^2
W = x^2+4*y^2+9*z^2+16*t^2
A = (D+N)/2 = x+3*z
B = (D-N)/4 = y+2*t
(x-3*z)^2 = 2*(W-4*y^2-16*t^2)-A^2
```

For four frames it enumerates bounded signed PCM16 t, derives y, and recovers x/z by exact square/divisibility checks. For three frames t=0 gives at most eight candidates. Reported endpoint signs constrain the candidates before one joint Gram assignment is accepted; only omitted endpoints allow a choice of sign.

Three-frame mono has no source-energy Gram diagonal, but still requires a signed PCM16 triple matching W, both endpoint powers and every reported endpoint sign using section 8.1's at-most-eight candidates.

These complete-source checks do not apply endpoint aggregates to tails of longer recordings and do not verify unreported coefficients, matrix/source commitments or arbitrary-length waveform realizability. Full sidecars provide reconstructed evidence. Signal relationships are not speaker geometry, direction-of-arrival or subjective stereo width.

## Optional full spectral sidecar

The compact percept commits to full matrices without embedding every coefficient. The optional schema is:

```text
qsol-map-spectral-sidecar-v0.2
```

Canonical NDJSON contains one header, every frozen short-profile row, every long-profile row, then one receipt trailer. Every coefficient is encoded as:

```json
["real", "imag", "power"]
```

with exact decimal strings and verified `power=real^2+imag^2`.

The verifier checks canonical UTF-8/LF bytes before text translation, exact typed header/positions, deterministic row order, coefficient arithmetic, record/receipt hashes, and reconstructed matrix commitments. It inverts both profiles to PCM16 with overlap/window/tail checks, requires one shared waveform, verifies the interleaved PCM digest, rebuilds frozen-v0.1 identity, and reconstructs long events, transients and channel relationships. Missing, extra, malformed or decode-failed records are rejected, including errors after a valid trailer.

Seekable inputs, including StringIO, must start at logical zero; nonzero positions are rejected without consumption or rewinding. Explicit record iterables are the complete supplied sequence, not evidence about previously discarded content. Non-seekable binary-backed inputs remain supported. StringIO verification with newline=None is rejected because it may already have erased CRLF; explicit newline="" and newline="\n" remain supported.

The public writer validates PCM16Wave metadata, immutable dimensions and plain PCM16 samples, then recomputes the actual interleaved sample digest in bounded chunks before rebuilding analysis or touching output. The rebuilt v0.2 envelope must match exactly. Destinations must be empty, seekable and at zero, and output must preserve exact UTF-8/LF bytes. Original RIFF bytes are not retained by PCM16Wave, so this check does not recompute the separate `source_sha256` or authenticate the recording.

Legal partial writes are completed before a receipt is returned. Invalid/stalled write counts or destination errors prevent success; partial output may remain. This is not a rollback or durable-storage guarantee. Verification uses bounded temporary spools rather than complete in-memory spectral matrices or unbounded waveforms.

## Quick start

No third-party Python packages are required.

### Frozen v0.1

```bash
python3 -m qsol_map analyze input.wav -o percept-v01.json
python3 -m qsol_map verify percept-v01.json
```

### v0.2

```bash
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json --sidecar spectral-v02.ndjson
python3 -m qsol_map verify-v0.2 percept-v02.json
python3 -m qsol_map verify-sidecar-v0.2 percept-v02.json spectral-v02.ndjson
```

Output aliases are rejected before writes, including input/stdout collisions and filesystem case/Unicode-normalization equivalence. The CLI reserves nontruncating regular-file handles before analysis, checks their identities and revalidates their paths, then writes through held descriptors instead of reopening replacement paths. This is not an atomic multi-file transaction.

## Strict input boundary

The canonical adapter accepts little-endian RIFF/WAVE, uncompressed PCM format 1 with exact 16-byte `fmt ` chunks, signed 16-bit samples, 1 to 8 channels, sample rates from 1 Hz through 768 kHz, and nonempty complete PCM frames.

It performs no hidden resampling, normalization, channel mixing, filtering, dithering, mastering or metadata-derived signal transformation. Unsupported or malformed inputs fail closed.

## Canonical verification

Identity-bearing JSON remains float-free and large exact observations are canonical decimal strings. Untrusted decimals are length-bounded before conversion; negative zero is rejected. Boolean values cannot stand in for schema integers, despite Python's ordinary `False==0` and `True==1` equality.

### Transform divisibility versus single-row square checks

The frozen butterfly schedule derives **per-bin coefficient divisors** by exact integer propagation: multiplication scales a divisor by the absolute Q15 factor, and sums/differences take the gcd. Every event's reported real/imag components must satisfy their divisors. With `g[k]=gcd(D_real[k]^2,D_imag[k]^2)`, every aggregate bin, including **multi-event** sums, must be divisible by g[k]. Each event denominator must be divisible by `gcd(g[k])`, which is **`2^64`** for the frozen transform, and each numerator by `gcd(k*g[k])`. Transferring one unit between event totals does not preserve these necessary conditions.

Divisibility survives summation. Perfect-square and two-square restrictions do not. Only single-event aggregate powers receive the bounded two-square filter and exact endpoint squares with roots divisible by `32768^10`. Multi-event endpoints need not be squares, but still obey their power divisor. These checks do not constitute complete large-integer factorization or a full waveform proof. See specification section 4.2.

Reported one-event endpoint signs obey source-tail even/odd window congruences and energy parity. Endpoint magnitude M obeys `M^2<=a*W`; equality forces a constant or alternating-constant windowed vector that must divide by each window weight into signed PCM16 samples and reproduce both endpoints and energy.

### Joint selected/omitted power

Fully selected bins have aggregate exactly equal to summed selected powers, counting zero selections. Other bins can contain additional power within each event's tie-aware cutoff: an earlier omitted bin must be strictly weaker than the weakest selected component, while a later bin may tie.

Independent bin caps are not sufficient. Residual event totals and residual aggregate bins must admit one nonnegative integer event-by-bin allocation, excluding selected cells and respecting cutoff capacities. Integer max-flow checks this condition. It does not prove each allocated cell is a realizable transform power or certify the complete waveform.

Each event centroid separately obeys `K<=N<=K+512*(D-S)`, where S/K are selected total/weighted power and D/N are denominator/numerator. Event totals also agree with aggregate total and weighted power. These moment constraints do not claim that a residual max-flow simultaneously realizes every event moment.

Transient arithmetic, deterministic cutoffs, known-neighbor eligibility, classification-aware mass capacity, short-source signed Gram witnesses and the exact all-zero cross-resolution rule remain independently required. Recomputing an outer digest does not waive contradictory evidence. Full sidecar verification separately reconstructs and binds actual PCM samples.

## Golden vectors

The regression suite protects the frozen v0.1 percept SHA-256:

```text
e7ec380529d01790981e819bf5f33f8c251a6c89caafe19458b9053ae573b49c
```

and v0.2 multi-resolution percept SHA-256:

```text
c167694d60661ceac1d01d6504cbd8b5db77286ce09b28a342629b03046735d7
```

The separately frozen sidecar receipt is also regression-protected. Fixtures are defined in the suite. A released profile's golden identity must not change silently.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Coverage includes frozen v0.1/v0.2/sidecar identities, repeated byte-identical analysis, represented high-frequency retention, zero onsets, exact relationships, malformed input, CLI and sidecar round trips, output alias protection and checkout benchmark execution.

Adversarial verification tests recompute hashes around contradictory observations. Coverage includes every-event and multi-event divisibility, event denominator/numerator transfers, endpoint equality cases, signed PCM16 limits, omitted endpoint signs, exact three/four-frame joint Gram witnesses, exhaustive small energy/endpoint domains, top-K ties, joint residual allocations, transient adjacency/capacity and the zero cross-resolution state. Independent pairwise witnesses cannot substitute for one shared assignment.

Sidecar tests cover reconstructed-evidence contradictions, Boolean positions, stale sample commitments, malformed direct wave objects, canonical LF before translation, stream starts, partial-write completion and failed-write receipts. Executable specification tests compare the normative long FFT with complete reference coefficient rows.

## Benchmarking and optimization

QSOL-MAP follows `QSOLKCB/OPT`: correctness outranks speed, reference behavior remains available, and performance claims stay local to measured environments.

The environment-scoped benchmark runs directly from a checkout:

```bash
python3 scripts/benchmark_v02.py
```

It records runtime/toolchain context and deterministic percept identity. It is **not** a CI performance gate and does not establish a portable speedup.

## Research lineage

The architecture draws on:

- **QSOLKCB/SONIFICATION**: receiver-neutral committed events, deterministic ordering, acyclic receipts, and claim boundaries;
- **QSOLKCB/SPECTRAL**: deterministic DSP, WAV/PCM handling, spectral views, provenance, and cross-modal signal experiments;
- **QSOLKCB/E8_MUSIC v1.1.0**: canonical observation contracts, source-to-signal identity chains, executable conformance, and formal-assurance boundaries;
- **QSOLKCB/OPT**: correctness-preserving optimization patterns for tests, DSP, invariant reuse, parallel work, and future Lean CI.

Neural-codec architectural reference:

> Neil Zeghidour, Alejandro Luebs, Ahmed Omran, Jan Skoglund, Marco Tagliasacchi, *SoundStream: An End-to-End Neural Audio Codec*, arXiv:2107.03312.

SoundStream demonstrates learned embeddings and residual vector quantization. QSOL-MAP reserves such learned representation for a future **L2 receiver**, separately identified from deterministic L1 evidence.

No SoundStream code, model weights, or codebooks are included.

## Research direction

```text
                  canonical audio source
                           |
                           v
              L1 deterministic observation
                 /                   \
                /                     \
       short + long spectra       future learned encoder
       transient/channel data             |
       optional full sidecar               v
                |                          RVQ
                |                           |
                |                           v
                |                    L2 token stream
                |                           |
                +------------+--------------+
                             |
                             v
                        L3 semantics
                             |
                             v
                       L4 human reports
```

See:

- [ROADMAP.md](ROADMAP.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/CLAIM_BOUNDARIES.md](docs/CLAIM_BOUNDARIES.md)
- [spec/QSOL-MAP-MULTIRES-v0.2.md](spec/QSOL-MAP-MULTIRES-v0.2.md)

## Claim boundary

QSOL-MAP does **not** claim that an AI has subjective auditory experience. It does not equate spectral analysis with human hearing, represented ultrasonic bins with verified physical ultrasonic capture, learned tokens with physical truth, or semantic labels with objective properties of music.

The compact percept and spectral sidecar are observation records under versioned contracts, not replacements for the source waveform and not proofs of scientific validity.

## Licence

Apache License 2.0. Copyright 2026 Trent Slade / QSOL-IMC.
