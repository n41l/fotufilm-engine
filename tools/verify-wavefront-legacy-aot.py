#!/usr/bin/env python3
"""Compare every legacy AOT class in separate clean-R and current-C executables."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import uuid

spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','reference-kernels','kernels','pack'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();candidate=Path(__file__).resolve().parents[1]
    reference=args.reference.resolve()
    if reference==candidate or subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True):
        raise ValueError('R must remain a separate clean checkout')
    root=candidate/'build/wavefront-legacy-aot'/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    driver=candidate/'tools/aot-parity.mm'
    report={'scope':__doc__,'performance_acceptance':False,'complete':False,
            'reference_base':subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip(),
            'common_driver_sha256':b.sha(driver),'pack_sha256':b.sha(args.pack),'engines':{}}
    runners={}
    def checkpoint():b.atomic_json(root/'verification.json',report)
    try:
        for label,repo,kernels in (('R',reference,args.reference_kernels.resolve()),('C',candidate,args.kernels.resolve())):
            stamp=(kernels/'.generated-from').read_text()
            expected=subprocess.check_output(['python3',str(repo/'tools/aot-release.py'),'key','macos'],text=True).strip()
            if stamp.split()[0]!=expected:raise ValueError('AOT source/configuration fingerprint changed')
            runner=root/f'{label}-runner';runners[label]=runner
            archives=sorted(kernels.glob('*.a'))
            with (root/f'{label}-build.log').open('w') as log:
                subprocess.run(['xcrun','clang++','-std=c++17','-O2','-fobjc-arc','-DFOTUFILM_HALIDE_IOS_AOT=1',
                    '-target','arm64-apple-macos14.0',f'-I{kernels}',f'-I{repo}/Sources/FotufilmHalide/include',
                    str(driver),str(repo/'Sources/FotufilmHalide/FotufilmHalideIOS.cpp'),*map(str,archives),
                    '-framework','Metal','-framework','Foundation','-o',str(runner)],stdout=log,stderr=log,check=True)
            count=int(subprocess.check_output([str(runner),'--count'],text=True))
            out=root/label;out.mkdir()
            hashes={}
            report['engines'][label]={'aot_identity':stamp,'runner_sha256':b.sha(runner),'classes':count,
                'archive_sha256':{p.name:b.sha(p) for p in archives},'output_sha256':hashes}
            for index in range(count):
                dump=out/f'{index:03d}.bin'
                with (out/f'{index:03d}.log').open('w') as log:
                    subprocess.run([str(runner),f'--pack={args.pack.resolve()}',f'--variant={index}',f'--out={dump}'],
                        stdout=log,stderr=log,check=True,timeout=120,
                        env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0'})
                hashes[dump.name]=b.sha(dump);checkpoint()
            print('EXECUTED',label,count,'legacy classes',flush=True)
        if report['engines']['R']['classes']!=report['engines']['C']['classes']:
            raise AssertionError('legacy class list changed')
        # Both builds use the same offline compiler and legacy expressions: require zero error.
        with (root/'comparison.log').open('w') as log:
            result=subprocess.run([str(runners['C']),'--compare',str(root/'R'),str(root/'C'),
                '--tolerance=0','--categorical-budget=0'],stdout=log,stderr=log)
        report['comparison']=(root/'comparison.log').read_text()
        report['passed']=result.returncode==0
        report['byte_identical_records']=report['engines']['R']['output_sha256']==report['engines']['C']['output_sha256']
        if not report['passed']:raise AssertionError('legacy R/C pixel regression; dumps preserved')
        report['complete']=True
        for label in ('R','C'):
            for dump in (root/label).glob('*.bin'):dump.unlink()
    except BaseException as error:report['failure']=str(error);raise
    finally:checkpoint()
    print('REPORT',root/'verification.json',flush=True)


if __name__=='__main__':main()
