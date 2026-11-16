# Stage twenty-one: native Metal method and queue-backpressure attribution

**The large elapsed interval is native commandBuffer acquisition. The original engine intentionally limits its queue to four non-completed command buffers. BestFit is faster in every control mode in this short cohort; earlier slowdown is not reproduced as a stable property.**

A command buffer here is a GPU command container, distinct from the MTLBuffer allocations holding image data. This experiment changes neither queue depth nor the allocation policy. Frozen R96623ba and its63 original AOT archives remain the engine/shader baseline; BestFit uses only the earlier isolated bounded allocation suffix.

UHD detailed-probe values, median of six process medians, milliseconds per frame:

| Method / scope | Original | BestFit |
| --- | --- | --- |
| Original native commandBuffer acquisition | 25.542 | 22.581 |
| Outer acquisition including base bookkeeping | 25.555 | 22.592 |
| Compute encoder creation | 0.171 | 0.151 |
| Function lookup | 0.024 | 0.019 |
| Pipeline-state creation | 0.240 | 0.212 |
| Pipeline binding | 0.006 | 0.005 |
| Buffer binding | 0.015 | 0.015 |
| Bytes binding | 0.001 | 0.001 |
| Threadgroup-memory setup | 0.001 | 0.001 |
| Dispatch | 0.061 | 0.050 |
| End encoding | 0.012 | 0.011 |
| Native commit | 0.141 | 0.128 |

The outer-minus-native wrapper delta, measured per frame before aggregation, is0.012/0.010ms. Thus the tens of milliseconds are inside the original Metal method, not mostly the base observer's map/timer bookkeeping. Other process-local hooks can still run inside native internals; this is not an uninstrumented driver-cycle count.

The [frozen source](/Users/kunhuang/Documents/fotufilm-wavefront/reference/Sources/FotufilmHalide/FotufilmHalideIOS.cpp:414) sets kMetalQueueDepth=4 and constructs newCommandQueueWithMaxCommandBufferCount: at line437. Its preceding comment explicitly describes keeping the host close behind GPU completion so intermediate frees can arrive and footprint does not become the sum of all stages. Detailed queue-construction observations independently record capacity4 for every acquisition. This capacity is command buffers, not image-pipeline stage count or frames in flight.

UHD original native acquisition25.542ms overlaps previously submitted GPU execution intervals for22.300ms; BestFit22.581ms overlaps21.413ms. Callback-pending is4 at3459/5760 original and3418/5760 BestFit acquisitions; this counter includes callback-delivery lag and is not exact hardware queue occupancy. Together with the configured capacity and low active CPU time, these observations are consistent with intentional queue backpressure. They do not expose the driver's exact semaphore or distinguish every OS descheduling interval.

The old command-encoding envelope is26.255/23.204ms. Timed native-method coverage within it is26.068/23.038ms, leaving0.194/0.165ms of residual per-frame elapsed time. The envelope largely consists of command-container acquisition, not pipeline creation or buffer-binding work. Frame main-thread user+system CPU is5.711/5.351ms, much smaller than the acquisition wall intervals. Explicit waitUntilCompleted remains separately recorded; waits and GPU intervals overlap and must not be added.

All calibration cells, API wall time in milliseconds:

| Size / mode | Original six process medians | Original aggregate | BestFit six process medians | BestFit aggregate |
| --- | --- | --- | --- | --- |
| HD / off | 7.464 / 6.672 / 7.324 / 6.750 / 6.764 / 13.405 | 7.044 | 7.141 / 6.760 / 7.215 / 6.781 / 6.872 / 6.807 | 6.839 |
| HD / basic | 7.278 / 7.260 / 7.099 / 7.427 / 8.075 / 7.369 | 7.324 | 7.170 / 7.254 / 7.491 / 7.185 / 7.144 / 7.302 | 7.220 |
| HD / detail | 7.164 / 7.225 / 7.474 / 7.247 / 7.642 / 7.364 | 7.306 | 7.057 / 7.155 / 7.954 / 7.192 / 7.199 / 7.253 | 7.196 |
| UHD / off | 34.701 / 33.222 / 34.958 / 33.206 / 35.847 / 32.858 | 33.962 | 30.514 / 30.669 / 30.812 / 31.049 / 30.701 / 30.871 | 30.757 |
| UHD / basic | 33.333 / 33.010 / 33.599 / 33.477 / 33.236 / 33.383 | 33.358 | 31.669 / 30.639 / 31.140 / 30.593 / 30.798 / 30.262 | 30.719 |
| UHD / detail | 33.395 / 34.455 / 33.392 / 35.714 / 33.346 / 34.853 | 33.925 | 31.682 / 30.415 / 30.599 / 30.617 / 30.854 / 30.716 | 30.667 |

UHD BestFit observed time reductions are9.44% off,7.91% basic and9.60% detailed; HD reductions2.91%/1.42%/1.51%. This short count-based cohort does not reproduce the earlier relative slowdown. It does not replace stage19's5s warm/30s measurement result or establish a stable speed gain. Background/driver state, short warmup/burst behavior, callbacks and trace I/O can affect comparisons; no exact correction or cross-campaign sample splicing is performed.

CommandBuffer acquisition can be a waiting location rather than removable CPU overhead. Raising the queue capacity might move waiting to frame completion, change GPU scheduling, or grow intermediate memory. This experiment does not test a larger capacity, batch commands, cache pipeline states or change fences. No claim is made that the next command's kernel caused its acquisition to wait: its label identifies what will be encoded, while the wait overlaps older GPU work.

Instrumentation records encoder creation, function lookup, pipeline creation/binding, buffer/bytes binding, threadgroup memory, dispatch/end and commit with generation tokens. Buffer lengths/indices are captured outside the binding timer. The original commandBuffer IMP is timed separately from the outer base wrapper. Source/runtime/shader bodies remain original; the methods observer only exists in diagnostic workers. All three modes initialize the same tiny dummy-library/classes before timing.

Validation and scope: six frozen cases × two policies × off/basic/detail give36 successful final preflight processes, exact original full-image SHA, finite/alpha and actual/AOT/dispatch checks. Final72 fresh processes use10 warm+12 measured frames, six cyclic Latin-square rounds at HD and reversed rounds at UHD. There are864 measured frames,720 warm frames,33984 measured kernel timestamps and16992 detailed kernel/method links. Eight new method/link/queue/interval tests, nine base-probe tests and thirteen resource tests pass. Every Halide command links once, each compute command has requested-method coverage and observed queue capacity4, with no unlinked measured events or commits.

The first pilot measured the outer factory; a later cold preflight stopped because Metal reused object addresses and the observer reused tokens. Its output pixels matched but command associations were invalid. The final observer issues a new generation on every native acquisition and repeats all36 preflights before the final cohort. Preserve pilot binaries, invalid preflight and fingerprints; they are excluded from the final statistics. Final tool sources are snapshotted in build/windowed-metal-stage21-v3/sources.

Storage recovery preceded sampling. Old dedicated experiment executables/raw traces/logs are losslessly gzip archived with raw/archive SHA verification, and only regenerable reference compiler output is removed. Restore maps are build/windowed-metal-stage21-storage.json and storage-2.json; earlier workers and numeric stage20 raw-frame files can be restored from those maps. Source, fixtures, reports and readable analyses remain. During the final cohort there is no native build, GPU verification, plotting or cleanup. Pool cap and free-space reserve remain1GiB, evidence budget256MiB; Docker and user services stay running.

Conclusion: the previous large encoding wall interval is now localized chiefly to native command-container acquisition under the original capacity4 backpressure. Pipeline-state creation, binding and endEncoding are small in this cohort. The cause of earlier BestFit relative latency differences is not settled; the current off/basic/detail controls are faster for BestFit. Keep production/defaults unchanged, preserve the memory result separately, and require independent time-window/holdout verification for any proposed queue/GPU change. No Taggii integration, push or upstream PR.

[Contract](windowed-metal-methods-contract.md), [complete metrics/evidence](windowed-metal-stage21-results.json). Final profile: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-metal-stage21-profile/report.json`. Worker/source snapshot build/windowed-metal-stage21-v3; final preflight build/windowed-metal-stage21-preflight-v3/report.json. Invalid preflight build/windowed-metal-stage21-preflight/report.json is excluded.

Reproduce in new directories:

```sh
python3 tools/prepare-windowed-metal.py --reference ../reference --output build/metal-workers-new
caffeinate -i -s python3 tools/run-windowed-metal.py --workers build/metal-workers-new/workers.json --proof build/windowed-unit-stage18-proof/report.json --reference ../reference --output build/metal-preflight-new --preflight
caffeinate -i -s python3 tools/run-windowed-metal.py --workers build/metal-workers-new/workers.json --proof build/windowed-unit-stage18-proof/report.json --reference ../reference --output build/metal-profile-new --preflight-proof build/metal-preflight-new/report.json
```

![Native Metal methods and representative frame](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-metal-stage21/breakdown.png)
