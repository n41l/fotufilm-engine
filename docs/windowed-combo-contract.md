# MTF pointwise fusion × best-fit pool combination

The first sanctioned combination experiment: candidate 1 (`windowed_mtf_fusion`, engine scheduling flag) together with the stage19 best-fit buffer-pool policy (exact-size first; on a miss with a rounded request of at least 64 KiB, reuse the smallest completed idle buffer within [rounded, 1.5 × rounded]; original fence/reference accounting and the 1 GiB idle cap unchanged). Neither is active by default; neither's single-arm saving may be assumed for the combination — this experiment exists because the two mechanisms touch the same intermediate fields.

Four arms on the active Portra Coffee UHD case, all pixel-identical to frozen R:

- **R-B1** — the frozen reference instrumented runner, original allocator.
- **MTF** — the current-source exact negative_luma twin rebuilt with `windowed_mtf_fusion=1` (one fresh archive plus 62 frozen), original allocator.
- **BF** — the frozen R archives from the frozen reference checkout with the best-fit suffix compiled into a diagnostic copy of its shim; no engine or archive change.
- **COMBO** — the fresh fused archive from the current source plus the same best-fit suffix on the current shim.

Isolation: the stage26 archives are built by `prepare-windowed-mtf.py` with identities that now declare `print_mtf_fusion: false` and `coupler_fusion: false`; the driver's `windowed_mtf_research` admission rejects any identity that does not. The best-fit suffix (`windowed-pool-best-fit.inc`) is hash-recorded in every stage26 report. No wavefront, trace override, print-MTF or coupler flag participates.

Verification: five cases (four frozen primary cases plus the odd 1919×1081 two-window crop) × five arms = 25 independent full-pixel comparisons, every arm bitwise-equal to R; dispatch counts R=W0=BF=77 and MTF=COMBO=73 on the active cases, unchanged elsewhere; two current-source JIT/AOT comparisons at worst linear error 1.9669533e-06 under the unchanged gates. A fresh 28-frame history is not re-run for this campaign: the fusion graph's histories are covered bit-identically by stage16 and stage24, and the pool policy is allocator-only.

Timing: predeclared 4×4 Williams square — R-B1/MTF/COMBO/BF, MTF/BF/R-B1/COMBO, BF/COMBO/MTF/R-B1, COMBO/R-B1/BF/MTF — so every arm follows every other exactly once; fresh process per arm, 5 s warm / 30 s measure / 2 s tail / 5 s idle, one in-flight frame, 1 GiB pool cap, 1 GiB disk reserve, 256 MiB evidence budget, no build, verification, cleanup or plotting during timing; Docker and user services stay running.

Bounded diagnostic of one active photographic case; no B_ref freeze, all-stock/holdout/retention/concurrency result, release acceptance, default activation, Taggii/iOS change, push or PR.

Reproduce:

```sh
python3 tools/prepare-windowed-mtf.py --control build/wavefront-post-mtf-final/control --halide-root build/halide-install --output build/windowed-mtf-combo-stage26
python3 tools/verify-windowed-combo.py --build build/windowed-mtf-combo-stage26 --output build/windowed-combo-stage26-proof --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference
python3 tools/verify-windowed-combo-jit.py --proof build/windowed-combo-stage26-proof/report.json --jit build/windowed-mtf-combo-stage26/windowed-mtf-jit --output build/windowed-combo-stage26-proof/jit-parity
python3 tools/run-windowed-combo-diagnostic.py --proof build/windowed-combo-stage26-proof/report.json --jit-proof build/windowed-combo-stage26-proof/jit-parity/report.json --reference ../reference --output build/windowed-combo-stage26-timing
```
