# Stage twelve: revised TWO-stage division

Status: implementation, core regression and the bounded pilot are complete, 2026-10-31. The new first stage emits selected MTF light plus three coarse blurred fields in one AOT invocation; stage two fuses upsampling/mix/log and the original tail. There is no fields-only third call. Retain it as an opt-in research candidate; **do not enable it by default or claim a stable speedup from this pilot**.

| Case | Original E2 median / p95 ms | New E2 median / p95 ms | Observed median reduction | Thermal old / new |
| --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 10.45 / 16.89 | 9.94 / 12.26 | +4.9% | 0 / 0 |
| portra400-coffee-3840x2160 | 57.81 / 101.63 | 42.46 / 48.14 | +26.5% | 1 / 0 |
| hp5plus400-coffee-1920x1080 | 14.22 / 29.17 | 12.21 / 17.11 | +14.1% | 1 / 1 |
| hp5plus400-coffee-3840x2160 | 29.62 / 45.14 | 30.57 / 49.10 | -3.2% | 1 / 1 |

| Case | Original → new device peak MiB | Original → new GPU dispatches | AOT calls both arms |
| --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 322.9 → 315.0 | 122 → 110 | 5 |
| portra400-coffee-3840x2160 | 1084.2 → 1090.1 | 240 → 240 | 10 |
| hp5plus400-coffee-1920x1080 | 286.1 → 278.8 | 98 → 86 | 5 |
| hp5plus400-coffee-3840x2160 | 627.7 → 642.5 | 175 → 175 | 10 |

Eight valid rounds, 12,625 measurement requests. One pair per case, alternating order, original 5/30/2/5-second protocol, fresh process per arm, one frame in flight and 1-GiB pool. Band512 / A2048 / margin360 / math/precision/sync are unchanged. No assistant-owned build or cleanup ran during timing. All phase hashes match the verified own-arm output.

This is matching-source C/C. Clean frozen R serves as the pixel oracle; upstream timing was not rerun. Portra UHD has different thermal maxima (control 1, candidate 0), and background drift remains unresolved. Its apparent 26.5% median reduction must not be attributed entirely to the cut. HP5 UHD is about 3.2% slower, and both UHD device peaks increase. All adverse outcomes, p95, footprint and retention remain in the raw report.

Twelve independent full-pixel comparisons pass. All four new E2 images are bitwise equal to the original E2; max error to R is about 2.563e-6 and alpha exact. Four traces confirm new-only selected/primary MTF regions, final F generated once, kernel binding counts and preceding-band GPU completion. They do not establish exclusive kernel costs or eliminate all U/horizontal recomputation.

The synthetic actual-GPU-helper probe passes nine incremental calls, one zero-height field update, A wrap and whole-frame field comparison with max error 0. Fourteen lifecycle frame comparisons, four invalid-option checks and injected post-producer failure/drain/recovery pass. It is not an injected hardware fault inside a particular producer subkernel.

126 Python checks, 11 CPU and 11 Metal stage checks, current generated headers/locks, default release build and 18 focused release Swift tests (FrameResourcesTests/FrameVariantTests) pass. The retained old three-stage host passes syntax-only compilation after the generic-call change. Full current-source release AOT/parity and broader JIT/render regression remain pending. Initial consumer-admission and shim namespace build failures are retained and were fixed before measured workers; they are not scored attempts.

Ordinary15 / bundle21 private kernels link frozen legacy63. The mixed diagnostic has no current-release stamp. Actual F payload is additional persistent storage versus original E2, not a promised total saving. Scratch/pool lifetimes and allocation size classes may affect peaks; no unmeasured attribution is asserted.

Decision: keep the experimental cut for follow-up, with no default or PR promotion. The pilot is mixed on UHD cost and thermally confounded; a repeated/held-out campaign has not started. A useful next independent control is producer lead based on the supported dependency bound rather than fixed360, while preserving the cut, ring, band and completion policy. That change is not implemented here. Formal stable B_ref, retention/locality and PR gates stay pending.

Implementation: `70fa45378391eb16b09cd98b12d480d70796acd1`. [Machine-readable provenance](wavefront-stage12-results.json) records hashes and every raw location; [two-stage contract/reproduction](wavefront-bundle-contract.md). The durable CLI preparation has not had a separate second full regeneration; the actual executed script and generated artifacts are retained.

Timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/wavefront-bundle/timing/893d4216de8a/report.json`.
Chart: `/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-two-stage-bundle-stage12/comparison.png`.

Docker was not quit. No Taggii/iOS code, public default, photographic math/stock data or external service was changed. No upstream PR was created.
