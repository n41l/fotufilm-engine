# Stage23: recent-frequency eviction does not beat BestFit

The proposed priority to improve eviction instead of using oversized buffers did not succeed in this concrete implementation. Recent-frequency exact-size eviction retains the frequent48MiB bin but repeatedly discards two128MiB buffers and several tiny bins. UHD Metal peak stays1183.72MiB; every measured UHD call creates12 new buffers. Its normal-driver latency is50.802ms versus41.915ms original (+21.20%); all three within-repeat UHD comparisons are slower. Reject this policy for promotion. This is evidence about one policy, not every possible eviction strategy.

Implementation e9d689b. The [fixed protocol](windowed-pool-recent-contract.md) uses the sum of current/previous frame size-request counts, breaking ties by physical last rental. Exact-size reuse remains exact; admission selects all victims before mutating the pool, so rejecting an incoming return never partially evicts useful idle buffers. Old demand expires after two frames and explicit pool release clears metadata. Source fence checks, references, rounding, original1GiB idle cap, queue capacity4, frame graph, shaders and film formulas stay unchanged. The policy exists only in generated diagnostic copies of frozen R96623ba; production and defaults remain unchanged.

Validation:7 native checks against the actual policy header plus4 pool and13 resource regression tests passed. Six frozen fixtures passed full normal-driver output dump SHA, finite/alpha and actual/AOT/dispatch checks against independent R. Four six-frame HD/UHD light/detail sequences and a13-frame changing-size/configuration/cleanup/re-entry history passed (37 resource frames). The observed resource ledger/fence completion/reuse, exact physical length=rounded request, references and all sampled idle-cap checks passed. No active or pending object becomes an eviction candidate: the original completion-gated return path is preserved, and only already-idle entries can be displaced. These are research checks; concurrency/all-stock/holdout and full release validation are not claimed.

The fixed timing cohort completed18 valid fresh processes and31826 measurement calls. Original, original BestFit and Recent share the unchanged common normal driver and original63 AOT archives, with5s warm/30s measure/2s tail/5s idle. Three cyclic orders at HD, reversed at UHD; positions balanced within each size but predecessor pairs are not fully balanced there. No detailed probes, native builds, GPU verification, plots or cleanup during timing. Docker/user services stayed running. Evidence was about29.88MiB, below256MiB;1GiB reserve held. Native film/AOT sources, queue4, windows and defaults were not changed.

| Case / metric | Original | BestFit | Recent frequency |
| --- | ---: | ---: | ---: |
| HD API median ms | 10.559 | 8.917 | 10.184 |
| HD worst process p95 ms | 24.989 | 17.881 | 17.369 |
| HD Metal peak MiB | 334.281 | 334.281 | 334.281 |
| UHD API median ms | 41.915 | 38.219 | 50.802 |
| UHD worst process p95 ms | 62.808 | 54.341 | 65.422 |
| UHD Metal peak MiB | 1183.719 | 991.719 | 1183.719 |
| UHD throughput median fps | 22.800 | 25.133 | 19.400 |

API and memory entries are medians of three independent process summaries, not pooled frame averages. Worst p95 is explicitly the maximum of the three process p95s. All raw process summaries and five-second bins are retained in [results JSON](windowed-pool-stage23-results.json).

| UHD repeat | Original ms | BestFit ms | Recent ms | Recent−original |
| --- | ---: | ---: | ---: | ---: |
| 1 | 41.915 | 38.219 | 51.787 | +23.55% |
| 2 | 39.332 | 39.507 | 49.847 | +26.73% |
| 3 | 41.953 | 36.503 | 50.802 | +21.09% |

| HD repeat | Original ms | BestFit ms | Recent ms |
| --- | ---: | ---: | ---: |
| 1 | 11.439 | 7.321 | 10.184 |
| 2 | 10.559 | 11.901 | 10.719 |
| 3 | 9.251 | 8.917 | 9.533 |

HD Recent's arm-median difference is−3.55%, although it is slower in two of the three paired repetitions. This is another reason not to infer stable speed improvement from a favorable aggregate. BestFit is8.82% faster than original at UHD in this cohort, but is slightly slower in one repetition. Earlier cohorts include the opposite aggregate direction; this does not justify default activation or retrospective correction of old scores.

Allocation evidence is stronger than ranking alone: HD all three arms create zero new buffers during all25705 measured calls. UHD original creates4 in2076 calls and3 in1; BestFit creates0 in all2306; Recent creates12 in all1738. Device peaks give Recent zero memory reduction, whereas BestFit remains192MiB/16.22% below original. Recent's process lifetime peak is also higher in this cohort (1784.30 versus1720.34MiB original); device peak is the primary memory observation and application-wide residency guarantees are not inferred.

After timing ended, the exact existing original resource observer c138018 was restored from its verified gzip and ran six UHD frames as a separate post-timing resource confirmation. Its steady new requested-size histogram is4×48MiB=192MiB/frame. Recent's own detailed six-frame proof instead ends with2×128MiB plus ten small buffers,268436452 requested bytes (about256MiB/frame). This direct observation confirms the tradeoff; no resource-driver latency is mixed into normal timing. Requested lengths are not a measurement of OS physical page allocation or zero-fill cost.

At UHD the request sequence asks for128MiB twice,48MiB20 times,56MiB8 times and72MiB6 times per steady frame. Giving every physical buffer the same size-bin frequency makes the many48MiB buffers look hot; the less frequently requested128MiB pair is still required every frame. Preserving exact size bins therefore moves the repeated new allocation to larger buffers rather than sharing storage between phases. BestFit can reuse a completed larger buffer for a smaller request, reducing the physical buffer set. This explains the observed allocation/memory pattern; it does not isolate how much latency comes from Metal allocation, mapping, GPU hazards, cache behavior or policy bookkeeping. No detailed method timing was collected in this cohort.

Boundary1-minute load varied4.21–15.66; thermal states were0/1 and swap/memory observations are retained. Processes are sequential on a changing background session; GPU frequency, power and other-process GPU use were not measured. Do not blame Docker or promote one favorable BestFit cohort to a universal speed claim. The consistent UHD Recent regressions plus failed memory objective are sufficient to reject this concrete policy without an additional tuning search.

Evidence paths: build/windowed-pool-stage23/workers.json and sources/; build/windowed-pool-stage23-proof/report.json (six normal cases and five resource histories); build/windowed-pool-stage23-timing/report.json,summary.json,validation.json (all18 processes); build/windowed-pool-stage23-reference-confirmation/report.json (post-timing allocation sizes). All failures/unfavorable results retained; this implementation had no failed preflight or interrupted timing campaign. The existing original observer was only restored after timing; no archive/cleanup/build occurred during timing.

Reproduce the7 native policy tests with xcrun clang++ -std=c++17 -O2 tools/test-windowed-pool-recent.cpp. Build using tools/prepare-windowed-pool-recent.py, verify with tools/verify-windowed-pool-recent.py and the frozen six-case proof, then run tools/run-windowed-pool-recent.py with that proof. Only after the timed controller exits, use tools/summarize-windowed-pool-recent.py and tools/windowed-pool-recent-chart.py. Worker and source fingerprints are bound in the manifests; exact original normal binaries and six-case proofs are checked at admission.

Decision: do not advance Recent frequency; preserve it as a negative experiment. BestFit remains an optional memory experiment with unchanged defaults. No Taggii/iOS integration, default activation, push or PR. Stable B_ref/full release/all-stock/holdout/retention/concurrency gates remain pending.
