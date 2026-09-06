# QSOL-MAP Multi-Resolution Deterministic Observation v0.2

Status: **reference profile candidate for repository release v0.2.0**

This specification extends Layer 1 without modifying the frozen v0.1 profile.

## 1. Compatibility rule

The v0.2 compact percept imports the result of the frozen profile:

```text
qsol-map-fixed-fft-v0.1
```

The v0.1 algorithm, identifiers, domains, matrix commitments and golden vector are unchanged. v0.2 records the v0.1 percept SHA-256 plus the v0.1 per-channel complex/power matrix commitments as a short-window reference.

The new aggregate profile is:

```text
qsol-map-multiresolution-v0.2
```

The new long-window profile is:

```text
qsol-map-fixed-fft-1024-v0.2
```

## 2. Input

v0.2 uses the existing strict PCM16 RIFF/WAVE adapter. It performs no hidden resampling, normalization, channel mixing, psychoacoustic filtering, dithering or metadata-derived signal processing.

## 3. Two spectral resolutions

### Short reference

The complete frozen v0.1 256-point / 128-hop analysis is executed unchanged.

### Long reference

Constants:

```text
frame = 1024 samples
hop   = 512 samples
bins  = 0..512
Q15_ONE = 32768
```

Frame starts are every 512 samples while the start address is below the source frame count. Missing tail samples are zero padded.

The long-window integer weight is:

```text
w[n] = min(n + 1, 1024 - n)
```

and the windowed sample is exact integer multiplication:

```text
xw[n] = x[n] * w[n]
```

## 4. Frozen long-window twiddles

The long transform uses committed Q15 integer tables representing the profile's frozen approximation to:

```text
exp(-i * 2*pi*k/1024)
```

Runtime trigonometric evaluation is not part of the canonical profile.

The Python reference uses arbitrary-precision integer arithmetic. No right shift, saturation, float conversion or fixed-width overflow is used in transform identity.

## 5. Long-window observations

For each channel and long frame, v0.2 records:

- frame index and exact sample start;
- exact windowed energy;
- exact spectral-centroid numerator/denominator in bin coordinates;
- deterministic dominant non-DC bin;
- the eight highest-power components, ranked by descending power then ascending bin;
- real, imaginary and power values for each retained component.

The complete complex and power matrices are committed separately with:

```text
QSOL-MAP/LONG-COMPLEX-MATRIX/v0.2
QSOL-MAP/LONG-POWER-MATRIX/v0.2
```

using the same length-prefixed canonical-row construction as v0.1.

## 6. Frequency support and high sample rates

For sample rate `f_s`, bin `k` represents the exact rational frequency:

```text
k * f_s / 1024
```

The packet records Nyquist as `f_s / 2` and does not infer hardware bandwidth from sample rate.

Aggregate long-window power is additionally grouped by authored reference regions:

```text
[0, 20 kHz)
[20 kHz, 40 kHz)
[40 kHz, Nyquist]
```

when those bin centres exist in the represented discrete-time band.

These boundaries are observation labels, not claims that 20 kHz is a universal biological hearing cutoff. v0.2 deliberately applies no psychoacoustic low-pass filter. If the supplied digital source contains represented energy above 20 kHz, the reference analysis retains it up to the source Nyquist limit.

A high sample rate does **not** prove that the recording hardware captured physically valid ultrasonic energy.

## 7. Deterministic transient candidates

Transient candidates are derived from consecutive **v0.1 short-window energies**.

A frame `i` is a candidate when:

```text
current > previous
and
2 * current >= 3 * previous
```

The rule identifier is:

```text
energy-rise-3-over-2-v0.2
```

The compact packet records candidate count, total positive energy delta, maximum positive delta and up to the 16 strongest candidates. Strongest candidates are ordered by descending positive delta, then ascending frame index.

This is an authored deterministic energy-rise detector. It is **not** claimed to be equivalent to a human auditory onset percept or a validated music-information-retrieval onset detector.

## 8. Channel relationships

Channels remain independent signal streams. v0.2 does not downmix.

For every ordered pair `i < j`, the compact packet records exact full-source integer quantities:

- dot product and its sign;
- sum of squares for each channel;
- sum-of-squares of `left - right`;
- sum-of-squares of `left + right`;
- exact rational zero-lag correlation squared when both channel energies are non-zero.

These are signal relationships, not inferred speaker geometry or a claim about perceived stereo width.

## 9. Compact percept identity

The v0.2 core schema is:

```text
qsol-map-percept-core-v0.2
```

The envelope schema is:

```text
qsol-map-percept-envelope-v0.2
```

Percept identity is:

```text
SHA256(
  UTF8("QSOL-MAP/PERCEPT/v0.2")
  + NUL
  + canonical_percept_core_bytes
)
```

Identity-bearing JSON remains float-free. Large exact integers are decimal strings.

## 10. Optional full spectral sidecar

The compact packet commits full matrices without embedding every coefficient. v0.2 optionally exports the full short+long evidence as canonical NDJSON:

```text
qsol-map-spectral-sidecar-v0.2
```

The sidecar contains:

1. one canonical header;
2. all short-profile frame rows in channel/frame order;
3. all long-profile frame rows in channel/frame order;
4. one canonical trailer containing record count and a domain-separated receipt.

Every coefficient entry is:

```json
["real", "imag", "power"]
```

where all three are canonical decimal strings and `power = real^2 + imag^2`.

The verifier checks canonical line encoding, row order, arithmetic, record receipt and reconstructed short/long matrix commitments against the compact percept.

The writer/verifier process one spectral row at a time rather than constructing full matrices in memory.

## 11. CLI

```bash
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json --sidecar spectral-v02.ndjson
python3 -m qsol_map verify-v0.2 percept-v02.json
python3 -m qsol_map verify-sidecar-v0.2 percept-v02.json spectral-v02.ndjson
```

The original v0.1 commands remain available:

```bash
python3 -m qsol_map analyze input.wav -o percept-v01.json
python3 -m qsol_map verify percept-v01.json
```

## 12. Golden vectors

The test suite freezes both:

- the existing v0.1 percept hash;
- a new deterministic v0.2 percept hash.

The v0.2 golden percept SHA-256 is:

```text
c167694d60661ceac1d01d6504cbd8b5db77286ce09b28a342629b03046735d7
```

for the fixture defined in `tests/test_multiresolution.py`.

## 13. Optimization boundary

The exact Python implementation remains the authority path. The analysis loops process one frame at a time and the full-evidence sidecar streams rows instead of materializing complete matrices.

`QSOLKCB/OPT` remains the optimization policy source. Performance measurements must include target environment/toolchain context. No portable speedup is claimed by this profile.

## 14. Non-goals

v0.2 is not:

- subjective AI hearing;
- a psychoacoustic model;
- a claim about sensor response beyond the recorded digital samples;
- lossless audio compression;
- semantic music understanding;
- learned tokenization;
- a spatial-audio geometry solver;
- a validated human-onset detector;
- a realtime-performance guarantee.
