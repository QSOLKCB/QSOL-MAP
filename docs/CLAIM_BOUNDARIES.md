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
2. a separate deterministic 1024-sample / 512-hop long-window spectral reference is computed using frozen Q15 twiddles and exact unbounded-integer Python arithmetic;
3. complete long complex and power matrices receive independent cryptographic commitments;
4. represented long-window bins are retained up to source Nyquist without a psychoacoustic low-pass filter;
5. aggregate power is reported in authored `[0,20 kHz)`, `[20,40 kHz)`, and `[40 kHz,Nyquist]` reference regions when such represented bins exist;
6. deterministic transient candidates are produced by the exact `energy-rise-3-over-2-v0.2` rule applied to frozen v0.1 short-frame energies;
7. a transition from zero previous energy is represented with `rise_ratio: null`, never a zero-denominator rational value;
8. exact pairwise channel signal relationships are recorded without downmixing;
9. an optional canonical NDJSON sidecar can carry every short and long complex spectral row while remaining separately verified against compact matrix commitments;
10. sidecar ordering, coefficient arithmetic, receipt hashes and exact typed position fields are checked fail-closed;
11. malformed oversized decimal strings are rejected before untrusted integer conversion can escape the verifier contract;
12. the v0.2 golden vector protects the current multi-resolution reference behavior.

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

## Transient boundary

The v0.2 transient candidate rule is deterministic and exact:

```text
current > previous
and
2 * current >= 3 * previous
```

It is an authored Layer-1 observation rule. Candidate count and strongest-candidate selection are protocol outputs, not empirical claims about human onset perception.

When `previous == 0`, the ratio is not finite. The canonical representation uses `rise_ratio: null` rather than encoding an invalid denominator of zero.

## Channel boundary

Channels are never implicitly mixed in the canonical v0.1 or v0.2 paths.

Pairwise v0.2 quantities such as dot product, difference energy, sum energy and zero-lag correlation squared are exact signal relationships. They do not by themselves establish acoustic scene geometry or spatial perception.

## Sidecar boundary

The optional `qsol-map-spectral-sidecar-v0.2` is complete spectral evidence for the declared short and long transforms, not a replacement audio format.

Its verifier checks deterministic ordering, typed integer position fields, coefficient arithmetic, receipt identity and reconstruction of the compact packet's matrix commitments.

A valid sidecar proves conformance to the declared serialization/commitment relationship. It does not prove that the source recording is authentic or scientifically meaningful.

## Determinism boundary

The current profiles are versioned Python references. They use exact integer signal arithmetic after parsing, but universal cross-language and cross-implementation byte identity is not yet a published claim.

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
- invalid structural data is rejected even when an attacker recomputes outer hashes.

These checks establish protocol validity, not trust in the origin of the data.

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
