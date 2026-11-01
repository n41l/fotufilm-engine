# Coupler unit-stride specialization diagnostic

Stage18 tests whether the generic box reduction retained by the stage17 Coupler fusion costs time when stride is one. The private `windowed_coupler_unit_stride` flag defaults false and has a distinct nondefault cache key. Only the already admitted full-float realtime Metal exact windowed negative/negative_luma Released source is specialized. At stride1, origin modulo stride is zero and the one-cell average equals the bounded source. The specialized kernel evaluates the unchanged release directly; stride>1 keeps the original box reduction and normalization. Graph/Stages film mathematics, public ABI and stock data do not change. MTF fusion stays off.

Each current arm contains two fresh archives and61 SHA-verified frozen originals. W0 is the current-source unfused correctness control; Generic enables release fusion with the unit specialization off; Unit enables both. Original R remains clean at96623ba0831a52dbddcda35727a206d4123a8b5f. This is a diagnostic composite, not a complete current-source AOT release.

Pre-timing verification:

- Six fixtures × R/W0/Generic/Unit yield24 rows (18 independent current-arm/R comparisons plus6 oracle/self rows). Four primary cases and two nonlinear odd fixtures all pass bitwise. Active Generic/Unit remove one dispatch per output window; primary HD41→40 and UHD77→75.
- Three fourteen-call current-arm histories yield42 comparisons against the independent original-engine history. Gamma[1.7,0.8,2.3] and sigma transitions1→4→1→2→1 exercise nonlinear release and same-process branch changes. Original wavefront-only fault frame11 is skipped on both sides. A verification-only Metal observer records the actual bound kernel. Sixteen checks confirm Generic retains reduction loops, Unit stride1 has no reduction/count loops, and Unit larger strides retain them. History executables are losslessly compressed with raw hashes after comparison.
- Six targeted fresh-archive JIT/AOT comparisons cover all three current arms and both nonlinear odd fixtures, at original1e-5 linear tolerance with finite and exact-alpha requirements. CPU/Metal stage checks, release build, relevant Swift tests, Python regressions and ten generator rejections complete before timing. Complete release AOT/JIT parity remains pending.
- An initial history invocation referenced the wrong frozen AOT directory and failed before compilation/GPU execution; its log is retained. A rejection harness initially assumed exit2 for a wrong variant, whereas existing graph admission returns1; expected status was corrected without source changes.

Timing is predeclared as18 rounds: original R, same-source Generic and Unit, on Portra Coffee1920x1080 and3840x2160, three repeats per arm/case. Orders for each case: R/Generic/Unit, Generic/Unit/R, Unit/R/Generic. W0 is not timed. Every arm runs in a fresh process using the unchanged common worker,5s warmup/30s measurement/2s tail/5s idle, one frame in flight and1GiB pool. Own-arm pixel hashes, actual symbol, one AOT call and dispatch count must match verification. Reserve1GiB free disk; timing evidence budget256MiB. No native builds, GPU verification, plotting or cleanup during timing. The kernel observer is never injected into performance workers. Docker and other user services remain running.

Report all repeats, median of round medians, worst round p95, repeated device peak and allocation counts. Compare Unit with both Generic and R. Loop elimination alone is not performance evidence; background variation remains a limitation. No stable B_ref, all-stock/holdout acceptance, default promotion, upstream PR or Taggii integration is implied.

Reproduce with fresh output directories using `prepare-windowed-unit.py`, `verify-windowed-unit.py`, `verify-windowed-unit-history.py` (frozen AOT directory `../reference/build/wavefront-macos`), and `verify-windowed-unit-jit.py`. Then run:

```sh
python3 tools/run-windowed-unit-diagnostic.py --proof build/windowed-unit-stage18-proof/report.json --history build/windowed-unit-stage18-history-v2/report.json --jit-proof build/windowed-unit-stage18-jit-proof/report.json --reference ../reference --output build/windowed-unit-stage18-timing
```
