#!/usr/bin/env python3
"""Build a clean-R worker and freeze the four photographic correctness inputs, without timing."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
from wavefront_aot_driver import build

spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','reference-kernels','worker-output','catalog','prepared','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();candidate=Path(__file__).resolve().parents[1];reference=args.reference.resolve()
    if reference==candidate or subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True):
        raise ValueError('R must remain a separate clean checkout')
    if args.output.exists():raise ValueError('preserve the existing frozen manifest; choose a new output')
    worker_output=args.worker_output.resolve()
    if not worker_output.is_relative_to(reference/'build'):
        raise ValueError('keep R generated workers in its independent build directory')
    base=subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()
    catalog=json.loads(args.catalog.read_text());prepared=json.loads(args.prepared.read_text())
    if base!=catalog['base_sha']:raise ValueError('stock fixtures belong to another base')
    cases=[]
    for stock in ('portra400','hp5plus400'):
        for workload in prepared['workloads']:
            size=f'{workload["width"]}x{workload["height"]}'
            pack=next(f for f in catalog['fixtures'] if f['stock']==stock and f['size']==size)
            path=(args.catalog.parent/pack['path']).resolve();image=Path(workload['path']).resolve()
            if b.sha(path)!=pack['sha256'] or b.sha(image)!=workload['sha256']:
                raise ValueError('frozen input changed')
            cases.append({'id':f'{stock}-coffee-{size}','stock':stock,'size':size,'pack':str(path),
                'pack_sha256':pack['sha256'],'input':str(image),'input_sha256':workload['sha256']})
    if len(cases)!=4 or {c['size'] for c in cases}!={'1920x1080','3840x2160'}:
        raise ValueError('expected the four original photographic correctness cases')
    driver=candidate/'tools/wavefront-benchmark.mm'
    worker=build(reference,args.reference_kernels,worker_output,driver)
    manifest={'verification_only':True,'B_ref_frozen':False,'source_base':base,
        'worker':str(worker),'worker_sha256':b.sha(worker),'prepared_sha256':b.sha(args.prepared),
        'catalog_sha256':b.sha(args.catalog),'cases':cases,
        'reference_aot_identity':(args.reference_kernels/'.generated-from').read_text(),
        'tool_sources':{p.name:b.sha(p) for p in (Path(__file__),driver,candidate/'tools/wavefront_aot_driver.py')}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    b.atomic_json(args.output,manifest)
    print('WORKER',worker,flush=True);print('FROZEN',args.output.resolve(),flush=True)


if __name__=='__main__':main()
