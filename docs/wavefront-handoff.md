# Fotufilm Metal optimization research handoff

Naming update2026-11-16: the active engine and documentation branches are `codex/fotufilm-metal-optimizations`; the research title is Fotufilm Metal 性能优化. The fork remains `n41l/fotufilm-engine`. Local directory paths and historical document filenames are retained for existing evidence links. The checkpoint branch name below describes its historical state.

Updated2026-11-02 after stage26. The agent then ran the sanctioned MTF-fusion × best-fit-pool combination as a 4×4 Williams factorial on the active Portra UHD case: 25/25 pixel comparisons bitwise-equal, JIT parity 1.97e-06, 16 valid rounds. COMBO is the fastest and most stable arm (39.943 ms median; −13.25% vs R; round spread 5.4 ms vs MTF's 29.1), the first configuration to beat every single-arm control. Memory savings overlap: −152.0 MiB (1183.72→1031.72), not the naive −304 — the fusion keeps its −112 while the pool's contribution shrinks to ≈−40 because the fusion removes two of the large freed blocks the pool recycles best; pool-only still holds the lowest peak (991.72). Defaults remain off; all-stock and size-mixing sweeps are the natural next step before any activation decision.

Canonical Chinese handoff, including verified artifact locations, current conclusions, constraints and suggested next steps:

[工作交接记录](/Users/kunhuang/.codex/worktrees/fotufilm-wavefront/sb_ai/Taggii/development-which/fotufilm-wavefront-handoff.md)

Engine code/results checkpoint before this documentation-only save:98986923ed0423969a70e1599cfec0945165e25f on codex/fotufilm-wavefront. Frozen independent reference:96623ba0831a52dbddcda35727a206d4123a8b5f. Candidate and reference are separate checkouts; do not edit the reference or Taggii/iOS vendor copies.

Current decisions:

- First candidate, MTF pointwise fusion: implemented and off by default. Stage16 observed77→73 dispatches,36.666→32.904ms,1183.72→1071.72MiB on the active Portra UHD case. Still an isolated diagnostic, not full release acceptance. See docs/windowed-mtf-stage16-results.{md,json} and windowed-mtf-fusion-contract.md.
- Second candidate, Coupler release/downsample fusion and stride1 specialization: tested without confirmed overall benefit; keep off (stages17/18).
- Third candidate, Print MTF vertical convolution fused into final output: implemented and measured in stage25; dispatch and storage goals met, no latency or memory benefit vs same-source control. Keep off. See docs/windowed-print-mtf-stage25-results.{md,json} and windowed-print-mtf-fusion-contract.md.
- BestFit pool: original stage19/22/23 studies show a192MiB UHD Metal-peak reduction, but latency ranking varies across campaigns. Optional research only; no default activation. Never add its savings to MTF without a new combined experiment.
- Recent-frequency exact-size eviction, stage23: reject this concrete policy. UHD41.915/38.219/50.802ms for original/BestFit/Recent; Metal1183.72/991.72/1183.72MiB; Recent creates12 new buffers/frame and is slower in all three UHD repeats. Complete evidence in docs/windowed-pool-stage23-results.{md,json}.

Keep Docker/user services running. Original queue capacity4, one in-flight frame and1GiB idle pool unless a separately declared future experiment explicitly changes a variable. Preserve1GiB disk reserve,256MiB per-cohort evidence budget and all failed/unfavorable runs. No builds, GPU verification, plotting or cleanup during timing. Old binaries/traces may exist as verified gzip archives; restore against recorded raw SHA before reuse. Do not reuse stale source/AOT keys, combine mixed-release archives as a complete current release, splice campaigns or infer GPU utilization from wall-time intervals.

Full release/AOT parity, stable B_ref, all-stock/holdout/retention/concurrency and upstream PR gates are still pending. No push, PR, Taggii/iOS integration or default activation has occurred as part of these latest diagnostics. All three audited fusion candidates are now closed (candidate1 positive-but-off, candidates2/3 no benefit); see docs/windowed-mtf-stage24-results.{md,json} and docs/windowed-print-mtf-stage25-results.{md,json}; awaiting user instruction.
