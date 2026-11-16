# Stage twenty-six: MTF fusion × best-fit pool combination

The sanctioned combination of candidate 1 (windowed MTF pointwise fusion) with the stage19 best-fit buffer-pool policy, tested together for the first time as a 4×4 Williams factorial on the active Portra UHD case: frozen original, fusion alone, pool alone, and the combination. All four experimental arms are pixel-identical to R. The fused twin is rebuilt from the current source (key `8c7c3a8b1d60d1cc17ae723cf8a0c0a7d4c4781bdaad8f7a3fafe6dea17a692b`); the pool policy is the unchanged stage19 suffix; the two never mix with the print-MTF or coupler flags.

Correctness: 25 of 25 independent full-pixel comparisons (four primary cases plus the odd two-window crop, five arms) bitwise-equal to R; dispatch R/W0/BF 77, MTF/COMBO 73 on the active cases and unchanged elsewhere; JIT/AOT worst linear error 1.9669533e-06. Single-call new-buffer totals on UHD: R 53, W0 52, MTF 51, BF 45, COMBO 44. Sixteen valid rounds, 10,794 measurement requests, every round re-checked against its own arm's proof hashes and dispatch counts.

| Arm | Four round medians ms | Median ms | Worst p95 ms | Device peak MiB |
| --- | --- | ---: | ---: | ---: |
| R-B1 | 41.432 / 46.593 / 45.492 / 47.540 | 46.042 | 63.008 | 1183.72 |
| MTF | 36.188 / 37.954 / 46.347 / 65.280 | 42.151 | 120.894 | 1071.72 |
| BF | 38.825 / 40.619 / 45.979 / 60.648 | 43.299 | 89.151 | 991.72 |
| COMBO | 35.514 / 40.445 / 40.877 / 39.440 | **39.943** | 56.374 | 1031.72 |

**Latency: the combination is the fastest and by far the most stable arm.** COMBO beats the original by 13.25%, the fusion alone by 5.24% and the pool alone by 7.75%; it wins three of four rounds outright and never exceeds 40.9 ms, while every other arm exceeded 45 ms at least once (its round spread is 5.4 ms against MTF's 29.1). The late-round drift that inflated MTF to 65.3 and BF to 60.6 ms in round 3 did not touch COMBO — one campaign cannot prove that stability, but the pattern is consistent.

**Memory: the savings overlap, they do not add.** Naive stacking would predict −304 MiB; the combination delivers −152.0 MiB (1183.72 → 1031.72). The fusion keeps its full −112, but the pool's contribution shrinks from −192 alone to about −40 on top of the fusion: the two MTF intermediates the fusion eliminates were among the large freed blocks the best-fit pool recycles best, so with them gone there is less for the policy to save. If minimum peak memory is the goal, pool-only (991.72) still wins; if latency and stability matter, the combination leads.

Conclusion: the combination is the best-performing configuration measured on this line, and the first arm to beat every single-arm control — still one upscaled SDR case, four balanced repeats, defaults off, no production/Taggii/iOS/push/PR, and the formal gates (all-stock, holdout, retention, concurrency, stable B_ref, release parity) remain pending. The natural next step toward any activation decision is an all-stock and size-mixing sweep of the COMBO configuration.

[Full evidence](windowed-combo-stage26-results.json), [contract](windowed-combo-contract.md). Raw timing: `build/windowed-combo-stage26-timing/c0a8a3a06fe5/report.json`; pixel proof `build/windowed-combo-stage26-proof/report.json`; JIT `build/windowed-combo-stage26-proof/jit-parity/report.json`.

[Figure](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-combo-stage26/comparison.png).
