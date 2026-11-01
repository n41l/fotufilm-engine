# Fotufilm macOS Metal research handoff

Updated2026-11-01 after stage23. The user asked to save records before a possible agent change. No new benchmark, optimization implementation or upstream delivery is running or was started by that request.

Canonical Chinese handoff, including verified artifact locations, current conclusions, constraints and suggested next steps:

[工作交接记录](/Users/kunhuang/.codex/worktrees/fotufilm-wavefront/sb_ai/Taggii/development-which/fotufilm-wavefront-handoff.md)

Engine code/results checkpoint before this documentation-only save:98986923ed0423969a70e1599cfec0945165e25f on codex/fotufilm-wavefront. Frozen independent reference:96623ba0831a52dbddcda35727a206d4123a8b5f. Candidate and reference are separate checkouts; do not edit the reference or Taggii/iOS vendor copies.

Current decisions:

- First candidate, MTF pointwise fusion: implemented and off by default. Stage16 observed77→73 dispatches,36.666→32.904ms,1183.72→1071.72MiB on the active Portra UHD case. Still an isolated diagnostic, not full release acceptance. See docs/windowed-mtf-stage16-results.{md,json} and windowed-mtf-fusion-contract.md.
- Second candidate, Coupler release/downsample fusion and stride1 specialization: tested without confirmed overall benefit; keep off (stages17/18).
- Third candidate, Print MTF vertical convolution fused into final output: audited only; not implemented or measured. See the third section of the canonical sb_ai fusion audit. Preserve horizontal/transmittance storage, sharpening reads, normalization and the existing radius1 shortcut if implementing later.
- BestFit pool: original stage19/22/23 studies show a192MiB UHD Metal-peak reduction, but latency ranking varies across campaigns. Optional research only; no default activation. Never add its savings to MTF without a new combined experiment.
- Recent-frequency exact-size eviction, stage23: reject this concrete policy. UHD41.915/38.219/50.802ms for original/BestFit/Recent; Metal1183.72/991.72/1183.72MiB; Recent creates12 new buffers/frame and is slower in all three UHD repeats. Complete evidence in docs/windowed-pool-stage23-results.{md,json}.

Keep Docker/user services running. Original queue capacity4, one in-flight frame and1GiB idle pool unless a separately declared future experiment explicitly changes a variable. Preserve1GiB disk reserve,256MiB per-cohort evidence budget and all failed/unfavorable runs. No builds, GPU verification, plotting or cleanup during timing. Old binaries/traces may exist as verified gzip archives; restore against recorded raw SHA before reuse. Do not reuse stale source/AOT keys, combine mixed-release archives as a complete current release, splice campaigns or infer GPU utilization from wall-time intervals.

Full release/AOT parity, stable B_ref, all-stock/holdout/retention/concurrency and upstream PR gates are still pending. No push, PR, Taggii/iOS integration or default activation has occurred as part of these latest diagnostics. Suggested next step is an independent repeat of candidate1, then a separate decision on candidate3; the latest user request only saves records.
