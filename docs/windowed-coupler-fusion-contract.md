# Isolated Coupler release/downsample fusion

In the exact negative and negative_luma windowed graphs, the released inhibitor is stored at full resolution before box downsampling and Gaussian diffusion. The experiment keeps the Log exposure shared field, and evaluates the original film curve, activation and release per source sample inside the box sum. It removes the Released store, never moves a nonlinear release after averaging, and retains the downsample grid and all diffusion/print stages.

The private `windowed_coupler_fusion` flag defaults false, has a distinct nondefault cache key and has no environment activation. Backend admission requires full-float realtime Metal windowing and an exact graph with Couplers and CouplerDiffusion compiled on, without a wavefront cut. Other gates/transport and non-exact graphs retain storage. The generator admits only the existing exact color negative/negative_luma twins and rejects mixed MTF/general/wavefront experiments, even a separate experiment explicitly set to zero. Existing MTF fusion remains off throughout this cohort.

Each W0/Fused diagnostic contains two freshly generated archives plus 61 hash-verified frozen original archives, not a complete current-source release set. Shared Graph/Stages math hashes must match the frozen control. Original R stays clean at `96623ba0831a52dbddcda35727a206d4123a8b5f`.

The two frozen Portra profiles have Coupler sigma 0.405/0.810 pixels, respectively, hence stride 1 in both. The main cases measure the removal of a release write followed by a grid read/write at the same resolution. An additional 1919x1081 odd stress case sets sigma4.2/radius13 (stride4) and gamma[1.7,0.8,2.3] to verify true coarse reduction and the ordering of nonlinear release. A 65x1081 nonlinear luma case covers the other twin and two output windows. Both stress fixtures use cropped Coffee pixels and explicitly changed parameters, not additional calibrated photographic profiles.

Correctness:

- Four frozen primary cases plus both stress fixtures: twelve independent current-arm/original-windowed pixel comparisons, with six oracle/self rows retained. W0 and inactive classes must match R bitwise. Active Fused retains original linear1e-5/encoded<1/255, finite and exact-alpha requirements. One actual dispatch per output window must disappear: HD41→40, UHD77→75, stress66→64 and77→75.
- Two fourteen-call histories against the restored SHA-verified R worker, with UHD luma calibration at HD geometry to exercise active negative/luma switching, stock, seed, camera gate, still/exact fallbacks, origin and encoded delivery. Sixteen comparisons use the fresh twins; inactive frames use frozen libraries and are labeled. Original wavefront fault frame11 is skipped on both sides; no new fault/drain behavior is claimed.
- Four current-source JIT/AOT comparisons: both on/off arms on both nonlinear odd fixtures. Cache-key separation is checked by the JIT harness.
- CPU/Metal stage checks, release build and relevant Swift tests, Python regressions and eight native generator rejection checks. Full release AOT/JIT parity remains a separate pending gate.

Timing: two frozen active Portra Coffee cases (1920x1080 and3840x2160), three repeats per arm/case. Predeclared orders R/W0/Fused, W0/Fused/R and Fused/R/W0 for each case. Each arm uses a fresh process, 5s warm/30s measure/2s tail/5s idle, one frame in flight and a1GiB pool. Phase hashes, actual symbol, one AOT and exact dispatch count must match the own-arm pixel proof. Reserve1GiB free space and limit timing evidence to256MiB. No compilation, GPU verification, plots or cleanup during timing. Docker and user services stay running.

These are bounded diagnostics with background variation; neither smaller static kernel families nor fewer dispatches prove a speedup. Device peaks include input/output, pools, tables and scratch; use repeated runs rather than the best isolated-frame observation. No all-stock/holdout, stable B_ref, default promotion, upstream PR or Taggii integration is implied. MTF combinations and Print MTF/output fusion are separate, unexecuted work.

Reproduce in fresh output folders:

```sh
python3 tools/prepare-windowed-coupler.py --control build/wavefront-post-mtf-final/control --halide-root build/halide-install --output build/windowed-coupler-stage17
python3 tools/verify-windowed-coupler.py --build build/windowed-coupler-stage17 --output build/windowed-coupler-stage17-proof --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference
python3 tools/verify-windowed-coupler-history.py --proof build/windowed-coupler-stage17-proof/report.json --original-history build/wavefront-lifecycle/8df1919b01a7 --output build/windowed-coupler-stage17-history
python3 tools/verify-windowed-coupler-jit.py --proof build/windowed-coupler-stage17-proof/report.json --jit build/windowed-coupler-stage17-validation/jit --output build/windowed-coupler-stage17-jit-proof
python3 tools/run-windowed-coupler-diagnostic.py --proof build/windowed-coupler-stage17-proof/report.json --history build/windowed-coupler-stage17-history/report.json --jit-proof build/windowed-coupler-stage17-jit-proof/report.json --reference ../reference --output build/windowed-coupler-stage17-timing
```

Build `tools/windowed-coupler-jit.cpp` with C++17, the pinned `build/halide-install` include/library/rpath, `Sources/FotufilmHalide/include`, and Metal/Foundation. The frozen R history executable is restored from its lossless archive and raw SHA checked before use. Historical source keys and workers remain associated with their original experiment.
