# Two-stage multi-output cut

This private macOS prototype keeps **two AOT stages**:

```
scene -> [exposure / gate / MTF / coarse halation fields] -> A + F0/F1/F2
      -> [upsample / mix / log / chemistry / grain / print / output]
```

It implements the user's revised two-stage division. The earlier three-unit
coarse-field proposal is a historical alternative, not this implementation.
There is no third fields-only stage or full-resolution LogExposure cache.
Default legacy selection and the ordinary post-MTF E2 remain unchanged.

## Incremental producer

The first output is the original selected MTF light, planar RGB float32 in the
existing 2048-row ring A. The other three outputs are the existing final coarse
blurred fields F, planar RGB float32 in full coarse-grid allocations. X stride
is 1; row/channel strides are W/2048*W for A and Wi/Hi*Wi for each F.

The producer writes only new logical A rows. Its coarse-field graph reads a
hybrid light function: this invocation's A output for new rows, the cached A
allocation for older rows. New-output reads are clamped to the new interval so
Halide bounds inference cannot expand the A output into previously cached rows.
These Func calls preserve an explicit producer dependency inside the AOT graph.
GPU buffers are views into the same native allocation; crops retain global
logical coordinates and device ownership through the final drain.

F advances as far as ready A permits, not merely to the current output band's
demand. For origin zero, a grid row q requires A through its original decimation
cell and vertical 3*r support. Before frame end, the ready row endpoint is
`max(0, floor(A_end / stride) - 3*r)`. At frame end, original boundary handling
allows all remaining coarse rows. The unblurred U chain still feeds subsequent
downsampling levels; U/horizontal scratch may repeat across calls. Each final
F logical row is produced once. Box weight tables still run per producer call.

A and all three F output intervals are passed in **one producer invocation**,
including differing/zero-height F intervals. Existing A wrap can still split a
producer update; no extra fields-only invocation is introduced. The initial
A batch remains 872 rows for consumer512/margin360. Reducing margin, changing
band size or producer batch limits is a separate experiment.

## Consumer and safety

The consumer reads direct light A plus the three F grids. Original global grid
coordinates, valid-weight interpolation, spectral mix, logarithm and downstream
graph expressions are preserved. It retains windowed fusion and the original
per-output-band sync. There is no intermediate host readback, whole-frame MTF
copy, whole-frame production barrier, new precision mode or seeded algorithm.

Before each producer call, validate every old A row the new F regions require,
including collisions with the new A physical slots. Before each consumer,
validate direct-light row labels and all F ready endpoints. A wrap requires the
old row's last output band to have completed. Existing scratch-pool GPU fences
remain in force; submitted labels do not themselves prove GPU completion.
Failure drains submitted work before releasing views; partial output is invalid.

Only the original three exact eligible stage/class combinations at bands512/1080 are
enabled by `FOTUFILM_BUNDLE_RESEARCH=1`. The generator's `--bundle` requires the
macOS wavefront opt-in and excludes `--three-stage`. New variant/layout intent
is declared in `aot-variants.json`; classes derive from its generated macros.
The private build guard checks `cut=bundle` as well as source/stage identity.

Full F payload is `12 * sum(ceil(W/si)*ceil(H/si))` bytes: about 8.9 MiB for
the measured UHD parameters. E2 has no B cache, so this is additional persistent
storage relative to E2. It is not a promised peak-memory reduction. Count full
input/output, A/F, U, horizontal scratch, tables, overlap, LUT and pool/retention.
Full coarse storage scales with height; this is not a height-independent bound.
Validation currently covers the recorded main/synthetic cases, not all settings.

## Reproduction and evidence

Use new output directories, a verified frozen legacy control and pinned Halide:

```sh
python3 tools/prepare-wavefront-bundle.py \
  --control build/wavefront-post-mtf-final/control \
  --halide-root build/halide-install --output build/bundle-reproduction
python3 tools/verify-wavefront-three-stage.py --bundle \
  --build build/bundle-reproduction --output build/bundle-proof \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --reference-worker ../reference/build/wavefront-benchmark-v2/instrumented/runner
python3 tools/verify-wavefront-bundle-trace.py --verification build/bundle-proof
python3 tools/verify-wavefront-lifecycle.py --bundle \
  --reference ../reference --reference-kernels ../reference/build/wavefront-macos \
  --kernels build/bundle-reproduction/control-bundle/kernels \
  --diagnostic-control build/bundle-reproduction/control-bundle \
  --diagnostic-kernels build/bundle-reproduction/bundle-normal \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json \
  --band 512 --compress-reference
python3 tools/run-wavefront-bundle-diagnostic.py \
  --proof build/bundle-proof/report.json --trace build/bundle-proof/bundle-trace.json \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --output build/bundle-timing
```

The ordinary arm has 18 private archives; bundle has those 18 plus nine new
producer/consumer archives. Both link the explicitly frozen legacy63 diagnostic
control. This is not a complete current-source release set. Trace replaces the
nine bundle functions; unused ordinary kernels remain normal in that directory.

The small `tools/probe-wavefront-bundle.cpp` uses the actual GPU decimation/blur
helpers with synthetic light. It checks unequal/empty F updates, A wrap and a
full-frame GPU comparison. It is a construction probe, not a full-film oracle.
Independent clean-R full-film comparisons and lifecycle tests are separate.

[Stage-twelve results](wavefront-stage12-results.md) records the current checks,
pilot, provenance, all unfavorable outcomes and pending release/PR gates.


## 1080-row band control

The declared private band set now also includes1080. The same bundle producer
and runtime worker serve both512 and1080; each band has its own compiled consumer.
The A ring remains2048, margin360, F layout/precision, cut and per-band sync remain
unchanged. `1080 + 2*360 <= 2048` is asserted; runtime row-label/old-A collision
and F-readiness guards still apply. At UHD the A wrap can split a producer update;
do not infer AOT calls just by doubling output bands.

`tools/verify-wavefront-bands.py` verifies both bands normal/trace directly against
the frozen original default-windowed worker and the prior512 output hashes.
`tools/run-wavefront-bands-diagnostic.py` requires that proof, uses one normal
worker for both band sizes and retains fresh original B1 rounds. This remains
a mixed legacy/private diagnostic set, not a complete current-source release.
The historical stage12/13 records and worker hashes remain unchanged.
