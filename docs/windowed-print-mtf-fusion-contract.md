# Isolated windowed Print MTF vertical-into-output fusion

The original exact `color_float_realtime_windowed_negative_luma` graph stores the print MTF blur's vertical result (`frame_print_mtf`) as a frame field between the horizontal cache and the unstored print chain. The experiment removes that storage alone: the reader kernel — `frame_output`, through the register-placed print chain — computes the vertical reduction in its own threads, once per output channel, with the same tap order, the same data/weight accumulation and the same radius-one shortcut `select`. The transmittance store, the horizontal cache, sharpening's reads of the original transmittance, boundary normalization and the box-free radius-one horizontal/vertical fold all remain untouched.

`GpuConfiguration::windowed_print_mtf_fusion` is private, explicit, off by default and separately cache-keyed when enabled. It applies only to full-float realtime Metal windowed schedules. There is no environment activation, public control, graph formula change, precision change, window-height change, wavefront cut or extra AOT call. The generator restricts `--windowed-print-mtf-fusion=0|1` to one explicit Mac exact negative_luma variant and rejects every mixed research mode, including combinations with the MTF or Coupler fusions.

The diagnostic builder replaces exactly one named archive in a hash-verified frozen 63-archive control. Both W0 and Fused therefore contain one fresh archive plus 62 frozen archives; neither is a current-source release set. Shared Graph/Stages hashes must match the frozen control. Original R remains detached and clean at `96623ba0831a52dbddcda35727a206d4123a8b5f`.

Verification, all against original windowed R-B1:

- Four frozen Coffee SDR cases plus the odd 1919x1081 crop: fifteen independent full-pixel comparisons, all bitwise-equal. Inactive cases must keep identical dispatch counts; the active case must remove exactly one actual dispatch per output window (77 to 75 at UHD, two windows) while retaining one AOT call.
- Two fourteen-frame histories against the hash-verified original R worker, UHD luma calibration at HD geometry, stock/seed/gate/stage/encoding switches; 28 comparisons, active frames bitwise-equal.
- Targeted current-source W0/Fused JIT versus their AOT workers on the odd two-window input, under the unchanged linear 1e-5 / encoded < 1/255 / finite / exact-alpha gates.
- Fail-closed archive admission (`windowed_print_mtf_research`) and generator rejection checks; no wavefront or trace overrides.

Timing is predeclared as three 5s warm / 30s measure / 2s tail / 5s idle rounds per arm on the active Portra Coffee UHD case, orders R/W0/Fused, W0/Fused/R, Fused/R/W0, fresh process per arm, one in-flight frame, 1 GiB pool, 1 GiB disk reserve, 256 MiB evidence budget, no build, GPU verification, cleanup or plotting during timing; Docker and user services stay running.

This is a bounded diagnostic of one active photographic case. It cannot freeze B_ref, prove all-stock/holdout or release acceptance, or justify default activation or an upstream PR. The MTF pointwise fusion and the pool experiments remain separate, uncombined candidates.

Reproduce with the pinned Halide installation:

```sh
python3 tools/prepare-windowed-print-mtf.py --control build/wavefront-post-mtf-final/control --halide-root build/halide-install --output build/windowed-print-mtf-stage25
python3 tools/verify-windowed-print-mtf.py --build build/windowed-print-mtf-stage25 --output build/windowed-print-mtf-stage25-proof --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference
python3 tools/verify-windowed-print-mtf-history.py --proof build/windowed-print-mtf-stage25-proof/report.json --original-history build/wavefront-lifecycle/8df1919b01a7 --output build/windowed-print-mtf-stage25-history
python3 tools/verify-windowed-print-mtf-jit.py --proof build/windowed-print-mtf-stage25-proof/report.json --jit build/windowed-print-mtf-stage25/windowed-print-mtf-jit --output build/windowed-print-mtf-stage25-proof/jit-parity
python3 tools/run-windowed-print-mtf-diagnostic.py --proof build/windowed-print-mtf-stage25-proof/report.json --history build/windowed-print-mtf-stage25-history/report.json --jit-proof build/windowed-print-mtf-stage25-proof/jit-parity/report.json --reference ../reference --output build/windowed-print-mtf-stage25-timing
```
