# macOS Metal wavefront experiment

This is an opt-in macOS research branch. The first milestone establishes a clean upstream
reference and tests a reusable predecessor in two existing Gaussian stages. The next milestone
adds frozen SDR photographs, independent-process baseline accounting and a private full-film
schedule experiment. The experiment preserves shared film expressions, float precision, stock
data and the original default selector. There is no final performance acceptance or upstream PR.

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

These first-milestone results establish correctness and feasibility. One-call cold times in
the capability report are diagnostics, not warm benchmarks. The later warm baseline is described
below; it does not yet establish a stable B_ref or a passing PR benefit gate.

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

## Photographic corpus and baseline accounting

`tools/wavefront-corpus.json` pins eight official scikit-image sample files at commit
`e8a42ba85aaf5fd9322ef9ca51bc21063b22fcae`, including their registry SHA-256 values,
public-domain/CC0 provenance and source URLs. Coffee is the frozen primary photograph, grass
is the tuning image, and the remaining six are holdouts. These are SDR samples; the coffee
1080p/4K workloads are explicitly upscaled, not native-resolution, RAW or HDR evidence.

`fetch-wavefront-corpus.py` verifies each download. `prepare-wavefront-corpus.py` applies EXIF
orientation, converts embedded profiles to sRGB (or explicitly assumes sRGB when absent), and
writes deterministic canonical PNGs. `wavefront-image-input.swift` decodes those to opaque,
top-left, extended-linear Rec.2020 RGBA Float32 before timing. The manifest records all source,
canonical and float-input hashes. CoreGraphics' internal conversion precision is part of this
common input preparation; both engines receive identical stored floats. Preparation does not
claim to recover HDR content.

The common external `wavefront-benchmark.mm` worker measures synchronous host-buffer calls,
observes actual AOT symbols, counts Metal dispatches and allocations, records device allocation
totals and kernel-maintained current/lifetime-peak process footprint, and checks finite output
and exact alpha. It warms for at least five seconds, uses the fixed 30-second window plus
two-second tail, then observes upstream's unchanged 1 GiB pool after five idle seconds. Fixed
input/seed output hashes must match between warmup and measurement. No decode or file write is
timed. This measures whole-process/resource totals, not yet exact live intermediate bytes.

`run-wavefront-baseline.py` uses fresh processes for Portra 400 / HP5 Plus at 1080p / 4K,
alternates B0/B1, and selects the faster median warm-throughput arm before E performance.
Three further selected-arm runs form three independent B/B pairs. The memory tolerance cap
remains min(4 MiB, 2% of baseline). Invalid rounds, timeouts and failures are retained. Large
throughput drift additionally requires review; it cannot be accepted as a reliable 5% regression
comparison just because thermal state is below serious.

A disk-full interruption left 15 complete rounds and one unfinished attempt. The controller
now saves compact atomic checkpoints after each arm, preserves raw per-request records in
`round.json`/JSONL, checks for at least 2 GiB free before a new process and resumes completed
rounds only when frozen worker, input, pack and statistical-module identities match. A changed
persistence controller is recorded separately. Incomplete attempts are preserved under their
original names, and retry directories are distinct. This does not discard unfavorable rounds or
change the statistical formulas. Disk cleanup was limited to user-approved, regenerable Taggii
Gauntlet build/module/index caches; SourcePackages and test evidence were preserved.

## Warm baseline outcome

All 36 valid R rounds were collected for the four frozen primary cases, including three B/B
pairs per selected arm. Faster provisional medians selected B1 in all four cases, but **B_ref is
not frozen**. Selected-arm warm throughput spans were 41.6%, 41.7%, 112.2% and 32.3% (Portra
1080p/4K, HP5 1080p/4K). Portra 4K's paired process-peak variation was 50,593,792 bytes, exceeding
the unchanged 4 MiB tolerance cap. These data cannot establish a 5% performance nonregression.
Thermal state 0–1 did not make this memory-pressure environment stable. Adverse and interrupted
attempts remain preserved. No E warm score or upstream PR is claimed.

The complete report is `build/wavefront-benchmark/formal/ddea1b871480/report.json`; the compact
committed record is `wavefront-stage2-results.json`. Its measurement worker and source hashes
remain the original v1 identities. Supporting multipass E required the common worker to allow
more than one AOT call. The R controller still requires exactly one. A separately rebuilt clean
R v2 worker and `build/wavefront-corpus/frozen-verification-v2.json` are used for correctness.
They do not retroactively change the old warm results. A future performance run must rebuild
both workers from the same current measurement source and collect a new baseline.

## Private complete-film experiment

The first full-film attempt used Halide `fold_storage` on the ungated pre-MTF light producer.
Pixels passed, but actual production of a 1080-row image totalled 1535 rows, with repeated
intervals `[0,313)`, `[199,569)`, `[455,825)`, `[711,1080)` and `[967,1080)`. Fixed full-frame
bounds did not resolve the overlap. The pinned Halide compiler could not prove monotonic
movement through float resampling and dynamic stride expressions. This route was rejected.
The frozen C control, source snapshot, binaries and failure traces remain under
`build/wavefront-schedule-control/`, `build/wavefront-candidate/a01ca4b42f2a/` and
`build/wavefront-schedule-probe/f4b42a43745e/`. They are diagnostics, not final candidate gates.

The selected implementation makes the producer/consumer order explicit. It captures the
**original shared graph expression** at pre-MTF light and compiles it as a private source
kernel. Nine consumers use 64/128/256-row bands for exact color PRINTED_NEGATIVE /
PRINTED_NEGATIVE_LUMA and monochrome PRINTED_SLIDE. Three source kernels share those classes.
Other stages keep their original per-window intermediates and still recompute their aprons.
Film mathematics, LUTs, stock data and Float32 precision remain unchanged.

Each synchronous call owns a 1024-row planar Float32 light cache, logical row labels and a
completion marker. The cache lives behind an aligned private configuration prefix in one
shared Metal allocation; it has no duplicate full-size host field. A consumer band uses a
conservative ±360-row source envelope. Its source interval is produced monotonically exactly
once, split only at physical cache wrap. Before overwriting a slot, the shim requires its last
possible consumer band to have completed. It synchronizes the GPU after every consumer and
drains submitted commands on success or error before releasing any buffer views. These
conservative synchronization costs must be included in future performance results. There is
no new cancellation control or band cancellation promise: the public contract remains a
synchronous whole-frame call, with no state retained for the next frame.

Admission also bounds the full serial source demand, rather than borrowing the upstream
performance selector's maximum-of-arms estimate. The conservative sum includes MTF, resampled
halation boxes, coupler/adjacency/fringe, grain and print reach. It must fit 360 rows in addition
to the existing 180-pixel window eligibility contract. The frozen Portra 1080p/4K source bounds
are 125/247; HP5 bounds are 147/294. Unsupported classes, exact stages, geometry, transport,
measurement modes, reach or band select the original legacy pipeline before output writes.
An admitted submission failure is returned after draining, with no legacy retry over partial
output.

`WavefrontSchedule` defaults to no experimental route. Build-time `FOTUFILM_AOT_WAVEFRONT=1`
adds twelve private kernels after every legacy tag, for 58 frame variants and 75 archives total.
The flag and generator inputs enter the source identity, preventing public-cache/release
substitution. Default generation and legacy selector order remain unchanged. The private
`FotufilmHalideWavefront.h` entry point takes explicit per-call options and reports actual mode,
fallback reason, production/consumption counts and drain status. Existing public entry points
pass no options. No global or thread-local runtime wavefront mode is introduced.

`wavefront-benchmark-adapter.cpp` routes only C's external worker to this entry point. The
common R/C measurement source stays identical. Trace kernels, enabled separately by
`FOTUFILM_AOT_WAVEFRONT_TRACE=1`, log actual source realization regions. A test-only Metal
observer records command-buffer GPU start/end times and completion status. `wavefront_trace.py`
requires contiguous source production `[0,H)` once, physical wrap consistency, all consumer
completion markers and prior-consumer GPU completion before subsequent source submission.
A smaller allocation or a fallback never counts as E reuse evidence.

The diagnostic four-case × three-band matrix passed pixels, source intervals and GPU completion
checks (`build/wavefront-managed/96815c42f25c/verification.json`). That iteration combined a
frozen C legacy control with new experimental kernels and explicitly records mixed candidate
revisions. It is not final-build or performance acceptance. Final verification requires the
complete candidate archive set to be rebuilt from one current source/configuration identity.

## Final AOT correctness results

The complete current-source macOS set finished with 58 frame variants and 75 archives. Its
source/configuration identity and helper/archive count passed; traced overrides share the
current generator inputs. The final matrix links one C revision, without the frozen old C
control. The compact record is `wavefront-stage3-results.json`.

| Check | Result |
| --- | --- |
| Four primary cases × three bands | 12 pixel/reuse/GPU-completion comparisons passed; maximum linear error `2.562999725341797e-6` |
| Non-traced E, four primary cases × three bands | 12 passed; source/consumer counts and actual private admission checked; normal and traced outputs independently meet the same clean-R pixel tolerance |
| Every legacy AOT class against clean R | 36 classes passed at zero tolerance; all complete output records byte-identical and nonconstant |
| C general/windowed against clean R primary cases | 8 comparisons passed, maximum linear error `2.562999725341797e-6` |
| Same-process lifecycle against clean R | 14 frames passed, maximum linear error `2.7915591155336372e-6`; includes cache-channel changes, encoded output, fallback, four invalid-option checks, injected submission failure and recovery |
| All frozen stock/size probes | 94 successful calls; E selected for 16/47 at 1080p and 17/47 at 4K; 61 explicit original-path fallbacks |
| Current stage tests | 11 CPU and 11 Metal passed |
| Release test build | Passed; skipped execution is not counted as a passing runtime test |
| Swift Metal runtime / AOT-JIT parity | 3/4 Swift tests passed; 32 zero-tolerance texture-none assertions failed by about `4e-9`, clean-R reproduction running; AOT/JIT parity running |

Fallback reasons comprise 54 unsupported exact-stage/class/warp combinations, two original
geometry/transport/spatial exclusions and five private serial-demand bound exclusions. Catalog
probes check actual symbols, counts, finite pixels and alpha; only the named primary/lifecycle
matrices establish full-pixel R/C agreement. These results do not establish memory or throughput
acceptance. No final B_ref or upstream PR is implied.

## Candidate verification commands

From `candidate/`, after the reference and frozen fixture steps above:

```sh
export HALIDE_ROOT="$PWD/build/halide-install"
export FOTUFILM_AOT_WAVEFRONT=1
python3 tools/fetch-wavefront-corpus.py --output build/wavefront-corpus/sources
mkdir -p build/wavefront-corpus
swiftc -O tools/wavefront-image-input.swift -o build/wavefront-corpus/prepare-image
python3 tools/prepare-wavefront-corpus.py --sources build/wavefront-corpus/sources \
  --output build/wavefront-corpus --converter build/wavefront-corpus/prepare-image
# These flags freeze correctness inputs without warm timing.
python3 tools/prepare-wavefront-verification.py --reference ../reference \
  --reference-kernels ../reference/build/wavefront-macos \
  --worker-output ../reference/build/wavefront-verification-v2/instrumented \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json \
  --prepared build/wavefront-corpus/prepared.json \
  --output build/wavefront-verification/frozen-cases.json
export WAVEFRONT_CASES="$PWD/build/wavefront-verification/frozen-cases.json"
export WAVEFRONT_R_WORKER="$PWD/../reference/build/wavefront-verification-v2/instrumented/runner"
FOTUFILM_AOT_NO_FETCH=1 FOTUFILM_AOT_JOBS=2 \
  bash tools/generate-halide-aot.sh macos build/wavefront-macos
FOTUFILM_AOT_JOBS=2 bash tools/generate-wavefront-trace.sh
python3 tools/verify-wavefront-managed.py --kernels build/wavefront-macos \
  --trace-kernels build/wavefront-explicit-kernels \
  --frozen-cases "$WAVEFRONT_CASES" \
  --reference-worker "$WAVEFRONT_R_WORKER"
python3 tools/verify-wavefront-candidate.py --reference ../reference \
  --kernels build/wavefront-macos \
  --frozen-cases "$WAVEFRONT_CASES" \
  --reference-worker "$WAVEFRONT_R_WORKER"
mkdir -p build/wavefront-compatibility-fixture
../reference/.build/release/fotufilm --dump-wasm-pack \
  build/wavefront-compatibility-fixture/example-negative-400-384x216.fswp \
  --stock example-negative-400 --pack-size 384x216
python3 tools/verify-wavefront-legacy-aot.py --reference ../reference \
  --reference-kernels ../reference/build/wavefront-macos --kernels build/wavefront-macos \
  --pack build/wavefront-compatibility-fixture/example-negative-400-384x216.fswp
python3 tools/verify-wavefront-lifecycle.py --reference ../reference \
  --reference-kernels ../reference/build/wavefront-macos --kernels build/wavefront-macos \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json
python3 tools/probe-wavefront-catalog.py --candidate-experiment --reference . \
  --kernels build/wavefront-macos \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json
```

The managed verifier checks all four main cases and three bands against clean R. The candidate
verifier independently checks C general/windowed and all three non-traced E bands against R. The lifecycle verifier keeps each
engine in one process across changed stocks, odd geometry, input, seed, alpha, gate, stage mask,
still/exact, band and legacy requests. It also checks invalid private options, negative/HDR
floats, encoded output, conservative reach fallback, and a test-only source-submission failure
followed by successful recovery. Injection is compiled only into its test shim. Catalog probes
report actual E or fallback for every frozen stock/size, not a numerical or performance score.

Release Swift build/tests and `tools/verify-aot-parity.sh` remain required. The parity harness
can use `FOTUFILM_PARITY_STREAM_WINDOWS=1` to compare and release each window output instead of
retaining all frame dumps. Final artifacts and reports stay generated-only. Do not mix traced
kernels into timed workers or treat the rejected auto-fold control as the current candidate.

## Formal B/E collector

`run-wavefront-comparison.py` requires a complete frozen clean-R baseline, current Mac/OS/boot/
toolchain identity, unchanged common measurement/statistical sources, the exact non-traced
worker from the successful pixel verification, and matching fixture hashes. It rejects the
old unstable v1 report before creating any E run. The shared round collector keeps R at exactly
one AOT call and validates E's first-call private admission, full source-row coverage, consumer
band count and the same observed AOT count on every warmup/measurement call. A non-success call
in either phase invalidates the round. These policy tests are synthetic; they claim no GPU or
performance coverage.

First collect a new v2 baseline after integration tests finish and resource pressure settles:

```sh
python3 tools/run-wavefront-baseline.py --reference ../reference \
  --worker "$WAVEFRONT_R_WORKER" --prepared build/wavefront-corpus/prepared.json \
  --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json \
  --output build/wavefront-benchmark-v2/formal
```

Only if its report has `B_ref_frozen: true`, use the band already frozen by the separate tuning
workload. The following command uses variables for that report, the successful normal-pixel
report, and its `band-N/runner`; do not choose N from the primary Coffee scores:

```sh
python3 tools/run-wavefront-comparison.py --reference ../reference \
  --reference-worker "$WAVEFRONT_R_WORKER" --worker "$WAVEFRONT_E_WORKER" \
  --baseline-report "$WAVEFRONT_BASELINE_REPORT" \
  --normal-verification "$WAVEFRONT_NORMAL_REPORT" \
  --verification-fixtures "$WAVEFRONT_CASES" --band "$WAVEFRONT_BAND" \
  --output build/wavefront-comparison
```

Each case collects three independent B/E pairs in B/E, E/B, B/E order, preserving all records
and failures. Resume requires the same frozen identities; invalid completed rounds cannot be
replaced. The collector checkpoints before another worker when fewer than 2 GiB are free, and
records per-arm system load, swap, memory-pressure and disk observations. It reports median
latency (+5%), worst-round p95 (+10%), median throughput (at least 95%) and pairwise total-memory
changes against the **unchanged** B/B epsilon. Matched-R drift/noise or thermal state at serious
requires review. A primary pass is not final performance acceptance: tuning/holdouts, local
intermediate attribution, same-process resource rotation and PR review remain separate gates.
