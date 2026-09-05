# Optimization Policy

QSOL-MAP uses QSOLKCB/OPT as the first reference for performance work.

## Current CI choices

The initial CI deliberately uses:
- one Ubuntu 24.04 lane;
- the runner's existing Python 3;
- no package installation;
- a pinned checkout action;
- a short timeout;
- concurrency cancellation for superseded runs;
- the complete unit suite on every pull request and `main` push.

This removes setup and matrix overhead without introducing a documentation-only bypass or skipping semantic coverage.

There is no published QSOL-MAP CI speedup claim yet. The first target-runner measurements should establish the baseline.

## Applied OPT principles

### OPT-PY-001

Applied:
- small deterministic fixtures;
- a complete but compact golden vector;
- no repeated research-scale sweeps in regression tests;
- full suite execution after behavior changes.

Not yet needed:
- caching;
- convergence exits;
- parameter-grid reduction.

These should be added only if profiling shows a real bottleneck.

### OPT-INV-001

Potential future use:
- reuse identical window/twiddle/profile structures;
- reuse analysis results only when exact source/profile identity proves equivalence.

No result-reuse optimization is currently enabled.

### OPT-DSP-001

Applied:
- static window and twiddle structures are precomputed and frozen;
- runtime trigonometric evaluation is removed from the reference path.

Future optimized backends may use bounded chunks, vectorization or native code, but only behind exact or explicitly bounded conformance checks.

### OPT-PAR-001

Not currently applied. The initial reference suite is too small to justify parallel complexity.

Future multi-channel or batch analysis may use bounded deterministic parallelism after benchmarking and output-order tests.

### OPT-LEAN-001

Reserved for a later formal-assurance phase after suitable mathematical invariants have been frozen.

## Rules for performance pull requests

A performance PR should record:
1. the exact contract being preserved;
2. baseline and optimized commit SHAs;
3. runner/OS/CPU/toolchain;
4. command used;
5. repetition count;
6. wall-time measurements;
7. correctness/conformance result;
8. rollback condition.

Do not copy worker counts, chunk sizes, tolerances, cache keys or historical percentages from OPT without re-measurement.

## Reference path rule

An optimized implementation must not become the sole specification.

The exact Python reference remains available until another implementation is independently frozen as an equal-authority conformance target.
