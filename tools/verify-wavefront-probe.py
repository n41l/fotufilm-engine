#!/usr/bin/env python3
"""Build independent R/C Metal AOT fragments and check numerical/reuse evidence.

R is an unmodified checkout. The external generator includes each checkout's
shared stage headers; C alone uses the explicit experimental folding schedule.
This is a fragment feasibility check, not a whole-film performance acceptance.
"""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open("w") as output:
        subprocess.run([str(x) for x in command], stdout=output, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--halide-root", required=True, type=Path)
    parser.add_argument("--bands", default="64,128,256")
    args = parser.parse_args()
    candidate = Path(__file__).resolve().parents[1]
    reference, halide = args.reference.resolve(), args.halide_root.resolve()
    if reference == candidate:
        raise ValueError("reference must be a separate checkout")
    if subprocess.check_output(["git", "-C", str(reference), "status", "--porcelain"], text=True):
        raise ValueError("reference checkout must be clean")
    source = candidate / "tools/wavefront-probe.cpp"
    driver = candidate / "tools/wavefront-probe-run.cpp"
    targets = []
    for label, checkout, mode, band in [
        ("R_general", reference, "general", 1080),
        ("R_windowed", reference, "windowed", 1080),
        ("C_legacy", candidate, "windowed", 1080),
        *[(f"C_producer_{b}", candidate, "wavefront", b)
          for b in map(int, args.bands.split(","))],
    ]:
        root = checkout / "build/wavefront-probe" / label
        root.mkdir(parents=True, exist_ok=True)
        generator = root / "generator"
        run(["xcrun", "clang++", "-std=c++17", "-O2", f"-I{halide}/include",
             f"-I{checkout}/Sources/FotufilmHalide", f"-I{checkout}/Sources/FotufilmHalide/include",
             source, f"-L{halide}/lib", "-lHalide", f"-Wl,-rpath,{halide}/lib", "-o", generator],
            root / "generator-build.log")
        fold = 512 if band <= 256 else 2048
        run([generator, mode, root, band, fold], root / "generate.log")
        runner = root / "runner"
        run(["xcrun", "clang++", "-std=c++17", "-O2",
             f"-DFOTUFILM_PROBE_FOLDED={int(mode == 'wavefront')}", f"-I{root}",
             f"-I{halide}/include", driver, root / "probe.a", "-framework", "Metal",
             "-framework", "Foundation", "-o", runner], root / "runner-build.log")
        targets.append({"label": label, "root": root, "runner": runner,
                        "aot_sha256": sha(root / "probe.a"), "runner_sha256": sha(runner)})
    report_dir = candidate / "build/wavefront-probe"
    results, lifecycle = [], []
    shapes = [(32, 63), (65, 127), (65, 128), (65, 129), (65, 255), (65, 256),
              (65, 257), (65, 513), (257, 769), (1080, 1920), (1919, 1081), (3840, 2160)]
    try:
        for width, height in shapes:
            for radius in (1, 3, 16):
                case = f"{width}x{height}-r{radius}"
                baseline = None
                for target in targets:
                    actual = target
                    reason = None
                    if target["label"].startswith("C_producer") and radius == 1:
                        # Admission must reject before calling/writing the folded AOT.
                        rejected = subprocess.run([str(target["runner"]), str(width),
                            str(height), str(radius), str(target["root"] / "must-not-exist.f32")])
                        if rejected.returncode != 3 or (target["root"] / "must-not-exist.f32").exists():
                            raise AssertionError("unsupported request was not rejected before writing")
                        actual = next(t for t in targets if t["label"] == "C_legacy")
                        reason = "radius-one specialization bypasses folded producer"
                    dump = target["root"] / f"{case}.f32"
                    trace = target["root"] / f"{case}.trace"
                    run([actual["runner"], width, height, radius, dump], trace)
                    pixels = array("f")
                    pixels.frombytes(dump.read_bytes())
                    if len(pixels) != width * height * 4:
                        raise AssertionError(f"incorrect dump size: {case}")
                    if baseline is None:
                        baseline = pixels
                    error = max(abs(x - y) for x, y in zip(baseline, pixels))
                    if error > 1e-5:
                        raise AssertionError(f"{target['label']} {case}: error {error}")
                    intervals = []
                    for line in trace.read_text().splitlines():
                        fields = line.split()
                        if len(fields) == 8 and fields[:2] == ["PRODUCE", "first_horizontal"]:
                            start, rows = int(fields[4]), int(fields[5])
                            if rows > 0:
                                intervals.append((start, start + rows))
                    if target["label"].startswith("C_producer") and reason is None:
                        if not intervals:
                            raise AssertionError("missing real predecessor production events")
                        for left, right in zip(intervals, intervals[1:]):
                            if left[1] > right[0]:
                                raise AssertionError(f"recomputed predecessor rows: {case}")
                    results.append({"case": case, "target": target["label"],
                                    "actual_target": actual["label"], "fallback_reason": reason,
                                    "max_abs_error": error, "output_sha256": sha(dump),
                                    "producer_intervals": intervals,
                                    "producer_rows": sum(end - start for start, end in intervals)})
                    # Keep traces and hashes; remove only this newly generated successful dump.
                    dump.unlink()
                print(f"PASS {case}", flush=True)
        for width, height in ((65, 513), (1080, 1920)):
            baseline = None
            for target in targets:
                case = f"lifecycle-{width}x{height}"
                dump = target["root"] / f"{case}.f32"
                run([target["runner"], width, height, 3, dump, 3],
                    target["root"] / f"{case}.trace")
                pixels = array("f")
                pixels.frombytes(dump.read_bytes())
                if baseline is None:
                    baseline = pixels
                if len(pixels) != len(baseline):
                    raise AssertionError("lifecycle dump size changed")
                error = max(abs(x - y) for x, y in zip(baseline, pixels))
                if error > 1e-5:
                    raise AssertionError("A/B/A geometry or changed-input parity failure")
                lifecycle.append({"case": case, "target": target["label"],
                                  "frames": 3, "max_abs_error": error,
                                  "output_sha256": sha(dump)})
                dump.unlink()
            print(f"PASS {case}", flush=True)
    finally:
        report = {"scope": "two original Gaussian stages; not a full-film or performance gate",
                  "reference_sha": subprocess.check_output(
                      ["git", "-C", str(reference), "rev-parse", "HEAD"], text=True).strip(),
                  "generator_source_sha256": sha(source), "driver_source_sha256": sha(driver),
                  "halide_dylib_sha256": sha(halide / "lib/libHalide.dylib"),
                  "targets": [{k: v for k, v in t.items() if k not in ("root", "runner")}
                              for t in targets], "results": results,
                  "expected_results": len(shapes) * 3 * len(targets), "lifecycle": lifecycle,
                  "complete": len(results) == len(shapes) * 3 * len(targets)
                      and len(lifecycle) == 2 * len(targets)}
        (report_dir / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
