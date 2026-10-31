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
| Swift Metal runtime | 3/4 passed; the untouched texture-none test fails identically at 32 components in clean R and C (maximum `5.587935447692871e-9`); no introduced failure observed, suite remains red |
| AOT/JIT compatibility | 36 classes passed, worst noncategorical error `1.57356262e-5`, using the upstream `1e-4`/four-code budget |
| C general/windowed boundary regression | 35 cases / 70 comparisons passed, including odd/tail/portrait, gates and reach fallbacks |

Fallback reasons comprise 54 unsupported exact-stage/class/warp combinations, two original
geometry/transport/spatial exclusions and five private serial-demand bound exclusions. Catalog
probes check actual symbols, counts, finite pixels and alpha; only the named primary/lifecycle
matrices establish full-pixel R/C agreement. These results do not establish memory or throughput
acceptance. The reference reproduction uses a separate release build and fresh JIT cache; source
remains clean. No test or tolerance was changed to hide its zero-tolerance failure. A fresh awake-controlled v2 clean-R baseline completed 36 valid rounds after all compilation
jobs completed, but failed the unchanged stability gates described below. No final B_ref or
upstream PR is implied.

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

Release Swift build and `tools/verify-aot-parity.sh` completed. The selected Swift Metal suite retains the identical clean-R texture-none precision failure described above. The parity harness
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

The first new v2 attempt stopped after four rounds (three valid, one invalid): request 1306
crossed a system Dark Wake thermal-emergency sleep and took about 925.4 seconds, beyond the
unchanged two-second tail. `pmset` recorded the matching sleep/wake interval; thermal state was
critical during the stalled request and nominal after full wake. The invalid round and power
evidence remain preserved under `build/wavefront-benchmark-v2/formal/0a70c5539006/` and
`build/wavefront-v2-sleep-events.log`. It was not converted into a valid score or resumed over.

Both collection CLIs now hold a controller-scoped `caffeinate -i -w PID` assertion and verify
that it remains active before each worker. It prevents idle system sleep without changing
display policy or overriding explicit user sleep, and releases automatically on controller exit.
The assertion's creation/release was tested directly.

## Awake clean-R baseline result

The fresh run at `build/wavefront-benchmark-v2/awake/0c2977588b8c/` completed all 36 rounds
without an invalid round. Each primary has three rounds of each original arm plus three more
of the provisionally selected arm, producing three B/B pairs. This is original-engine
calibration, not E speedup evidence.

| Case | Provisional original arm | Throughput range drift | B/B memory noise |
| --- | --- | --- | --- |
| Portra 1080p | B1 | 6.35% | pass |
| Portra 4K | B1 | 10.29% | pass |
| HP5 1080p | B1 | 12.23% | pass |
| HP5 4K | B1 | 10.41% | pass |

The unchanged timing range review threshold is 5%; B/B memory epsilon and its original caps
remain unchanged. `B_ref_frozen` is false. No samples were discarded and no E performance
round was started. See [stage-four summary](wavefront-stage4-results.json) for raw report/worker
hashes, every original arm's rates, epsilon, thermal and environment observations. These results
do not identify the cause of the remaining timing variation. A reliable clean-R baseline,
separate band tuning, paired E/holdout measurements, local intermediate attribution and
same-process resource rotation remain required before the PR benefit gate.

## Stability diagnosis after the awake campaign

The preserved 36-round analysis recomputes the original scores from every request and
partitions each 30-second window into synchronous API envelopes and their complement.
Outside-API time accounts for at most 0.250% of a window. Actual variants and dispatch counts
are constant within each arm. All 1080p measurement calls allocate zero new observed Metal
buffers; some original 4K arms still allocate each call. These observations narrow the scope,
but neither allocation counts nor pre-round load establish the cause of timing variation.

Two six-round fixed Portra 1080p B1 campaigns used the exact original R worker and unchanged
5/30/2-second protocol, single in-flight frame and 1 GiB pool:

| Control | Six-round FPS range drift | B/B memory noise | Frozen B_ref |
| --- | --- | --- | --- |
| Before closing the system storage page | 8.33% | pass | no |
| After the user closed the page | 12.23% | pass | no |

The storage helper processes exited after the page closed. Spotlight processes remained;
process snapshots are context, not proof of a GPU interference cause. The sixth post-close
sample was 119.93 FPS and remains in the result. Neither campaign passes the unchanged 5%
range gate. A small diagnostic cannot freeze the four-case reference even when it passes.

A **separate instrumented R worker** was built from the original R AOT and the unchanged
common driver, with `wavefront-timing-adapter.mm` substituted only at the driver's API call.
Its cold verification output matches the original R byte for byte. Six warm diagnostic rounds
joined all 24,967 observed request IDs, including 21,179 measurement requests, to CPU/wait/GPU
records. Each measured call has 44 observed completed/timestamped command buffers, three
`waitUntilCompleted` calls and one observed queue. Raw GPU intervals are preserved and their
union is independently checked; overlapping command-buffer intervals are not simply added.

| Diagnostic component | Range of round means | Range drift |
| --- | --- | --- |
| Real R API wall time inside the adapter | 7.48–9.59 ms | 28.23% |
| Main-thread CPU time | 1.64–1.73 ms | 5.12% |
| Process CPU time | 2.79–2.99 ms | 7.27% |
| Observed Metal wait wall time | 1.68–2.32 ms | 37.83% |
| GPU command-buffer interval union | 5.52–7.61 ms | 37.94% |

These times **overlap** and must not be summed as disjoint costs. GPU envelopes include
scheduling/preemption effects and are not hardware utilization or a clock-frequency reading.
Callbacks and raw diagnostic logging perturb scheduling; their FPS and variation cannot
replace unmodified-worker scores. The evidence points toward GPU-timeline variability in
the diagnostic reproduction, without proving GPU frequency, another GPU client or shared
memory pressure as the cause. Coarse thermal state 0 alone does not guarantee stable timing.
A bounded `sudo -n powermetrics` availability check required local administrator authentication;
no GPU power/frequency samples were obtained and no system settings were changed.

Reproduce the offline analysis and fixed-arm diagnosis from `candidate/`:

```sh
python3 tools/test-wavefront-stability.py
python3 tools/analyze-wavefront-stability.py --report "$WAVEFRONT_BASELINE_REPORT" \
  --output build/wavefront-stability-analysis/new-analysis
python3 tools/run-wavefront-stability.py --source-report "$WAVEFRONT_BASELINE_REPORT" \
  --reference ../reference --worker "$WAVEFRONT_R_WORKER" \
  --case portra400-coffee-1920x1080 --mode B1 --output build/wavefront-stability-fixed
# FIXED_REPORT is the resulting complete fixed-arm diagnostic report.
python3 tools/run-wavefront-timing.py --reference ../reference \
  --kernels ../reference/build/wavefront-macos --source-report "$FIXED_REPORT" \
  --output build/wavefront-stability-timing
```

The 20 synthetic tests validate interval clipping/union, score integrity, request coverage,
completion status and gating. See [stage-five results](wavefront-stage5-results.json) for
source/worker/report hashes and every preserved campaign. No E performance round or upstream
PR was started. A quiet reference environment and/or authorized GPU telemetry is needed to
continue the stability investigation before the formal four-case baseline.

## Simulator-off control

Runtime checks confirmed no booted simulator. Docker Desktop and a virtual-machine process
remained; Docker version/container/stats queries each timed out after 12 seconds, and a direct
local-socket ping timed out after three seconds before and after collection. These observations
do not quantify Docker's GPU or container workload.

Six fixed Portra 1080p B1 rounds using the original R worker returned 90.33, 85.03, 136.07,
130.60, 98.20 and 104.00 FPS. All rounds were valid and B/B memory noise passed, but the range
was 60.02%, above the unchanged 5% gate. Simulator was off at the before/after checks and its
launchd was absent in the middle snapshot. Docker was not shut down. Closing Simulator did
not stabilize this campaign; it neither proves Docker is the cause nor rules out a simulator
contribution to earlier measurements.

[Stage-six results](wavefront-stage6-results.json) preserve input/worker identity, every raw-round
hash and service-query evidence. A Docker-fully-off control remains unmeasured. No formal B_ref,
E score or PR was produced.

## Count-based resource attribution and rotation

The resource campaign is independent of the unstable timing baseline. It ran with Docker
left running and reused the normal R-63/C-75 AOT sets. The production shim, schedules,
physics, stock data and default entry points were unchanged in this stage. Optional external
builder hooks create a diagnostic shim copy; default builder calls retain their prior wrappers.

Four primary cases each ran six fresh processes per original arm and three per E band
(64/128/256): 84 light processes, six calls each. Calls 1–3 cover cold/warmup, calls 4–6
supply the warm device peak, while process-lifetime peaks include cold initialization.
Separate detailed workers ran three calls for each of 20 profiles. This count-based protocol
is **not** the formal five-second warmup / thirty-second timing protocol and produces no E
latency or FPS score. Old timing reports supply only frozen pixel hashes; all memory epsilon
values were measured anew from three R/R pairs with unchanged caps.

Light workers supply Metal device totals and process physical footprint. Detailed workers
record unique physical buffer objects, logical rentals/views, AOT argument roles, GPU fence
completion and read-only pool snapshots. They supply attribution and lifecycle validation;
their observer memory is excluded from R/C footprint comparisons. Interval sweeps compute
coincident working peaks. Category maxima must not be added. GPU-safe intervals are
conservative bounds ending at CPU observations of completion, not GPU-clock allocation
lifetimes. The logical working domain includes per-call AOT intermediates plus the frontier
and configuration, including downsampled intermediates; it is not a named-edge spatial-local
breakdown and does not establish the formal 25% local-memory benefit gate.

| Case | R-B0 device MiB | R-B1 device MiB | E64 / E128 / E256 device MiB | R-B1 logical working MiB | E64 / E128 / E256 logical working MiB |
| --- | --- | --- | --- | --- | --- |
| Portra 1080p | 462.25 | 334.28 | 144.83 / 168.56 / 197.78 | 142.44 | 31.52 / 39.96 / 56.84 |
| Portra 4K | 1734.25 | 1183.72 | 685.59 / 702.77 / 809.50 | 250.02 | 106.77 / 117.08 / 137.70 |
| HP5 1080p | 482.78 | 274.81 | 131.88 / 156.11 / 176.66 | 102.88 | 29.17 / 35.26 / 47.45 |
| HP5 4K | 1574.38 | 667.72 | 411.25 / 435.14 / 471.73 | 170.89 | 65.01 / 70.90 / 86.89 |

Device columns are the maximum observed light-worker warm peak for each arm; the raw summary
retains every round, cold peaks, process-lifetime peaks and both original comparators.
Relative to the named R-B1 arm, E device peaks fall approximately 29–57% and logical working
peaks 45–78%. R-B1 is not a frozen B_ref. Portra 4K process-lifetime R/R epsilon exceeds 4 MiB
for both B0 (11.58 MiB) and B1 (95.39 MiB); their lower observed C process peaks cannot pass
an uncalibrated gate. Device-total calibration is stable in every primary profile.

The frozen eight-step rotation changes Coffee/Grass, stock, resolution, RGB/luma class and
band; it includes legacy, unsupported-band fallback and A again. Each process runs two
contexts, each with two cycles (32 frames; C has 20 actual E frames). R-B0/R-B1 run their own
legacy sequence; C runs its legacy/E mixture. Eight full clean-R/C oracle comparisons pass
(max linear error 2.802e-6, finite output and exact alpha); resource frames additionally match
frozen own-arm output hashes. All 23 detailed processes classify their Halide rentals,
return frame intermediates/frontier after API/drain, and respect the original idle-pool budget.

Natural idle waits five seconds without releasing the pool. Explicit cleanup separately
destroys the context, releases the pool and waits five seconds. All detailed rotation cleanup
pool snapshots are empty; light-worker device residual is 1,785,856 bytes for R and C, so this
does not imply zero total device allocation. Natural idle can retain close to the original
1 GiB pool budget and single-case savings do not fully carry through mixed cache histories.

A separate repeat of the unchanged light rotation (six R-B1 processes, three C processes)
calibrates every phase. Natural-idle R/R device/footprint epsilon is 8–31 MiB, above the 4 MiB
cap: these comparisons remain **unassessed**, rather than demonstrating a C regression.
After explicit cleanup, R footprint calibration is stable, but maximum C minus minimum R is
6.438 MiB after frame 16 (epsilon 0.234 MiB) and 6.063 MiB after frame 32 (epsilon 2.562 MiB).
Both exceed measured epsilon. Cleanup device totals match exactly. The remaining process
footprint has not been attributed; these observations do not identify a leak or a specific
host/Metal cache. Full retained-memory nonregression has **not passed**.

Dispatch cost also needs work: Portra 1080p steady frames issue 41 dispatches in R-B1 versus
693/367/204 in E64/E128/E256; at 4K the counts are 77 versus 1629/816/433. This is a resource
tradeoff, not measured speedup or slowdown. No E timing was collected. The next engineering
investigation can attribute post-cleanup footprint and reduce repeated band dispatches;
formal baseline, separate tuning/holdouts and PR gates remain open.

Reproduce from `candidate/`, after generating the prior normal AOT, public corpus and
verification inputs described above (paths below identify this preserved cohort):

```sh
python3 tools/test-wavefront-resources.py
python3 tools/verify-wavefront-resources.py --reference ../reference \
  --reference-kernels ../reference/build/wavefront-macos --kernels build/wavefront-macos \
  --frozen-cases build/wavefront-corpus/frozen-verification-v2.json \
  --normal-verification build/wavefront-candidate/9baf1b6d6b30/verification.json \
  --baseline-report build/wavefront-benchmark-v2/awake/0c2977588b8c/report.json \
  --prepared build/wavefront-corpus/prepared.json --converter build/wavefront-corpus/prepare-image \
  --output build/wavefront-resource-campaign
# RESOURCE_REPORT and RESOURCE_WORKERS identify the newly printed report and workers.json.
python3 tools/summarize-wavefront-resources.py --report "$RESOURCE_REPORT" \
  --output build/wavefront-resource-summary/new-summary
python3 tools/calibrate-wavefront-resource-rotation.py --source-report "$RESOURCE_REPORT" \
  --workers "$RESOURCE_WORKERS" --output build/wavefront-resource-rotation-calibration
```

Thirteen synthetic tests pass, including interval/fence/alias checks, caps, cold-peak inclusion
and default-builder isolation. The campaign preserves source snapshots, four worker hashes,
raw traces, process records and unfavorable results. [Stage-seven results](wavefront-stage7-results.json)
contains the source/worker identities and artifact hashes for 119 recorded resource processes.
No production AOT was regenerated in this stage; no branch was pushed or upstream PR created.


## First R/E latency diagnostic

This first latency diagnostic measures R/E while the formal reference remains unfrozen.
A separate diagnostic controller reuses the unchanged, already pixel-verified normal R and
E64/E128/E256 workers. It does not change the formal collector's stable-B_ref requirement.
Four primary cases each run three adjacent pairs: R/E64, E128/R, R/E256. Each arm is a fresh
process with five-second warmup, thirty-second measurement, two-second tail and five-second
retained idle; the original 1 GiB pool and one in-flight frame are unchanged. Docker stays running.
Each E band/case has one measurement window; this does not estimate E between-round variance.

All 24 rounds passed accounting, successful real variant/GPU execution and own-arm output
hash checks. The timings cover the synchronous API (upload, compute, waits and readback),
excluding image decoding/file writes/application presentation. They use the identical lightweight
counters in both arms; detailed resource observers are absent. Old baseline records supply only
pixel hashes. Median and nearest-rank p95 are per-request; window FPS is independently counted.

| Case | R controls median range ms | E64 median / p95 ms | E128 median / p95 ms | E256 median / p95 ms |
| --- | --- | --- | --- | --- |
| Portra 1080p | 7.07–7.47 | 25.00 / 47.92 | 15.04 / 31.77 | 17.36 / 31.19 |
| Portra 4K | 42.22–49.14 | 93.09 / 136.83 | 69.98 / 101.86 | 58.45 / 81.71 |
| HP5 1080p | 8.24–9.49 | 21.86 / 53.60 | 13.79 / 24.86 | 10.89 / 12.21 |
| HP5 4K | 23.67–24.68 | 57.52 / 60.56 | 38.72 / 40.91 | 30.90 / 32.84 |

| Case | E64 / adjacent R | E128 / adjacent R | E256 / adjacent R | R median range drift |
| --- | --- | --- | --- | --- |
| Portra 1080p | 3.54× | 2.12× | 2.32× | 5.67% |
| Portra 4K | 1.89× | 1.66× | 1.30× | 16.40% |
| HP5 1080p | 2.65× | 1.45× | 1.19× | 15.09% |
| HP5 4K | 2.33× | 1.63× | 1.31× | 4.27% |

Every ratio uses its adjacent original R control, not a frozen B_ref or a shared selected R
score. Larger bands were not uniformly faster in these observations. No band is selected from
the primary cases. Preserve the reference drift, p95 tails and all rounds: these are diagnostic
results, not a formal speed/PR pass. The stage-seven cleanup-footprint failure remains open.

```sh
python3 tools/test-wavefront-latency-diagnostic.py
python3 tools/test-wavefront-metrics.py
python3 tools/test-wavefront-comparison.py
python3 tools/run-wavefront-latency-diagnostic.py --reference ../reference \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --verification build/wavefront-candidate/9baf1b6d6b30/verification.json \
  --baseline-report build/wavefront-benchmark-v2/awake/0c2977588b8c/report.json \
  --output build/wavefront-latency-diagnostic
```

Five diagnostic aggregation tests, 16 existing metric-accounting tests and 27 existing
comparison/gating tests pass. [Stage-eight results](wavefront-stage8-results.json) preserve
the exact workers/sources, all 24 raw-round hashes, environment and observed comparisons.
No production code or AOT was changed, no branch pushed and no upstream PR created.


## Isolated 512-row diagnostic

The original windowed path uses 1080-row windows. The research path now admits 512 rows;
512 plus both conservative 360-row margins needs 1232 live rows, so its prior 1024-row
cache is insufficient. The experimental cache is 2048 rows, protected by a compile-time
capacity assertion and the existing live-label/GPU-drain checks. Both fresh E256 and E512
controls use this same cache. Historical 1024-row scores are a separate cohort.

A broad 78-archive rebuild and selected Swift Metal JIT tests were interrupted by the
controller after excessive unmodified-legacy compilation; CPU samples and partial outputs
remain. They are not counted as numerical failures or passes. CPU/Metal stage tests each
passed 11 checks and the release Swift build passed. Full current-source release AOT,
release parity and completion of the selected Swift suite remain required before release.

The measured composite reuses 63 frozen, verified legacy archives and builds all 15 current
wavefront archives (plus six independent trace overrides). Shared stage/graph sources match
the frozen control. Default builder source-fingerprint checks remain strict; this explicit
diagnostic route records both component identities. Formal comparison rejects mixed-revision
diagnostics even if a future reference is stable. No release/PR acceptance is implied.

Twenty-four normal pixel comparisons, four traced 512 cases and fourteen lifecycle frames
pass. Invalid-option checks and injected source submission failure/drain/recovery pass too.
The current band uses real 512 consumers, including the RGB+luma lifecycle case; full-frame
comparison includes strip seams. A separate timing campaign uses R/E256, E512/R for each
primary case, 5/30/2/5-second warm/window/tail/idle, fresh processes and one in-flight frame.

**The original Portra 1080p E256 row below overlaps controller cache deletion. See the explicit clean follow-up below; this original case is retained, not used as the primary displayed comparison.**

| Case | R median range ms | E256 median / p95 ms | E512 median / p95 ms | E512 median reduction vs E256 |
| --- | --- | --- | --- | --- |
| Portra 1080p | 7.50–9.69 | 11.45 / 12.18 | 10.12 / 10.97 | 11.6% |
| Portra 4K | 38.85–50.68 | 56.14 / 73.19 | 52.76 / 73.32 | 6.0% |
| HP5 1080p | 6.61–6.71 | 9.09 / 9.99 | 7.99 / 8.88 | 12.1% |
| HP5 4K | 21.68–27.03 | 31.83 / 37.31 | 28.77 / 40.02 | 9.6% |

| Case | E256 / E512 dispatches | E256 / E512 device peak MiB | E512 new buffers / measured call |
| --- | --- | --- | --- |
| Portra 1080p | [203] / [122] | 221.8 / 302.4 | [0] |
| Portra 4K | [432] / [240] | 873.5 / 1181.2 | [6, 7] |
| HP5 1080p | [163] / [98] | 200.7 / 265.9 | [0] |
| HP5 4K | [306] / [170] | 519.7 / 611.7 | [0] |

These are per-request median/p95 observations; FPS is independently counted. Every E band
has one window, R has two controls per case, and R still drifts. Device peaks include cold
initialization and are not calibrated total-memory acceptance. Lower observed E512 medians
do not establish a stable speedup or authorize band selection on these primary inputs.

Rebuild the isolated components with the previously preserved 75-archive control and its
normal proof (the old source ref is explicit):

```sh
python3 tools/prepare-wavefront-wide-diagnostic.py --control-kernels build/wavefront-macos \
  --control-proof build/wavefront-candidate/9baf1b6d6b30/verification.json \
  --control-ref deacc05 --halide-root build/halide-install --output build/wavefront-wide-reproduction
```

Use its `control/kernels`, `kernels` and `trace-kernels` in the existing verifiers with
`--diagnostic-control`, `--diagnostic-kernels`, and (for traced checks) `--trace-kernels`.
The lifecycle verifier takes `--band 512`; the latency diagnostic takes `--bands 256,512`
and the newly produced normal verification report. It cannot enter the formal collector.
[Stage-nine results](wavefront-stage9-results.json) preserve every component/worker/source
identity, all 16 timing rounds, interruptions, cleanup manifests and validation reports.
No branch was pushed and no upstream PR created.


### Known controller interference and explicit reverse-order follow-up

Own cache deletion overlapped the first Portra 1080p E256 measurement, about 16.8 seconds
after its environment observation and 23.3 seconds before the worker finished. That original
case is retained and marked environmentally contaminated; protocol accounting remains valid.
A separately recorded R/E512, E256/R follow-up repeats only the affected case with the same
frozen workers, input and 5/30/2/5 protocol, with no concurrent compilation or cache cleanup.
It does not replace a source round. The table below labels each row's source; it is a display
of separate diagnostic observations, not pooled formal acceptance. All 20 protocol-valid rounds
remain preserved. The single-window and R-drift limitations still apply.

| Case / source | R median range ms | E256 median / p95 ms | E512 median / p95 ms | E512 median reduction vs E256 |
| --- | --- | --- | --- | --- |
| Portra 1080p（clean reverse-order follow-up） | 7.67–11.56 | 11.51 / 13.21 | 10.09 / 11.05 | 12.4% |
| Portra 4K（original） | 38.85–50.68 | 56.14 / 73.19 | 52.76 / 73.32 | 6.0% |
| HP5 1080p（original） | 6.61–6.71 | 9.09 / 9.99 | 7.99 / 8.88 | 12.1% |
| HP5 4K（original） | 21.68–27.03 | 31.83 / 37.31 | 28.77 / 40.02 | 9.6% |


## Post-MTF frontier diagnostic (stage ten)

The private frontier now captures the original final MTF-selected RGB float value.
Region blur policy preserves the applicable Metal optimizations without adding a
producer window loop. Consumer bands remain 512 and the row cache remains 2048
for this comparison. The default legacy selector is unchanged.

The new private AOTs pass 24 normal pixel comparisons, four actual kernel/reuse
traces and 14 lifecycle frames. Portra UHD MTF result coverage drops from 3056 to
2160 rows. Six active pre-cut 512 archives were rebuilt from 339e78e and match
the original bytes. Root traces also establish repeated per-band curve/weight/CDF
table construction. A realization event is not necessarily an executed kernel;
kernel binding names/counts confirm the radius-one fused path remains active.

Eight pre/post diagnostic rounds contain 15,396 measurement calls, one pair per
case, 5/30/2/5 protocol, same API/pool/waits. Median ms pre → post:
Portra HD 9.26 → 9.37, Portra UHD 51.07 → 36.74, HP5 HD 10.25 → 10.01,
HP5 UHD 26.41 → 26.78. Device peak MiB pre → post: 302.4 → 322.9,
1181.2 → 1084.2, 265.9 → 286.1, 611.7 → 627.7. Only the Portra UHD pair is
favorable on both measures; all adverse results are retained. Single pairs,
thermal states 0/1 and unfrozen R preclude a stable causal or PR benefit claim.

Retain this as research, not a release promotion. The initial producer batch is
872 rows despite the 512-row consumer band. Isolate a producer batch cap next,
counting additional source/table dispatches and complete memory; no such cap is
implemented yet. Do that before table or halation extraction. Formal reference,
retention, full same-source 78 AOT/release parity and broader Swift checks remain
pending. The release build passes; the focused Swift test bundle builds but the
test was interrupted during Halide IR JIT, with logs/sample retained.

[Stage-ten results](wavefront-stage10-results.md), [machine-readable evidence](wavefront-stage10-results.json)
and [edge contract](wavefront-post-mtf-contract.md) record all identities and
limitations. Disk pressure stopped the first timing attempt before any score.
Historical C workers and inactive temporary Metal sources were losslessly
archived, hash-verified and journaled; raw reports, AOT and current workers remain.
Restore an old worker with
`python3 build/wavefront-post-mtf/archived-workers/restore.py <path-substring>`.
Cleanup ended before measurement; no concurrent compiler or cleanup ran in the
successful campaign. The assistant did not quit Docker, push or create a PR.


## Stage eleven: opt-in three-stage LogExposure control

At the user's request, test an actual third stage before the separate producer
batch-limit experiment. The new GPU-resident B cache holds post-halation
LogExposure; it does not persist the individual coarse fields or change the
per-band wait. The initial four-case diagnostic has no E3 median improvement
over E2. Only Portra UHD E2 is faster than named R-B1 in this bounded run;
reference stability is still unfrozen. Retain the prototype as a research control,
without enabling it by default or promoting a speed claim.

See [stage-eleven results](wavefront-stage11-results.md),
[provenance](wavefront-stage11-results.json) and
[two-cache contract/reproduction](wavefront-three-stage-contract.md).
The prior stage-ten “next batch limit” ordering is historical; the independent
batch-only, table, persistent coarse-field and asynchronous experiments remain
unimplemented. Full current-source release/Swift/parity and formal reference,
retention and performance gates remain pending.


## Stage twelve: revised two-stage responsibilities

The user clarified and authorized a two-stage multi-output experiment. Stage one
now emits selected light plus three coarse blurred fields; stage two consumes
both and fuses the original tail. There is no third fields-only invocation. All
four output hashes match original E2; A/F and final MTF production traces pass,
as do lifecycle, default release build and 18 targeted release Swift tests.

The eight-round paired pilot is mixed: three lower medians, HP5 UHD about 3.2%
higher; HD peaks decrease, UHD peaks increase. Portra UHD arms have different
thermal maxima. No stable speedup/default promotion/PR is claimed. See
[stage-twelve results](wavefront-stage12-results.md),
[provenance](wavefront-stage12-results.json) and
[two-stage contract](wavefront-bundle-contract.md).
The old three-unit coarse-field proposal remains unexecuted as that topology.
Producer lead based on safe edge demand is an independent, unimplemented next
control; the present experiment preserves margin360/band512/A2048/sync.


## Stage thirteen: actual original pipeline comparison

The prior stage-twelve control was our earlier E2, not upstream's original
pipeline. A fresh twelve-round, three-arm comparison reuses the clean frozen
original worker for general B0 and default-enabled-window B1, plus the unchanged
revised E2 worker. All four direct B1 pixel comparisons are bitwise equal.

The revised E2 is slower than original default B1 in every observed median:
Portra HD +24.1%, Portra UHD+luma +17.6%, HP5 HD +30.1%, HP5 UHD +16.7%.
It beats general B0, but B0 is not default on these eligible inputs. Three
device peaks decrease relative to B1; HP5 HD increases by about 4 MiB.

Each arm/case has one round; B_ref remains unfrozen. B1 uses 1080-row windows
and E2 uses 512-row bands, with different call/cache lifetimes; this is not
exclusive cut-position attribution. Keep the original default for speed; no
default promotion or speedup PR. No engine/AOT change was made in this stage.
Producer-lead tightening remains unimplemented. See
[stage-thirteen results](wavefront-stage13-results.md) and
[full provenance](wavefront-stage13-results.json).


## Stage fourteen:1080-row band control

The opt-in bundled two-stage cut now also supports1080-row bands with the same
A2048, margin360, fields, precision, pool and per-band sync. The same current
normal worker serves512/1080; original default B1 uses1080-row windows.
Eight normal pixel comparisons are bitwise equal to original B1/prior512; eight
trace checks pass the unchanged numeric contract and real A/F/GPU checks.
4K trace outputs have tiny differences from normal, retained in the report.
Fourteen streamed frame-history comparisons and failure recovery pass.

The complete restarted twelve-round pilot retains the earlier interrupted
controller-check attempt and all unfavorable outcomes. One round per arm/case
cannot freeze B_ref or pass performance/release/retention gates; no default
promotion or upstream PR. See [stage-fourteen results](wavefront-stage14-results.md)
and [full provenance](wavefront-stage14-results.json).


## Stage fifteen: reuse local optimizations in whole-frame general

At the user's request, test the first next priority: independent register,
normalized-reduction, counted-cell and radius-one policies, preserving the
full general feature graph and one AOT call. Defaults stay0; no window loop,
wavefront, precision change or automatic combination. Four original R outputs
support24 direct comparisons, and five complete histories pass70 frames.
The restarted28-round pilot retains fresh R-B0/R-B1 and same-source G0, all
unfavorable rows and the first interrupted campaign. Original stability,
release/parity, retention and holdout gates remain pending; no default or PR.
See [general-stage15 results](general-stage15-results.md),
[full provenance](general-stage15-results.json) and
[contract](general-optimizations-contract.md).
