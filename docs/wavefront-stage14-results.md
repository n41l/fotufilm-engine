# Stage fourteen: 1080-row wavefront band control

**1080-row bands improve three of four observed medians versus 512, but Portra UHD becomes slower. All four device peaks rise versus both 512 and original B1. Keep the original default.**

Compare original default-windowed 1080 with current same-worker bundled 512 and 1080. All cases use the frozen inputs and original 5/30/2/5-second protocol, one frame in flight, 1 GiB pool. The current worker serves both bands; A2048, lead360, cut, F layout, precision and per-band sync are unchanged.

| Case | Original B1 median ms | Wavefront 512 median ms | Wavefront 1080 median ms |1080 vs512 time reduction |1080 vs B1 time increase |
| --- | --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 9.72 | 11.42 | 10.29 | +9.9% | +5.9% |
| portra400-coffee-3840x2160 | 46.84 | 47.80 | 52.95 | -10.8% | +13.0% |
| hp5plus400-coffee-1920x1080 | 8.70 | 10.83 | 8.53 | +21.3% | -2.0% |
| hp5plus400-coffee-3840x2160 | 28.10 | 31.46 | 29.02 | +7.7% | +3.3% |

| Case | B1 / E512 / E1080 p95 ms | B1 / E512 / E1080 device peak MiB | Thermal maxima B1 /512 /1080 |
| --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 12.45 / 17.61 / 13.27 | 334.3 / 315.0 / 381.2 | 1 / 1 / 1 |
| portra400-coffee-3840x2160 | 60.44 / 59.30 / 60.19 | 1183.7 / 1090.1 / 1506.2 | 1 / 1 / 1 |
| hp5plus400-coffee-1920x1080 | 12.62 / 14.23 / 10.44 | 274.8 / 278.8 / 322.9 | 1 / 1 / 1 |
| hp5plus400-coffee-3840x2160 | 49.06 / 46.84 / 38.62 | 667.7 / 642.5 / 859.1 | 1 / 1 / 1 |

Twelve valid rounds, 22426 measurement requests. One round per arm/case; all rows and unfavorable results retained. B_ref remains unfrozen. No native compilation, GPU verification or cache cleanup during timing. These C/AOT times exclude the Swift invocation/application save path.

| Case | AOT calls B1 /512 /1080 | Actual steady dispatches B1 /512 /1080 |
| --- | --- | --- |
| portra400-coffee-1920x1080 | [1] / [5] / [2] | [41] / [110] / [42] |
| portra400-coffee-3840x2160 | [1] / [10] / [5] | [77] / [240] / [117] |
| hp5plus400-coffee-1920x1080 | [1] / [5] / [2] | [33] / [86] / [34] |
| hp5plus400-coffee-3840x2160 | [1] / [10] / [5] | [55] / [175] / [86] |

Normal output is bitwise identical to original B1 and prior512 in all eight case/band comparisons. Eight trace checks pass A/F regions, final MTF new rows, actual kernel bindings and previous-band GPU completion. The four 4K trace outputs have tiny differences up to 2.027e-6, under the unchanged 1e-5 numeric contract; alpha exact. Trace512/1080 hashes match each other. The difference is observed in traced builds; its precise compiler/schedule cause has not been isolated. It is retained rather than called bitwise parity.

Fourteen streamed lifecycle comparisons, four invalid options, combined-producer failure drain/recovery and unsupported bundle64 original fallback pass. 185 Python tests, CPU/Metal 11 each, C++17 release build and 18 focused release Swift tests pass. Plain swift build failed on the preexisting noexcept callback alias under its default standard; the C++17 commands pass. Full current-source release AOT/JIT parity remains pending.

The first AOT whitelist rejection, initial stricter trace-hash check, history dump-write failure and first timing controller selecting trace hashes instead of normal hashes are retained in the JSON provenance. The repeated history used the same frozen C worker in a single process, compared each frame against saved hashed R, and freed successful dumps; no frame-history reset. Historical workers and failed dumps were losslessly archived, with restore manifests. Docker and user services remain running.

This experiment measures the band-size tradeoff in the current implementation. It cannot isolate every underlying cost or prove wavefront always wins/loses. Band size changes scratch/batches/calls inherently; coarse thermal agreement does not establish controlled GPU frequency or background load. Keep the default unchanged until repeated/holdout and the original release, total-memory/retention and performance gates pass.

Engine implementation `55ff532`; controller fix `2bed1f4`; original `96623ba0831a52dbddcda35727a206d4123a8b5f`; AOT key `9b5d9d5c4e2f98ec10769389f1039487403dbbe36023477d09ad94a1fd4db15f`. [Full provenance](wavefront-stage14-results.json).

Reproduce with new output directories, the pinned Halide and a verified frozen control:

```sh
python3 tools/prepare-wavefront-bundle.py --control build/wavefront-post-mtf-final/control --halide-root build/halide-install --output build/bands-reproduction
python3 tools/verify-wavefront-bands.py --build build/bands-reproduction --output build/bands-proof --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference --prior-proof build/wavefront-bundle/verification-v2/report.json
python3 tools/run-wavefront-bands-diagnostic.py --proof build/bands-proof/report.json --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference --output build/bands-timing
```

Actual raw timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/wavefront-band 1080-timing/ef1a955b7fd9/report.json`.

Chart: `/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-band 1080-stage14/comparison.png`.
