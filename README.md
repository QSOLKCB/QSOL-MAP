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

The complete identity-bearing v0.2 quarter-wave Q15 table, full-table reconstruction rule, and long FFT algorithm are published in `spec/QSOL-MAP-MULTIRES-v0.2.md`. Section 4.1 specifies ten-bit input reversal, all ten radix-2 stages, twiddle-index scheduling, exact scaled butterflies and retained-bin ordering, with no per-stage division or final normalization. An executable specification regression compares complete coefficient rows against the implementation.

The compact verifier bounds long/transient energies by the exact source-sized PCM16/window maxima, checks short-source integer realizability, and requires the complete channel Gram matrix to be positive semidefinite with rank no greater than the source frame count.

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

v0.2 derives transient candidates from consecutive frozen v0.1 short-frame energies.

A frame is a candidate when:

```text
current > previous
and
2 * current >= 3 * previous
```

The rule identifier is:

```text
energy-rise-3-over-2-v0.2
```

For a transition from zero previous energy, `rise_ratio` is `null`. A finite rational numerator/denominator is emitted only when the previous energy is non-zero.

Candidate energies and summary totals are source-sized against the frozen short triangular window. If the source produces fewer than two short frames, no transition exists and both summary totals are zero. The compact verifier also accounts for omitted candidates beyond the 16 reported strongest events when checking the positive-delta summary.

Each reported previous/current short tail containing one sample must have energy `x^2`; a two-sample tail must have energy `x^2 + 4*y^2`, for signed PCM16 integers. The same exact energy checks cover one/two-sample long windows, including mono sources and tails of longer recordings. An energy below the maximum can still be impossible and is rejected.

This is an authored deterministic signal event, not a claim of equivalence to human onset perception.

## Channel relationships

QSOL-MAP never implicitly downmixes canonical input.

For every channel pair `i < j`, v0.2 records exact quantities including:

- dot product and sign;
- each channel's sum of squares;
- `left - right` energy;
- `left + right` energy;
- exact zero-lag correlation squared when both channel energies are non-zero.

The complete channel Gram matrix must be jointly feasible: positive semidefinite and of rank no greater than the declared source frame count. Very short sources receive additional integer-realizability checks; for two-frame multichannel sources the exact feasible PCM assignment must also reproduce the declared long-window energy. Two-frame mono sources have no pairwise records, but must still admit integer PCM16 samples realizing their weighted energy.

These are signal relationships. They are not speaker geometry, direction-of-arrival, or subjective stereo-width measurements.

## Optional full spectral sidecar

The compact percept commits to full matrices without embedding every coefficient.

v0.2 can additionally write:

```text
qsol-map-spectral-sidecar-v0.2
```

as canonical NDJSON containing:

1. one header;
2. every frozen short-profile spectral row;
3. every long-profile spectral row;
4. one receipt trailer.

Every coefficient is encoded as:

```json
["real", "imag", "power"]
```

with exact decimal strings and verified `power = real^2 + imag^2`.

The verifier checks:

- canonical UTF-8 line bytes with exact LF terminators before any text newline translation;
- exact typed header data;
- plain non-Boolean integer position fields;
- deterministic row order;
- coefficient arithmetic;
- record and receipt hashes;
- reconstructed v0.1 and v0.2 matrix commitments;
- exact PCM16 reconstruction from both spectral profiles, including overlap/tail/window-divisibility checks;
- equality of the short- and long-profile reconstructed waveforms;
- reconstructed interleaved PCM SHA-256 against `pcm_s16le_sha256`;
- frozen v0.1 percept identity rebuilt from short-profile evidence;
- transient observations rebuilt from short spectral rows;
- channel relationships rebuilt from reconstructed PCM;
- missing, extra, malformed, or decode-failed records.

The public writer validates the supplied `PCM16Wave` immutable tuple-of-tuples layout, declared channel/frame counts, metadata and plain signed PCM16 samples. Before rebuilding analysis or touching output, it recomputes the actual interleaved signed little-endian PCM SHA-256 in bounded chunks and requires equality with `pcm_s16le_sha256`. Directly constructed or stale wave objects cannot receive a receipt merely because rebuilding their envelope copies the same incorrect hash.

The writer then independently rebuilds the deterministic v0.2 percept and refuses to write if the supplied envelope differs, including altered matrix commitments with a recomputed outer percept digest. It also requires an empty, seekable destination positioned at zero so it cannot append a valid receipt to stale content. The original RIFF container bytes are not retained by `PCM16Wave`, so this writer-side check does not recompute the separate `source_sha256` commitment.

The verifier uses bounded temporary spools for reconstruction rather than building complete spectral matrices or an unbounded waveform in memory.

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

The CLI rejects compact-percept/sidecar output aliases before writing. Existing aliases are checked by filesystem identity; initially nonexistent names are also checked against target-filesystem case folding and Unicode normalization equivalence, including NFC/NFD-equivalent spellings such as precomposed and decomposed `é`.

## Strict input boundary

The canonical adapter accepts:

- little-endian RIFF/WAVE;
- uncompressed integer PCM format 1;
- exact 16-byte PCM `fmt ` chunks;
- signed 16-bit samples;
- 1 to 8 channels;
- sample rates from 1 Hz through 768 kHz;
- non-empty data containing complete PCM frames.

The adapter performs no hidden:

- resampling;
- normalization;
- channel mixing;
- filtering;
- dithering;
- mastering;
- metadata-derived signal transformation.

Unsupported or malformed inputs fail closed.

## Canonical verification

Identity-bearing JSON remains float-free. Large exact integer observations are decimal strings.

v0.2 bounds untrusted decimal-string length before converting it to Python integers. This preserves the verifier's fail-closed Boolean contract even on Python builds that enforce an integer-string digit limit.

The verification path also rejects Boolean values where canonical schemas require integers. Ordinary Python equality treats `False == 0` and `True == 1`; QSOL-MAP does not allow that language behavior to blur protocol types.

Source-sized PCM/window energy bounds, exact short-source integer feasibility, transform-power bounds, transient-summary constraints, and exact channel Gram-rank feasibility reject contradictory compact observations even when outer hashes are recomputed. These necessary checks are not a complete compact-only integer feasibility proof for arbitrary source lengths; full sidecar verification separately reconstructs and binds the actual PCM evidence.

## Golden vectors

The test suite protects both protocol generations:

- frozen v0.1 percept SHA-256:

```text
e7ec380529d01790981e819bf5f33f8c251a6c89caafe19458b9053ae573b49c
```

- v0.2 multi-resolution percept SHA-256:

```text
c167694d60661ceac1d01d6504cbd8b5db77286ce09b28a342629b03046735d7
```

The fixtures are defined in the regression suite. A released profile's golden identity must not change silently.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Coverage includes:

- frozen v0.1 identity;
- repeated byte-identical v0.2 analysis;
- v0.2 golden identity;
- high-sample-rate represented-bin retention;
- silence-to-signal transient handling and source-sized transient bounds;
- exact and jointly feasible channel relationships;
- one/two-sample mono and tail energy feasibility, including signed PCM16 limits;
- malformed/oversized verifier input;
- sidecar round-trip and reconstructed-evidence tamper rejection;
- Boolean sidecar position rejection even after receipt recomputation;
- sidecar writer rejection of stale PCM digests, malformed direct wave objects, and envelopes that contradict the supplied WAV;
- execution of the normative long FFT algorithm against complete reference coefficient rows;
- canonical LF sidecar verification before text newline translation;
- CLI v0.2 and sidecar round-trips;
- filesystem output-alias rejection including normalization-equivalent names;
- direct checkout execution of the benchmark harness.

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
