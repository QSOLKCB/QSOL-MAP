# Claim Boundaries

## What QSOL-MAP v0.1 may claim

The current reference implementation may claim that, for an accepted PCM16 RIFF/WAVE input and the frozen profile:

1. the complete input bytes are identified by SHA-256;
2. the PCM data chunk is independently identified by SHA-256;
3. channels are analyzed independently without hidden downmixing;
4. the exact triangular-window rule and committed twiddle constants are used;
5. the transform is computed with deterministic exact integer operations in the Python reference;
6. aggregate power and compact frame observations are derived from that transform;
7. complete complex and power matrices are cryptographically committed;
8. the canonical percept core receives a domain-separated SHA-256 identity;
9. the included golden vector protects the current reference behavior.

## What QSOL-MAP v0.1 does not claim

It does not claim:

- that an AI subjectively hears or experiences music;
- that L1 is equivalent to a human auditory system;
- that the packet is a complete psychoacoustic model;
- that the packet is a lossless representation of the waveform;
- that two percept packets with similar features necessarily sound similar to humans;
- that spectral power alone captures timbre, rhythm, harmony or musical meaning;
- that the current sparse frame events preserve every phase relationship;
- that the current transform is optimal, real-time, or compression-efficient;
- that a learned neural codec has already been implemented;
- that SoundStream code or weights are included;
- that any E8, qutrit, quantum, cosmological or other symbolic interpretation is intrinsic to the audio;
- that frequencies above conventional human hearing are present unless the source capture and sampling chain actually preserved them;
- that a sample rate proves the microphone or recording hardware had usable response all the way to Nyquist;
- that a cryptographic hash proves scientific validity or authenticity of the original physical event.

## Nyquist boundary

For a digital signal sampled at `f_s`, the representable discrete-time band is bounded by the sampling process and its Nyquist frequency `f_s / 2`.

QSOL-MAP may analyze bins above conventional human-audible ranges when the source sample rate supports them. That means only that the digital recording contains information in those represented bands. It does not establish that the source sensor captured them accurately.

## Determinism boundary

The current profile is a versioned Python reference. It uses exact integer signal arithmetic after parsing, but cross-language and cross-implementation byte identity is not yet a published claim.

A future implementation may claim conformance only after passing frozen vectors for:
- input parsing;
- windowing;
- transform coefficients;
- matrix commitments;
- packet serialization;
- percept identity.

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
