# macOS Metal wavefront experiment

This is an opt-in research harness. It does not change the engine, the variant registry,
legacy dispatch, shared film expressions, stocks, or application integration. The first
milestone establishes a clean upstream reference and tests a reusable predecessor in two
existing Gaussian stages. There is no complete-film wavefront implementation or performance
acceptance yet.

## Frozen research environment

The original research point was `064bcabe5651bb5fcf7afb7cafa0aa47e67e76af`. Before implementation,
both clean reference R and candidate C were moved to upstream
`96623ba0831a52dbddcda35727a206d4123a8b5f`. Upstream already added 1080-row windows,
stage-exact twins, register placement and a Metal allocation pool. Those windows still
recompute spatial aprons. Comparing only against the old 256-row implementation would miss
these improvements.

The first run used an M4 Pro (12 CPU cores, 24 GB unified memory), macOS 27.0.1,
Xcode 27.1 (`27A9269`), macOS SDK 27.0, Metal `32023.921.6`, LLVM/LLD 22.1.8 and Halide
gitlink `58868f0c7106f8e1214c8ae14f55e3157659b8e0`. AOT targets ARM64 macOS 14.0 and uses
safe Metal math. This local Xcode build differs from the repository's declared public-release
recipe (`27A266a`); both local arms are rebuilt with the same actual compiler. Nothing here
publishes a release or establishes iOS, simulator or Intel Mac results.

R and C use separate source, AOT and runner directories. They share only a read-only Halide
installation and frozen public fixtures. Reference engine sources remain unmodified.

## Results of the first milestone

| Check | Result |
| --- | --- |
| Packed configuration / variant generation checks | Passed |
| Existing stage tests | 11 CPU and 11 Metal comparisons, no failures |
| Benchmark-accounting synthetic tests | 16 passed |
| Independent numerical-oracle tests | 9 passed |
| Upstream general/windowed fixtures | 35 cases, 70 frame comparisons passed; maximum linear error `2.86102294921875e-6`, encoded error `0.0015872264048084617` |
| Actual window selection in those fixtures | 27 cases selected a windowed symbol; 8 selected the original general fallback |
| Public stock inputs | 47 non-example stocks × 1080p/4K = 94 independently scaled packs |
| R stock capability probes | 188 successful calls across general/windowed requests; windowed selected for 47/47 at 1080p and 40/47 at 4K |
| Independent R/C fragment matrix | 216 comparisons passed, maximum error zero; 72 real folded-path results and 36 explicitly labelled radius-one fallbacks |
| Same-process fragment lifecycle | 12 A/B/A geometry sequences, 36 calls; changed input/alpha, maximum error zero |

At 4K the upstream selector falls back because spatial reach exceeds its 180-pixel limit:
Agfachrome 100 (203), Astia 100F (259), Double-X 5222 (244), F-64D (237), PRO 160NS (212),
PRO 400H (203), and Provia 100F (233). The diagnostic reach calculation is extracted verbatim
from R's shim; it does not choose or replace the actual runtime variant.

These are correctness and feasibility results. One-call cold times in the capability report
are diagnostics, not warm benchmarks. No B_ref has been selected from them. Device allocation
peaks, process footprint, retained pools, throughput, latency and the PR benefit gate remain
unmeasured.

## What the prototype proves

`wavefront-probe.cpp` calls the existing `GpuSchedule::gpu_gaussian` twice. R builds general
and windowed fragments using its own stage headers. C builds its legacy fragment separately
and a test-only schedule with a 64/128/256-row consumer, 512-row circular storage for the
first horizontal predecessor, and the original per-window storage for other intermediates.
The shared Gaussian expressions and float precision are unchanged.

Host-side realization traces record actual producer regions. Tests require non-overlapping
positive-height intervals for the reused predecessor, compare complete pixels against clean
R general AOT, and verify finite output and exact alpha. For example, at 65×513, radius 3,
band 128, the reused predecessor produces rows `[-3,134)`, `[134,262)`, `[262,390)`,
`[390,516)` and an empty final interval. The halo is retained across bands.

Two limitations were found by executing the prototype:

- Folding every stage preserved pixels but did not eliminate upstream apron recomputation.
  Sliding the final stage introduces bounds selects that Halide cannot prove monotonic for
  its ancestors. A smaller allocation alone is insufficient evidence of wavefront reuse.
- The upstream radius-one shortcut bypasses the horizontal producer and can trigger a fold
  order assertion. The prototype rejects that request before allocating/writing and the
  test controller invokes C's independently built legacy fragment. It is recorded as a
  fallback, never a successful folded-path execution. Failure records and a direct-kernel reproducer trace are retained.

The prototype is a monolithic synchronous AOT call with frame-level completion. It adds no
band cancellation API or persistent cross-frame pool. The lifecycle test alternates geometry
A/B/A and changes input/alpha in the same Metal process, so stale frame state is observable.

The full-film extension must choose a producer that remains active for the exact requested
stages and geometry. In the frozen primary stocks, HP5 Plus has one-pixel MTF radii at both
main sizes and Portra 400 does at 1080p. The fragment's selected horizontal blur cannot simply
be applied to those whole-film requests. Do not count their fallback as full-film E coverage.

## Reproduce

Start with sibling `candidate/` and clean `reference/` checkouts at the frozen base. Run the
following from `candidate/`. Output directories are generated-only; never point them at source
or user data. AOT generation may replace its destination. Only macOS commands are used.

```sh
git submodule update --init --depth 1 third_party/Halide
LLVM_ROOT=/opt/homebrew/opt/llvm@22 LLD_ROOT=/opt/homebrew/opt/lld@22 \
  FOTUFILM_BUILD_JOBS=4 bash tools/build-halide.sh
export HALIDE_ROOT="$PWD/build/halide-install"
python3 tools/generate-config-layout.py --check
python3 tools/generate-aot-variants.py --check
python3 tools/test-wavefront-metrics.py
python3 tools/test-wavefront-compare.py
bash tools/test-stages.sh

FOTUFILM_DISABLE_HALIDE=1 swift build --package-path ../reference \
  -c release --product fotufilm --jobs 4
python3 tools/wavefront-catalog.py --cli ../reference/.build/release/fotufilm \
  --output ../reference/build/wavefront-fixtures/catalog \
  --base-sha 96623ba0831a52dbddcda35727a206d4123a8b5f \
  --size 1920x1080 --size 3840x2160
```

Generate R's AOT from R, using the same `HALIDE_ROOT`:

```sh
cd ../reference
FOTUFILM_AOT_NO_FETCH=1 FOTUFILM_AOT_JOBS=4 \
  bash tools/generate-halide-aot.sh macos build/wavefront-macos
cd ../candidate
python3 tools/verify-wavefront-baseline.py --reference ../reference \
  --kernels ../reference/build/wavefront-macos \
  --pack ../reference/build/wavefront-fixtures/catalog/portra400-1920x1080.fswp
python3 tools/probe-wavefront-catalog.py --reference ../reference \
  --kernels ../reference/build/wavefront-macos \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json
python3 tools/verify-wavefront-probe.py --reference ../reference \
  --halide-root "$HALIDE_ROOT"
```

`wavefront_aot_driver.py` instruments R through external symbol wrappers and an external
fixture driver. R's shim translation unit alone sees symbol aliases; wrappers call the
original archive symbols and report exactly which symbol ran. The original source tree is
not edited. The baseline verifier compares and releases B1 output one frame at a time, preserving both
seeds in the original process. At most three frame dumps coexist. It checks full expected
frame sizes and replaces successful dumps with hashes and comparison records. Failed dumps and
all trace logs remain available.

Evidence lives in `reference/build/wavefront-baseline/verification.json`,
`reference/build/wavefront-stock-probe/capabilities.json`,
`reference/build/wavefront-fixtures/catalog/catalog.json`, and
`candidate/build/wavefront-probe/verification.json`. They retain binary/source hashes and
actual symbols or producer regions. `wavefront-stage1-results.json` is a compact summary.

Next gates are the frozen warm baseline and memory measurement protocol, active-producer
selection for whole-film color/monochrome requests, independent candidate AOT and complete
legacy regression. Final performance acceptance and an upstream PR follow only after those
gates pass.

A later verification attempt encountered a full disk while dumping a 4K frame. Its failure
record, partial lengths and hashes are retained under `reference/build/wavefront-baseline/`
as `disk-full-attempt.*` and `disk-full-artifacts.json`. The lower-occupancy collector was
then validated over the full fixture set; the failed attempt is not a passing measurement.
