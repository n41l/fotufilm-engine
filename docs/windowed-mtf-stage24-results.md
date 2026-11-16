# Stage twenty-four: independent repeat of the windowed MTF fusion timing

Re-ran the stage16 three-arm campaign with the original binaries: R-B1 taken from the frozen reference tree, W0 and Fused restored losslessly from their gzip archives and raw-SHA verified before execution. No rebuild, no new AOT, no source change; implementation remains `a45d89d` and the source key `4f9d84dc2c9aba095e55d1c1d36fdab8bfa2556b1d34be1f1c928cfaaa664325`. The runner re-verified the complete 15-row proof, 28-frame history and targeted JIT parity inputs, the frozen reference checkout, and every worker, archive identity and frozen input SHA before the first round. Defaults remain off.

Nine valid rounds, 5,373 measurement requests, same predeclared orders R/W0/Fused, W0/Fused/R, Fused/R/W0, fresh process per arm, 5 s warm / 30 s measure / 2 s tail / 5 s idle, one in-flight frame, 1 GiB pool, 1 GiB disk reserve held, 5.23 MiB of evidence. Every round re-checked own-arm phase output SHA, actual variant, exactly one AOT call and the proof's dispatch counts (77 / 77 / 73). Docker and user services stayed running; no build, GPU verification, plotting or cleanup during timing.

| Arm | Three round medians ms | Median ms | Worst p95 ms | Total device peak MiB |
| --- | --- | ---: | ---: | ---: |
| R-B1 | 48.217 / 51.133 / 55.363 | 51.133 | 101.435 | 1183.72 |
| W0 | 40.371 / 46.616 / 64.616 | 46.616 | 110.490 | 1183.72 |
| Fused | 41.404 / 43.714 / 50.059 | 43.714 | 69.540 | 1071.72 |

Observed summary: Fused is 14.51% faster than original R-B1 and 6.23% faster than same-source W0; the repeated total device peak falls 112 MiB (9.46%). Per round, Fused beats R-B1 in all three rounds (−14.13 / −14.51 / −9.58%), while against W0 it is faster in two rounds (−6.23 / −22.53%) and slower in round 0 (+2.56%, where W0 recorded its fastest 40.371 ms round). Across both campaigns Fused has now beaten R-B1 in six of six rounds and W0 in five of six, but the W0 margin this time is smaller than stage16's 13.20%.

The −112 MiB device-peak reduction reproduced exactly in every Fused round, matching stage16 bit for bit (1183.72 → 1071.72 MiB).

Absolute latencies are 25–40% above stage16 for every arm (R-B1 36.666 → 51.133 ms; W0 37.908 → 46.616; Fused 32.904 → 43.714). This is campaign-wide drift, not an arm regression: background 1-minute load ranged 4.22–15.61, system memory free 36–43%, and swap usage sat at 11144–11340 of 12288 MiB for the whole campaign. These observations do not establish a root cause. Only within-campaign comparisons are valid; the two campaigns are reported separately and never spliced.

Repeat with restored binaries; the stage16 pixel, history and JIT proofs apply unchanged to these bit-identical workers and were not re-run. Thermals stayed at or below state 1.

Conclusion: the direction and memory benefit of candidate 1 reproduce against the frozen original, with a weaker and not unanimous margin against the same-source control. Still one upscaled SDR case, three repeats, no all-stock/holdout/retention/concurrency result, no stable B_ref, no release acceptance. Keep `windowed_mtf_fusion` off by default; do not combine with BestFit savings; no Taggii/iOS change, push or PR.

[Full evidence](windowed-mtf-stage24-results.json), [stage16 original](windowed-mtf-stage16-results.md), [contract](windowed-mtf-fusion-contract.md). Raw timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-mtf-stage16-repeat/f81614a5f6c1/report.json`.

[Figure](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-mtf-stage24/comparison.png).
