# Stage eleven: three-stage LogExposure diagnostic

Status: the bounded diagnostic is complete, 2026-10-31. **This three-stage layout did not improve speed over the two-stage control in any of the four measured cases.** Retain it as an opt-in research control; do not enable it by default or submit a speedup PR on these results.

The two-stage candidate has a lower median than named R-B1 only for Portra UHD in this run. R-B1 is not a frozen best baseline. All numbers are one warm round per case/arm with background Docker running and thermal state 0/1; neither the favorable nor adverse differences establish stable causal performance.

| Case | R-B1 median / p95 ms | E2 median / p95 ms | E3 median / p95 ms | E3 vs E2 median |
| --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 7.45 / 16.59 | 9.36 / 10.63 | 9.94 / 17.61 | +6.3% |
| portra400-coffee-3840x2160 | 50.40 / 117.79 | 38.35 / 43.18 | 51.73 / 63.98 | +34.9% |
| hp5plus400-coffee-1920x1080 | 7.24 / 9.81 | 8.72 / 12.91 | 10.11 / 13.08 | +15.9% |
| hp5plus400-coffee-3840x2160 | 22.73 / 29.21 | 24.66 / 30.67 | 25.42 / 28.41 | +3.1% |

| Case | R-B1 device peak MiB | E2 peak MiB | E3 peak MiB | E2 → E3 GPU dispatches |
| --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 334.3 | 322.9 | 312.9 | 122 → 135 |
| portra400-coffee-3840x2160 | 1183.7 | 1084.2 | 1181.3 | 240 → 275 |
| hp5plus400-coffee-1920x1080 | 274.8 | 286.1 | 297.1 | 98 → 111 |
| hp5plus400-coffee-3840x2160 | 667.7 | 627.7 | 692.2 | 175 → 205 |

Twelve valid rounds, 24,366 measurement requests, original 5/30/2/5-second protocol, one frame in flight and 1-GiB pool. All own-arm phase hashes match the verified outputs. Common driver unchanged; no compilation or cleanup during timing. Device peaks include cold start. Full request events, phase hashes, environment observations and unfavorable p95 values remain in the raw report.

The third stage boundary stores the original LogExposure value after halation. Both edges are GPU-resident RGB float32 rings (A2048/B1024), with output bands of 512 rows. Coarse halation grids remain internal to stage two. The per-band sync remains. This implementation does not demonstrate GPU stage concurrency. UHD stage two is invoked seven times for five output bands because of ring wrap. Extra calls, tables, materialization and memory are observed costs; exclusive stage GPU cost is not yet known. Per-edge demand/batch changes are also part of the design, so this is not a causal test of stage count alone.

Twelve full-pixel R comparisons, four actual-kernel/region/completion traces, fourteen lifecycle frames, four invalid-option checks and failure/drain/recovery at both predecessor stages pass. Max linear error is about 2.563e-6; alpha exact. E2/E3 hashes differ within tolerance; E3 trace/normal hashes match. Twenty-one host dependency checks, 115 Python tests, 11 CPU and 11 Metal stage checks pass; generated headers/locks are current.

Private AOT has 15 E2 or 18 E3 archives plus the frozen legacy63 diagnostic control. This is explicitly mixed and cannot serve as full current-source release validation. Current-revision full release AOT/parity/Swift checks, stable B_ref, retention and formal performance gates remain pending. Earlier release/Swift results apply only to their recorded revisions. No PR was created, Docker was not quit, and Taggii/iOS was not changed.

Implementation: `f9c4175f98c5f05f84b0bfc610d504fd4a39d55b`. [Machine-readable provenance](wavefront-stage11-results.json) includes all paths/hashes, exact source keys, workers, AOT identities, cleanup manifest and reproduction limitations. [Cache contract and commands](wavefront-three-stage-contract.md).

Local timing report: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/wavefront-three-stage/timing/61f3b38b4a95/report.json`.
Local chart: `/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-three-stage-stage11/comparison.png`.

The durable CLI preparation/verifier are equivalent to the retained executed scripts but have not had a second full rebuild. The executed preparation control-directory correction is recorded in JSON. This limitation is not hidden by stamping a release.

Next investigation, if continued: quantify repeated halation/table and wrap costs before another split. Keep the producer-batch-only experiment, persistent coarse-field proposal and asynchronous scheduler separate. More stages alone is not an optimization objective.
