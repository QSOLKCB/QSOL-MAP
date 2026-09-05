# Provenance and Design Lineage

QSOL-MAP is a new repository. It does not vendor code from the references below. Their role is methodological and architectural unless otherwise stated.

## QSOL source lineage

### QSOLKCB/SONIFICATION

Pinned reference commit:

```text
da3207663ecf4ff9936dc18bca3429f5a65a17ec
```

Relevant ideas:
- receiver-neutral committed event documents;
- deterministic ordering;
- implementation and artifact identity;
- acyclic receipt construction;
- explicit separation between mathematical structure and rendered audio;
- strict scientific claim boundaries.

### QSOLKCB/SPECTRAL

Pinned reference commit:

```text
5265b7f130287f80b5cf0d3de5bb2953152f90cd
```

Relevant ideas:
- deterministic DSP and source hashing;
- reproducible PCM/WAV artifacts;
- waveform and FFT observations;
- fingerprints and manifests;
- visual analysis kept separate from audio identity;
- cross-modal light-to-sound experimentation in PHOTOACOUSTIC.

### QSOLKCB/E8_MUSIC

Pinned reference release:

```text
v1.1.0
commit d8e5983d84af03f03a969abe3356dcf80c0e0e97
```

Relevant ideas:
- separate interpretive and canonical audio contracts;
- source -> signal -> PCM -> WAV identity chains;
- fail-closed canonical profiles;
- separation of formalized transform correctness, implementation conformance, scientific validation and physical truth.

### QSOLKCB/OPT

Pinned reference commit:

```text
10c2e27075b9174ef2f2d586c281dc1da45588b5
```

Relevant optimization records:
- OPT-PY-001 deterministic test execution;
- OPT-INV-001 invariant-driven computation reuse;
- OPT-DSP-001 control-rate, sparse and vectorized DSP;
- OPT-PAR-001 bounded deterministic parallel execution;
- OPT-LEAN-001 trust-preserving Lean dependency reuse.

QSOL-MAP does not import historical speedup percentages as expected performance. Every optimization must be re-measured in this repository.

## Neural audio codec reference

Neil Zeghidour, Alejandro Luebs, Ahmed Omran, Jan Skoglund, Marco Tagliasacchi.

**SoundStream: An End-to-End Neural Audio Codec.**

arXiv:2107.03312, 2021.

Relevant ideas:
- learned waveform encoder;
- residual vector quantization;
- discrete compact audio representations;
- decoder reconstruction;
- bitrate-scalable residual quantization.

QSOL-MAP does not contain SoundStream source code, model weights, codebooks or a compatibility claim. SoundStream is cited as prior art and motivation for the future L2 learned-token layer.

## Why provenance is pinned

Mutable `main` branches are useful for development but weak evidence anchors. This document records exact commits/releases so later protocol discussions can distinguish:
- what the source repository contained at the time of design;
- what QSOL-MAP independently implemented;
- what remains proposed.
