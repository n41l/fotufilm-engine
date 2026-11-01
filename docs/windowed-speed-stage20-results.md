# Stage twenty: allocator, CPU, GPU and wait timing probes

**The directly timed allocation CPU path is small in this cohort. GPU execution coverage and elapsed command encoding are much larger; overlapping intervals must not be added.**

Final scope-correct cohort:32 fresh processes,10 warm+40 measured frames each,1,280 measured frames and37,760 measured kernel command timestamps. Four process medians are aggregated by their median below; complete per-process/pooled distributions, p95/max, raw intervals and observer controls are retained.

| Size / cell | API wall ms | Main-thread CPU ms | Allocation CPU inclusive ms | Explicit wait wall ms | GPU interval union ms |
| --- | --- | --- | --- | --- | --- |
| HD / R-off | 7.723 | 1.541 | — | — | — |
| HD / R-on | 7.557 | 1.568 | 0.016 | 1.603 | 5.431 |
| HD / BestFit-off | 7.394 | 1.587 | — | — | — |
| HD / BestFit-on | 8.004 | 1.625 | 0.016 | 1.676 | 5.851 |
| UHD / R-off | 39.761 | 6.480 | — | — | — |
| UHD / R-on | 40.099 | 7.006 | 0.213 | 3.766 | 30.439 |
| UHD / BestFit-off | 41.661 | 6.582 | — | — | — |
| UHD / BestFit-on | 38.013 | 6.891 | 0.077 | 3.897 | 31.412 |

UHD probe-on detail:

| CPU-side scope | R median / p95 ms | BestFit median / p95 ms | Relationship |
| --- | --- | --- | --- |
| Allocator inclusive | 0.213 / 0.263 | 0.077 / 0.112 | includes reclaim, search and fresh driver allocation |
| Metal buffer creation | 0.103 / 0.145 | 0.000 / 0.000 | subset of allocator in this path; driver API wall time |
| Pool reclamation | 0.075 / 0.104 | 0.051 / 0.080 | nested in allocator |
| Eviction release | 0.022 / 0.030 | 0.000 / 0.000 | nested in reclaim; release-message wall time |
| Runtime object release | 0.039 / 0.057 | 0.039 / 0.068 | includes strings/pipelines and logical buffer returns |
| Command encoding envelope | 30.607 / 35.044 | 28.285 / 40.576 | creation through commit entry; elapsed, not active CPU |
| Command commit | 0.243 / 0.309 | 0.231 / 0.361 | CPU call wall time |
| Explicit waitUntilCompleted | 3.766 / 4.947 | 3.897 / 6.439 | overlaps GPU execution; not every implicit blocking mechanism |

The typical inclusive allocation CPU delta is0.136ms/frame; direct Metal creation is0.103ms for R and zero at the BestFit median. Original allocator p95/max are0.263/0.316ms; BestFit0.112/0.927ms. This bounds the observed direct host-call opportunity, not all allocation consequences: initialization, mapping or other work deferred elsewhere is not isolated.

The original UHD GPU union is30.439ms and span37.430ms; BestFit union31.412ms and span35.408ms. Summed per-kernel intervals are41.912/45.980ms, demonstrating overlap and why they are not elapsed frame times. Explicit wait3.766/3.898ms overlaps reported GPU intervals for3.620/3.765ms. Do not add wait to GPU union, or nested allocation scopes to their parent. Union measures covered timestamp intervals, not GPU utilization/active cycles. Submit-entry→GPU-start delay is a scheduling observation, not pure queue/fence wait.

Command encoding envelopes total30.607/28.285ms in wall time, while the main thread accumulates7.006/6.891ms of user+system CPU sampled around the API. Therefore the encoding envelope cannot be described as30ms of active CPU work; driver blocking, descheduling and probe overhead are not separated. The explicit wait hook covers waitUntilCompleted only. CPU copying, internal driver stalls, asynchronous work on other threads and hardware cache/DRAM/spill costs are not individually measured.

Each probe-on cell has160 measured frames. R UHD creates640×48MiB buffers plus two4KiB buffers:158 frames create4, two create5. BestFit creates three4KiB buffers and one832KiB buffer:157 frames create0, two create1, one creates2. The four recurring48MiB allocations disappear, but do not describe all160 frames as allocation-free. R HD has one single-buffer exception; the other159 frames and all BestFit HD frames create zero. Raw size/count observations are in JSON.

Longer UHD GPU command envelopes, ranked by R per-call median (families group entry variants/windows, not additive stage costs):

| Kernel family | R per-command median ms | BestFit per-command median ms |
| --- | --- | --- |
| frame_output_v40 | 1.802 | 1.973 |
| frame_print_mtf_transmittance_v40 | 1.673 | 1.681 |
| frame_mtf_v40_horizontal | 1.445 | 1.785 |
| frame_coupler_diffused_v40_spread | 1.293 | 1.413 |
| frame_mtf_secondary_v40 | 1.158 | 1.171 |
| frame_grain_field_v40 | 1.017 | 1.463 |
| frame_coupler_diffused_v40_spread_horizontal | 0.927 | 0.923 |
| frame_light_gate_v40 | 0.903 | 1.909 |

Top entries include output, Print MTF transmittance, MTF horizontal, Coupler spread and secondary MTF. Their command durations are GPU-reported execution envelopes; this does not identify an optimization root cause or prove a particular stage is the critical path.

Observer controls matter: UHD probe-off API medians are R39.761/BestFit41.660ms, while probe-on gives40.099/38.013ms. The policy comparison changes direction. Observed probe effects include background variation, callbacks/timers and trace serialization between API calls; they are not an exact overhead correction. This count-based cohort uses10 warm frames rather than stage19's5-second warmup/30-second measure window. Do not merge the datasets or replace the previous latency nonregression failure with a probe-on win.

Instrumentation: wrappers time the original allocator/runtime release; read-only scopes in generated shim copies time reclamation and eviction release. A process-local observer times Metal allocation, command creation and waitUntilCompleted. Every Halide command gets an additional completion callback recording its existing label and GPUStartTime/GPUEndTime. The observed frozen runtime emits one compute command per kernel; every measured kernel count matches the independent dispatch proof (HD41,UHD77), plus three sync command buffers per frame. CPU/Metal clock domains and API bounds are checked. Probe callback drain and trace writing occur after the API timer; their flush time is recorded. No new wait is inserted inside the API.

The final driver measures the same inner autoreleasepool cleanup scope as the common benchmark. Initial missing-clock-declaration compilation failure is preserved under build/windowed-speed-stage20/R/build.log and fixed before GPU execution. Earlier v2 pilots and v3 preflight/profile remain exploratory: v3 excluded caller pool cleanup from its API timer. Corrected v4 repeats all24 preflight cells and32 profile processes from scratch, with no sample splicing. The v2/v3 obsolete workers are losslessly archived with restore maps under their build directories.

Verification: six frozen cases × two policies × probes on/off give24 final preflight processes with exact original output SHA, finite/alpha, actual symbol, one AOT and dispatch checks. Final32 processes repeat phase SHA at warmup/measurement boundaries and all-call coverage checks. Nine probe/interval/transform regressions and13 existing resource tests pass. Frozen R stays clean; production/default, film math, AOT archives, ABI and windowing are unchanged. GPU SDK/runtime source hashes and generated shim metadata are saved. No native build, GPU validation, plotting or cleanup occurred during the final sampling cohort; Docker and user services remain running.

Conclusion: prioritize GPU-stage investigation and the source of elapsed encoding/driver stalls before extending direct allocation CPU optimization. This is a diagnostic direction, not a new implemented optimization or a causal attribution. Keep default behavior unchanged; full stock/holdout, concurrent behavior, stable baseline and formal release gates remain pending. No Taggii integration, push or upstream PR.

[Contract](windowed-speed-contract.md), [complete metrics and source fingerprints](windowed-speed-stage20-results.json). Final profile: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-speed-stage20-profile-v4/report.json`. Final worker manifest build/windowed-speed-stage20-v4/workers.json; final preflight build/windowed-speed-stage20-preflight-v4/report.json. The unscoped exploratory report `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/windowed-speed-stage20-profile/report.json` is explicitly excluded.

Reproduce into new output folders:

```sh
python3 tools/prepare-windowed-speed.py --reference ../reference --output build/speed-workers-new
caffeinate -i -s python3 tools/run-windowed-speed.py --workers build/speed-workers-new/workers.json --proof build/windowed-unit-stage18-proof/report.json --reference ../reference --output build/speed-preflight-new --preflight
caffeinate -i -s python3 tools/run-windowed-speed.py --workers build/speed-workers-new/workers.json --proof build/windowed-unit-stage18-proof/report.json --reference ../reference --output build/speed-profile-new --preflight-proof build/speed-preflight-new/report.json
```

![4K probe breakdown](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-windowed-speed-stage20/breakdown.png)
