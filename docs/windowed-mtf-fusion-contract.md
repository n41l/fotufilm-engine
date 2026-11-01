# Isolated windowed MTF fusion

The original exact `color_float_realtime_windowed_negative_luma` graph stores its primary/secondary mix, neutral-axis correction, and final MTF light separately. The experiment computes the mixed three records once in the final store's thread, inlines the neutral-axis correction, and retains the final light shared by halation and direct-light readers.

`GpuConfiguration::windowed_mtf_fusion` is private, explicit, off by default and separately cache-keyed when enabled. It applies only to full-float realtime Metal windowed schedules. There is no environment activation, public control, graph formula change, precision change, window-height change, wavefront cut or extra AOT call. The generator restricts `--windowed-mtf-fusion=0|1` to one explicit Mac exact negative_luma variant and rejects mixed research modes.

The diagnostic builder replaces exactly one named archive in a hash-verified frozen 63-archive control. Both W0 and Fused therefore contain one fresh archive plus 62 frozen archives; neither is a current-source release set. Shared Graph/Stages hashes must match the frozen control. Original R remains detached and clean at `96623ba0831a52dbddcda35727a206d4123a8b5f`.

Verification uses original windowed R-B1, current-source W0, and Fused:

- Four frozen Coffee SDR cases plus a 1919x1081 crop with changed seed and UHD-calibrated luma configuration. Ten independent full-pixel comparisons; the report also retains five oracle/self rows. W0 and all unaffected paths must remain bitwise equal to R. Active paths must remove two actual dispatches per output window, while retaining one AOT call.
- Two fourteen-frame histories against a restored hash-verified original R worker. The color pack deliberately uses UHD calibration on HD geometry to keep the luma twin active across stock/seed/gate/stage/encoding switches. Odd active two-window geometry is covered separately by the pixel proof. The driver omits its original wavefront-specific fault frame on both sides; this introduces no new fault/drain behavior.
- Targeted current-source W0/Fused JIT versus their AOT workers on the odd two-window input. Existing finite/alpha and linear 1e-5 limits remain unchanged; encoded comparisons retain the original less-than-1/255 limit.
- CPU/Metal stage tests, release build and relevant frame resource/variant tests, Python regression and native CLI rejection tests. Full release AOT/JIT parity remains a separate pending gate.

Timing is predeclared as three 5s warm/30s measure/2s tail/5s idle rounds per arm on the active Portra Coffee UHD case. Orders are R/W0/Fused, W0/Fused/R, Fused/R/W0. Fresh process per arm, one in-flight frame, 1 GiB pool, unchanged normal driver, full hashes at phase boundaries and exact actual symbol/dispatch agreement with own-arm proof. Reserve 1 GiB free disk and at most 256 MiB timing evidence. No native build, GPU verification, cleanup or plotting during timing. Docker and user services remain running.

This is a bounded diagnostic with three repeats of one active photographic case. It cannot freeze B_ref, prove all-stock/holdout or release acceptance, or justify default activation or an upstream PR. Coupler/downsample and Print MTF/output fusion remain separate unimplemented candidates.

Reproduce in new output directories with the pinned Halide installation:

```sh
python3 tools/prepare-windowed-mtf.py --control build/wavefront-post-mtf-final/control --halide-root build/halide-install --output build/windowed-mtf-stage16
python3 tools/verify-windowed-mtf.py --build build/windowed-mtf-stage16 --output build/windowed-mtf-stage16-proof --fixtures build/wavefront-corpus/frozen-verification-v2.json --reference ../reference
python3 tools/verify-windowed-mtf-history.py --proof build/windowed-mtf-stage16-proof/report.json --original-history build/wavefront-lifecycle/8df1919b01a7 --output build/windowed-mtf-stage16-history
```

The JIT harness is compiled against the pinned Halide library; its completed two-arm comparison is required before `run-windowed-mtf-diagnostic.py`. The frozen R history executable may require restoration from `runner.stage15.gz`; raw SHA is checked before execution. Historical source keys describe their own builds and must not be silently reused after edits.
