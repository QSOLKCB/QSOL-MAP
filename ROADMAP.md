# QSOL-MAP Roadmap

## v0.1 - Protocol foundation and deterministic L1 reference

- [x] Define L0-L4 epistemic layer firewall.
- [x] Strict PCM16 RIFF/WAVE adapter.
- [x] Independent source and PCM SHA-256 identities.
- [x] Exact integer triangular window and frozen Q15 complex twiddle constants.
- [x] Exact-integer 256-point FFT reference.
- [x] Aggregate spectral power and compact frame events.
- [x] Complex-matrix and power-matrix commitments.
- [x] Canonical percept envelope and domain-separated hash.
- [x] Frozen end-to-end golden vector.
- [x] Dependency-free optimized CI baseline guided by QSOLKCB/OPT.

## v0.2 - Multi-resolution deterministic observation

- [ ] Add a second long-window spectral profile without changing v0.1.
- [ ] Define optional full spectral sidecar artifacts so compact packets can commit to richer evidence.
- [ ] Add transient/onset observations with an exact reference contract.
- [ ] Add channel relationship and spatial observations without implicit downmixing.
- [ ] Add explicit analysis for high sample-rate inputs so captured ultrasonic bands remain available rather than being discarded for psychoacoustic reasons.
- [ ] Benchmark and optimize bounded analysis chunks using QSOLKCB/OPT patterns.

## v0.3 - L2 learned-token receiver

- [ ] Define model-manifest schema.
- [ ] Bind architecture, weights, codebooks, preprocessing, runtime, and token stream to hashes.
- [ ] Prototype a residual-vector-quantized receiver inspired by neural audio codec research such as SoundStream.
- [ ] Keep L1 available independently of the learned path.
- [ ] Define deterministic/reference inference expectations separately from accelerator replay expectations.
- [ ] Compare L2 similarity against L1 physical/spectral similarity without equating them.

## v0.4 - Cross-modal receivers

- [ ] Visual spectral-field receiver.
- [ ] Haptic/vibrotactile receiver.
- [ ] Light/audio reciprocal experiment informed by SPECTRAL PHOTOACOUSTIC.
- [ ] Receiver-neutral event interface.
- [ ] Accessibility evaluation protocol.

## v0.5 - Human perceptual correspondence

- [ ] Dataset format for voluntary human perceptual reports.
- [ ] Keep reports at L4 and statistical models at L3.
- [ ] Measure correlations between deterministic L1 features, L2 tokens, and human labels.
- [ ] Define uncertainty and inter-rater disagreement explicitly.

## v0.6 - Formal assurance

- [ ] Freeze mature transform definitions.
- [ ] Add Lean 4 reference formalization for transform invariants that are actually suitable for proof.
- [ ] Keep formalized mathematics separate from executable conformance and empirical validation.
- [ ] Apply QSOLKCB/OPT trust-preserving Lean CI patterns after the proof boundary is defined.

## Release rule

Do not freeze a major canonical profile until:
1. its claim boundary is explicit;
2. golden vectors are stable;
3. replay identity is documented;
4. tests cover malformed and adversarial inputs;
5. optimization does not weaken the reference contract.
