#!/usr/bin/env python3
"""Save source-linked realization coverage without inferring GPU time."""
import argparse
import hashlib
import json
from pathlib import Path
from wavefront_region_analysis import analyze

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new evidence file required')
    report = {'performance_acceptance': False, 'traces': {}}
    for path in args.traces:
        data = path.read_bytes()
        report['traces'][str(path.resolve())] = {
            'sha256': hashlib.sha256(data).hexdigest(), **analyze(data.decode().splitlines())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(args.output)
