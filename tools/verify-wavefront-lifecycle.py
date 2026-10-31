#!/usr/bin/env python3
"""Independent R/C same-process frame history and private-admission regressions."""
import argparse
import gzip
import shutil
import json
import os
from pathlib import Path
import subprocess
import uuid
from wavefront_aot_driver import build
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=module_from_spec(spec);spec.loader.exec_module(b)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',required=True,type=Path)
    p.add_argument('--reference-kernels',required=True,type=Path)
    p.add_argument('--kernels',required=True,type=Path)
    p.add_argument('--catalog',required=True,type=Path)
    p.add_argument('--band',type=int,choices=(64,128,256,512),default=256)
    p.add_argument('--compress-reference',action='store_true',help='losslessly compress R dumps before running C to limit temporary disk use')
    p.add_argument('--diagnostic-control',type=Path)
    p.add_argument('--diagnostic-kernels',type=Path)
    args=p.parse_args();candidate=Path(__file__).resolve().parents[1];reference=args.reference.resolve()
    if candidate==reference or subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True):
        raise ValueError('R must remain a separate clean checkout')
    catalog=json.loads(args.catalog.read_text())
    if subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()!=catalog['base_sha']:
        raise ValueError('R fixture base changed')
    packs=[]
    for stock in ('portra400','hp5plus400'):
        fixture=next(f for f in catalog['fixtures'] if f['stock']==stock and f['size']=='1920x1080')
        path=(args.catalog.parent/fixture['path']).resolve()
        if b.sha(path)!=fixture['sha256']:raise ValueError('stock pack changed')
        packs.append(path)
    root=candidate/'build/wavefront-lifecycle'/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    driver=candidate/'tools/wavefront-lifecycle.cpp'
    runners={'R':build(reference,args.reference_kernels,root/'R-build',driver),
             'C':build(candidate,args.kernels,root/'C-build',driver,
                 definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1','-DFOTUFILM_WAVEFRONT_TESTING=1'),
                 driver_definitions=('-DFOTUFILM_WAVEFRONT_OPTIONS_TESTS=1',f'-DFOTUFILM_LIFECYCLE_BAND={args.band}',),
                 **(dict(diagnostic_control=args.diagnostic_control,diagnostic_kernels=args.diagnostic_kernels) if args.diagnostic_control else {}))}
    compare=root/'compare'
    subprocess.run(['xcrun','clang++','-std=c++17','-O2',str(candidate/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
    report={'scope':'fourteen compared synchronous calls plus a C-only injected submission failure per engine in one process; A/B/A, geometry, stock, input, seed, alpha, camera gate, stage/still/exact/band fallback',
            'mixed_candidate_revisions':bool(args.diagnostic_control),'final_candidate_accepted':False,
            'reference_base':catalog['base_sha'],'driver_sha256':b.sha(driver),
            'runner_sha256':{k:b.sha(v) for k,v in runners.items()},
            'pack_sha256':{p.name:b.sha(p) for p in packs},'results':[],'complete':False,'performance_acceptance':False}
    def checkpoint():b.atomic_json(root/'verification.json',report)
    try:
        frames={}
        for label,runner in runners.items():
            out=root/label;out.mkdir()
            with (out/'events.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
                subprocess.run([str(runner),*map(str,packs),str(out)],stdout=stdout,stderr=stderr,check=True,
                    timeout=600,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0','FOTUFILM_METAL_POOL':'1024'})
            events=[json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
            frames[label]=[e for e in events if e['type']=='frame']
            if len(frames[label])!=14:raise AssertionError('missing lifecycle frames')
            if label=='R' and args.compress_reference:
                report['reference_dump_compression']={}
                for event in frames[label]:
                    path=out/(str(event['frame'])+'.rgba32f');compressed=path.with_suffix(path.suffix+'.gz')
                    checksum=b.sha(path)
                    with path.open('rb') as src,gzip.open(compressed,'wb',compresslevel=1) as dst:
                        shutil.copyfileobj(src,dst,1024*1024)
                    report['reference_dump_compression'][str(event['frame'])]={'raw_sha256':checksum,'gzip_sha256':b.sha(compressed)}
                    path.unlink()
                checkpoint()
            if label=='C' and not any(e['type']=='invalid_options' and e['passed'] and e['checks']==4 for e in events):
                raise AssertionError('invalid-option rejection checks missing')
            if label=='C' and not any(e['type']=='injected_failure' and e['passed'] and e['drained'] for e in events):
                raise AssertionError('injected failure/drain/recovery checks missing')
        for left,right in zip(frames['R'],frames['C']):
            frame=left['frame']
            if frame!=right['frame']:raise AssertionError('frame history changed')
            expected=frame<4 or frame==9 or frame==12 or frame==13
            if right['actual_mode']!=int(expected) or ('_wavefront_' in right['actual_variant'])!=expected:
                raise AssertionError('fallback/legacy was counted as E')
            lp=root/'R'/f'{frame}.rgba32f';rp=root/'C'/f'{frame}.rgba32f'
            compressed=lp.with_suffix(lp.suffix+'.gz')
            if args.compress_reference:
                proof=report['reference_dump_compression'][str(frame)]
                if b.sha(compressed)!=proof['gzip_sha256']:raise AssertionError('compressed R evidence changed')
                with gzip.open(compressed,'rb') as src,lp.open('wb') as dst:
                    shutil.copyfileobj(src,dst,1024*1024)
                if b.sha(lp)!=proof['raw_sha256']:raise AssertionError('R decompression changed pixels')
            result=subprocess.run([str(compare),str(lp),str(rp),left['encoding']],capture_output=True,text=True)
            comparison=json.loads(result.stdout)
            passed=comparison['passed'] and result.returncode==0 and comparison['samples']==left['width']*left['height']*4
            report['results'].append({'R':left,'C':right,'R_output_sha256':b.sha(lp),'C_output_sha256':b.sha(rp),
                                      'comparison':comparison,'passed':passed})
            checkpoint()
            if not passed:raise AssertionError('lifecycle pixel disagreement; failed outputs preserved')
            lp.unlink();rp.unlink()
            if args.compress_reference:compressed.unlink()
            print('PASS frame',frame,right['actual_variant'],flush=True)
        report['complete']=True
    except BaseException as error:
        report['failure']=str(error);raise
    finally:checkpoint()
    b.atomic_json(root.parent/'latest.json',{'report':str(root/'verification.json')})
    print('REPORT',root/'verification.json',flush=True)


if __name__=='__main__':main()
