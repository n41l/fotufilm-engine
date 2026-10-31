# Stage fifteen: independent general kernel optimizations

**No single option improves all four observed medians. Registers raise every device peak; original windowed remains fastest on every case. Keep all options disabled by default.**

Priority 1 tests four scheduling changes without a window loop, wavefront, precision change, pruned feature graph or extra AOT call. Mask 0 is a matched current-source control. Each option is tested independently; no combination is enabled.

| Case | Original general | G0 | Registers | Normalized | Counted | Radius1 | Original windowed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 11.59 | 11.66 | 11.14 | 12.85 | 17.89 | 14.28 | 8.26 |
| portra400-coffee-3840x2160 | 71.26 | 70.64 | 77.84 | 71.58 | 70.56 | 62.53 | 33.43 |
| hp5plus400-coffee-1920x1080 | 9.79 | 9.68 | 9.43 | 9.65 | 9.63 | 9.50 | 5.57 |
| hp5plus400-coffee-3840x2160 | 61.33 | 60.24 | 56.39 | 58.38 | 57.88 | 66.74 | 19.08 |

Warm median milliseconds. Fresh original general/windowed controls are retained; same-source G0 is the isolated-option comparison.

| Option | Cases faster than G0 | Observed median reduction range | Device peak change range MiB |
| --- | --- | --- | --- |
| registers | 3/4 | -10.2% to +6.4% | +24.0 to +352.0 |
| normalized | 2/4 | -10.2% to +3.1% | +0.0 to +0.0 |
| counted | 3/4 | -53.4% to +3.9% | +0.0 to +0.0 |
| radius1 | 2/4 | -22.4% to +11.5% | +0.0 to +96.0 |

| Case | Original general | G0 | Registers | Normalized | Counted | Radius1 | Original windowed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| portra400-coffee-1920x1080 | 462.2 | 462.2 | 550.3 | 462.2 | 462.2 | 462.2 | 334.3 |
| portra400-coffee-3840x2160 | 1734.2 | 1734.2 | 2086.3 | 1734.2 | 1734.2 | 1734.2 | 1183.7 |
| hp5plus400-coffee-1920x1080 | 482.8 | 482.8 | 506.8 | 482.8 | 482.8 | 482.8 | 274.8 |
| hp5plus400-coffee-3840x2160 | 1574.4 | 1574.4 | 1926.4 | 1574.4 | 1574.4 | 1670.4 | 667.7 |

Total device peak MiB includes cold start, input/output, pool, LUT and scratch. Full p95, throughput, process footprint/peaks, retained resources, thermal maxima and raw locations are preserved in JSON; no partial device saving is formal memory acceptance.

| Case | Actual steady GPU dispatches: R-B0 / G0 / Reg / Norm / Count / Radius1 / R-B1 |
| --- | --- |
| portra400-coffee-1920x1080 | [49] / [49] / [47] / [49] / [49] / [46] / [41] |
| portra400-coffee-3840x2160 | [54] / [54] / [52] / [54] / [54] / [51] / [77] |
| hp5plus400-coffee-1920x1080 | [40] / [40] / [38] / [40] / [40] / [38] / [33] |
| hp5plus400-coffee-3840x2160 | [40] / [40] / [38] / [40] / [40] / [39] / [55] |

All 28 timing rounds are valid, with 48,957 measurement requests. Predeclared seven-arm order rotates by two positions per case; fresh process, 5s warm /30s measure /2s tail /5s idle, one frame in flight, 1 GiB pool. Each own-arm normal phase hash, actual symbol, one-call count and steady dispatch count matches its independent proof. One round per arm/case cannot establish stable causal gains or freeze B_ref.

Four original R-B0 oracle outputs support 24 full-pixel comparisons (20 current general and 4 original windowed). G0 matches R-B0 bitwise on all 4 cases; worst linear error across all compared arms is 2.563e-06, under unchanged 1e-5 tolerance, finite and exact alpha. Five full 14-frame histories pass 70 comparisons, worst error 2.65241e-06. 60 frames use current general archives; 10 still/exact requests use frozen legacy libraries and are marked inactive. The original wavefront-only fault frame is excluded on both sides; no new host fault/cache mechanism is introduced.

189 Python tests, CPU/Metal 11 stages each, C++17 release build and 18 focused release Swift tests pass. General nonzero options are cache-keyed, defaults stay 0, and portable/windowed defaults are unchanged. Complete current-source release AOT/JIT parity and wider coverage remain pending; this is two fresh general archives plus 61 frozen archives per arm.

The first timing campaign stopped after 5 rounds at the original 1 GiB disk guard, and is retained separately. After auditing and clearing 7.66 GiB of idle reproducible caches, the entire 28-round cohort restarted with unchanged native workers. The first pixel campaign also ended at a dump-write failure after 21 successful rows; it is retained and is not a complete proof. The same frozen workers reran all cases after own regenerable build caches were removed and inactive historical workers/Metal source files were losslessly archived with hashes. All history dumps are streamed and removed only after successful comparison. No native compilation, GPU verification, plotting or cache cleanup occurs during timing. Docker and user services remain running.

Keep defaults unchanged. Individual observations must survive balanced repeated/holdout tests and original release, footprint/retention and speed gates before promotion. A gain over general alone does not establish a gain over upstream windowed. Later priorities and combined flags remain separate, unexecuted experiments.

Native implementation `107bb9a`; interrupted-run/plot tooling `1a061e0`; original `96623ba0831a52dbddcda35727a206d4123a8b5f`; AOT source key `794eca5c6bed0565227f037d1257b51c27779de06aca5ed7777bd1ae142d6b03`. [Full evidence](general-stage15-results.json), [contract](general-optimizations-contract.md).

Reproduce with pinned Halide, verified legacy control, frozen fixtures and new output directories:

```sh
python3 tools/prepare-general-optimizations.py --control build/wavefront-post-mtf-final/control --halide-root build/halide-install --output build/general-reproduction
python3 tools/verify-general-optimizations.py --build build/general-reproduction --output build/general-proof-reproduction --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference
python3 tools/verify-general-history.py --build build/general-reproduction --proof build/general-proof-reproduction/report.json --reference-history build/wavefront-lifecycle/8df1919b01a7 --catalog ../reference/build/wavefront-fixtures/catalog/catalog.json --output build/general-history-reproduction --archive-workers
python3 tools/run-general-optimizations-diagnostic.py --proof build/general-proof-reproduction/report.json --history build/general-history-reproduction/report.json --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference --output build/general-timing-reproduction
```

Raw final timing: `/Users/kunhuang/Documents/fotufilm-wavefront/candidate/build/general-optimizations-timing/de98baae8a72/report.json`.

The frozen Coffee UHD input is an upscaled SDR workload, not native4K/RAW/HDR. Later corpus holdouts remain untested.

[Latency chart](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-general-stage15/latency.png), [device-peak chart](/Users/kunhuang/.codex/visualizations/2026/10/30/01a18d11-7818-7982-b2f7-71166c1fc048/fotufilm-general-stage15/memory.png).
