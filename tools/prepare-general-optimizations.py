#!/usr/bin/env python3
"""Build isolated whole-frame Metal optimization arms with a frozen legacy control.

Only two existing general float-realtime archives are replaced per arm. This is
an explicit diagnostic composite; no current-source release stamp is produced.
"""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
from prepare_general_helper import ARMS
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('control','halide-root','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.output.resolve();root.mkdir();old=a.control.resolve();control=json.loads((old/'control.json').read_text())
 for n,h in control['artifacts'].items():
  if sha(old/n)!=h:raise ValueError('frozen legacy artifact changed')
 for n,h in control['source'].items():
  if n.startswith(('Sources/FotufilmHalide/Graph/','Sources/FotufilmHalide/Stages/')) and sha(c/n)!=h:raise ValueError('shared film math changed')
 spec=importlib.util.spec_from_file_location('v',c/'tools/generate-aot-variants.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);table=v.Table(json.loads(v.SCHEMA.read_text()))
 indices=[i for i,x in enumerate(table.variants) if x[0] in ('color_float_realtime','monochrome_float_realtime')]
 if len(indices)!=2:raise ValueError('exact two general variant classes required')
 key=subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip();halide=a.halide_root.resolve();sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip();generator=root/'generator'
 cmd=['xcrun','clang++','-std=c++17','-O2','-isysroot',sdk,'-I'+str(halide/'include'),'-I'+str(c/'Sources/FotufilmHalide/include'),str(c/'tools/generate_halide_ios.cpp'),'-L'+str(halide/'lib'),'-lHalide','-Wl,-rpath,'+str(halide/'lib'),'-o',str(generator)]
 with (root/'generator-build.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=log)
 (root/'generator-build.json').write_text(json.dumps({'command':cmd,'source_key':key,'sha256':sha(generator)},indent=2)+'\n')
 target=root/'control';(target/'kernels').mkdir(parents=True)
 for path in (old/'kernels').iterdir():
  if path.is_file():(target/'kernels'/path.name).hardlink_to(path)
 (target/'control.json').write_text(json.dumps(control,indent=2)+'\n')
 env={**os.environ};env.pop('FOTUFILM_AOT_WAVEFRONT',None);env.pop('FOTUFILM_AOT_WAVEFRONT_TRACE',None)
 for arm,bits in ARMS.items():
  out=root/arm;out.mkdir()
  for index in indices:
   args=[str(generator),str(out),'--macos','--variant='+str(index),'--general-optimizations='+str(bits)]
   with (out/f'variant-{index}.log').open('w') as log:subprocess.run(args,check=True,stdout=log,stderr=log,env=env)
  (out/'source-key.txt').write_text(key+'\n')
  (out/'identity.json').write_text(json.dumps({'kind':'general','source_key':key,'optimizations':bits,'windowed':False,'wavefront':False,'stage_count':1,'variant_indices':indices,'generator_sha256':sha(generator),'archives':{x.name:sha(x) for x in out.glob('*.a')}},indent=2)+'\n')
  if subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip()!=key:raise ValueError('generator sources changed')
  print('BUILT',arm,bits,flush=True)
 print('BUILD',root,flush=True)
if __name__=='__main__':main()
