# QSOL-MAP Roadmap

## v0.1.0 - Protocol foundation and deterministic L1 reference

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

## v0.2.0 - Multi-resolution deterministic observation

- [x] Add a second long-window spectral profile without changing v0.1.
- [x] Publish the exact identity-bearing 1024-point Q15 twiddle contract, including the full normative quarter-wave table and deterministic reconstruction rule.
- [x] Publish the full long FFT algorithm: ten-bit input permutation, radix-2 butterflies, stage widths, twiddle-index schedule, exact scaling and retained-bin ordering, with executable specification conformance coverage.
- [x] Define optional full spectral sidecar artifacts so compact packets can commit to richer evidence.
- [x] Add transient/onset observations with an exact reference contract.
- [x] Add channel relationship and spatial-signal observations without implicit downmixing.
- [x] Add explicit analysis for high sample-rate inputs so captured represented ultrasonic bands remain available rather than being discarded for psychoacoustic reasons.
- [x] Add an environment-scoped benchmark harness guided by QSOLKCB/OPT without turning performance into a portable claim.
- [x] Harden verification against oversized decimal strings, Boolean/int ambiguity, output collisions, sidecar tampering and zero-denominator onset ratios.
- [x] Bind compact long-frame and transient energies to source-sized PCM16/window maxima, require short-source integer realizability, and require channel Gram feasibility including rank no greater than frame count.
- [x] Require exact one/two-sample long-window energy feasibility for mono and multichannel sources and tails, and for previous/current short-tail energies in transient candidates.
- [x] Check omitted single-event aggregate powers using bounded necessary two-square conditions, while preserving the distinction from multi-event sums and full coefficient verification.
- [x] Require one joint PCM16 assignment for three-frame multichannel Gram data and exact long-window energies, not just realizable diagonals or separate pairwise witnesses.
- [x] Account for omitted transient candidates and transition multiplicity in compact summary verification.
- [x] Reconstruct short and long sidecar profiles back to one PCM16 waveform and bind it to the PCM digest, frozen v0.1 identity, transient observations and channel relationships.
- [x] Verify canonical UTF-8/LF sidecar bytes before text newline translation and require empty writer destinations.
- [x] Require the sidecar writer to validate immutable PCM16 sample layout and recompute the interleaved PCM digest before rebuilding the exact v0.2 envelope or touching output.
- [x] Complete legal partial sidecar writes and reject non-progress, invalid counts or destination failures without returning a successful receipt.
- [x] Reject output aliases by filesystem identity, including case-equivalent and Unicode-normalization-equivalent names on filesystems that alias those spellings.
- [x] Freeze a v0.2 golden percept vector while preserving the published v0.1 golden vector.

### v0.2.0 implementation notes

Implemented profiles:

```text
qsol-map-fixed-fft-v0.1          frozen short reference
qsol-map-fixed-fft-1024-v0.2     long-window reference
qsol-map-multiresolution-v0.2    aggregate L1 profile
```

The optional full-evidence sidecar schema is:

```text
qsol-map-spectral-sidecar-v0.2
```

Sidecar conformance includes exact UTF-8/LF record bytes, exact reconstruction of both spectral profiles to one PCM16 waveform, verification of the reconstructed interleaved PCM SHA-256, rebuild of the frozen v0.1 percept identity, and reconstruction of transient/channel observations.

The full normative long transform is in specification section 4.1. The short-window feasibility checks reject unattainable one/two-sample energies without claiming complete compact-only integer feasibility for arbitrary lengths. The three-frame multichannel check is exact for its declared Gram and window-energy data; the single-event two-square filter is a bounded necessary check, not general large-integer factorization. Writer-side PCM validation binds the actual sample payload; it cannot recompute the original RIFF container hash from a `PCM16Wave` object that does not retain those bytes. Write-completion checks prevent false success receipts, but do not promise rollback of partial output or durable storage.

v0.2 remains Layer 1 deterministic acoustic observation. It does not introduce learned tokenization or semantic interpretation.

## v0.3.0 - L2 learned-token receiver

- [ ] Define model-manifest schema.
- [ ] Bind architecture, weights, codebooks, preprocessing, runtime, and token stream to hashes.
- [ ] Prototype a residual-vector-quantized receiver inspired by neural audio codec research such as SoundStream.
- [ ] Keep L1 available independently of the learned path.
- [ ] Define deterministic/reference inference expectations separately from accelerator replay expectations.
- [ ] Compare L2 similarity against L1 physical/spectral similarity without equating them.

## v0.4.0 - Cross-modal receivers

- [ ] Visual spectral-field receiver.
- [ ] Haptic/vibrotactile receiver.
- [ ] Light/audio reciprocal experiment informed by SPECTRAL PHOTOACOUSTIC.
- [ ] Receiver-neutral event interface.
- [ ] Accessibility evaluation protocol.

## v0.5.0 - Human perceptual correspondence

- [ ] Dataset format for voluntary human perceptual reports.
- [ ] Keep reports at L4 and statistical models at L3.
- [ ] Measure correlations between deterministic L1 features, L2 tokens, and human labels.
- [ ] Define uncertainty and inter-rater disagreement explicitly.

## v0.6.0 - Formal assurance

- [ ] Freeze mature transform definitions suitable for proof.
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
