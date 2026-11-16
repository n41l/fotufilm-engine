# Stage nineteen: bounded best-fit pool reuse

**A UHD memory win, not a speed win. Keep this policy experimental and defaults unchanged.**

On the complete twelve-round cohort, total repeated UHD device peak falls192MiB (16.22%) and every measured frame creates zero new Metal buffers rather than four. However both median times are higher; the nonregression requirement is not satisfied.

| Case / arm | Three round medians ms | Median ms | Worst p95 ms | Device peak MiB |
| --- | --- | --- | --- | --- |
| HD / R-B1 | 6.996 / 8.522 / 11.806 | 8.522 | 29.347 | 334.28 |
| HD / BestFit | 11.852 / 12.299 / 11.768 | 11.852 | 17.349 | 334.28 |
| UHD / R-B1 | 43.546 / 44.388 / 48.219 | 44.388 | 80.752 | 1183.72 |
| UHD / BestFit | 45.800 / 46.082 / 46.610 | 46.082 | 70.003 | 991.72 |

Observed median latency rises39.08% at HD and3.82% at UHD. HD original medians drift6.996→8.522→11.806ms, so the cohort does not establish a causal regression magnitude. BestFit is slower in two of three pairings at each size. Do not discard the slower results or claim latency nonregression from memory savings.

Warm measurement allocation counts: HD R9,123 and BestFit7,275 calls are all zero; UHD R1,851 calls are all four, BestFit1,825 calls are all zero. The original warm UHD peak is1183.72MiB and BestFit991.72MiB in every repeat. These normal-worker totals include I/O, tables, scratch and pool holding. Detailed observers are not used for latency or process-memory nonregression.

The original pool cause is observed directly: near the start of each warm UHD frame, a24KiB request reclaims completed returns. Existing idle481.19MiB plus returned700.06MiB exceed the1GiB idle cap, and four48MiB returned buffers are physically released during reclamation. Later48MiB requests see no exact idle match, some48MiB returns still pending, and idle56/72MiB allocations available. They allocate four new48MiB buffers. Both idle-cap eviction and exact-bin selection contribute. Roles identify these as AOT intermediates; this does not identify individual film fields or quantify allocation-time cost.

The bounded policy keeps exact-match preference and otherwise selects the smallest idle allocation from rounded size through1.5×rounded for requests>=64KiB. Smaller requests remain exact. Actual lengths stay in ownership metadata and actual bytes are subtracted from idle accounting. Fence/refcount/reclamation, allocation rounding and1GiB cap stay unchanged. It never waits for or directly selects pending buffers.

No production engine source, shader, film math, public ABI or default changes. Workers use frozen R96623ba and its complete original63-archive AOT set; the policy is appended only to an isolated generated shim copy. MTF/Coupler fusions are off, and no new wavefront stages are involved. Implementationa1e60a9.

Verification before timing: original light/detail workers each run six frames at both sizes (24 frames); candidate light/detail repeat these24 frames. A12-frame mixed history traverses all six fixtures forward/backward, including Portra/HP5 and nonlinear odd stride4/luma cases. Every output SHA matches the independent original-windowed proof, actual symbol and dispatch count remain original, one AOT per call. The separate normal performance worker passes six full-image SHA comparisons. Detailed ledgers report no errors, sufficient physical capacity for every lease and GPU completion before reuse; all submitted fences complete successfully. Four resource-analysis regressions plus thirteen existing resource tests pass. The frame histories are count-based diagnostics, not a promise of lower variable-size memory: the candidate mixed history can peak1250.16MiB. Broader stocks, concurrency, feature/encoding histories, holdout and formal release/promotion gates remain pending.

The first campaign15d841cd734d stopped at the1GiB reserve after nine valid rounds. Its complete partial data and failure remain preserved and are excluded from the table. With timing stopped, this task's dedicated1.04GiB rebuildable Swift/Xcode output was removed; sixteen inactive legacy diagnostic workers were losslessly archived and raw/archived SHA checks preserved. Four completed stage19 diagnostic workers had already been archived separately. No source, fixture, report or other project was deleted. The normal BestFit and frozen R timing workers remain available. Disk recovery and restore maps live under build/windowed-pool-stage19/{disk-recovery,worker-archives}.json.

The complete rerun6ef5c7a907cb contains12 valid rounds and20,074 measurement calls, with the original5/30/2/5s protocol, fresh processes, one in-flight frame,1GiB pool and disk reserve. HD orders R/BestFit, BestFit/R, R/BestFit; UHD reverses those orders. Phase SHA, actual symbol, dispatch and single AOT checks pass in every run. No builds, GPU verification, plotting or cleanup occurred inside either timing campaign; Docker and user services remained running. Preserve both campaigns separately.

Conclusion: buffer selection can reduce holding/fragmentation without changing the image graph. Eliminating new allocations does not establish a speed gain. CPU allocation time, per-kernel GPU execution and hazard/cache effects have not been separated; none is established as the slowdown cause. Keep the general best-fit experiment off. A future independently declared experiment could narrow oversized reuse or profile CPU/GPU costs before changing policy; it must not silently reuse this cohort as acceptance. No MTF combination, default activation, Taggii integration, push or upstream PR.

[Contract](windowed-pool-contract.md), [complete metrics and evidence](windowed-pool-stage19-results.json). Raw complete timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-pool-stage19-timing/6ef5c7a907cb/report.json`.

Reproduce into fresh folders using the saved tools:

```sh
python3 tools/inspect-windowed-pool.py --reference ../reference --proof build/windowed-unit-stage18-proof/report.json --output build/pool-original-new
python3 tools/prepare-windowed-pool-best-fit.py --reference ../reference --proof build/windowed-unit-stage18-proof/report.json --output build/pool-best-fit-new
python3 tools/run-windowed-pool-diagnostic.py --reference ../reference --proof build/windowed-unit-stage18-proof/report.json --candidate-proof build/pool-best-fit-new/normal-proof.json --forensics build/pool-original-new/report.json --best-fit-history build/pool-best-fit-new/report.json --output build/pool-timing-new
```

The consolidated preparation tool saves the same exercised builder flags and verification steps; the initial exploratory builds and their exact generated-shim fingerprints remain separately recorded. Normal candidate proof from this run is build/windowed-pool-stage19-performance/normal-proof.json; detailed histories are build/windowed-pool-stage19-best-fit/report.json.

![All round medians and repeated device peaks](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-pool-stage19/comparison.png)
