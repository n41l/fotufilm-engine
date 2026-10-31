#!/usr/bin/env python3
"""Build isolated wide-band kernels with a frozen, unchanged legacy control.

This is a diagnostic composite, not a complete current-source release AOT set.
No generated-from stamp for a current-source release is written.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('control-kernels','control-proof','halide-root','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--control-ref',required=True)
    a=p.parse_args();c=Path(__file__).resolve().parents[1];out=a.output.resolve()
    if out.exists():raise ValueError('new output directory required')
    proof=json.loads(a.control_proof.read_text());old=a.control_kernels.resolve()
    if not proof['complete'] or any(not row['comparison']['passed'] for row in proof['results']):
        raise ValueError('complete passing normal control proof required')
    for name,h in proof['C_aot_sha256'].items():
        if sha(old/name)!=h:raise ValueError('frozen control archive changed')
    for name,h in proof['source_sha256'].items():
        if name.startswith('Sources/'):
            if hashlib.sha256(subprocess.check_output(['git','-C',str(c),'show',a.control_ref+':'+name])).hexdigest()!=h:
                raise ValueError('control source ref does not match pixel proof')
    out.mkdir(parents=True);control=out/'control';kernels=control/'kernels';kernels.mkdir(parents=True)
    for path in old.iterdir():
        if path.is_file() and (path.suffix in ('.a','.h') or path.name=='.generated-from') and '_wavefront_' not in path.name:
            (kernels/path.name).hardlink_to(path)
    release=module('release',c/'tools/aot-release.py');variants=module('variants',c/'tools/generate-aot-variants.py')
    source={}
    for name in sorted(set(release.generator_inputs())|{'Sources/FotufilmHalide/FotufilmHalideIOS.cpp','Sources/FotufilmHalide/FotufilmHalideWavefront.h'}):
        data=subprocess.check_output(['git','-C',str(c),'show',a.control_ref+':'+name]);h=hashlib.sha256(data).hexdigest()
        if name.startswith(('Sources/FotufilmHalide/Stages/','Sources/FotufilmHalide/Graph/')) and sha(c/name)!=h:
            raise ValueError('shared film expressions differ from frozen control')
        source[name]=h;target=control/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    table=variants.Table(json.loads(variants.SCHEMA.read_text()))
    offset=len(table.variants)+len(table.windowed)+len(table.exact_windowed)
    lights=list(dict.fromkeys((v,n,m) for v,n,m,_,_ in table.wavefront))
    count=len(table.wavefront)+len(lights)
    (control/'control.json').write_text(json.dumps({'scope':__doc__,'source_commit':a.control_ref,
        'control_source_key':(old/'.generated-from').read_text().split()[0],'normal_proof_sha256':sha(a.control_proof),
        'source':source,'artifacts':{str(path.relative_to(control)):sha(path) for path in kernels.iterdir()},
        'experimental_archive_count':count},indent=2)+'\n')
    sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
    generator=out/'generate-halide-aot';halide=a.halide_root.resolve()
    compiler_env=dict(os.environ)
    for name in ('SDKROOT','IPHONEOS_DEPLOYMENT_TARGET','MACOSX_DEPLOYMENT_TARGET'):compiler_env.pop(name,None)
    with (out/'generator-build.log').open('w') as log:
        subprocess.run(['xcrun','clang++','-std=c++17','-O2','-isysroot',sdk,'-target',platform.machine()+'-apple-macos',
            '-I'+str(halide/'include'),'-I'+str(c/'Sources/FotufilmHalide/include'),str(c/'tools/generate_halide_ios.cpp'),
            '-L'+str(halide/'lib'),'-lHalide','-Wl,-rpath,'+str(halide/'lib'),'-o',str(generator)],check=True,stdout=log,stderr=log,env=compiler_env)
    for trace in (False,True):
        target=out/('trace-kernels' if trace else 'kernels');target.mkdir()
        env={**os.environ,'FOTUFILM_AOT_WAVEFRONT':'1'};env.pop('FOTUFILM_AOT_WAVEFRONT_TRACE',None)
        if trace:env['FOTUFILM_AOT_WAVEFRONT_TRACE']='1'
        indices=[offset+i for i,(_,_,_,_,rows) in enumerate(table.wavefront) if not trace or rows==512]
        indices+=list(range(offset+len(table.wavefront),offset+count))
        key=subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True,env=env).strip()
        for index in indices:
            with (target/f'variant-{index}.log').open('w') as log:
                subprocess.run([str(generator),str(target),'--macos',f'--variant={index}'],check=True,env=env,stdout=log,stderr=log)
        (target/'source-key.txt').write_text(key+'\n')
        (target/'identity.json').write_text(json.dumps({'generator_sha256':sha(generator),'source_key':key,
            'variant_indices':indices,'archives':{path.name:sha(path) for path in target.glob('*.a')}},indent=2)+'\n')
    print(out)

if __name__=='__main__':main()
