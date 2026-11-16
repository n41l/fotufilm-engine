# Stage twenty-five: windowed Print MTF vertical-into-output fusion

The third audited fusion candidate, implemented and measured for the first time. The print MTF blur's vertical result is no longer stored: `frame_output` computes it in its own threads, once per channel, keeping the transmittance and horizontal stores, the boundary normalization, sharpening's transmittance reads and the radius-one shortcut. Private `windowed_print_mtf_fusion`, off by default, separately cache-keyed; only the exact `color_float_realtime_windowed_negative_luma` twin is rebuilt per arm (one fresh archive plus 62 frozen), source key `8c7c3a8b1d60d1cc17ae723cf8a0c0a7d4c4781bdaad8f7a3fafe6dea17a692b`.

Correctness is complete and clean: fifteen independent full-pixel comparisons (four primary cases plus the odd 1919x1081 two-window crop) all bitwise-equal to R; two fourteen-frame histories, 28 comparisons, active frames bitwise; two current-source JIT/AOT comparisons at worst linear error 1.9669533e-06 under the unchanged gates; 13 fail-closed admission tests and 6 generator rejection checks. Actual dispatches drop exactly as designed on the active case — 77 to 75 (one vertical pass per window, two windows) — and stay bit-identical on every inactive case. The eliminated `frame_print_mtf` family is absent from the Fused archive; `frame_print_mtf_horizontal` and `frame_print_mtf_transmittance` remain.

Timing: the first predeclared attempt stopped itself after five valid rounds when macOS swap growth took free disk below the 1 GiB reserve; that campaign is retained unspliced. After 17 lossless-verified archive actions (index in `build/windowed-print-mtf-stage25/disk-recovery.json`) the full nine rounds were re-run from scratch: 5,654 measurement requests, all valid, own-arm phase hashes and dispatch counts matching the proof throughout.

| Arm | Three round medians ms | Median ms | Worst p95 ms | Total device peak MiB |
| --- | --- | ---: | ---: | ---: |
| R-B1 | 40.162 / 58.994 / 55.176 | 55.176 | 94.179 | 1183.72 |
| W0 | 40.267 / 47.276 / 40.915 | 40.915 | 63.020 | 1183.72 |
| Fused | 38.350 / 47.483 / 57.212 | 47.483 | 74.019 | 1183.72 |

No benefit is confirmed. Against same-source W0 the summary is 16.05% slower; per round Fused wins one (−4.76%), ties one (+0.44%) and loses one (+39.83%). The apparent −13.94% against R-B1 rides on R's two slow rounds; this campaign drifted severely (R-B1's own rounds span 40.2–59.0 ms; background 1-minute load 4.2–9.7, swap steady at ~12.3 GiB used, memory free 42–47%), so neither summary is a stable estimate — but nothing here supports the fusion. Unlike the MTF pointwise fusion, the device peak does not move at all: 1183.72 MiB on every arm and round, because the removed per-window field did not shrink the concurrently retained buffer set; whole-run new-buffer counts barely differ (R 52, W0 53, Fused 48).

Conclusion: keep `windowed_print_mtf_fusion` off; the structural goal (one pass and one intermediate field fewer per window) was met, but neither latency nor memory improved against the same-source control. All three audited fusion candidates have now been implemented and measured; only candidate 1 (MTF pointwise fusion) retains a positive signal. Do not combine this with MTF or pool experiments. Single upscaled SDR case, three repeats, no all-stock/holdout/retention/concurrency, no stable B_ref, no release acceptance, no Taggii/iOS change, push or PR.

[Full evidence](windowed-print-mtf-stage25-results.json), [contract](windowed-print-mtf-fusion-contract.md). Raw timing: `build/windowed-print-mtf-stage25-timing/382cbcae7d48/report.json`; first stopped attempt retained at `build/windowed-print-mtf-stage25-timing/b36b1df153d5`.

[Figure](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-print-mtf-stage25/comparison.png).
