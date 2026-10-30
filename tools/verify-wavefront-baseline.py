#!/usr/bin/env python3
"""Stream the unmodified upstream window fixtures through independent B0/B1 processes.

Only one case's dumps live on disk. Successful dumps are replaced by hashes and
comparison records; all trace/variant evidence and unsuccessful dumps remain.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
from wavefront_aot_driver import build


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--kernels", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    candidate = Path(__file__).resolve().parents[1]
    reference, kernels, pack = (p.resolve() for p in (args.reference, args.kernels, args.pack))
    if subprocess.check_output(["git", "-C", str(reference), "status", "--porcelain"], text=True):
        raise ValueError("reference must be clean")
    summary_root = reference / "build/wavefront-baseline"
    out = summary_root / "runs" / uuid.uuid4().hex[:12]
    out.mkdir(parents=True, exist_ok=True)
    source = (reference / "tools/aot-window-tests.cpp").read_text()
    shapes = {name: (int(width), int(height)) for name, width, height in
              re.findall(r'\{\s*"([a-z0-9-]+)"\s*,\s*(\d+)\s*,\s*(\d+)', source)}
    names = list(shapes)
    marker = "for (const Case &test : cases) {"
    if source.count(marker) != 1 or not names:
        raise ValueError("upstream fixture structure changed; inspect before adapting")
    source = source.replace(marker, marker + '\n        if (const char *filter = '
                            'std::getenv("FOTUFILM_WINDOW_CASE")) {\n'
                            '            if (std::strcmp(filter, test.name)) continue;\n        }')
    # B1 pauses only after a complete, synchronized output dump. The controller
    # compares/deletes that pair before admitting the next frame. No engine code changes.
    write_marker = '            if (!written) return 2;'
    if source.count(write_marker) != 1:
        raise ValueError("upstream dump completion changed; inspect before adapting")
    source = source.replace(write_marker, write_marker + '''
            if (std::getenv("FOTUFILM_WINDOW_ACK")) {
                const auto ready_path = path.string() + ".ready";
                const auto ack_path = path.string() + ".ack";
                FILE *ready = std::fopen(ready_path.c_str(), "wb");
                if (!ready) return 2;
                std::fclose(ready);
                const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(90);
                while (!std::filesystem::exists(ack_path)) {
                    if (std::chrono::steady_clock::now() > deadline) return 2;
                    std::this_thread::sleep_for(std::chrono::milliseconds(1));
                }
                std::filesystem::remove(ack_path);
            }''')
    source = ('#include <cstdlib>\n#include <chrono>\n#include <thread>\n'
              'extern "C" { const char *fotufilm_bench_actual_variant = nullptr; '
              'int fotufilm_bench_aot_calls = 0; int fotufilm_bench_trace_variants = 1; }\n' + source)
    driver = out / "window-driver.cpp"
    driver.write_text(source)
    runner = build(reference, kernels, out / "instrumented", driver)
    compare = out / "compare"
    subprocess.run(["xcrun", "clang++", "-std=c++17", "-O2",
                    str(candidate / "tools/wavefront-compare.cpp"), "-o", str(compare)], check=True)
    results, executions = [], []
    try:
        for name in names:
            directories = []
            # Preserve both seeds in the original process, but consume B1's
            # dumps one at a time. Peak disk use is three frames, not four.
            for mode in ("0", "1"):
                directory = out / name / mode
                directory.mkdir(parents=True, exist_ok=True)
                log = out / name / f"{mode}.log"
                with log.open("w") as output:
                    process = subprocess.Popen([str(runner), str(pack), str(directory)],
                        env={**os.environ, "FOTUFILM_AOT_WINDOWED": mode,
                             "FOTUFILM_TRACE_VARIANT": "1", "FOTUFILM_WINDOW_CASE": name,
                             **({"FOTUFILM_WINDOW_ACK": "1"} if mode == "1" else {})},
                        stdout=output, stderr=output)
                    try:
                        if mode == "1":
                            for frame in (0, 1):
                                filename = f"{name}-{frame}.f32"
                                right = directory / filename
                                ready = Path(str(right) + ".ready")
                                deadline = time.monotonic() + 90
                                while not ready.exists():
                                    if process.poll() is not None:
                                        raise RuntimeError(f"fixture exited before complete frame: {name}, see {log}")
                                    if time.monotonic() > deadline:
                                        raise TimeoutError(f"fixture dump timeout: {name}")
                                    time.sleep(0.01)
                                left = directories[0] / filename
                                encoding = "rec709" if "rec709" in filename else "srgb" if "srgb" in filename else "linear"
                                compared = subprocess.run([str(compare), str(left), str(right), encoding],
                                                          capture_output=True, text=True)
                                comparison = json.loads(compared.stdout)
                                width, height = shapes[name]
                                comparison["expected_samples"] = width * height * 4
                                comparison["frame_size_exact"] = comparison["samples"] == width * height * 4
                                comparison["passed"] = comparison["passed"] and comparison["frame_size_exact"] and not compared.returncode
                                results.append({"case": name, "frame": filename, "B0_sha256": sha(left),
                                                "B1_sha256": sha(right), "comparison": comparison})
                                if not comparison["passed"]:
                                    raise AssertionError(f"numerical disagreement: {name}")
                                left.unlink()
                                right.unlink()
                                ready.unlink()
                                Path(str(right) + ".ack").touch()
                        if process.wait(timeout=90):
                            raise RuntimeError(f"fixture returned failure: {name}, see {log}")
                    finally:
                        if process.poll() is None:
                            # This diagnostic driver waits for ACK only after synchronous
                            # completion; termination cannot recycle an in-flight GPU slot.
                            process.terminate()
                            process.wait()
                variants = re.findall(r"^AOT_VARIANT (\w+)$", log.read_text(), re.M)
                if not variants or (mode == "0" and any("windowed" in v for v in variants)):
                    raise AssertionError("missing or incorrect runtime variant evidence")
                executions.append({"case": name, "requested_windowed": mode == "1",
                                   "actual_variants": variants})
                directories.append(directory)
            print(f"PASS {name}", flush=True)
    finally:
        summary = {"reference_sha": subprocess.check_output(
                       ["git", "-C", str(reference), "rev-parse", "HEAD"], text=True).strip(),
                   "fixture_sha256": sha(pack), "runner_sha256": sha(runner),
                   "comparator_sha256": sha(compare), "adapted_fixture_sha256": sha(driver),
                   "tool_sources_sha256": {name: sha(candidate / "tools" / name) for name in (
                       "verify-wavefront-baseline.py", "wavefront_aot_driver.py", "wavefront-compare.cpp")},
                   "wrapper_sha256": sha(out / "instrumented/wrappers.cpp"),
                   "aot_sha256": {p.name: sha(p) for p in sorted(kernels.glob("*.a"))},
                   "run_directory": str(out.relative_to(reference)),
                   "source_cases": names, "executions": executions, "results": results,
                   "complete": len(executions) == len(names) * 2
                       and len(results) == len(names) * 2
                       and all(r["comparison"]["passed"] for r in results)}
        (out / "verification.json").write_text(json.dumps(summary, indent=2) + "\n")
        (summary_root / "verification.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
