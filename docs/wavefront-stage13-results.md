# Stage thirteen: compare with the actual original pipeline

**The revised two-stage implementation does not beat the original default-windowed pipeline in this four-case pilot.** All four candidate medians are higher, by about 17%–30%. The default remains unchanged.

Original means the clean frozen upstream snapshot `96623ba0831a52dbddcda35727a206d4123a8b5f`, not the earlier experimental E2. B0 is the original general/full-frame path. B1 is the original enabled-window selector and actually executes its windowed twins on all four eligible cases; B1 corresponds to the original default here. Both use the same frozen original worker.

| Case | Original general B0 median ms | Original default B1 median ms | New two-stage median ms | New vs B1 |
| --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 12.77 | 7.29 | 9.04 | +24.1% |
| portra400-coffee-3840x2160 | 87.80 | 43.13 | 50.74 | +17.6% |
| hp5plus400-coffee-1920x1080 | 11.30 | 6.67 | 8.68 | +30.1% |
| hp5plus400-coffee-3840x2160 | 58.31 | 21.00 | 24.50 | +16.7% |

| Case | B0 / B1 / new total device peak MiB | B1 / new p95 ms | B1 / new AOT calls | B1 / new steady GPU dispatches |
| --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 462.2 / 334.3 / 315.0 | 11.31 / 16.63 | [1] / [5] | [41] / [110] |
| portra400-coffee-3840x2160 | 1734.2 / 1183.7 / 1090.1 | 62.16 / 82.80 | [1] / [10] | [77] / [240] |
| hp5plus400-coffee-1920x1080 | 482.8 / 274.8 / 278.8 | 8.89 / 11.45 | [1] / [5] | [33] / [86] |
| hp5plus400-coffee-3840x2160 | 1574.4 / 667.7 / 642.5 | 25.80 / 30.83 | [1] / [10] | [55] / [175] |

The candidate is faster than B0 in every measured case, but B0 is not the original default on these inputs. Relative to B1, device peak decreases by about 19.3 MiB (Portra HD), 93.6 MiB (Portra UHD) and 25.2 MiB (HP5 UHD), and increases by about 4.0 MiB (HP5 HD). Peak figures include cold start, input/output, caches, scratch, LUT and pool. Raw process peaks and retention are also preserved. This is not an overall performance or memory acceptance pass.

Twelve valid rounds, 23,974 measurement requests, predeclared rotating order, one fresh process per arm, original 5/30/2/5-second protocol, one frame in flight and 1-GiB pool. Each arm/case has one round. B1/candidate thermal maxima match (HD Portra0; other cases1), but coarse thermal agreement does not control GPU frequency or background drift. B_ref remains unfrozen. No assistant-owned native build, GPU verification or cache cleanup ran during timing.

The original B1 window is 1080 rows; candidate output bands are 512 rows with A2048 and lead360. The comparison includes these configuration choices, stage-call and cache-lifetime differences. It cannot uniquely attribute the gap to a cut or rule out every other two-stage design. Do not select slower general B0 as the sole reference to claim an upstream speedup.

Four new direct full-pixel comparisons against original B1 pass with maximum error0 and exact alpha; all four output hashes are identical to the candidate. The independent general-R proof is retained from stage12, and timed B0/B1/candidate phase hashes each match their own proof. Actual variants, AOT counts and GPU work were checked on every warm/measurement call. No engine source, AOT or verified worker was rebuilt or changed in this stage.

Decision: keep the original default-windowed pipeline for speed. Retain the revised cut only as a research memory/scheduling tradeoff. Any further optimization should target B1 and use controlled band/call-lifetime comparisons; repeated/holdout testing, complete release parity and original formal gates remain pending. No default switch or speedup PR is justified by these results.

Candidate implementation `70fa45378391eb16b09cd98b12d480d70796acd1`; comparison tools `f24a40df644c5b1f9c79a99c47d25e44f4e5ba73`. [Full provenance and raw locations](wavefront-stage13-results.json), [prior C/C experiment](wavefront-stage12-results.md).

Reproduce with the already verified workers and new output directories:

```sh
python3 tools/verify-wavefront-upstream.py \
  --candidate-proof build/wavefront-bundle/verification-v2/report.json \
  --reference ../reference \
  --reference-worker ../reference/build/wavefront-benchmark-v2/instrumented/runner \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --compare build/wavefront-bundle/verification-v2/compare \
  --output build/original-proof-reproduction
python3 tools/run-wavefront-upstream-diagnostic.py \
  --proof build/wavefront-bundle/verification-v2/report.json \
  --upstream-proof build/original-proof-reproduction/report.json \
  --trace build/wavefront-bundle/verification-v2/bundle-trace.json \
  --fixtures build/wavefront-corpus/frozen-verification-v2.json \
  --reference ../reference --output build/original-timing-reproduction
```

Actual timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/wavefront-upstream/timing/b1a71a88f24b/report.json`.
Chart: `/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-original-stage13/comparison.png`.

The assistant did not quit Docker, change user services, modify Taggii/iOS or create an upstream PR.
