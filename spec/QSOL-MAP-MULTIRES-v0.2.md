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

### 4.2 Normative per-bin coefficient divisors and event sums

The integer butterfly matrix implies guaranteed **per-bin coefficient divisors** at every retained output bin. Independent compact verifiers MUST derive them from the frozen transform, not an ad hoc list of special bins.

Represent an expression by a nonnegative divisor `d` guaranteed to divide every value for arbitrary integer real input. Divisor zero denotes an identically zero expression. Initialize every bit-reversed input with real divisor 1 and imaginary divisor 0. Propagate through the exact stage/base/offset schedule of section 4.1:

```text
scale(d, a) = 0                  if d == 0 or a == 0
scale(d, a) = d * abs(a)         otherwise

divisor(sum_or_difference) = gcd(d1, d2)

tr_div = gcd(scale(vr, wr), scale(vi, wi))
ti_div = gcd(scale(vr, wi), scale(vi, wr))
out_real_div = gcd(scale(ur, 32768), tr_div)
out_imag_div = gcd(scale(ui, 32768), ti_div)
```

Here `(ur,ui)` and `(vr,vi)` are input component divisors and `(wr,wi)` is the committed integer twiddle. Both butterfly outputs inherit the same divisor pair. Retain the first 513 pairs as `D_real[k]` and `D_imag[k]`.

Every reported component in **every long event**, including a channel with multiple events, MUST satisfy:

```text
D_real[k] == 0  implies real == 0
D_real[k] != 0  implies real mod D_real[k] == 0
D_imag[k] == 0  implies imag == 0
D_imag[k] != 0  implies imag mod D_imag[k] == 0
```

Define the corresponding power and sum divisors:

```text
g[k] = gcd(D_real[k]^2, D_imag[k]^2)
g_total = gcd(g[0], ..., g[512])
g_moment = gcd(0*g[0], 1*g[1], ..., 512*g[512])
```

Each aggregate power MUST be divisible by `g[k]`, including **multi-event aggregates**, because every summand has that divisor. This applies to omitted as well as reported bins. A zero divisor requires a zero value.

Each individual event's centroid denominator is `sum(P[k])` and its numerator is `sum(k*P[k])`. Therefore compact acceptance MUST require:

```text
denominator mod g_total == 0
numerator mod g_moment == 0
```

with the same zero-divisor convention. Under the frozen table, `g_total = 2^64`. Transferring one unit between event totals does not preserve this rule even if the channel aggregate is unchanged. Bin 8's real and imaginary divisors include `2^78`, so its power divisor includes `2^156`; DC, Nyquist and bin 256 include the existing exact scale constraints.

Divisibility is closed under summation. It MUST be enforced on multi-event sums. In contrast, the perfect-square endpoint and bounded two-square conditions in section 5 describe one row and MUST NOT be imposed on multi-event aggregate powers. A sum of endpoint squares need not itself be square. These necessary conditions do not establish complete FFT-row or waveform realizability.

## 5. Long-window observations

For each channel and long frame, v0.2 records:

- frame index and exact sample start;
- exact windowed energy;
- exact spectral-centroid numerator/denominator in bin coordinates;
- deterministic dominant non-DC bin;
- the eight highest-power components, ranked by descending power then ascending bin;
- real, imaginary and power values for each retained component.

For `a` available source samples before zero padding, require:

```text
windowed_energy <= 32768^2 * sum(w[n]^2 for n = 0..a-1)
```

For `a=1`, the energy must be a signed PCM16 square `x^2`; for `a=2`, it must be `x^2+4*y^2`. These rules apply to mono and multichannel sources and tails. Bounds on longer windows are necessary constraints, not a complete integer-realizability proof.

For a **complete two-sample source**, the sole event's scaled signed endpoints satisfy:

```text
s = 32768^10
D = x + 2*y
N = x - 2*y
D^2 + N^2 = 2 * windowed_energy
x = (D + N) / 2
y = (D - N) / 4
```

Both divisions must be exact, `x,y` must lie in `[-32768,32767]`, and the same witness must satisfy weighted energy and every reported endpoint sign. An omitted endpoint permits either sign of its observed magnitude. A multichannel source must use these same candidates for one joint Gram assignment, not a separate energy-only witness.

For exactly one long event, the aggregate equals its exact power row. Every bin, including omitted bins, obeys section 4.2 and must represent an integer complex power. The bounded necessary two-square filter removes powers of two from each nonzero power, requires odd part 1 modulo 4, and requires even valuations at `{3,7,11,19,23,31}`. DC and Nyquist additionally require perfect squares with square roots divisible by `32768^10`, regardless of source length or channel count. Zero is allowed. These checks reject values such as 3, 6, 12 and 21 without unbounded factorization. They are not a complete two-square existence proof. Only these single-row square conditions, not section 4.2 divisibility, are excluded from multi-event aggregates.

The reported top-component list for a single-event channel must match the aggregate row's descending-power/ascending-bin top eight exactly, and the dominant non-DC bin must match that row. For every event, component power equals `real^2+imag^2`; DC/Nyquist imaginary components are zero. Energy is zero exactly when total spectral power is zero. Total retained power is bounded by the finite transform gain `(2*max(32768^2,max_k(C[k]^2+S[k]^2)))^10` times windowed energy.

For a single event, divide endpoint roots by `s=32768^10` to obtain magnitudes. A reported endpoint keeps its signed scaled real value; only omitted endpoints remain sign-unspecified. For an allowed signed pair:

```text
D + N = 2 * sum(w[n] * x[n] for even n < a)
D - N = 2 * sum(w[n] * x[n] for odd  n < a)
```

Each side must be divisible by the gcd of its available coefficients `2*w[n]`; an empty parity requires exact zero. Both endpoint magnitudes and windowed energy have the same parity. Each endpoint magnitude `M` also obeys `M^2<=a*windowed_energy`. Equality forces the complete windowed vector to be constant for DC or alternating-constant for Nyquist. The signed endpoint must divide exactly by `a`; the forced vector must divide by every committed weight into signed PCM16 samples and reproduce the energy and both endpoint observations, including reported signs. Independent congruence witnesses cannot replace that equality witness.

For each channel/bin, let `A[k]` be aggregate power, `S[k]` the selected-power subtotal, `C[k]` the number of selecting events and `E` the event count. Per-event selected bins are unique; zero-power selections count. Require:

```text
S[k] <= A[k]
C[k] == E implies S[k] == A[k]
```

For the weakest selected component `(b_w,p_w)` in an event, omitted bins obey:

```text
b < b_w implies omitted_power[b] <= p_w - 1
b > b_w implies omitted_power[b] <= p_w
```

An earlier tied bin would have displaced the cutoff component. Selected bins contribute exactly their reported powers. Each aggregate also fits the sum of these selected contributions and omitted-bin caps across events.

### 5.1 Joint residual-power allocation

Independent bin caps are insufficient. Subtract each event's selected powers from its denominator to obtain row residual `r[e]`, and each bin's selected subtotal from its aggregate to obtain column residual `c[k]`. All residuals are nonnegative and their grand totals agree. There MUST exist a nonnegative integer matrix `z[e,k]` such that:

```text
sum_k z[e,k] = r[e]
sum_e z[e,k] = c[k]
z[e,k] = 0                         when event e selects bin k
z[e,k] <= p_w - (1 if k < b_w else 0) otherwise
```

This is an integer max-flow feasibility condition: source-to-event capacities `r[e]`, omitted event-to-bin capacities given above, and bin-to-sink capacities `c[k]`; acceptance requires flow equal to the total residual. Zero rows/columns may be omitted. This condition does not require each allocated cell to be an actual complex power, enforce per-cell transform divisibility, or reconstruct a waveform. The separate aggregate/component/event divisibility checks remain mandatory.

For each event, let `D` be denominator, `N` numerator, `S` selected total power and `K` selected weighted power. Require:

```text
K <= N <= K + 512 * (D - S)
sum(event denominators) = sum(aggregate powers)
sum(event numerators) = sum(k * aggregate[k])
```

The upper bound assigns omitted power to bin 512. These moment bounds remain necessary checks, not a claim that the residual max-flow also realizes every individual event moment.

For multichannel sources, each event energy is at most its channel's source energy times the maximum long weight squared, and the sum of covering event energies is at least the full-source energy. Adjacent events with a one/two-sample later tail must admit a common squared-sample witness whose preceding overlap contribution fits the previous energy. The remaining preceding non-overlap energy must be nonnegative; residuals up to 65536 additionally receive exact weighted-square feasibility over weights 1..512. Larger residuals do not receive a complete compact realizability proof.

The complete complex and power matrices are committed separately with:

```text
QSOL-MAP/LONG-COMPLEX-MATRIX/v0.2
QSOL-MAP/LONG-POWER-MATRIX/v0.2
```

using the same length-prefixed canonical-row construction as v0.1.

## 6. Frequency support and high sample rates

For sample rate `f_s`, bin `k` represents the exact rational frequency `k*f_s/1024`. The packet records Nyquist as `f_s/2` and does not infer hardware bandwidth from sample rate.

Aggregate power is grouped, by actual bin centres, into authored regions:

```text
[0, 20 kHz)
[20 kHz, 40 kHz)
[40 kHz, Nyquist]
```

Each subtotal is derived from the corresponding aggregate bins, not just their grand total. These labels do not establish a universal biological hearing cutoff. No psychoacoustic low-pass filter is applied. Represented energy above 20 kHz is retained up to Nyquist; a high sample rate does not prove physically valid ultrasonic capture.

## 7. Deterministic transient candidates

Candidates derive from consecutive **frozen v0.1 short-window energies** using:

```text
current > previous
and
2 * current >= 3 * previous
```

The rule identifier is `energy-rise-3-over-2-v0.2`. The compact packet records candidate count, total positive delta, maximum positive delta, and exactly `min(16,candidate_count)` strongest candidates, ranked by descending delta then ascending frame index. Each candidate records short-frame index, sample start, previous/current energies, exact positive delta and `rise_ratio`.

Every candidate energy obeys its source-sized PCM16 short-window maximum and its exact one/two-sample-tail energy feasibility. Candidate records describing the same short frame must agree on its energy. A one/two-sample current tail must also have a squared-sample witness compatible with its previous frame's overlap contribution, with nonnegative remainder and exact weighted-square residual feasibility through 65536 over the short non-overlap weights 1..128.

Let `T=max(0,short_event_count-1)`, `Psum=positive_delta_sum`, `M=maximum_positive_delta`, and `Rsum` the sum of reported candidate deltas. Require source-sized summary bounds, `0<=M<=Psum<=T*M`, every reported delta bounded by the summary, and:

```text
T == 0 implies Psum == M == 0
T == 1 implies Psum == M
M == 0 implies Psum == 0
Psum >= Rsum + candidate_count - reported_candidate_count
```

When every transition is reported as a candidate, both summary statistics equal the reported sum and maximum exactly. For a truncated list, let the weakest reported delta/frame be `(d_w,f_w)`. An omitted candidate at frame `f` obeys `d<=d_w-1` for `f<f_w`, otherwise `d<=d_w`.

Known adjacent reported energies constrain candidate eligibility in both mixed and all-candidate sets. For previous energy `P`, current energy `C`, and delta `d=C-P`:

```text
known P only: d >= max(1,ceil(P/2)), and P+d <= current source bound
known C only: d >= C-min(previous source bound,C-1,floor(2*C/3))
both known: d=C-P>0 and 2*C>=3*P
```

Enough eligible unreported frames must exist for the omitted-candidate count. Their smallest required contributions must fit the unreported mass `Psum-Rsum`. When all transitions are candidates, the exact omitted mass also fits the per-frame cutoff allowances and `M` equals the strongest reported candidate delta.

A maximum stronger than the strongest reported candidate must come from a non-candidate transition. Acceptance requires at least one such unreported transition and enough unreported mass to attain `M`. Its known adjacent energies must permit that exact delta and fail the onset threshold. With neither energy known, the necessary cap is:

```text
d <= min((previous_max-1)//2,(current_max-1)//3)
```

because a positive non-candidate rise requires `P>=2*d+1` and `C>=3*d+1`. With one known energy, the inferred other energy must satisfy source/tiny-tail feasibility and `2*C<3*P`; with both known, `d=C-P` is exact.

### 7.1 Total unreported mass capacity

Every unreported transition receives a non-candidate positive-delta cap `n[f]`:

```text
both known: C-P if C>P and 2*C<3*P, else 0
P only: max(0,min(current_max-P,(P-1)//2))
C only: C-(floor(2*C/3)+1), if that minimum P fits previous_max and P<C; else 0
neither: min((previous_max-1)//2,(current_max-1)//3), or 0 for a zero bound
```

For an eligible omitted candidate derive a candidate cap `a[f]`: exact `C-P` when both are known, `current_max-P` when only P is known, C when only C is known, otherwise `current_max`. Intersect with the top-16 tie-aware allowance and require it to meet the candidate minimum above.

For omitted count `O`, start with `sum(n[f])` and replace exactly O eligible transition caps with candidate caps. The maximum capacity is the baseline plus the O largest gains `a[f]-n[f]`, including negative gains when required. Fewer than O eligible frames is rejection. Require `Psum-Rsum` not to exceed this capacity. These are necessary independently bounded transition/classification constraints, not a complete witness for the shared short-energy chain.

For nonzero previous energy the finite ratio is:

```json
"rise_ratio": {"numerator": "current_energy", "denominator": "previous_energy"}
```

When previous energy is zero it is `null`, never a zero-denominator ratio.

All covering long-event energies zero prove the channel samples are zero because their window weights are strictly positive. Such a channel requires candidate count zero, empty candidates, and both transient summaries zero.

This is an authored deterministic detector, not equivalence to human onset perception or a validated music-information-retrieval onset detector.

## 8. Channel relationships

Channels remain independent; there is no downmix. Each pair `i<j` records full-source dot product and sign, left/right sum of squares, difference/sum energies and zero-lag correlation squared. Correlation is null if either source energy is zero. Otherwise its numerator is dot squared and denominator is the product of source energies. Require exact sum/difference identities, consistent channel energies across pairs, PCM16 source-energy bounds, the Cauchy bound, positive-semidefinite complete Gram matrix and exact rank no greater than `frame_count`.

For a one-frame multichannel source, the real DC coefficient divided by `32768^10` recovers each signed sole sample. Its energy is that PCM16 sample's square; every dot product equals the signed sample product, not merely its magnitude. One-frame long energies and both endpoint powers must describe those same samples.

Complete two-frame multichannel sources require one joint signed PCM16 vector assignment matching every Gram entry, the long weighted energies and endpoint evidence as defined in section 5. Mono two-frame sources still require the endpoint-compatible weighted-energy witness despite having no pair records.

Complete three- and four-frame multichannel sources require the joint signed witness in section 8.2. For three frames, the established source/window energy equations `E=x^2+y^2+z^2`, `W=x^2+4*y^2+9*z^2`, and `W-E=3*y^2+8*z^2` remain necessary, but energy-only candidates cannot contradict reported spectral endpoint signs. Separate witnesses for each pair are insufficient.

These are signal relationships, not inferred speaker geometry or perceived stereo width.

### 8.1 Three-frame mono weighted-energy feasibility

A complete three-frame mono source must admit signed PCM16 `(x,y,z)` with `W=x^2+4*y^2+9*z^2`. There is one long event. With `s=32768^10`, its exact endpoint powers satisfy:

```text
P0 = (s*(x+2*y+3*z))^2
P512 = (s*(x-2*y+3*z))^2
```

Require perfect-square powers and roots divisible by s. For each permitted sign choice `D=+/-sqrt(P0)/s`, `N=+/-sqrt(P512)/s`, compute:

```text
y = (D-N)/4
A = (D+N)/2
R = 2*(W-4*y^2)-A^2
```

Both divisions are exact; R is nonnegative and square. For either signed root `d=+/-sqrt(R)`, derive `x=(A+d)/2`, `z=(A-d)/6` by exact division. All coordinates must lie in `[-32768,32767]`. At least one triple exists; zero signs/repeated roots need not be duplicated. At most eight candidates are considered.

Every reported endpoint component fixes the signed scaled real value that the same witness must reproduce. Only omitted endpoints permit either sign. This is exact for weighted energy, endpoint powers and reported signs, not for the remaining spectrum, matrix commitments or source hashes. It applies to the complete three-frame mono source, not three-sample tails of longer sources. Rehashed `[1,0,0]` with W=2 and `[1,0,1]` with only a reported Nyquist sign flipped must be rejected.

### 8.2 Joint signed three- and four-frame multichannel witnesses

For each channel, source energy E is its Gram diagonal, W is its sole long-event weighted energy, and endpoint powers yield magnitudes after exact square-root/scale checks. Reported DC/Nyquist components fix signed D/N; unreported endpoints allow either sign of their magnitude. The same signed PCM16 vector MUST satisfy:

```text
E = x^2 + y^2 + z^2 + t^2
W = x^2 + 4*y^2 + 9*z^2 + 16*t^2
D = x + 2*y + 3*z + 4*t
N = x - 2*y + 3*z - 4*t
-32768 <= x,y,z,t <= 32767
```

For a three-frame source use t=0 and retain `(x,y,z)`; for a four-frame source retain `(x,y,z,t)`.

For each allowed D/N pair derive `A=(D+N)/2=x+3z` and `B=(D-N)/4=y+2t`, rejecting nonexact division. For four frames enumerate integer t within PCM16 and the necessary bounds `t^2<=E`, `16*t^2<=W`; for three frames consider only zero. Then:

```text
y = B - 2*t
R = 2*(W - 4*y^2 - 16*t^2) - A^2
x = (A + u)/2
z = (A - u)/6
```

Require y in range and `y^2+t^2<=E`; require R nonnegative and square; try both `u=+/-sqrt(R)` with exact divisions and x/z in range. Retain only vectors reproducing E and W exactly. D/N are then reproduced by construction. There are at most four endpoint sign pairs, 65536 t values per pair and two root signs, with no search over coordinate pairs or floating-point approximation. Three-frame enumeration has at most eight candidates.

At least one candidate per channel must exist. One **joint** assignment across channels must reproduce every Gram dot product using those exact candidates. Backtracking over at most eight channels, checking assigned dot products and diagonals, is one implementation; separate per-pair assignments are not sufficient. Repeated channel evidence may reuse a candidate set only under exact equality of all its inputs.

This rejects four-frame orthogonal norms 1 and 7 and three-frame identical-channel Gram data paired with opposite reported DC signs. It is exact feasibility for the stated short-source energies, endpoints and Gram data, not verification of unreported coefficients, matrix/source hashes, arbitrary source lengths or tails of longer sources. Full sidecar verification remains the reconstructed-evidence path.

## 9. Compact percept identity

The core schema is `qsol-map-percept-core-v0.2` and envelope schema is `qsol-map-percept-envelope-v0.2`. Identity is:

```text
SHA256(UTF8("QSOL-MAP/PERCEPT/v0.2") + NUL + canonical_percept_core_bytes)
```

Identity-bearing JSON remains float-free. Large exact integers are decimal strings. The implementation identifier is `qsol-map-python-reference-0.2.0` and package version is `0.2.0`.

## 10. Verification contract

The compact verifier fails closed for untrusted data. Acceptance requires:

- exact schemas, Layer-1 identity, implementation/profile definitions and canonical source metadata;
- exact typed fields, not Boolean/int equality aliases; canonical matrix/source digests and bounded canonical decimal strings;
- valid event structure, source/window and finite-transform energy bounds, tiny-tail and overlap feasibility;
- section 4.2 **per-bin coefficient divisors** for every event's reported coefficients, all aggregate powers including multi-event sums, and each event's denominator/numerator sum divisors;
- single-event two-square filters, endpoint squares/scale/parity, signed window congruences, endpoint Cauchy bounds and equality witnesses;
- exact aggregate equality for fully selected bins, selected lower bounds, tie-aware omitted-bin capacities and one joint residual allocation under section 5.1;
- exact global centroid identities and per-event selected/omitted moment bounds;
- valid transient structure, source/tail bounds, adjacent reported-energy consistency, exact complete selections, top-16 ordering, mixed-set eligibility, unreported mass capacity and maximum feasibility under sections 7 and 7.1;
- the all-zero cross-resolution rule;
- exact channel identities, PSD/rank/source bounds, one/two-sample integer witnesses, three-frame mono witnesses under section 8.1 and shared signed three/four-frame multichannel witnesses under section 8.2;
- the final domain-separated percept digest.

Untrusted decimal strings are bounded to 1024 digits before integer conversion. Signed zero is encoded only as `"0"`, not `"-0"`. Malformed documents must return `False`, not escape the Boolean contract through conversion or recursion errors. Compact acceptance is not a complete arbitrary-length waveform or source-authenticity proof.

## 11. Optional full spectral sidecar

The compact packet commits full matrices without embedding every coefficient. The optional schema `qsol-map-spectral-sidecar-v0.2` is canonical NDJSON: one header, all short-profile rows in channel/frame order, all long-profile rows in channel/frame order, then one receipt trailer.

Each record is exact UTF-8 terminated by one LF byte. CRLF and other translated delimiters are noncanonical. Binary-backed text inputs are read before newline translation. Seekable inputs, including StringIO, begin at logical position zero; nonzero positions are rejected without consuming or rewinding. Already-zero binary-backed text wrappers are synchronized before exact reads. Non-seekable binary-backed inputs bypass tell/seek. Explicit record iterables are checked as the complete supplied sequence, with no claim about previously discarded data.

StringIO verifier inputs using newline=None are rejected because prior CRLF can already have been erased. Explicit newline="" and newline="\n" remain supported. Writer semantics differ: newline=None preserves written LF, while translating newline="\r" or newline="\r\n" sinks are rejected. Binary-backed writer output bypasses text translation.

Every coefficient entry is `["real","imag","power"]`, with bounded canonical decimals and `power=real^2+imag^2`. Acceptance requires:

- canonical UTF-8/LF/header bytes and the complete-stream rules above;
- exact deterministic order and plain non-Boolean channel/frame/sample positions;
- coefficient syntax, bounds, endpoint reality and power arithmetic;
- record/trailer receipts and reconstructed short/long matrix commitments;
- exact inverse PCM16 reconstruction for both profiles with overlap, window divisibility, sample-range and zero-tail checks;
- identical reconstructed short/long waveforms;
- reconstructed interleaved PCM SHA-256 equal to `source.pcm_s16le_sha256`;
- rebuilt frozen-v0.1 percept equal to `short_reference.percept_sha256`;
- long-event observations, transients and channel relationships equal to reconstructed evidence;
- no missing/extra records, including decode failures after a valid trailer.

Before analysis rebuild or output, the writer independently validates PCM16Wave metadata, immutable tuple-of-tuples dimensions and plain signed PCM16 samples. It recomputes SHA-256 in bounded chunks over frame-major, ascending-channel signed little-endian PCM bytes and requires the supplied PCM digest to match. Inconsistency raises ValueError before output or receipt. The writer then rebuilds v0.2 and requires exact canonical-envelope equality, including matrix and observation commitments.

Destinations must be provably empty, seekable and at offset zero. Legal short writes are completed; counts must be plain integers greater than zero and no larger than the remaining payload. Zero, None, negative, Boolean, non-integer or oversized counts raise OSError; destination errors propagate. Failed output may remain partial, but no successful receipt is returned. Binary-backed text output uses exact UTF-8 and completed text write counts are character counts. This does not promise rollback or durable storage.

PCM16Wave does not retain original RIFF bytes; sample commitment validation does not recompute `source_sha256` or prove authenticity. Verification uses bounded reads and temporary spools rather than complete in-memory matrices/waveforms, and validates the envelope before allocating channel spools.

## 12. CLI

```bash
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json
python3 -m qsol_map analyze-v0.2 input.wav -o percept-v02.json --sidecar spectral-v02.ndjson
python3 -m qsol_map verify-v0.2 percept-v02.json
python3 -m qsol_map verify-sidecar-v0.2 percept-v02.json spectral-v02.ndjson
```

Percept and sidecar outputs must identify different destinations and must not alias the input or implicit stdout as applicable. Existing aliases use filesystem identity. Initially nonexistent names are checked for filesystem case folding and Unicode normalization equivalence, including NFC/NFD spellings such as precomposed/decomposed `é`. The CLI reserves nontruncating regular-file handles, validates identities before writes, and writes through held descriptors rather than reopening replacement pathnames after analysis. A changed reserved path fails rather than being followed. This is not an atomic multi-file transaction.

Frozen v0.1 commands remain:

```bash
python3 -m qsol_map analyze input.wav -o percept-v01.json
python3 -m qsol_map verify percept-v01.json
```

## 13. Golden vectors

The suite freezes the existing v0.1 percept hash and the deterministic v0.2 percept hash:

```text
c167694d60661ceac1d01d6504cbd8b5db77286ce09b28a342629b03046735d7
```

for `tests/test_multiresolution.py`'s fixture. The existing separately frozen sidecar receipt also remains protected. These prerelease verifier corrections do not change authored transform output or golden identities.

## 14. Optimization boundary

The exact Python implementation remains the authority path. Analysis processes one frame at a time; sidecar evidence streams rows. QSOLKCB/OPT remains the optimization policy source. Measurements include target environment/toolchain context and imply no portable speedup. The checkout-runnable benchmark is:

```bash
python3 scripts/benchmark_v02.py
```

It is not a CI performance gate.

## 15. Non-goals

v0.2 is not subjective AI hearing, a psychoacoustic model, proof of sensor response beyond supplied samples, lossless audio compression, semantic music understanding, learned tokenization, a spatial geometry solver, a validated human-onset detector, or a realtime/portable performance guarantee.
