# Post-MTF experiment results (stage ten)

The cut preserves pixels and removes repeated MTF result rows, but this first
configuration does not improve every workload. Retain it as a private experiment;
do not promote it or create an upstream benefit PR. Source: `55ae6b1ec24f82c6f784b825ea4a1b1ea7174613`.

| Case | Pre median / p95 ms | Post median / p95 ms | Device peak MiB |
| --- | --- | --- | --- |
| portra400 1920x1080 | 9.26 / 10.00 | 9.37 / 9.99 | 302.4 → 322.9 |
| portra400 3840x2160 | 51.07 / 86.96 | 36.74 / 37.65 | 1181.2 → 1084.2 |
| hp5plus400 1920x1080 | 10.25 / 14.96 | 10.01 / 13.86 | 265.9 → 286.1 |
| hp5plus400 3840x2160 | 26.41 / 34.51 | 26.78 / 37.16 | 611.7 → 627.7 |

Eight protocol-valid rounds contain 15,396 measurement requests. Both arms are
C wavefront candidates, not upstream R. Consumer band 512, ring 2048, one frame
in flight, 1-GiB pool, 5-second warmup / 30-second measurement / 2-second tail /
5-second idle. Each arm/case has one round; thermal maxima vary between 0 and 1.
The primary images are tuning data. Portra HD uses PRINTED_NEGATIVE, Portra UHD
adds MTF_LUMA, and HP5 uses PRINTED_SLIDE; differences are not attributable to
resolution alone. These observations are not a stable causal
speedup, final tile selection, holdout result or formal memory nonregression.

## What was verified

- 24 normal full-pixel comparisons, four trace cases with exact kernel-binding /
  dispatch count agreement, and 14 lifecycle frames passed against independent R.
  Max normal linear error: 2.562999725e-06; alpha exact.
  All four 512 outputs are byte-identical to the pre-cut C outputs. Invalid options,
  pre-write fallback, injected source failure, drain and next-frame recovery passed.
- CPU/Metal stage tests: 11 each. Python tests: 137; host demand checks: 11.
  Swift release build passed. The focused Swift test bundle built, then its process
  was interrupted while compiling Halide IR, without an assertion result. Logs and
  CPU sample are retained; this test is not marked passed or numerically failed.
- The detailed resource observer classified all 413 leases / 107 physical buffers,
  verified frame intermediates returned, GPU completion and the original pool cap.
  Its totals are separate from light-worker metrics and are not a full named-edge
  spatial-local benefit or retention acceptance.
- All active pre-cut 512 archives were rebuilt from 339e78e and are byte-identical
  to their verified frozen archives. The new 15 private normal AOTs and six trace
  overrides match current source. Frozen legacy63 remain explicitly mixed: full
  same-source 78 AOT, release parity and broader Swift regression remain pending.

## What the traces establish

Portra UHD's MTF final result has 2160 generated rows rather than 3056, while the
output frontier is produced once per logical row. Radius-one non-merged source
blur uses its fused kernel: a horizontal realization event alone does not mean
the horizontal GPU kernel executed. Actual kernel binding counts match dispatches.
Curve, blur and grain tables are still generated once per band (five times on
UHD). Their independent GPU cost has not been measured.

## Decision and next experiment

Portra UHD's observed median falls about 28.1% and device peak about 8.2%. Two
other medians increase slightly, and the other three device peaks increase.
No per-case adverse result is removed. The current consumer band of 512 does
not cap source production to 512: the initial source batch is 872 rows under the
unchanged +/-360 margin. Source scratch and pool size classes are a hypothesis
for the peak regressions, not a proven attribution.

Before extracting tables or halation fields, separately test a producer batch
limit while preserving the ring capacity, consumer band, expression precision
and GPU completion policy. That change is not implemented here. Recheck pixel /
reuse / lifecycle and measure added source/table dispatches alongside memory.
Multiple source calls inside one band may remain in flight before the existing
consumer sync; count all scratch leases. A batch cap alone does not prove a lower
peak. Stop or revise if complete cost is worse. Formal B_ref, retention and PR gates
remain unchanged. The assistant did not quit Docker or modify Taggii/iOS.

## Reproduction and evidence

The implementation contract is [wavefront-post-mtf-contract.md](wavefront-post-mtf-contract.md).
The machine-readable [stage-ten report](wavefront-stage10-results.json) records
source hashes, independent proofs, archive identities, all cases and raw reports.
Use `tools/prepare-wavefront-wide-diagnostic.py` with control-ref `deacc05`, the
frozen legacy proof and a new output directory; it explicitly builds a diagnostic
composite. Run the normal, managed and lifecycle verifiers with that diagnostic
control/kernel pair. `--compress-reference` on the lifecycle verifier only changes
temporary disk storage; decompressed R bytes are hash-verified.

`tools/run-wavefront-cut-diagnostic.py --help` describes the no-dump pre/post
campaign. Its 1-GiB reserve / 128-MiB between-round evidence budget applies only
to this bounded diagnostic; the formal baseline controller's 2-GiB guard is
unchanged. The first attempt was stopped by the disk guard before any window.
Cleanup ended before the retry; no compiler or cleanup ran during its windows.

Historical C workers and inactive temporary Metal text were losslessly archived,
verified and journaled to recover space. Original reports, source and AOT remain;
old worker payloads can be restored with
`python3 build/wavefront-post-mtf/archived-workers/restore.py <original-path-substring>`.
This restores exact original bytes and modes. Active proof/timing workers are
retained. No push, PR, default legacy selection or release is part of this result.
