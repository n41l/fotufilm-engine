#!/usr/bin/env python3
"""Observe actual B0/B1 symbols for every public stock fixture; not a benchmark."""
import argparse
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
import subprocess
from wavefront_aot_driver import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--kernels", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--candidate-experiment", action="store_true",
                        help="probe C's explicit band-256 experiment; not a numerical oracle or performance run")
    args = parser.parse_args()
    candidate = Path(__file__).resolve().parents[1]
    reference, kernels, catalog = (p.resolve() for p in (args.reference, args.kernels, args.catalog))
    if args.candidate_experiment != (reference == candidate):
        raise ValueError("C requires --candidate-experiment; R must be a separate checkout")
    if not args.candidate_experiment and subprocess.check_output(["git", "-C", str(reference), "status", "--porcelain"], text=True):
        raise ValueError("reference must be clean")
    out = reference / "build/wavefront-stock-probe"
    if args.candidate_experiment:out = candidate/'build/wavefront-candidate-stock-probe'/uuid.uuid4().hex[:12]
    out.mkdir(parents=True, exist_ok=True)
    shim = (reference / "Sources/FotufilmHalide/FotufilmHalideIOS.cpp").read_text()
    begin, end = "    const int32_t stride[] =", "    static const bool windowed_enabled"
    if shim.count(begin) != 1 or shim.count(end) != 1:
        raise ValueError("upstream reach calculation changed; inspect before adapting")
    reach_probe = out / "reach.inc"
    reach_probe.write_text(shim[shim.index(begin):shim.index(end)])
    experimental = dict(definitions=(f"-I{reference}/Sources/FotufilmHalide",
                       f'-DFOTUFILM_BENCH_REACH_PROBE="{reach_probe}"', '-DFOTUFILM_AOT_WAVEFRONT_HOST=1'),
        driver_definitions=('-Dfotufilm_halide_metal_process_linear_float=fotufilm_wavefront_bench_process_linear_float',),
        adapter=candidate/'tools/wavefront-benchmark-adapter.cpp') if args.candidate_experiment else {}
    if experimental:
        runner=build(reference,kernels,out/'instrumented',candidate/'tools/wavefront-frame-probe.cpp',**experimental)
    else:runner = build(reference, kernels, out / "instrumented", candidate / "tools/wavefront-frame-probe.cpp",
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
            for mode in (("1",) if args.candidate_experiment else ("0", "1")):
                name = f"{fixture['stock']}-{fixture['size']}-{mode}"
                process = subprocess.run([str(runner), str(pack)],
                    env={**os.environ, "FOTUFILM_AOT_WINDOWED": mode, "FOTUFILM_TRACE_VARIANT": "1"},
                    capture_output=True, text=True, timeout=90)
                (out / f"{name}.log").write_text(process.stdout + process.stderr)
                record = json.loads(process.stdout)
                record.update(stock=fixture["stock"], size=fixture["size"],
                              requested_windowed=mode == "1", fixture_sha256=fixture["sha256"])
                record["fallback_reason"] = None
                if args.candidate_experiment:
                    record['requested_experimental']=True
                    record['actual_experimental']='_wavefront_' in record.get('actual_variant','')
                    policy=re.search(r'WAVEFRONT_POLICY requested=1 actual=(\d) rows=256 reason=(.*)',process.stderr)
                    if record['status']=='success' and (not policy or int(policy[1])!=int(record['actual_experimental'])):
                        raise AssertionError('actual experiment/fallback policy evidence missing')
                    record['fallback_reason']=None if record['actual_experimental'] else (policy[2] if policy else record.get('reason'))
                elif mode == "1" and record["status"] == "success" and "windowed" not in record["actual_variant"]:
                    if record["spatial_reach"] > record["upstream_window_reach_limit"]:
                        record["fallback_reason"] = "spatial reach exceeds upstream window limit"
                    else:
                        record["fallback_reason"] = "upstream selector rejection: unresolved"
                results.append(record)
                if process.returncode or record["status"] == "failure":
                    raise AssertionError(f"full-frame failure: {name}")
                expected_calls = 1
                if args.candidate_experiment and record.get('actual_experimental'):
                    counts=re.search(r'WAVEFRONT_COUNTS rows=(\d+) source_calls=(\d+) consumer_calls=(\d+) ring_rows=(\d+)',process.stderr)
                    if not counts or int(counts[1])!=record['height'] or int(counts[4])!=1024:
                        raise AssertionError('explicit source/consumer counts missing')
                    expected_calls=int(counts[2])+int(counts[3])
                    record['producer_rows']=int(counts[1]);record['producer_calls']=int(counts[2]);record['consumer_calls']=int(counts[3])
                if record["status"] == "success" and (record["aot_calls"] != expected_calls
                    or (mode == "0" and "windowed" in record["actual_variant"])):
                    raise AssertionError("incorrect actual variant")
            print(f"PROBED {fixture['stock']} {fixture['size']}", flush=True)
    finally:
        (out / "capabilities.json").write_text(json.dumps({
            "scope": "C actual experiment/fallback discovery; no numerical oracle or performance claim" if args.candidate_experiment
                else "R capability discovery; cold times are not performance acceptance",
            "requested_experimental": args.candidate_experiment,
            "engine_head": subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip(),
            "reference_sha": manifest["base_sha"], "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "reach_diagnostic_sha256": hashlib.sha256(reach_probe.read_bytes()).hexdigest(),
            "tool_sources_sha256": {name: hashlib.sha256((candidate / "tools" / name).read_bytes()).hexdigest()
                for name in ("probe-wavefront-catalog.py", "wavefront_aot_driver.py", "wavefront-frame-probe.cpp")},
            "results": results, "complete": len(results) == len(manifest["fixtures"]) * (1 if args.candidate_experiment else 2),
            "all_calls_valid": len(results) == len(manifest["fixtures"]) * (1 if args.candidate_experiment else 2) and all(
                r["status"] == "unsupported" or (r["status"] == "success" and r["aot_calls"] == (r.get("producer_calls",0)+r.get("consumer_calls",0) if r.get("actual_experimental") else 1)
                    and (r["requested_windowed"] or "windowed" not in r["actual_variant"]))
                for r in results)}, indent=2)+"\n")
    print('REPORT',out/'capabilities.json',flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
