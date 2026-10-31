# Stage fifteen: general optimization status

Historical snapshot of the first interrupted attempt. Superseded by [the complete restarted campaign](general-stage15-results.md).

**Implementation and correctness checks are complete. Performance comparison is incomplete: the original1GiB disk guard stopped after5 of28 planned rounds. Defaults remain unchanged.**

Four independent opt-in switches port register fusion, normalized-reduction fusion, analytical valid-cell counts and radius-one specialization into the general graph. No window loop, wavefront, feature pruning, precision change or extra AOT call is introduced. Radius-one preserves the old large-radius fallback.

24 direct pixel comparisons against4 independent original general outputs pass, including20 current-general comparisons. G0 is bitwise equal to R-B0 on all4 cases. Worst linear error 2.563e-06 remains below the unchanged1e-5 contract; finite/alpha checks pass. Five complete histories pass70 frame comparisons (60 current-archive frames); worst error 2.65241e-06. 189 Python tests, CPU/Metal11 stages each, C++17 release build and18 focused Swift tests pass.

| Portra1080p arm | Warm median ms | Device peak MiB |
| --- | --- | --- |
| R-B0 | 14.66 | 462.2 |
| G0 | 14.87 | 462.2 |
| registers | 14.37 | 550.3 |
| normalized | 18.09 | 462.2 |
| counted | 23.97 | 462.2 |

Radius1 and original windowed are unmeasured for this case; all three other cases remain unmeasured. These initial values are not stable performance estimates. Do not infer an upstream speedup or select a default from them.

The saved environment snapshots show12.8GB swap usage throughout, without proving active swap caused the change. Free disk space declined during the campaign, and the unchanged1GiB guard stopped before the next arm. All unfavorable results remain. No native compilation, GPU verification, plotting or cache cleanup occurred inside timing. Docker/user services and caches belonging to other tasks were left alone.

Passing release/test build caches were removed only after regression completion; inactive historical workers and Fotufilm-generated Metal sources were losslessly archived with hashes. The original pixel dump-write failure and interrupted timing are retained. Current workers, AOT and all evidence remain available.

Resume by restoring adequate headroom, then rerun the complete28-round predeclared cohort from scratch; do not splice in the interrupted rows. Full current-source release/parity, wider coverage, repeats/holdout and formal acceptance remain pending.

[Contract and tools](general-optimizations-contract.md), [full status and evidence](general-stage15-status.json).

Raw interrupted timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/general-optimizations-timing/c70734ff59be/report.json`.
