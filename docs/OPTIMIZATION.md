# Optimization Policy

QSOL-MAP uses QSOLKCB/OPT as the first reference for performance work.

## Current CI choices

CI deliberately uses:
- one Ubuntu 24.04 lane;
- the runner's existing Python 3;
- no package installation;
- a pinned checkout action;
- a short timeout;
- concurrency cancellation for superseded runs;
- the complete unit suite on every pull request and `main` push.

This removes setup and matrix overhead without introducing a documentation-only bypass or skipping semantic coverage.

There is no published portable QSOL-MAP CI speedup claim. Correctness remains the gate.

## v0.2 reference workload

v0.2 adds a 1024-point exact-integer long-window transform, channel-pair observations and optional full-spectral evidence. These are intentionally more expensive than the frozen v0.1 short reference.

The implementation applies bounded-memory structure before more aggressive optimization:

- static long-window and twiddle tables are frozen outside hot loops;
- one long frame is transformed at a time;
- full spectral sidecars stream one row at a time instead of materializing complete matrices;
- compact percepts retain hashes/aggregates rather than embedding all coefficients;
- no parallel worker count or native backend is assumed without target measurements.

## Environment-scoped benchmark

Run from an ordinary repository checkout:

```bash
python3 scripts/benchmark_v02.py
```

Optional controls:

```bash
python3 scripts/benchmark_v02.py --frames 48000 --sample-rate 48000 --repeats 3
```

The harness records:
- frame count;
- sample rate;
- repetition count;
- individual elapsed nanoseconds;
- median elapsed nanoseconds;
- deterministic percept SHA-256;
- Python version and implementation;
- platform, machine and processor strings;
- an explicit claim boundary.

The harness is **not** a CI performance gate and does not establish a portable speedup. Before/after optimization claims require measurements on the same runner class and preserved conformance evidence.

## Applied OPT principles

### OPT-PY-001

Applied:
- small deterministic fixtures;
- frozen v0.1 and v0.2 golden vectors;
- adversarial regression cases targeted at contract boundaries;
- no repeated research-scale sweeps in regression tests;
- full suite execution after behavior changes.

Not currently needed:
- large caches;
- convergence exits;
- statistical sweep reduction.

These should be added only if profiling shows a real bottleneck and the tested invariant remains intact.

### OPT-INV-001

Applied structurally:
- v0.2 reuses the exact frozen v0.1 result as its short-reference evidence instead of redefining the v0.1 protocol.

Future computation reuse is allowed only when exact source/profile identity or another named invariant proves equivalence. No approximate result reuse belongs in the canonical path.

### OPT-DSP-001

Applied:
- static window and twiddle structures are precomputed and frozen;
- runtime trigonometric evaluation is removed from both canonical spectral references;
- sidecar generation and verification process bounded rows rather than full matrices.

Future optimized backends may use bounded chunks, vectorization, native code, SIMD or GPU work only behind exact or explicitly bounded conformance checks. The exact Python path remains the authority reference.

### OPT-PAR-001

Not currently applied to the canonical implementation. The reference must first establish target measurements and deterministic output-order rules.

Future multi-channel or batch analysis may use bounded deterministic parallelism after benchmarking and exact output-order/conformance tests.

### OPT-LEAN-001

Reserved for a later formal-assurance phase after suitable mathematical invariants have been frozen.

## Verification performance is also a correctness issue

Untrusted v0.2 decimal strings are bounded before integer conversion. This is not promoted as a speed optimization; it is a fail-closed resource and correctness boundary that prevents malformed multi-thousand-digit inputs from escaping or dominating numeric validation.

Likewise, sidecar lines have an explicit maximum character count and are processed sequentially.

Do not weaken these validation boundaries for benchmark gains.

## Rules for performance pull requests

A performance PR should record:
1. the exact contract being preserved;
2. baseline and optimized commit SHAs;
3. runner/OS/CPU/toolchain;
4. command used;
5. repetition count;
6. wall-time measurements;
7. correctness/conformance result;
8. memory or allocation observations when relevant;
9. rollback condition.

Do not copy worker counts, chunk sizes, tolerances, cache keys or historical percentages from OPT without re-measurement.

## Reference path rule

An optimized implementation must not become the sole specification.

The exact Python reference remains available until another implementation is independently frozen as an equal-authority conformance target.
