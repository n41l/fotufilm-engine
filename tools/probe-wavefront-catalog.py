#!/usr/bin/env python3
"""Observe actual B0/B1 symbols for every public stock fixture; not a benchmark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from wavefront_aot_driver import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--kernels", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args()
    candidate = Path(__file__).resolve().parents[1]
    reference, kernels, catalog = (p.resolve() for p in (args.reference, args.kernels, args.catalog))
    if subprocess.check_output(["git", "-C", str(reference), "status", "--porcelain"], text=True):
        raise ValueError("reference must be clean")
    out = reference / "build/wavefront-stock-probe"
    out.mkdir(parents=True, exist_ok=True)
    shim = (reference / "Sources/FotufilmHalide/FotufilmHalideIOS.cpp").read_text()
    begin, end = "    const int32_t stride[] =", "    static const bool windowed_enabled"
    if shim.count(begin) != 1 or shim.count(end) != 1:
        raise ValueError("upstream reach calculation changed; inspect before adapting")
    reach_probe = out / "reach.inc"
    reach_probe.write_text(shim[shim.index(begin):shim.index(end)])
    runner = build(reference, kernels, out / "instrumented", candidate / "tools/wavefront-frame-probe.cpp",
                   definitions=(f"-I{reference}/Sources/FotufilmHalide",
                                f'-DFOTUFILM_BENCH_REACH_PROBE="{reach_probe}"'))
    manifest = json.loads(catalog.read_text())
    results = []
    try:
        for fixture in manifest["fixtures"]:
            if fixture["export_status"] != "success":
                raise ValueError("catalog includes unsuccessful export")
            pack = catalog.parent / fixture["path"]
            if hashlib.sha256(pack.read_bytes()).hexdigest() != fixture["sha256"]:
                raise ValueError("fixture hash changed")
            for mode in ("0", "1"):
                name = f"{fixture['stock']}-{fixture['size']}-{mode}"
                process = subprocess.run([str(runner), str(pack)],
                    env={**os.environ, "FOTUFILM_AOT_WINDOWED": mode, "FOTUFILM_TRACE_VARIANT": "1"},
                    capture_output=True, text=True, timeout=90)
                (out / f"{name}.log").write_text(process.stdout + process.stderr)
                record = json.loads(process.stdout)
                record.update(stock=fixture["stock"], size=fixture["size"],
                              requested_windowed=mode == "1", fixture_sha256=fixture["sha256"])
                record["fallback_reason"] = None
                if mode == "1" and record["status"] == "success" and "windowed" not in record["actual_variant"]:
                    if record["spatial_reach"] > record["upstream_window_reach_limit"]:
                        record["fallback_reason"] = "spatial reach exceeds upstream window limit"
                    else:
                        record["fallback_reason"] = "upstream selector rejection: unresolved"
                results.append(record)
                if process.returncode or record["status"] == "failure":
                    raise AssertionError(f"full-frame failure: {name}")
                if record["status"] == "success" and (record["aot_calls"] != 1
                    or (mode == "0" and "windowed" in record["actual_variant"])):
                    raise AssertionError("incorrect actual variant")
            print(f"PROBED {fixture['stock']} {fixture['size']}", flush=True)
    finally:
        (out / "capabilities.json").write_text(json.dumps({
            "scope": "R capability discovery; cold times are not performance acceptance",
            "reference_sha": manifest["base_sha"], "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "reach_diagnostic_sha256": hashlib.sha256(reach_probe.read_bytes()).hexdigest(),
            "tool_sources_sha256": {name: hashlib.sha256((candidate / "tools" / name).read_bytes()).hexdigest()
                for name in ("probe-wavefront-catalog.py", "wavefront_aot_driver.py", "wavefront-frame-probe.cpp")},
            "results": results, "complete": len(results) == len(manifest["fixtures"]) * 2,
            "all_calls_valid": len(results) == len(manifest["fixtures"]) * 2 and all(
                r["status"] == "unsupported" or (r["status"] == "success" and r["aot_calls"] == 1
                    and (r["requested_windowed"] or "windowed" not in r["actual_variant"]))
                for r in results)}, indent=2)+"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
