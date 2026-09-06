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
- strict sidecar ordering, arithmetic, matrix-commitment, and receipt verification;
- a frozen v0.2 golden percept vector.

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

This is an authored deterministic signal event, not a claim of equivalence to human onset perception.

## Channel relationships

QSOL-MAP never implicitly downmixes canonical input.

For every channel pair `i < j`, v0.2 records exact quantities including:

- dot product and sign;
- each channel's sum of squares;
- `left - right` energy;
- `left + right` energy;
- exact zero-lag correlation squared when both channel energies are non-zero.

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

- canonical line encoding;
- exact typed header data;
- plain non-Boolean integer position fields;
- deterministic row order;
- coefficient arithmetic;
- record and receipt hashes;
- reconstructed v0.1 and v0.2 matrix commitments;
- missing or extra records.

The writer and verifier process one spectral row at a time rather than building complete sidecar matrices in memory.

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

The CLI rejects using the same filesystem path for the compact percept and the sidecar, preventing one output from truncating the other.

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
- silence-to-signal transient handling;
- exact channel relationships;
- malformed/oversized verifier input;
- sidecar round-trip and tamper rejection;
- Boolean sidecar position rejection even after receipt recomputation;
- CLI v0.2 and sidecar round-trips;
- output-path collision rejection;
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
