# QSOL-MAP Fixed FFT Profile v0.1

Status: **reference profile**

Profile identifier:

```text
qsol-map-fixed-fft-v0.1
```

Implementation identifier:

```text
qsol-map-python-reference-0.1.0
```

## 1. Input adapter

The canonical adapter accepts a complete little-endian RIFF/WAVE file with:

- RIFF form `WAVE`;
- exactly one `fmt ` chunk;
- an exactly 16-byte PCM `fmt ` body; extended `fmt ` forms are unsupported;
- exactly one `data` chunk;
- integer PCM format code 1;
- 16 bits per sample;
- 1 through 8 channels;
- sample rate 1 through 768000 Hz;
- `block_align = channels * 2`;
- `byte_rate = sample_rate * block_align`;
- a non-empty data payload containing an integer number of frames;
- a RIFF size matching the complete supplied byte sequence.

Unknown non-`fmt `/`data` chunks are retained in the source byte hash but ignored by the signal adapter.

The adapter performs no:
- resampling;
- normalization;
- channel mixing;
- dithering;
- filtering;
- metadata interpretation.

## 2. L0 identities

Two independent hashes are recorded:

```text
wav_sha256       = SHA256(complete input bytes)
pcm_s16le_sha256 = SHA256(data chunk payload)
```

These are ordinary SHA-256 hashes, not signatures.

## 3. Channel separation

Interleaved PCM frames are deinterleaved by channel index.

Every channel is analyzed independently.

## 4. Framing

Constants:

```text
N   = 256 samples
hop = 128 samples
```

Frame start addresses are:

```text
0, 128, 256, ...
```

for every start strictly less than the channel sample count.

Samples beyond the end of the channel are zero.

This makes tail handling explicit and ensures even a short non-empty input produces at least one frame.

## 5. Integer triangular window

`WINDOW_WEIGHTS[n]` is defined exactly as `min(n + 1, 256 - n)` for `n = 0..255`.

Windowed input is computed exactly as:

```text
w[n] = sample[n] * WINDOW_WEIGHTS[n]
```

There is no division or right shift.

The large scale is intentional.

## 6. Frozen complex twiddles

`TWIDDLE_COS_Q15[k]` and `TWIDDLE_SIN_Q15[k]` are committed integer tables.

They represent the profile's frozen approximation to:

```text
exp(-i * 2*pi*k/256)
```

with:

```text
Q15_ONE = 32768
```

Runtime trigonometric evaluation is not part of the profile.

## 7. Radix-2 transform

Input is placed in 8-bit-reversed index order.

For each radix-2 butterfly:

```text
t_re = v_re * wr - v_im * wi
t_im = v_re * wi + v_im * wr

u_re_scaled = u_re * Q15_ONE
u_im_scaled = u_im * Q15_ONE

out_even = (
    u_re_scaled + t_re,
    u_im_scaled + t_im
)

out_odd = (
    u_re_scaled - t_re,
    u_im_scaled - t_im
)
```

Every stage applies the same scale to both paths.

No right shift, saturation, fixed-width overflow, float conversion, or rounding occurs in the Python reference.

Only bins `0..128` are retained for real input.

## 8. Power

For each complex coefficient:

```text
power[k] = real[k]^2 + imag[k]^2
```

The Python reference uses unbounded exact integers.

## 9. Frequency interpretation

A bin does not store a rounded floating-point frequency.

For sample rate `f_s` and bin `k`:

```text
frequency_hz = k * f_s / 256
```

The packet stores this as a rule plus the integer sample rate and bin index.

## 10. Frame events

Each frame records:

- frame index;
- start sample;
- exact windowed energy;
- spectral-centroid numerator and denominator;
- dominant non-DC bin;
- four highest-power components.

Ranking is:

```text
descending power, then ascending bin index
```

Each top component includes:

- bin;
- real coefficient;
- imaginary coefficient;
- power.

Large integer values are decimal strings.

## 11. Matrix commitments

The complete complex coefficient row is represented for hashing as canonical JSON:

```text
[["real","imag"], ...]
```

The complete power row is:

```text
["power", ...]
```

For each matrix, hashing begins with:

```text
UTF8(domain) + NUL
```

For every row:

```text
uint64_be(len(canonical_row_bytes)) + canonical_row_bytes
```

Domains:

```text
QSOL-MAP/COMPLEX-MATRIX/v0.1
QSOL-MAP/POWER-MATRIX/v0.1
```

The resulting SHA-256 digests commit to the full matrices without embedding the matrices in the compact percept packet.

## 12. Aggregate power

For each bin:

```text
aggregate_power[k] = sum(power_frame[k] for all frames)
```

Aggregate powers are encoded as decimal strings.

## 13. Waveform observations

Per channel:

```text
sample_count
peak_abs
sum_squares
zero_crossings
```

Zero crossings use the last non-zero sign. Zero samples do not independently create crossings.

## 14. Canonical percept core

Identity-bearing JSON:

- uses UTF-8;
- sorts object keys lexicographically;
- uses compact separators;
- has no trailing newline;
- permits null, booleans, strings, arrays, objects and portable safe integers;
- forbids floats;
- requires larger exact integers to be decimal strings.

Percept identity is:

```text
SHA256(
  UTF8("QSOL-MAP/PERCEPT/v0.1")
  + NUL
  + canonical_percept_core_bytes
)
```

The digest is stored outside the core in the envelope, avoiding a circular self-hash.

Verification is fail-closed. A v0.1 verifier accepts only the v0.1 envelope and core schemas, the declared L1 layer, the supported profile and implementation identifiers, the required source/profile/channel/event structure, canonical field types, and lowercase 64-character hexadecimal SHA-256 strings. A matching percept digest alone is not sufficient to validate an arbitrary dictionary as a QSOL-MAP percept.

## 15. Golden vector

`tests/test_analysis.py` contains a deterministic generated PCM fixture and freezes:

- percept SHA-256;
- power-matrix SHA-256;
- complex-matrix SHA-256.

A change to these values is a canonical protocol change unless the existing implementation is demonstrated to be incorrect relative to this specification.

## 16. Non-goals

v0.1 is not:
- a psychoacoustic codec;
- a neural codec;
- a lossless audio representation;
- a music transcription system;
- a subjective hearing model;
- a real-time performance claim;
- a cross-language conformance claim.
