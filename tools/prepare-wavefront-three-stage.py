#!/usr/bin/env python3
"""Build matching two-/three-stage private AOT sets with a frozen legacy control.

Diagnostic composite only. Requires an existing verified wide-diagnostic control.
Creates a new directory and never stamps a current-source full release.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('control','halide-root','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();c=Path(__file__).resolve().parents[1];out=a.output.resolve();old=a.control.resolve()
    if out.exists():raise ValueError('new output directory required')
    control=json.loads((old/'control.json').read_text())
    for name,h in control['artifacts'].items():
        if sha(old/name)!=h:raise ValueError('frozen control artifact changed')
    for name,h in control['source'].items():
        if name.startswith(('Sources/FotufilmHalide/Stages/','Sources/FotufilmHalide/Graph/')) and sha(c/name)!=h:
            raise ValueError('shared film math changed')
    s=importlib.util.spec_from_file_location('variants',c/'tools/generate-aot-variants.py')
    v=importlib.util.module_from_spec(s);s.loader.exec_module(v);table=v.Table(json.loads(v.SCHEMA.read_text()))
    offset=len(table.variants)+len(table.windowed)+len(table.exact_windowed)
    lights=list(dict.fromkeys((v,n,m) for v,n,m,_,_ in table.wavefront))
    source_indices=list(range(offset+len(table.wavefront),offset+len(table.wavefront)+len(lights)))
    finals=[offset+i for i,(_,_,_,_,rows) in enumerate(table.wavefront) if rows==512]
    helpers=list(range(source_indices[-1]+1,source_indices[-1]+1+len(lights)))
    count=len(table.wavefront)+len(lights)
    key=subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip()
    out.mkdir(parents=True);generator=out/'generator';halide=a.halide_root.resolve()
    sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
    command=['xcrun','clang++','-std=c++17','-O2','-isysroot',sdk,
        '-I'+str(halide/'include'),'-I'+str(c/'Sources/FotufilmHalide/include'),str(c/'tools/generate_halide_ios.cpp'),
        '-L'+str(halide/'lib'),'-lHalide','-Wl,-rpath,'+str(halide/'lib'),'-o',str(generator)]
    with (out/'generator-build.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=log)
    (out/'generator-build.json').write_text(json.dumps({'command':command,'source_key':key,'generator_sha256':sha(generator)},indent=2)+'\n')
    for kind,stage,trace,indices in (('two-normal',2,False,list(range(offset,offset+count))),
            ('three-normal',3,False,finals+helpers),('three-trace',3,True,finals+source_indices+helpers)):
        target=out/kind;target.mkdir()
        if stage==3:
            for path in (out/'two-normal').iterdir():
                if path.suffix in ('.a','.h'):(target/path.name).hardlink_to(path)
        fresh=target/'fresh';fresh.mkdir()
        env={**os.environ,'FOTUFILM_AOT_WAVEFRONT':'1'};env.pop('FOTUFILM_AOT_WAVEFRONT_TRACE',None)
        if trace:env['FOTUFILM_AOT_WAVEFRONT_TRACE']='1'
        for index in indices:
            args=[str(generator),str(fresh),'--macos',f'--variant={index}']+(['--three-stage'] if stage==3 else [])
            with (fresh/f'variant-{index}.log').open('w') as log:subprocess.run(args,check=True,env=env,stdout=log,stderr=log)
        for path in fresh.iterdir():
            if path.suffix not in ('.a','.h'):continue
            dest=target/path.name
            if dest.exists():dest.unlink()
            dest.hardlink_to(path)
        if stage==3:
            (target/'fotufilm_three_stage_declarations.h').write_text(''.join('#include "'+path.name+'"\n' for path in sorted(target.glob('*_wavefront_halation_*.h'))))
        (target/'source-key.txt').write_text(key+'\n')
        (target/'identity.json').write_text(json.dumps({'source_key':key,'stage_count':stage,'trace':trace,
            'generator_sha256':sha(generator),'variant_indices':indices,'fresh_archives':{x.name:sha(x) for x in fresh.glob('*.a')},
            'archives':{x.name:sha(x) for x in target.glob('*.a')}},indent=2)+'\n')
        if subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip()!=key:
            raise ValueError('generator sources drifted during build')
    for stage in (2,3):
        target=out/f'control-{stage}';kernels=target/'kernels';kernels.mkdir(parents=True)
        for path in (old/'kernels').iterdir():
            if path.is_file():(kernels/path.name).hardlink_to(path)
        (target/'control.json').write_text(json.dumps({**control,'experimental_archive_count':count+(len(lights) if stage==3 else 0),
            'experiment_stage_count':stage},indent=2)+'\n')
    print(out)


if __name__=='__main__':main()
