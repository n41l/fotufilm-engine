#!/usr/bin/env python3
"""Verify explicit row producer/consumer on frozen photographs; no performance gate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
from wavefront_aot_driver import build
from wavefront_trace import analyze_explicit
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=module_from_spec(spec);spec.loader.exec_module(b)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernels',required=True,type=Path)
    p.add_argument('--frozen-cases',required=True,type=Path)
    p.add_argument('--reference-worker',required=True,type=Path)
    p.add_argument('--diagnostic-control',type=Path)
    p.add_argument('--diagnostic-kernels',type=Path)
    p.add_argument('--bands',default='64,128,256')
    p.add_argument('--trace-kernels',type=Path)
    args=p.parse_args();repo=Path(__file__).resolve().parents[1]
    frozen=json.loads(args.frozen_cases.read_text());reference=args.reference_worker.resolve()
    if b.sha(reference)!=frozen['worker_sha256'] or (not args.diagnostic_control and b.sha(repo/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']):
        raise ValueError('frozen R/common worker changed')
    root=repo/'build/wavefront-managed'/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    runners={}
    for rows in map(int,args.bands.split(',')):
        runners[rows]=build(repo,args.kernels,root/f'band-{rows}',repo/'tools/wavefront-benchmark.mm',
            definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1',),
            driver_definitions=('-Dfotufilm_halide_metal_process_linear_float=fotufilm_wavefront_bench_process_linear_float',),
            adapter=repo/'tools/wavefront-benchmark-adapter.cpp',
            adapter_definitions=(f'-DFOTUFILM_WAVEFRONT_BAND={rows}','-DFOTUFILM_WAVEFRONT_TRACE=1','-x','objective-c++','-fblocks'),
            diagnostic_control=args.diagnostic_control,diagnostic_kernels=args.diagnostic_kernels,
            trace_overrides=sorted(args.trace_kernels.glob('fotufilm_halide_ios_*_wavefront_*.a')) if args.trace_kernels else ())
    compare=root/'compare'
    subprocess.run(['xcrun','clang++','-std=c++17','-O2',str(repo/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
    report={'scope':__doc__,'mixed_candidate_revisions':bool(args.diagnostic_control),'performance_acceptance':False,
            'current_driver_sha256':b.sha(repo/'tools/wavefront-benchmark.mm'),'frozen_R_driver_sha256':frozen['tool_sources']['wavefront-benchmark.mm'],'final_candidate_accepted':False,'results':[],'complete':False,
            'worker_sha256':{str(k):b.sha(v) for k,v in runners.items()},'R_worker_sha256':b.sha(reference),
            'frozen_cases_sha256':b.sha(args.frozen_cases),'reference_base':frozen['source_base'],
            'candidate_aot_identity':(args.kernels/'.generated-from').read_text(),
            'candidate_archive_sha256':{p.name:b.sha(p) for p in sorted(args.kernels.glob('*.a'))},
            'trace_source_key':(args.trace_kernels/'source-key.txt').read_text().strip() if args.trace_kernels else None,
            'trace_archive_sha256':{p.name:b.sha(p) for p in sorted(args.trace_kernels.glob('*.a'))} if args.trace_kernels else {},
            'source_sha256':{str(p.relative_to(repo)):b.sha(p) for p in [repo/'Sources/FotufilmHalide/FotufilmHalideIOS.cpp',
                repo/'Sources/FotufilmHalide/FotufilmHalideWavefront.h',repo/'Sources/FotufilmHalide/FotufilmWavefrontAdmission.h',
                repo/'tools/wavefront-benchmark-adapter.cpp',repo/'tools/wavefront_trace.py']}}
    def checkpoint():b.atomic_json(root/'verification.json',report)
    try:
        for case in frozen['cases']:
            out=root/case['id'];out.mkdir()
            for key in ('input','pack'):
                if b.sha(case[key])!=case[key+'_sha256']:raise ValueError('frozen input changed')
            left=out/'R.rgba32f'
            with (out/'R.jsonl').open('w') as stdout,(out/'R.stderr').open('w') as stderr:
                subprocess.run([str(reference),case['pack'],case['input'],'--dump',str(left)],
                    stdout=stdout,stderr=stderr,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0'},check=True,timeout=120)
            for rows,runner in runners.items():
                right=out/f'E-{rows}.rgba32f';log=out/f'E-{rows}.jsonl';errors=out/f'E-{rows}.stderr'
                with log.open('w') as stdout,errors.open('w') as stderr:
                    subprocess.run([str(runner),case['pack'],case['input'],'--dump',str(right)],
                        stdout=stdout,stderr=stderr,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0','FOTUFILM_METAL_POOL':'1024'},check=True,timeout=120)
                events=[json.loads(line) for line in log.read_text().splitlines()]
                calls=[e for e in events if e['type']=='call_complete']
                if len(calls)!=1 or calls[0]['status']!='success' or calls[0]['gpu_dispatches']<1 or '_wavefront_' not in calls[0]['actual_variant']:
                    raise AssertionError('actual E/GPU execution missing')
                result=subprocess.run([str(compare),str(left),str(right),'linear'],capture_output=True,text=True)
                pixels=json.loads(result.stdout);w,h=map(int,case['size'].split('x'))
                numeric=pixels['passed'] and pixels['samples']==w*h*4 and result.returncode==0
                evidence=analyze_explicit(errors.read_text().splitlines(),w,h,rows,calls[0]['aot_calls'])
                report['results'].append({'case':case['id'],'band':rows,'actual':calls[0]['actual_variant'],
                    'aot_calls':calls[0]['aot_calls'],'comparison':pixels,'trace':evidence,'passed':numeric and evidence['passed'],
                    'R_output_sha256':b.sha(left),'E_output_sha256':b.sha(right)})
                checkpoint()
                print(case['id'],rows,'numeric',numeric,'explicit_reuse',evidence['passed'],flush=True)
                if not numeric:raise AssertionError('pixel disagreement; outputs preserved')
                right.unlink()
            left.unlink()
        report['complete']=True
        report['all_checks_passed']=all(r['passed'] for r in report['results'])
    except BaseException as error:report['failure']=str(error);raise
    finally:checkpoint()
    print('REPORT',root/'verification.json',flush=True)
    return 0 if report['all_checks_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
