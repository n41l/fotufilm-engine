# Fork-main integration validation — 2026-11-16

The user authorized committing this research branch and merging it into the user-owned fork main. This integrates the experiments and their evidence; it does not activate experimental defaults, integrate Taggii/iOS or constitute an upstream release.

Code tested:0e44d464c6b4cc8dd8360f9adaaabe03ba9f9f01. Only this validation record is added afterwards.

- 89 targeted Python regression tests passed, including isolated fusion admission, resource analysis, allocator and CPU/GPU method probes.
- CPU/Metal stage checks:11 each, zero failures.
- Release Swift build passed;18 FrameResources/FrameVariant release tests passed.
- Generated configuration and AOT-variant consistency checks passed.
- Fresh generator compilation and all63 default macOS AOT libraries completed.
- AOT/JIT comparison:36 variants, zero failing, no constant-output failures. Worst agreeing difference1.57356262e-05, within the existing1e-4/categorical-budget4 contract.
- General/windowed comparison:all70 frames agree, worst linear difference2.81e-06, within the existing1e-5 and encoded<1/255 contract.

The full parity harness used new build/pr-merge-parity-20261116 and build/pr-merge-parity-kernels-20261116 directories, two workers and the pinned Halide installation. Historical outputs were preserved. The raw log and machine-readable validation are in the former directory. No performance campaign was rerun and no thresholds were relaxed. This validates the current default paths plus the focused tests; all-stock, holdout, retention/concurrency, stable performance B_ref and experimental release promotion remain separate gates.

PRs:n41l/fotufilm-engine#1 (research implementation/tools/results), n41l/sb_ai#8 (research records and handoff). The documentation PR has already merged. The research branch remains named codex/fotufilm-metal-optimizations.
