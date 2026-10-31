#!/usr/bin/env python3
"""Full-pixel C general/windowed regression against independent frozen R. Never a performance gate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
from wavefront_aot_driver import build
from importlib.util import spec_from_file_location, module_from_spec

spec=spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
baseline=module_from_spec(spec);spec.loader.exec_module(baseline)
sha=baseline.sha
atomic_json=baseline.atomic_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--reference-worker',required=True,type=Path)
    parser.add_argument('--kernels',required=True,type=Path)
    parser.add_argument('--frozen-cases',required=True,type=Path)
    args=parser.parse_args()
    candidate=Path(__file__).resolve().parents[1];reference=args.reference.resolve()
    if candidate==reference or subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True):
        raise ValueError('R must be a separate clean checkout')
    frozen=json.loads(args.frozen_cases.read_text());worker=args.reference_worker.resolve()
    if sha(worker)!=frozen['worker_sha256']:raise ValueError('frozen R worker changed')
    if sha(candidate/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:
        raise ValueError('common measurement/verification driver changed')
    if subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base']:
        raise ValueError('R base changed')
    for case in frozen['cases']:
        for field in ('pack','input'):
            if sha(case[field])!=case[field+'_sha256']:raise ValueError('frozen input changed')
    root=candidate/'build/wavefront-candidate'/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    driver=candidate/'tools/wavefront-benchmark.mm'
    kernels=args.kernels.resolve()
    runners={'C_B0':build(candidate,kernels,root/'legacy',driver)}
    runners['C_B1']=runners['C_B0']
    compare=root/'compare'
    subprocess.run(['xcrun','clang++','-std=c++17','-O2',str(candidate/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
    report={'scope':'full shared film graph, fixed SDR photographs, four main cases; no warm performance acceptance',
            'reference_base':frozen['source_base'],'frozen_cases_sha256':sha(args.frozen_cases),
            'common_driver_sha256':sha(driver),'R_worker_sha256':sha(worker),
            'C_worker_sha256':{k:sha(v) for k,v in runners.items()},
            'C_aot_sha256':{p.name:sha(p) for p in sorted(kernels.glob('*.a'))},
            'source_sha256':{p:sha(candidate/p) for p in (
                'Sources/FotufilmHalide/FotufilmHalideIOS.cpp','Sources/FotufilmHalide/Pipeline/Gpu.h',
                'Sources/FotufilmHalide/FotufilmHalideWavefront.h','Sources/FotufilmHalide/aot-variants.json',
                'tools/verify-wavefront-candidate.py','tools/wavefront-benchmark-adapter.cpp','tools/wavefront_aot_driver.py')},
            'results':[],'complete':False,'performance_acceptance':False,'experimental_reuse_coverage':False}
    def checkpoint():atomic_json(root/'verification.json',report)
    def invoke(label,runner,case):
        out=root/case['id'];out.mkdir(exist_ok=True)
        dump=out/f'{label}.rgba32f';log=out/f'{label}.jsonl';errors=out/f'{label}.stderr'
        with log.open('w') as stdout,errors.open('w') as stderr:
            subprocess.run([str(runner),case['pack'],case['input'],'--dump',str(dump)],
                env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1' if label=='C_B1' else '0',
                     'FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0'},
                stdout=stdout,stderr=stderr,check=True,timeout=120)
        events=[json.loads(line) for line in log.read_text().splitlines()]
        calls=[e for e in events if e['type']=='call_complete']
        identity=next(e for e in events if e['type']=='identity')
        if identity['input_sha256']!=case['input_sha256'] or identity['encoded_output']:
            raise AssertionError('verification input or linear output contract changed')
        if len(calls)!=1 or calls[0]['status']!='success' or calls[0]['aot_calls']!=1 or calls[0]['gpu_dispatches']<1:
            raise AssertionError('missing successful actual AOT/GPU execution')
        actual=calls[0]['actual_variant']
        if ('windowed' in actual)!=(label=='C_B1') or '_wavefront_' in actual:
            raise AssertionError('legacy selection changed')
        return dump,actual
    try:
        for case in frozen['cases']:
            left,actual=invoke('R_B0',worker,case)
            for label,runner in runners.items():
                right,variant=invoke(label,runner,case)
                result=subprocess.run([str(compare),str(left),str(right),'linear'],capture_output=True,text=True)
                comparison=json.loads(result.stdout)
                width,height=map(int,case['size'].split('x'))
                comparison['passed']=comparison['passed'] and comparison['samples']==width*height*4 and result.returncode==0
                report['results'].append({'case':case['id'],'candidate':label,'R_actual':actual,'C_actual':variant,
                    'R_output_sha256':sha(left),'C_output_sha256':sha(right),'comparison':comparison})
                checkpoint()
                if not comparison['passed']:raise AssertionError('pixel disagreement; failed dumps preserved')
                right.unlink()
                print('PASS',case['id'],label,flush=True)
            left.unlink()
        report['complete']=len(report['results'])==len(frozen['cases'])*len(runners)
    except BaseException as error:
        report['failure']=str(error);raise
    finally:checkpoint()
    atomic_json(root.parent/'latest.json',{'report':str(root/'verification.json')})
    print('REPORT',root/'verification.json',flush=True)


if __name__=='__main__':main()
