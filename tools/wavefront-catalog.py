#!/usr/bin/env python3
"""Export public-stock fixtures from an unmodified engine CLI.

This records inputs, not wavefront eligibility. Runtime variant/reach/fallback
must be observed separately. Each resolution gets its own physical-scale pack.
"""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--size", action="append", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cli = args.cli.resolve()
    listing = subprocess.check_output([str(cli), "--list-stocks"], text=True)
    records = []
    stocks = [line.split("\t", 1)[0] for line in listing.splitlines()
              if line and not line.startswith("example-")]
    for size in args.size:
        width, height = map(int, size.split("x"))
        if width <= 0 or height <= 0:
            raise ValueError("invalid frame size")
        for stock in stocks:
            path = args.output / f"{stock}-{size}.fswp"
            exported = subprocess.run([str(cli), "--dump-wasm-pack", str(path.resolve()),
                                       "--stock", stock, "--pack-size", size, "--seed", "42"],
                                      capture_output=True, text=True)
            log = args.output / f"{stock}-{size}.log"
            log.write_text(exported.stdout + exported.stderr)
            if exported.returncode:
                records.append({"stock": stock, "size": size, "export_status": "failure",
                                "returncode": exported.returncode, "log": log.name})
                continue
            data = path.read_bytes()
            header = struct.unpack_from("<10I", data)
            if data[:4] != b"FSWP" or header[2:4] != (width, height):
                raise ValueError(f"invalid export: {path}")
            records.append({"stock": stock, "size": size, "export_status": "success",
                            "path": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                            "pack_version": header[1], "feature_mask": header[4],
                            "seed": header[5], "configuration_floats": header[6],
                            "runtime_eligibility": "not_measured"})
    manifest = {"base_sha": args.base_sha, "cli_sha256": hashlib.sha256(cli.read_bytes()).hexdigest(),
                "non_example_stock_count": len(stocks), "sizes": args.size, "fixtures": records}
    (args.output / "catalog.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"stocks": len(stocks), "fixtures": len(records),
                      "failures": sum(r["export_status"] != "success" for r in records)}))
    return int(any(r["export_status"] != "success" for r in records))


if __name__ == "__main__":
    raise SystemExit(main())
