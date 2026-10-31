# Post-MTF frontier experiment

Status: T13/T14 experiment in progress, 2026-10-31. This is a macOS diagnostic;
the legacy selector and public ABI are unchanged. Halation, table extraction and
asynchronous submission are separate future experiments.

## Frozen scope and controls

- Clean R: `96623ba0831a52dbddcda35727a206d4123a8b5f`, pinned Halide gitlink
  `58868f0c7106f8e1214c8ae14f55e3157659b8e0`.
- Pre-cut C: `339e78e`, full-width 512-row bands, 2048-row ring. The active 512
  archives and host are rebuilt from that source snapshot for the new comparison.
- Post-cut C: the worktree source hashes recorded by the generator, normal-pixel
  and trace verifiers. All 15 private normal archives are rebuilt together.
- Use the four frozen 1080p/UHD Portra/HP5 cases in
  `build/wavefront-corpus/frozen-verification-v2.json`. Synthetic lifecycle frames
  exercise different content, seeds, stock, geometry and stage selection.
- Existing primary images have already informed this hypothesis. They are tuning
  evidence, not a final holdout. No tile size or formal threshold is selected here.
- The 63 frozen legacy archives remain explicitly mixed with new private kernels.
  This is never stamped as a complete current-source release. Final T7 and the
  stable B_ref, retention and performance gates remain required.

## Edge contract

| Property | Post-MTF light edge |
| --- | --- |
| Logical value | The original `Store::MtfSelected` value after primary, optional secondary/luma and final MTF selection. Exact-stage graphs may elide named selects; intercept the unique store point and require exactly one match. |
| Format | Three planar float32 channels. Source/output row stride is W; channel stride is W*2048. No half narrowing, new curve, tone mapping or RGB/luma reordering. |
| Coordinates | Frame x/y coordinates. Physical row is logical y modulo 2048. Current admission requires full-frame input/output, origin zero and the original eligible stages/classes/geometry. |
| Producer input | Original scene exposure and camera gate, original MTF Gaussian expressions and stores. A requested post-MTF interval needs the primary/luma/secondary input apron; producer scratch and overlapping apron work remain counted. |
| Consumer demand | Halation scales form a union, followed by the union of active coupler/adjacency demands and then print-MTF support. Coordinate-only grain blur is a separate predecessor, not an added light reach. Grid alignment and interpolation use the existing shared geometry helpers. |
| Safe reach | `wavefront_post_mtf_reach` states the supported graph's branch bound. It is not a minimum allocation. Keep the old conservative source admission as an additional restriction; do not broaden eligibility. |
| Initial capacity | Keep the old +/-360-row requested cache span and 2048 physical rows. A 512-row band needs at most 1232 retained rows under that contract. No smaller-ring or narrower-margin tuning in this experiment. |
| Generation / readiness | All row labels are call-scoped. Labels after source return identify ordered submission, not CPU-observed GPU completion. Source and consumer use the existing Metal queue, with the existing consumer device sync before reuse. Trace checks actual queue completion ordering. |
| Readers / last use | Both direct light and all halation-grid descendants can read the edge. Preserve rows through every consumer band whose requested interval intersects them; only the completed-band watermark permits replacement. |
| Wrap / tail | Split source production at physical ring wrap, keep absolute logical coordinates, shorten the final output band, produce each logical edge row once. Frame boundaries keep the original normalization; band edges are not image boundaries. |
| Failure | Unsupported requests fall back before output writes. Admitted failures drain submitted work and invalidate that output; never rerun legacy over partial output. Buffers and crop views remain alive until required GPU work completes. |

## Schedule audit

The old producer was non-windowed because exposure alone needed no row loop. Moving
MTF there without another change would disable the Metal radius-one fused blur and
fused normalized-tap accumulation. `GpuSchedule` now separates region blur policy
from window-loop placement. The post-MTF producer enables that policy but keeps
compute-root crop inference, not a second row-window loop. Existing legacy callers
retain their original defaults. Merged four-channel primary MTF keeps its original
separable path; eligible non-merged radius-one kernels keep their 3x3 path.

Materialized MTF predecessors still preserve their float32 boundaries. The consumer
substitutes the RGB ring at the final store, so the unused MTF ancestry is pruned.
Do not remove stored expressions or force half values to reduce traffic. Source
realizations and generated schedules must verify these claims for actual radii.

## Memory and halation review

At UHD the ring payload changes from 120 MiB to 90 MiB in the luma class; mono
retains 90 MiB. These are ring payloads, not total device peaks. Source scratch,
configuration, full input/output, pool allocations and overlapping lifetimes count.

Halation is a deterministic image-dependent spatial field, not a seeded random
process. Its unblurred pyramid feeds subsequent downsampling levels; blurred
outputs are sampled by their own scale. The three final UHD fields occupy about
8.9 MiB in these cases, excluding all downsample and blur scratch. Whole coarse
allocation may be cheap, but its rows must become ready without an implicit
full-frame MTF allocation or barrier. No field-cache implementation is included.

## Observation and decision

The old UHD Portra trace generated 3056 rows of its MTF result for a 2160-row
union (41.48% additional coverage). `tools/analyze-wavefront-regions.py` records
per-function unions and input trace hashes. Coverage is not runtime or FLOPs;
changing x/channel domains are reported as unassessed instead of approximated.

Diagnostic root tracing also records 1D/2D table realizations. It does not establish
per-table GPU time or imply every defined table runs. Table extraction remains T15.
The global TraceRealizations target failed in the pinned compiler; that failed
attempt and a root-level inspection error are retained separately. Root-only
tracing uses a private LoopLevel copy so inspection cannot lock the actual schedule.

Normal kernels are timed without detailed tracing or a concurrent compiler/cache
cleanup. Observe independent pre/post processes with the same API, seed, pool,
band, ring capacity and completion policy, alternating order across cases. A
single pair per case is exploratory only; stable R and repeated holdout data are
still needed for acceptance. Docker remains running.

Record complete pixel/alpha comparisons, actual producer regions, source/consumer
GPU completion, table counts, dispatches, allocations, total device peaks and end
to end latency. A faster enqueue or smaller region is not a passing speed result.
If the cut worsens complete cost, retain the evidence and revise or remove it.
