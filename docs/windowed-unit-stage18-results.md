# Stage eighteen: Coupler stride1 specialization

**Keep the option off. Actual stride1 reduction loops disappear, but this cohort does not demonstrate an end-to-end gain over same-source generic fusion.**

Original R, Generic release fusion and Unit specialization run eighteen valid rounds with34,691 measurement calls. W0 is an unfused current-source correctness control only and is not timed. Both measured Portra profiles use stride1; MTF fusion remains off.

| Case / arm | Three round medians ms | Median ms | Worst p95 ms | Repeated device peak MiB |
| --- | --- | --- | --- | --- |
| HD / R-B1 | 7.113 / 13.373 / 9.097 | 9.097 | 26.127 | 334.28 |
| HD / Generic | 6.854 / 7.889 / 9.007 | 7.889 | 13.600 | 334.28 |
| HD / Unit | 7.390 / 11.822 / 12.480 | 11.822 | 19.768 | 334.28 |
| UHD / R-B1 | 42.826 / 42.916 / 41.446 | 42.826 | 56.272 | 1183.72 |
| UHD / Generic | 43.224 / 41.352 / 40.690 | 41.352 | 51.249 | 1183.72 |
| UHD / Unit | 41.996 / 42.223 / 41.546 | 41.996 | 52.532 | 1183.72 |

Unit has29.95% higher HD median time than R and49.85% higher than Generic. Original HD drifts from7.11 to13.37ms, so these are observed cohort differences, not established causal regression sizes. UHD Unit is1.94% faster than R but1.56% slower than Generic. In per-index UHD comparisons Unit beats Generic once and is slower twice; it beats R twice and is slower once. Small differences and background variation do not support a specialization win. Do not splice prior campaigns into this comparison.

Repeated device peaks are identical across all arms. Every HD measurement has zero new Metal buffers; every UHD measurement has four, including all2,118 Unit calls. Counts are successful newBufferWithLength creations, not allocated bytes or attribution to specific fields. The retained grid remains; removing reduction control flow did not reduce observed allocation churn or total device holding. Full process peaks, retained footprints, thermal state and all-round histograms remain in JSON.

Actual dispatch counts are R/Generic/Unit41/40/40 for HD and77/75/75 for UHD, one AOT per frame. Specialization adds no dispatch reduction beyond release fusion.

The shared Graph/Stages film math is unchanged. A private default-false flag specializes only the captured Released source in the previously admitted exact full-float realtime Metal windowed negative/negative_luma graphs. At stride1, the original one-sample box average equals the bounded source. The generated selected kernel has no reduction loops or box count; nonunit branches preserve the original per-source nonlinear release followed by sum/count. The grid store and subsequent Gaussian remain.

Verification:24 direct rows (18 independent plus6 oracle/self) and42 same-process history comparisons are bitwise equal to independent original R. Twenty-four history comparisons use the two fresh twins. Sixteen Metal binding checks observe actual kernel changes for sigma0.810→4.2→1.999→2.0→0.810 (stride1→4→1→2→1); Unit stride1 binds loop-free kernels and nonunit binds generic reduction kernels. Generic retains its reduction kernels. The verification-only observer is never loaded in normal timing workers.

Six fresh-archive JIT/AOT comparisons pass the original1e-5 threshold with worst linear error2.62260437e-06, finite and exact alpha. CPU/Metal11 stages each,281 Python tests (8 skipped, includes15 focused), ten native generator rejections, release build and18 relevant release Swift tests pass. Each current arm has2 new+61 frozen archives; full current-source release AOT/JIT parity remains pending.

Original R stays clean at96623ba0831a52dbddcda35727a206d4123a8b5f. Implementation8df5f7c, source key 1a3b9570961e56d8f00a0f892aabc6f9fe4f0f8ce80cde3aaa3fc7eb036471a0. The first history invocation used the wrong frozen AOT directory and failed before compilation/GPU execution; preserved log stage18-history.log. Corrected run history-v2 is complete. An initial rejection-harness expectation of exit2 for a wrong variant was corrected to the existing admission exit1, without source changes. No failed image comparison or tolerance relaxation occurred.

Timing follows the [predeclared contract](windowed-unit-stride-contract.md): fresh processes, balanced R/Generic/Unit orders,5s warm/30s measure/2s tail/5s idle, one in-flight frame,1GiB pool,1GiB disk reserve and256MiB evidence budget. Own-arm phase hashes, symbol, dispatches and AOT counts match proof. No builds, GPU verification, plots or cleanup during timing. Docker and user services remain running. All observed thermal states are1; this does not establish a quiet machine or stable B_ref.

Decision: stop extending this stride1 fusion hypothesis on current evidence; keep both private flags off. The loop hypothesis is tested but insufficient to explain end-to-end cost. Next useful independent experiment is allocation/pool reuse instrumentation, before changing pool policy, or the already scoped Print MTF/output boundary. No all-stock/holdout, formal acceptance, default promotion, Taggii integration, push or upstream PR.

[Complete metrics and evidence hashes](windowed-unit-stage18-results.json). Raw timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-unit-stage18-timing/ae7f220eb772/report.json`. Pixel proof `build/windowed-unit-stage18-proof/report.json`, history `build/windowed-unit-stage18-history-v2/report.json`, targeted JIT `build/windowed-unit-stage18-jit-proof/report.json`, validation `build/windowed-unit-stage18-validation/validation.json`.

![All rounds and repeated memory](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-unit-stage18/comparison.png)
