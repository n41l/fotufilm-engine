# Stage sixteen: windowed MTF pointwise fusion

The active Portra UHD case removes four actual GPU dispatches per frame (77 to 73) and two pointwise intermediate fields. All direct original-windowed and history comparisons are bitwise equal. Three balanced timing repeats are diagnostic; defaults remain off.

| Arm | Three round medians ms | Median ms | Worst p95 ms | Total device peak MiB |
| --- | --- | --- | --- | --- |
| R-B1 | 34.270 / 36.666 / 37.756 | 36.666 | 49.550 | 1183.72 |
| W0 | 39.792 / 37.472 / 37.908 | 37.908 | 96.134 | 1183.72 |
| Fused | 31.072 / 34.302 / 32.904 | 32.904 | 41.992 | 1071.72 |

Observed median latency reduction: 10.26% against original R-B1 and 13.20% against same-source W0. Repeated total device peak falls 112 MiB (9.46%) against both controls. 7,333 measurement requests across nine valid rounds.

The first isolated frame saved 256 MiB (1183.72 to 927.72 MiB). Repeated rendering settles at a higher Fused device peak; the table reports repeated-run observations rather than promoting the larger one-frame saving. Total device peak includes pools and scratch, and is not a direct count of logical removed-buffer bytes.

Only the exact color negative_luma twin is rebuilt per arm: one fresh archive plus 62 frozen archives. It retains the original 1080-row loop, final shared MTF light, precision, formula graph and one AOT call. Mixed records are computed once per output thread; the neutral-axis correction inlines into that store. There is no extra cut or wavefront runtime.

Ten independent full-pixel comparisons (four primary cases plus odd 1919x1081 geometry, two candidate arms) pass bitwise against R; five oracle/self rows are also saved. The other three primary cases use their original frozen classes and remain unchanged. Two fourteen-frame histories pass bitwise; fourteen comparisons actually exercise the fresh luma archive, including encoded output. The histories deliberately use UHD calibration at HD geometry to exercise this twin; they are correctness stress tests, not native4K photographic performance evidence. Two current-source JIT/AOT comparisons pass at worst linear error 1.96695328e-06, under the unchanged 1e-5 gate, finite and exact alpha.

249 Python suite tests (8 skipped), 11 focused tests (7 overlap with the suite), five native generator rejection tests, CPU/Metal 11 stages each, release build and 18 relevant release Swift tests pass. The initial discover command found zero tests and is retained; explicit module loading produced the actual suite result.

Orders: R/W0/Fused, W0/Fused/R, Fused/R/W0. Fresh process, 5s warm/30s measure/2s tail/5s idle, one frame in flight and 1 GiB pool. Own-arm phase hashes and exact symbol/dispatch counts match proof throughout. No native compilation, GPU verification, plotting or cache cleanup occurred during timing. Docker and user services stayed running.

Three repeats and order balancing do not remove background variation. This is one upscaled SDR fixture; no all-stock, holdout, release/platform acceptance or formal B_ref freeze is claimed. Full current-source release AOT/JIT parity remains pending. Keep the switch off by default; no Taggii changes or upstream PR. Coupler/downsample and Print MTF/output fusion are separate unimplemented experiments.

Implementation `a45d89d`; source key `4f9d84dc2c9aba095e55d1c1d36fdab8bfa2556b1d34be1f1c928cfaaa664325`. [Full evidence](windowed-mtf-stage16-results.json), [contract](windowed-mtf-fusion-contract.md). Raw timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-mtf-stage16-timing/c2a45505230b/report.json`.

[Latency and repeated-memory figure](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-mtf-stage16/comparison.png).
