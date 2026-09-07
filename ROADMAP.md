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
- [x] Bind complete two-sample channel energy to its exact DC/Nyquist endpoint powers with `D^2 + N^2 = 2*windowed_energy`.
- [x] Check omitted single-event aggregate powers using bounded necessary two-square conditions, while preserving the distinction from multi-event sums and full coefficient verification.
- [x] Require exact aggregate equality for bins selected in every long event, including zero-power selections, while allowing unreported contributions for partially selected bins.
- [x] Enforce the `32768^10` coefficient scale on both selected and omitted DC/Nyquist endpoint powers for every single-event channel; do not impose a single-square requirement on multi-event sums.
- [x] Preserve reported DC/Nyquist signs and enforce source-tail window congruences; omitted endpoints remain sign-unspecified.
- [x] Enforce descending-power/ascending-bin top-component cutoffs, including a strict lower power for earlier omitted bins that would otherwise win a tie.
- [x] Bound every event centroid numerator from both sides using selected power plus the maximum contribution of omitted bins.
- [x] Require one joint PCM16 assignment for three-frame multichannel Gram data and exact long-window energies, not just realizable diagonals or separate pairwise witnesses.
- [x] Validate three-frame mono weighted energy against signed PCM16 triples and exact DC/Nyquist powers with at most eight endpoint-derived candidates, without a coordinate search, and require every reported endpoint sign to match the same witness.
- [x] Account for omitted transient candidates and transition multiplicity in compact summary verification.
- [x] Enforce the deterministic top-16 transient cutoff for omitted candidates, including ascending-frame tie ordering.
- [x] Require a declared transient maximum stronger than the strongest reported candidate to be attainable by an actual non-candidate transition with sufficient unreported positive-delta mass.
- [x] Reconstruct short and long sidecar profiles back to one PCM16 waveform and bind it to the PCM digest, frozen v0.1 identity, transient observations and channel relationships.
- [x] Verify canonical UTF-8/LF sidecar bytes before text newline translation and require empty writer destinations.
- [x] Reject seekable verifier inputs not positioned at logical zero, without consuming or rewinding them; explicit record iterables remain scoped to the complete supplied sequence.
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

Compact conformance also preserves signed endpoint evidence. For a single event, reported DC/Nyquist signs must satisfy the committed even/odd long-window congruences, while omitted endpoints may use either sign. For a complete two-sample channel, the scaled endpoint magnitudes additionally satisfy `D^2 + N^2 = 2*windowed_energy`. The three-frame mono witness must match every reported endpoint sign. Per-event top-K bounds use the authored descending-power/ascending-bin ordering, so an earlier omitted bin cannot tie the weakest selected bin. Per-event centroid numerators are bounded below by selected weighted power and above by assigning all omitted power to bin 512.

Transient conformance treats the reported 16 strongest candidates as an actual deterministic cutoff. Omitted candidates must rank after that cutoff, with equal deltas permitted only at later frame indices. If a summary maximum exceeds the strongest reported candidate, it must be supplied by a non-candidate transition and the unreported positive-delta mass must be large enough to realize it. When every transition is a candidate, the omitted positive mass must fit the top-16 cutoff allowances and the maximum remains the strongest reported delta.

The three-frame mono check in specification section 8.1 is exact for its weighted energy and two endpoint powers. It does not extend to three-sample tails of longer sources or prove the remaining spectral/source commitments. Regression coverage includes the rehashed energy-2 example, 14625 exhaustive small energy/endpoint cases, signed PCM16 limits and unchanged sidecar round trips.

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
