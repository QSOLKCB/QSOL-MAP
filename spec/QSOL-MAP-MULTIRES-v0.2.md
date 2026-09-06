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

The long transform uses the following **normative frozen quarter-wave cosine table** for the 1024-point Q15 profile. These 257 integers are identity-bearing and are not regenerated at runtime:

```text
32768, 32767, 32766, 32762, 32758, 32753, 32746, 32738, 32729, 32718, 32706, 32693,
32679, 32664, 32647, 32629, 32610, 32590, 32568, 32546, 32522, 32496, 32470, 32442,
32413, 32383, 32352, 32319, 32286, 32251, 32214, 32177, 32138, 32099, 32058, 32015,
31972, 31927, 31881, 31834, 31786, 31737, 31686, 31634, 31581, 31527, 31471, 31415,
31357, 31298, 31238, 31177, 31114, 31050, 30986, 30920, 30853, 30784, 30715, 30644,
30572, 30499, 30425, 30350, 30274, 30196, 30118, 30038, 29957, 29875, 29792, 29707,
29622, 29535, 29448, 29359, 29269, 29178, 29086, 28993, 28899, 28803, 28707, 28610,
28511, 28411, 28311, 28209, 28106, 28002, 27897, 27791, 27684, 27576, 27467, 27357,
27246, 27133, 27020, 26906, 26791, 26674, 26557, 26439, 26320, 26199, 26078, 25956,
25833, 25708, 25583, 25457, 25330, 25202, 25073, 24943, 24812, 24680, 24548, 24414,
24279, 24144, 24008, 23870, 23732, 23593, 23453, 23312, 23170, 23028, 22884, 22740,
22595, 22449, 22302, 22154, 22006, 21856, 21706, 21555, 21403, 21251, 21097, 20943,
20788, 20632, 20475, 20318, 20160, 20001, 19841, 19681, 19520, 19358, 19195, 19032,
18868, 18703, 18538, 18372, 18205, 18037, 17869, 17700, 17531, 17361, 17190, 17018,
16846, 16673, 16500, 16326, 16151, 15976, 15800, 15624, 15447, 15269, 15091, 14912,
14733, 14553, 14373, 14192, 14010, 13828, 13646, 13463, 13279, 13095, 12910, 12725,
12540, 12354, 12167, 11980, 11793, 11605, 11417, 11228, 11039, 10850, 10660, 10469,
10279, 10088, 9896, 9704, 9512, 9319, 9127, 8933, 8740, 8546, 8351, 8157,
7962, 7767, 7571, 7376, 7180, 6983, 6787, 6590, 6393, 6195, 5998, 5800,
5602, 5404, 5205, 5007, 4808, 4609, 4410, 4211, 4011, 3812, 3612, 3412,
3212, 3012, 2811, 2611, 2411, 2210, 2009, 1809, 1608, 1407, 1206, 1005,
804, 603, 402, 201, 0
```

Let this tuple be `Q[0..256]`. The complete cosine table `C[k]` for `k mod 1024` is reconstructed exactly by:

```text
quadrant, offset = divmod(k mod 1024, 256)

quadrant 0: C[k] =  Q[offset]
quadrant 1: C[k] = -Q[256 - offset]
quadrant 2: C[k] = -Q[offset]
quadrant 3: C[k] =  Q[256 - offset]
```

The complete sine table is then defined exactly by:

```text
S[k] = -C[(256 - k) mod 1024]
```

The transform twiddle at index `k` is therefore the exact integer pair `(C[k], S[k])`. The table is the normative contract; no rounding, truncation, tie-breaking or runtime trigonometric generation rule is implicit.

The frozen table approximates:

```text
exp(-i * 2*pi*k/1024)
```

Runtime trigonometric evaluation is not part of the canonical profile.

The Python reference uses arbitrary-precision integer arithmetic. No right shift, saturation, float conversion or fixed-width overflow is used in transform identity.

### 4.1 Normative long FFT algorithm

The input to this algorithm is exactly the 1024 integer windowed samples `xw[0..1023]` defined in section 3, including the zero-padded tail. The algorithm does not apply a second window.

First, reverse exactly ten bits of each index, including leading zeros:

```text
rev10(j) = sum(((j div 2^b) mod 2) * 2^(9-b) for b = 0..9)
state[j] = (xw[rev10(j)], 0), j = 0..1023
```

Execute ten radix-2 stages in this exact order:

```text
width = 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024
half = width div 2
step = 1024 div width
base = 0, width, 2*width, ..., 1024-width
 offset = 0..half-1
 twiddle_index = offset * step
 left = base + offset
 right = left + half
```

For each butterfly, read both input pairs before overwriting either output. With `u = state[left]`, `v = state[right]`, `wr = C[twiddle_index]`, `wi = S[twiddle_index]`, and `q = 32768`, compute:

```text
tr = v.real * wr - v.imag * wi
 ti = v.real * wi + v.imag * wr
state[left]  = (q * u.real + tr, q * u.imag + ti)
state[right] = (q * u.real - tr, q * u.imag - ti)
```

All products and sums are exact integers. In particular, the `q` multiplication of the upper input occurs at every stage. There is no division by `q`, no per-stage rounding or normalization, and no final division by 1024 or by `q^10`.

After the last stage, retain `state[0]` through `state[512]` inclusive in ascending natural bin order. Do not apply another bit permutation. These 513 complex pairs form the committed long complex row; each corresponding power is `real^2 + imag^2`.

The following executable reference is normative. `quarter` must be the exact 257 integers in section 4. The conformance suite executes this block and compares complete coefficient rows with the implementation, including asymmetric impulses and a nontrivial integer input.

<!-- BEGIN NORMATIVE LONG FFT -->
```python
def long_fft_reference(windowed, quarter):
    if len(windowed) != 1024 or len(quarter) != 257:
        raise ValueError("expected 1024 windowed samples and 257 frozen constants")

    def cosine(index):
        quadrant, offset = divmod(index % 1024, 256)
        if quadrant == 0:
            return quarter[offset]
        if quadrant == 1:
            return -quarter[256 - offset]
        if quadrant == 2:
            return -quarter[offset]
        return quarter[256 - offset]

    cosines = tuple(cosine(index) for index in range(1024))
    sines = tuple(-cosines[(256 - index) % 1024] for index in range(1024))
    state = []
    for index in range(1024):
        reversed_index = sum(
            ((index // (2 ** bit)) % 2) * (2 ** (9 - bit))
            for bit in range(10)
        )
        state.append((windowed[reversed_index], 0))

    for width in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024):
        half = width // 2
        step = 1024 // width
        for base in range(0, 1024, width):
            for offset in range(half):
                index = offset * step
                wr, wi = cosines[index], sines[index]
                left, right = base + offset, base + offset + half
                ur, ui = state[left]
                vr, vi = state[right]
                tr = vr * wr - vi * wi
                ti = vr * wi + vi * wr
                state[left] = (32768 * ur + tr, 32768 * ui + ti)
                state[right] = (32768 * ur - tr, 32768 * ui - ti)
    return tuple(state[:513])
```
<!-- END NORMATIVE LONG FFT -->

An impulse with `xw[0] = 1` and all other entries zero produces `(32768^10, 0)` at every retained bin. This scaling is part of the profile. An ordinary normalized or floating-point FFT is not a substitute for this algorithm, even if it uses the same twiddle table.

## 5. Long-window observations

For each channel and long frame, v0.2 records:

- frame index and exact sample start;
- exact windowed energy;
- exact spectral-centroid numerator/denominator in bin coordinates;
- deterministic dominant non-DC bin;
- the eight highest-power components, ranked by descending power then ascending bin;
- real, imaginary and power values for each retained component.

For a long frame with `a` source samples available before zero padding, exact PCM16 input requires:

```text
windowed_energy <= 32768^2 * sum(w[n]^2 for n = 0..a-1)
```

When `a = 1`, the energy must additionally equal `x^2` for a signed PCM16 integer `x`. When `a = 2`, it must equal `x^2 + 4*y^2` for signed PCM16 integers `x` and `y`. These exact feasibility checks apply to every channel, including mono sources, and to one- or two-sample tails of longer sources. An upper bound alone does not permit an unattainable integer energy. For longer windows these checks do not claim to solve the full integer realizability problem; full sidecar verification separately reconstructs and binds the actual samples.

For a channel with exactly one long event, `aggregate_power_by_bin` is its exact power row. Every entry, including omitted interior bins, must be a sum of two integer squares; DC and Nyquist must additionally be perfect squares. The compact verifier applies these bounded necessary checks to each nonzero entry: remove all powers of two and require the remaining odd part to be 1 modulo 4; require an even exponent of each prime in the fixed set `{3, 7, 11, 19, 23, 31}`. Zero is allowed. These checks reject impossible powers such as 3, 6, 12, and 21 without attempting unbounded factorization of large FFT integers. Passing them is not a complete two-square factorization proof or proof of a realizable FFT row. The single-row restriction does not apply to aggregates over multiple events, which sum more than two squares. Full sidecar verification checks the actual integer coefficients.

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

Each reported candidate records:

- short-profile frame index;
- exact sample start;
- previous energy;
- current energy;
- exact positive delta;
- `rise_ratio`.

Each previous/current candidate energy must fit the exact PCM16 maximum implied by the corresponding frozen 256-sample triangular window and source-tail availability. For either short frame with only one available source sample, energy must be a PCM16 integer square. With two available samples, energy must be `x^2 + 4*y^2` for PCM16 integers, since both triangular windows start with weights 1 and 2. The check uses the availability of each previous/current frame independently and applies to every channel.

The summary `positive_delta_sum` and `maximum_positive_delta` are likewise bounded by the source-sized short-frame maxima. When the source produces fewer than two short frames, no transition exists and both summary totals are exactly `"0"`.

If `T = short_event_count - 1`, every positive delta is at most `maximum_positive_delta`, so:

```text
positive_delta_sum <= T * maximum_positive_delta
```

Every omitted candidate is still a strict positive integer rise. Therefore, when `candidate_count` exceeds the number of reported strongest candidates:

```text
positive_delta_sum >=
    sum(reported candidate positive_delta)
    + (candidate_count - reported_candidate_count)
```

For non-zero previous energy:

```json
"rise_ratio": {
  "numerator": "current_energy",
  "denominator": "previous_energy"
}
```

When the previous energy is exactly zero, the finite ratio is undefined and the canonical representation is:

```json
"rise_ratio": null
```

A zero denominator is never emitted.

This is an authored deterministic energy-rise detector. It is **not** claimed to be equivalent to a human auditory onset percept or a validated music-information-retrieval onset detector.

## 8. Channel relationships

Channels remain independent signal streams. v0.2 does not downmix.

For every ordered pair `i < j`, the compact packet records exact full-source integer quantities:

- dot product and its sign;
- sum of squares for each channel;
- sum-of-squares of `left - right`;
- sum-of-squares of `left + right`;
- exact rational zero-lag correlation squared when both channel energies are non-zero.

When either channel has zero total energy, `zero_lag_correlation_squared` is `null`.

The complete channel Gram matrix must be positive semidefinite and its exact rank must not exceed the source `frame_count`, because the declared channel vectors live in that sample-dimensional space.

For short sources, additional integer realizability constraints are identity-bearing. A one-frame channel energy must be a PCM16 integer square. A two-frame multi-channel source must admit one joint set of exact PCM16 integer vectors whose Gram products equal every declared channel relationship. For those two-frame vectors, the long event energy must also equal the exact committed weighted energy:

```text
windowed_energy = sample[0]^2 * w[0]^2 + sample[1]^2 * w[1]^2
```

with `w[0] = 1` and `w[1] = 2`. A two-frame mono source has no pairwise Gram records, but must still admit PCM16 samples realizing that same weighted energy. A merely bounded but unattainable value is invalid.

For a three-frame multi-channel source, one joint assignment of signed PCM16 triples must reproduce every Gram entry and each channel's long-window energy. Individually realizable diagonals or separate witnesses for each pair are insufficient. For each channel, with declared source energy `E` and windowed energy `W`, its candidate triple `(x, y, z)` must satisfy:

```text
E = x^2 + y^2 + z^2
W = x^2 + 4*y^2 + 9*z^2
W - E = 3*y^2 + 8*z^2
-32768 <= x, y, z <= 32767
```

The reference enumerates at most 32769 magnitudes of `z`, derives `y^2` and `x^2` exactly, checks integer squares and PCM16 limits, and then searches for one assignment satisfying all channel dot products. The magnitude 32768 permits only the negative sign. This is an exact feasibility check for the declared three-frame Gram and weighted-energy data, not a reconstruction of the committed full spectrum or a general feasibility solver for arbitrary source lengths.

These are signal relationships, not inferred speaker geometry or a claim about perceived stereo width.

### 8.1 Three-frame mono weighted-energy feasibility

A source with exactly three PCM frames and one channel has no Gram records, but its long event must still admit signed PCM16 samples `(x, y, z)` with:

```text
W = x^2 + 4*y^2 + 9*z^2
-32768 <= x, y, z <= 32767
```

There is exactly one long event, so its DC and Nyquist aggregate powers `P0` and `P512` are exact frame powers. Section 4.1 gives the exact endpoint scale `s = 32768^10`. The same candidate triple must satisfy:

```text
P0   = (s * (x + 2*y + 3*z))^2
P512 = (s * (x - 2*y + 3*z))^2
```

Both powers must be perfect squares whose nonnegative square roots are divisible by `s`. For every sign choice `D = +/-sqrt(P0)/s` and `N = +/-sqrt(P512)/s`, compute:

```text
y = (D - N) / 4
A = (D + N) / 2
R = 2 * (W - 4*y^2) - A^2
```

Require exact integer division and a nonnegative perfect square `R`. For either root `d = +/-sqrt(R)`, derive `x = (A+d)/2` and `z = (A-d)/6`, again requiring exact division and all three signed PCM16 bounds. At least one valid triple must exist. Zero signs or repeated roots need not be duplicated. There are at most eight candidate triples, so no search over PCM16 coordinate pairs or large-integer factorization is needed.

This is exact feasibility for the declared weighted energy and the two endpoint powers. It does not verify the remaining spectrum, its matrix commitments, or the source digests. The check applies to the complete three-frame mono source, not to three-sample tails of longer sources where aggregate endpoints are sums across events. Full sidecar verification remains the complete reconstructed-evidence check. In particular, rehashing a genuine `[1, 0, 0]` envelope after replacing its energy `"1"` with `"2"` must return `False`.

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

The package implementation identifier is:

```text
qsol-map-python-reference-0.2.0
```

and the package version is `0.2.0`.

## 10. Verification contract

The compact v0.2 verifier is fail-closed for untrusted data.

It requires:

- exact envelope/core schemas;
- Layer-1 identity;
- exact implementation/profile definitions;
- canonical source metadata;
- exact typed integer fields rather than Python Boolean/int equality aliases;
- canonical matrix/source SHA-256 digests;
- valid bounded decimal strings;
- valid long-event structure, source/window energy bounds, one/two-sample energy feasibility including mono and tails, finite transform-power bounds, and top-component capacity bounds;
- three-frame mono weighted-energy and endpoint-power feasibility under section 8.1, without bypassing mono sources because Gram records are absent;
- the bounded single-event aggregate two-square checks and exact endpoint squares in section 5, including bins omitted from the compact components;
- valid transient rule structure, arithmetic, source-sized energy bounds, one/two-sample short-tail feasibility, transition-multiplicity bounds, and minimum contributions from omitted candidates;
- valid channel-pair structure, correlation arithmetic, positive-semidefinite Gram feasibility, Gram rank not exceeding `frame_count`, and short-source integer realizability including joint two- and three-frame Gram/long-energy compatibility;
- the final domain-separated percept digest.

Untrusted decimal strings are bounded to at most 1024 digits before `int()` conversion. This is both a format bound and a fail-closed guard against Python's configurable integer-string digit limit.

Malformed documents must produce `False` from verification rather than escaping the Boolean verifier contract through conversion errors.

## 11. Optional full spectral sidecar

The compact packet commits full matrices without embedding every coefficient. v0.2 optionally exports the full short+long evidence as canonical NDJSON:

```text
qsol-map-spectral-sidecar-v0.2
```

The sidecar contains:

1. one canonical header;
2. all short-profile frame rows in channel/frame order;
3. all long-profile frame rows in channel/frame order;
4. one canonical trailer containing record count and a domain-separated receipt.

Every record is encoded as exact UTF-8 bytes terminated by one LF byte (`0x0A`). CRLF (`0x0D 0x0A`) and other translated line endings are non-canonical. Verification of file-backed text streams must inspect the underlying bytes before any `TextIOWrapper` newline translation can convert CRLF into LF.

Every coefficient entry is:

```json
["real", "imag", "power"]
```

where all three are canonical bounded decimal strings and `power = real^2 + imag^2`.

Acceptance requires all of the following identity-bearing evidence relationships:

- canonical UTF-8/LF line encoding and exact canonical header bytes;
- exact deterministic row order and plain non-Boolean integer channel/frame/sample position fields;
- coefficient decimal syntax, bounds, and exact power arithmetic;
- records receipt and trailer receipt;
- reconstructed short and long complex/power matrix commitments against the compact percept;
- exact inverse reconstruction of PCM16 samples from both spectral profiles, including overlap consistency, window divisibility, PCM16 range, and zero-padded tails;
- identical reconstructed PCM waveform from the short and long profiles;
- SHA-256 of the reconstructed interleaved PCM payload equal to `source.pcm_s16le_sha256`;
- reconstruction of the frozen v0.1 percept identity from the short-profile evidence equal to `short_reference.percept_sha256`;
- transient observations reconstructed from the short-profile rows equal to the compact transient observations;
- channel relationships recomputed from reconstructed PCM equal to the compact channel relationships;
- no missing or extra records, including decode failures after an otherwise valid trailer.

The public sidecar writer validates the supplied `PCM16Wave` independently before rebuilding analysis or touching its destination. The Python API requires an immutable tuple of channel tuples with exactly the declared channel count and frame count, plain signed PCM16 integer samples, and adapter-valid integer metadata. It recomputes SHA-256 over the samples serialized in frame order, then ascending channel order within each frame, with each sample encoded as signed 16-bit little-endian bytes. This digest must equal `pcm_s16le_sha256`; a stale or directly constructed inconsistent wave raises `ValueError` before any sidecar output or receipt. Hashing uses bounded payload chunks, not a complete duplicate PCM payload.

The writer then accepts an envelope only when rebuilding v0.2 analysis from those validated samples produces that exact canonical envelope, so it cannot emit a receipt for evidence that contradicts declared matrix or observation commitments. The destination must be provably empty, seekable, and positioned at byte/character offset zero before the header is written; append-positioned or stale-tail destinations are rejected.

Every record payload and LF terminator must be fully accepted by the destination before the writer returns a successful receipt. The Python adapter loops on legal short writes; a write count must be a plain integer greater than zero and no greater than the remaining payload length. Zero, `None`, negative, Boolean, non-integer or oversized counts raise `OSError`, and destination exceptions propagate. A failed write may leave partial output, but must not return a successful receipt. This is not a transactional rollback or durable-storage guarantee. Binary-backed text streams use exact UTF-8 bytes; the adapter's text `write()` return value is the completed character count.

`PCM16Wave` does not retain the original RIFF container bytes. This writer check therefore validates the sample-payload commitment, not a reconstruction of `source_sha256` or authenticity of the source recording.

The verifier uses bounded row reads and bounded temporary spools rather than constructing complete spectral matrices or unbounded in-memory waveforms.

## 12. CLI

```bash
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json --sidecar spectral-v02.ndjson
python3 -m qsol_map verify-v0.2 percept-v02.json
python3 -m qsol_map verify-sidecar-v0.2 percept-v02.json spectral-v02.ndjson
```

The compact percept output and sidecar output must identify different filesystem destinations. Existing aliases are detected by filesystem identity. For initially nonexistent names in one target directory, the implementation also rejects aliases produced by filesystem case folding and Unicode normalization equivalence, including NFC/NFD-equivalent spellings such as precomposed and decomposed `é`, when the target filesystem treats those names as the same destination. A collision is rejected before either output is written.

The original v0.1 commands remain available:

```bash
python3 -m qsol_map analyze input.wav -o percept-v01.json
python3 -m qsol_map verify percept-v01.json
```

## 13. Golden vectors

The test suite freezes both:

- the existing v0.1 percept hash;
- a new deterministic v0.2 percept hash.

The v0.2 golden percept SHA-256 is:

```text
c167694d60661ceac1d01d6504cbd8b5db77286ce09b28a342629b03046735d7
```

for the fixture defined in `tests/test_multiresolution.py`.

## 14. Optimization boundary

The exact Python implementation remains the authority path. The analysis loops process one frame at a time and the full-evidence sidecar streams rows instead of materializing complete matrices.

`QSOLKCB/OPT` remains the optimization policy source. Performance measurements must include target environment/toolchain context. No portable speedup is claimed by this profile.

The environment-scoped benchmark must run from an ordinary checkout:

```bash
python3 scripts/benchmark_v02.py
```

It is not a CI performance gate.

## 15. Non-goals

v0.2 is not:

- subjective AI hearing;
- a psychoacoustic model;
- a claim about sensor response beyond the recorded digital samples;
- lossless audio compression;
- semantic music understanding;
- learned tokenization;
- a spatial-audio geometry solver;
- a validated human-onset detector;
- a realtime-performance guarantee;
- a portable benchmark claim.
