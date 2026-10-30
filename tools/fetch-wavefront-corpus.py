#!/usr/bin/env python3
"""Fetch only the fixed, checksum-verified public SDR corpus; no Python image dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proxy')
    args = parser.parse_args()
    manifest_path = Path(__file__).with_name('wavefront-corpus.json')
    manifest = json.loads(manifest_path.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    for item in manifest['images']:
        if Path(item['file']).name != item['file']:
            raise ValueError('unsafe corpus filename')
        destination = args.output / item['file']
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError(f'existing file differs; preserved: {destination}')
            continue
        with tempfile.NamedTemporaryFile(dir=args.output, delete=False) as temporary:
            pending = Path(temporary.name)
        try:
            command = ['curl', '-q', '--fail', '--location', '--retry', '2', '--max-time', '60']
            if args.proxy:
                command += ['--proxy', args.proxy]
            subprocess.run([*command, '--silent', '--show-error', '--output', str(pending), item['url']], check=True)
            if hashlib.sha256(pending.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError(f'upstream checksum mismatch: {item["file"]}')
            pending.rename(destination)
        finally:
            pending.unlink(missing_ok=True)
        print('VERIFIED', item['file'], flush=True)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
