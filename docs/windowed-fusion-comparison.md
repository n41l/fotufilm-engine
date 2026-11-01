# Why the two fusion experiments behave differently

This audit reads the saved stage16/stage17 timing events and the actual Metal source files named in their build logs. It runs no new build or GPU work. The two W0 generated Metal files are byte-identical, but timing campaigns remain separate and background/host variation is not controlled away.

| Common UHD case | MTF pointwise fusion | Coupler release/downsample fusion |
| --- | --- | --- |
| Removed logical device fields | Mixed and Separated | Released |
| Retained shared/output field | Final MTF light | Log exposure and downsample grid |
| Actual frame dispatches | 77 to73 | 77 to75 |
| Generated consumer | Pointwise arithmetic; three mixed records thread-local | Curve/release expressions inside dynamic box-reduction loops |
| Steady new Metal buffers/frame | Approximately4 to exactly1 | Approximately4 to exactly4 |
| Repeated total device peak | 1183.72 to1071.72 MiB | 1183.72 MiB on both sides |

MTF starts with already computed convolution results. Its mix and neutral-axis correction are cheap, same-pixel operations. Generated fused MTF kernels contain no sampling loop or pow expression, and explicitly hold the three mixed records in a thread-local float[3]. The final shared MTF buffer remains, so downstream halation readers do not redo the convolutions. Two materializations and their downstream reads disappear per window without introducing a reduction. A retained array is not proof of physical register allocation or absence of spills.

Coupler starts from Log exposure and carries curve lookup, activation and release into each source sample of a box reduction. Released disappears, but the downsample output remains. The generic generated kernel still calculates dynamic cell bounds, loops and valid-sample normalization. Both measured profiles have stride1; the current implementation does not provide a dedicated identity-grid path. Three generated downsample specializations retain6/24/6 static for-statements. Their release pow expressions are now inside this code; the original separate Released kernel already contained those expressions, so they are not all newly added operations. Counts include alternative branches and do not establish runtime instruction counts or the cause of regression.

The strongest additional runtime evidence is allocation churn. Across all three UHD measurement rounds, stage16 Fused records1 newBufferWithLength call in every one of2696 measurement requests, versus about4 in both controls. Stage17 Fused records4 in every one of2037 requests, as do almost all controls. These calls are actual successful Metal buffer creations observed by the unchanged driver; they are not declarations of logical graph fields. No allocation sizes or call ancestry were captured.

The pool rounds large requests into size classes, reuses only an equal-size idle class, waits for GPU fences, and limits idle retention to the configured1GiB. Its implementation therefore permits a removed logical field to leave overall retention and steady allocations unchanged. The logs show that outcome for Coupler. Which exact bucket/fence/eviction caused it is not established without an allocator trace.

The supported explanation for the first win is the combination of fewer cheap pointwise boundaries, less intermediate traffic, and substantially fewer observed fresh allocations. The second removed fewer fields and did not improve observed allocation churn or total retained device memory; its arithmetic was moved into a generic reduction kernel. No per-kernel GPU/DRAM/register/spill profile exists, so the10.3% observation cannot be divided into precise bandwidth, launch and allocation contributions, nor can Coupler regression be attributed to registers or loops alone.

The next concrete Coupler hypothesis is a stride1 specialization that eliminates the identity-grid machinery, with the existing release-before-reduction path retained for larger strides. This audit does not implement or measure that change. Both research switches remain off.

[Structured counts, source fingerprints and representative kernel excerpts](windowed-fusion-comparison.json). Earlier measurements: [MTF](windowed-mtf-stage16-results.md), [Coupler](windowed-coupler-stage17-results.md).
