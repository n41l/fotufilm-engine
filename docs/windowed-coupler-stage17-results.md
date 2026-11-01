# Stage seventeen: Coupler release/downsample fusion

**Keep this option disabled and do not combine it with MTF fusion. Repeated total device peaks do not fall; both observed medians are slower than original windowed.**

The isolated experiment removes one Released pass per output window while preserving per-sample nonlinear release before reduction, shared Log exposure, the original1080-row window and one AOT invocation. MTF fusion remains off. All direct original-windowed and frame-history comparisons are bitwise equal; timing is diagnostic and defaults remain off.

| Case / arm | Three round medians ms | Median ms | Worst p95 ms | Repeated device peak MiB |
| --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 / R-B1 | 7.233 / 8.471 / 8.293 | 8.293 | 14.314 | 334.28 |
| portra400-coffee-1920x1080 / W0 | 7.259 / 10.006 / 9.424 | 9.424 | 23.545 | 334.28 |
| portra400-coffee-1920x1080 / Fused | 7.915 / 8.910 / 9.494 | 8.910 | 18.257 | 334.28 |
| portra400-coffee-3840x2160 / R-B1 | 41.730 / 41.702 / 46.973 | 41.730 | 77.955 | 1183.72 |
| portra400-coffee-3840x2160 / W0 | 45.545 / 41.772 / 42.078 | 42.078 | 94.376 | 1183.72 |
| portra400-coffee-3840x2160 / Fused | 45.017 / 40.371 / 43.864 | 43.864 | 59.445 | 1183.72 |

| Case | Observed time reduction vs R / W0 | Device peak reduction MiB vs R / W0 |
| --- | --- | --- |
| portra400-coffee-1920x1080 | -7.43% / 5.46% | 0.00 / 0.00 |
| portra400-coffee-3840x2160 | -5.11% / -4.25% | 0.00 / 0.00 |

Eighteen valid rounds, 34,407 measurement requests. Actual dispatch counts R/W0/Fused: HD41/41/40 and UHD77/77/75.

Both measured profiles have stride1 (sigma0.405/0.810 pixels): this removes a release write before a same-resolution grid pass. True coarse stride4 and nonlinear gamma[1.7,0.8,2.3] are separately verified on odd1919x1081 geometry; the luma twin is also checked on65x1081. These changed-parameter crops are correctness stress cases, not additional calibrated photographic profiles.

Twelve independent full-pixel comparisons pass bitwise, with six oracle/self rows retained. Two14-call histories pass bitwise; sixteen comparisons use the freshly compiled exact twins. Their color pack uses UHD calibration at HD geometry for active negative/luma, stock/seed/gate/stage/encoding transitions. Original wavefront fault frame11 is excluded on both sides. No new host fault/drain API is introduced. Four current-source JIT/AOT comparisons pass with worst linear error 2.62260437e-06, under the unchanged1e-5 gate, finite and exact alpha; encoded histories retain the original<1/255 gate.

266 Python tests (8 skipped, includes13 focused), eight native generator rejection tests, CPU/Metal11 stages each, release build and18 relevant release Swift tests pass. Two fresh archives plus61 frozen archives per arm form a diagnostic composite; complete current-source release AOT/JIT parity remains pending.

Fresh process,5s warm/30s measure/2s tail/5s idle, one in-flight frame and1GiB pool. For each case, orders are R/W0/Fused, W0/Fused/R, Fused/R/W0. Own-arm phase hashes, exact actual symbol, dispatch and single AOT count match pixel proof in every request. No native compilation, GPU verification, plotting or cleanup occurred during timing. Docker and user services stayed running.

Use repeated-run total device peaks above, not the lower one-frame observation. Totals include inputs/outputs, pools, LUT and scratch; complete process/retained/thermal data and individual rounds are saved in JSON. Three repeats and order balancing do not remove background variation. These two frozen Coffee SDR workloads are upscaled; no all-stock/holdout result or stable B_ref is claimed.

Keep defaults off. The two HP5 cases use unchanged frozen classes and only prove compatibility. MTF combinations and Print MTF/output fusion remain untested; no default activation, Taggii/iOS change, push or upstream PR.

Implementation `aba20e2`; source key `c43620ff28c49a420dae528b472f65fa38c705060a40a9ad04d10fab6708cf1f`. [Full evidence](windowed-coupler-stage17-results.json), [contract](windowed-coupler-fusion-contract.md). Raw timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-coupler-stage17-timing/7b3a1e93cbdd/report.json`.

The HD comparison changes direction depending on original R or same-source W0; UHD is slower against both. Control variation limits causal attribution. Both measured profiles use stride1, so a reduction in coarse-grid thread count is not an explanation for these timings. Register/loop costs and pool retention need direct profiling; neither is established here.

[All-round latency and repeated-memory chart](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-coupler-stage17/comparison.png).
