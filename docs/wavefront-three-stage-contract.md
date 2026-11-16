# Three-stage LogExposure prototype

Private macOS research only. The default legacy and ordinary two-stage paths do
not select this build. It changes scheduling and bindings; Graph/Stages math,
the public ABI and photographic stock data remain unchanged.

The actual frame graph is:

```
scene -> exposure/gate/MTF -> A -> halation/mix/log -> B -> chemistry/grain/print/output
```

This caches the post-halation **log exposure** field. The three coarse halation
fields and their downsample/blur intermediates are still generated inside the
middle AOT call. This is not the separate persistent multiscale-field proposal.

| Property | A | B |
| --- | --- | --- |
| Original graph store | MtfSelected | LogExposure |
| Format | Planar RGB float32 | Planar RGB float32 |
| Capacity | 2048 full-width rows | 1024 full-width rows |
| Row mapping | logical y modulo 2048 | logical y modulo 1024 |
| Next consumer | Halation plus direct-light mix/log | Chemistry plus print/output |
| Demand support | halation reach + log reach | max active coupler/adjacency reach + print radius |

Reach uses the existing geometry helpers, grid alignment and interpolation
allowance. Coordinate-only grain is a separate branch. The original admission
also remains required, including exact class/stages, full frame, zero origin,
transport and spatial bounds. Only 512-row output bands are admitted in this
prototype. Other requests fall back before writing output.

Both caches share one GPU-resident Metal allocation with the configuration
prefix. The first stage sees its original prefix+A buffer extent through a view;
the middle and final stage see prefix+A+B. No intermediate host readback occurs.
The caches and logical row labels belong to one invocation. Logical rows are
produced once; reads require every demanded row label, and an overwrite requires
the old row's last output band to have completed. Native buffer/crop lifetimes
extend through the final queue drain. Existing scratch-pool GPU fences still
apply, including multiple predecessor calls in flight.

The host keeps the output-band device sync and final drain. Three stages do not
imply three concurrent GPU engines or an asynchronous scheduler. Physical wrap
can split an AOT production interval and add table/dispatch work. Count both
caches, scratch, tables, overlapping submissions and retained pool in peak memory.
Neither fewer logical rows nor more stage boundaries is a speed claim.

Build identity is explicit: generator `--three-stage` requires the macOS
wavefront opt-in, and the host requires `FOTUFILM_THREE_STAGE_RESEARCH=1`.
The diagnostic builder checks the host/control/kernel stage count in addition to
the existing source fingerprint. The 15 ordinary private archives and 18
three-stage archives are combined with the frozen legacy63 control for these
experiments. They are not a complete current-source release set. Three-stage
trace copies of the unused non-512 consumers remain two-stage and are never
selected by the three-stage host.

## Reproduction

Use a **new** output directory, a verified frozen wide-diagnostic control and the
pinned local Halide installation. For example, from the candidate checkout:

```sh
python3 tools/prepare-wavefront-three-stage.py \
  --control build/wavefront-post-mtf-final/control \
  --halide-root build/halide-install --output build/three-stage-reproduction
python3 tools/verify-wavefront-three-stage.py \
  --build build/three-stage-reproduction --output build/three-stage-proof \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --reference-worker ../reference/build/wavefront-benchmark-v2/instrumented/runner
python3 tools/verify-wavefront-three-stage-trace.py \
  --verification build/three-stage-proof
python3 tools/verify-wavefront-lifecycle.py \
  --reference ../reference --reference-kernels ../reference/build/wavefront-macos \
  --kernels build/three-stage-reproduction/control-3/kernels \
  --diagnostic-control build/three-stage-reproduction/control-3 \
  --diagnostic-kernels build/three-stage-reproduction/three-normal \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json \
  --band 512 --three-stage --compress-reference
python3 tools/run-wavefront-stage-diagnostic.py \
  --proof build/three-stage-proof/report.json \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --reference-report build/wavefront-benchmark-v2/awake/0c2977588b8c/report.json \
  --reference-worker ../reference/build/wavefront-benchmark-v2/instrumented/runner \
  --output build/three-stage-timing
```

Timing uses the unchanged common driver and the original 5/30/2/5-second protocol,
one fresh process per arm, single frame in flight, 1-GiB pool and no image dumps.
The bounded diagnostic keeps a 1-GiB disk reserve; formal campaign guards are not
relaxed. Do not compile, clean caches or run other experiments during timing.
The named R-B1 arm is not a frozen B_ref. One round per case/arm, rotating order,
background load and thermal differences limit causal conclusions.

The trace checker validates real A/B production extents, complete output bands,
row readiness, slot overwrite, kernel binding count and preceding output-band
GPU completion. Phase tags label command-buffer commit scopes; they are not
per-kernel fences or reliable exclusive stage times. Realization events alone
do not prove that a kernel executed.

[Stage-eleven results](wavefront-stage11-results.md) records measured behavior,
all adverse outcomes, provenance and remaining release/acceptance checks.
