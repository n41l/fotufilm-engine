# Stage22: UHD long-window repeat with sampled Metal attribution

The aggregate original-driver slowdown appears again:44.822ms R versus46.718ms BestFit (+1.896ms,+4.23%). It is not stable across repeats: BestFit is faster twice and slower twice, with deltas from−3.264 to+11.375ms. Detailed counterparts reverse the aggregate ranking (51.000 versus44.157ms). This cohort therefore does not identify a causal allocator regression or a stable speedup. The Metal allocation-peak reduction remains192MiB (16.22%). Defaults remain unchanged.

Implementation6e6c0ad. Fixed [protocol](windowed-long-contract.md), exact original normal binaries, frozen R96623ba and original63 AOT libraries, one in-flight frame,1GiB pool and queue capacity4. Four Williams orders × four cells=16 fresh processes; each has5s warmup/30s measurement/2s completion tail/5s idle. Portra Coffee3840x2160 only. No native builds, GPU verification, plots or cleanup occurred during timing. Docker/user services stayed running.

All16 rounds valid:9378 measured calls,240 detailed measurement traces plus40 warm traces. Full output hashes, actual symbol, one AOT and77 dispatches/call match independent R. All sampled CPU/GPU intervals, native factory/compute/commit links and observed queue capacities pass. Six fixtures × two sampled workers=12 full-dump SHA preflights passed;37 focused tests passed (3 driver/order,8 methods,9 base,4 pool,13 resources). First cold preflight preserved separately: it rejected a legitimate commandless queue-construction event. The final controller keeps that event with token0 and validates capacity4; every unmatched command/commit still fails. No pixel or command-link threshold was relaxed.

| Original-driver repeat | R ms | BestFit ms | BestFit−R ms |
| --- | ---: | ---: | ---: |
| 1 | 39.111 | 35.847 | −3.264 |
| 2 | 47.201 | 47.983 | +0.782 |
| 3 | 46.071 | 45.454 | −0.617 |
| 4 | 43.573 | 54.948 | +11.375 |
| Median of process medians | 44.822 | 46.718 | +1.896 |

Median of the four within-repeat differences is+0.083ms, a different statistic from subtracting the two arm medians. Neither controls sub-minute background changes: processes are sequential, not simultaneous. Preserve the predeclared arm-median result; do not select the more favorable estimator. Original-driver throughput medians are19.583/19.083fps. Per-process p95s are retained in JSON, spanning46.766–105.438ms. These are diagnostic measurements, not release non-regression acceptance.

| Low-frequency trace metric, ms/frame | R | BestFit |
| --- | ---: | ---: |
| All-call API median | 51.000 | 44.157 |
| Sampled-call API median | 55.762 | 45.671 |
| Unsampled-call API median | 50.591 | 44.108 |
| Allocator inclusive CPU elapsed | 0.302 | 0.116 |
| Native Metal allocation CPU elapsed | 0.126 | 0.000 |
| Native commandBuffer acquisition elapsed | 37.523 | 29.979 |
| Acquisition overlap with earlier GPU intervals | 31.640 | 28.492 |
| Pipeline creation elapsed | 0.800 | 0.725 |
| Encoding envelope | 40.485 | 31.836 |
| Encoding residual after native-method union | 0.652 | 0.655 |
| Compute GPU interval union | 39.352 | 34.512 |
| GPU all-command span | 50.807 | 41.176 |
| Explicit waitUntilCompleted | 5.481 | 4.881 |
| Main-thread user+system CPU | 10.543 | 11.574 |

Each entry is the median of four independent process medians; sampled quantities use30 frames/process. Nested/overlapping intervals and independently aggregated medians cannot be added or subtracted as a complete frame decomposition. In particular, native acquisition is wall time including queue backpressure/descheduling, not active CPU cost. The unchanged source deliberately limits the queue to4 unfinished commands to keep host allocation from outrunning GPU frees. Callback-pending histograms often reach4, but include notification lag and do not measure exact queue occupancy. Acquisition/GPU overlap supports this waiting-location interpretation without establishing internal driver causes for the normal-driver difference.

The observed direct allocation CPU reduction is0.186ms; it does not explain a+1.896ms normal-driver aggregate difference. Net sampled thread CPU is higher for BestFit, so an allocator-only explanation is also incomplete. These trace measurements have a different comparison direction, and cannot be used to assign the original-driver delta to a kernel or infer zero deferred allocation/mapping/cache/hazard costs.

Trace writing/drain occurs outside API latency and inside throughput time: median selected-frame cost10.114/11.493ms; median total over30 samples327.712/450.842ms (about1.09%/1.50% of the30s window). Inactive hooks remain installed on unsampled calls; sampling and setup may change scheduling. Sampled versus unsampled medians also differ. The Mach trace/API-clock bracket difference is only about0.135/0.167microseconds, so the large ranking change is not a timer-scope arithmetic discrepancy. Do not apply a constant observer correction.

Original-driver Metal peaks1183.719/991.719MiB; BestFit had zero new Metal buffers in all2445 measurement calls. R allocated4 in2441 calls,3 in5 calls and2 in1 call: completion/reclaim timing occasionally changes the exact-bin outcome. All2401 BestFit trace-process measurement calls also allocate zero new buffers. These are device-allocation observations for this fixture; they are not universal application-memory guarantees.

Boundary1-minute system load varied4.21–38.56; memory-free observation36–48%, and used swap changed during the campaign. Per-call thermal states were0 or1, with no2/3 recorded. These observations show a changing background session but do not establish which process caused latency, whether GPU frequency changed, or whether Docker was responsible. GPU clocks/power and other-process GPU utilization were not measured. Old stage19 results remain separate and cannot be retrospectively decomposed using this cohort.

Evidence: build/windowed-long-stage22-profile/report.json, summary.json,validation.json, per-round raw requests and280 traces (about107MiB, below256MiB budget;1GiB reserve held). Workers/source snapshots: build/windowed-long-stage22; final preflight: build/windowed-long-stage22-preflight-v2/report.json. Excluded first attempt: build/windowed-long-stage22-preflight/report.json. Machine-readable process medians, five-second bins, allocation/thermal histograms, boundary observations and source fingerprints are in [results JSON](windowed-long-stage22-results.json).

Reproduce with tools/prepare-windowed-long.py, then tools/run-windowed-long.py --preflight on the frozen six-case proof; restore the original BestFit runner.gz and verify its manifest SHA before use. The timed controller requires that preflight report and the original six-case normal proof. Summarize with tools/summarize-windowed-long.py and render with tools/windowed-long-chart.py only after the timed cohort ends. The chart is stored in the local visualization folder fotufilm-windowed-long-stage22/comparison.png.

The experiment reproduces a slow aggregate without a stable causal ranking. The strongest supported findings remain lower Metal allocation peak and a large native commandBuffer waiting interval. A stable B_ref, all-stock/holdout/retention/concurrency and release gates remain pending. No production change, Taggii/iOS integration, default activation, push or PR.
