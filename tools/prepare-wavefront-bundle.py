#!/usr/bin/env python3
"""Matching original/bundled two-stage AOT with a verified frozen legacy control.

Diagnostic composite only. No current-source full-release stamp is produced.
"""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('control','halide-root','output'):p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();c=Path(__file__).resolve().parents[1];root=a.output.resolve();old=a.control.resolve()
 if root.exists():raise ValueError('new output directory required')
 control=json.loads((old/'control.json').read_text())
 for n,h in control['artifacts'].items():
  if sha(old/n)!=h:raise ValueError('frozen legacy artifact changed')
 for n,h in control['source'].items():
  if n.startswith(('Sources/FotufilmHalide/Graph/','Sources/FotufilmHalide/Stages/')) and sha(c/n)!=h:raise ValueError('shared film math changed')
 manifest=json.loads((c/'Sources/FotufilmHalide/aot-variants.json').read_text())
 declaration=dict(manifest['wavefront_experiment']['bundle_research']);declaration.pop('bands',None)
 if declaration!={'band':512,'light_ring_rows':2048,'producer_margin':360,'outputs':['light','halation_0','halation_1','halation_2'],'field_layout':'planar-float32'}:raise ValueError('unsupported bundle declaration')
 spec=importlib.util.spec_from_file_location('variants',c/'tools/generate-aot-variants.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);table=v.Table(manifest)
 offset=len(table.variants)+len(table.windowed)+len(table.exact_windowed);lights=list(dict.fromkeys((v,n,m) for v,n,m,_,_ in table.wavefront));count=len(table.wavefront)+len(lights)
 normal=list(range(offset,offset+count));bundle=list(range(offset+count,offset+count+len(lights)+len(table.bundle)))
 key=subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip();root.mkdir(parents=True)
 sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip();halide=a.halide_root.resolve();generator=root/'generator'
 command=['xcrun','clang++','-std=c++17','-O2','-isysroot',sdk,'-I'+str(halide/'include'),'-I'+str(c/'Sources/FotufilmHalide/include'),str(c/'tools/generate_halide_ios.cpp'),'-L'+str(halide/'lib'),'-lHalide','-Wl,-rpath,'+str(halide/'lib'),'-o',str(generator)]
 with (root/'generator-build.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=log)
 (root/'generator-build.json').write_text(json.dumps({'command':command,'source_key':key,'sha256':sha(generator)},indent=2)+'\n')
 env={**os.environ,'FOTUFILM_AOT_WAVEFRONT':'1'};env.pop('FOTUFILM_AOT_WAVEFRONT_TRACE',None)
 for kind,cut,trace,indices in (('control-normal',False,False,normal),('bundle-normal',True,False,bundle),('bundle-trace',True,True,bundle)):
  target=root/kind;target.mkdir();fresh=target/'fresh';fresh.mkdir()
  if cut:
   for path in (root/'control-normal').iterdir():
    if path.suffix in ('.a','.h'):(target/path.name).hardlink_to(path)
  for index in indices:
   args=[str(generator),str(fresh),'--macos',f'--variant={index}']+(['--bundle'] if cut else [])
   with (fresh/f'variant-{index}.log').open('w') as log:subprocess.run(args,check=True,stdout=log,stderr=log,env={**env,**({'FOTUFILM_AOT_WAVEFRONT_TRACE':'1'} if trace else {})})
  for path in fresh.iterdir():
   if path.suffix in ('.a','.h'):(target/path.name).hardlink_to(path)
  if cut:(target/'fotufilm_bundle_declarations.h').write_text(''.join('#include "'+x.name+'"\n' for x in sorted(target.glob('*_wavefront_bundle*.h'))))
  (target/'source-key.txt').write_text(key+'\n')
  (target/'identity.json').write_text(json.dumps({'source_key':key,'stage_count':2,'cut':'bundle' if cut else 'post_mtf','trace':trace,'generator_sha256':sha(generator),'variant_indices':indices,'archives':{x.name:sha(x) for x in target.glob('*.a')}},indent=2)+'\n')
  if subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip()!=key:raise ValueError('generator sources drifted')
 for name,cut in (('control-2',False),('control-bundle',True)):
  target=root/name;(target/'kernels').mkdir(parents=True)
  for path in (old/'kernels').iterdir():
   if path.is_file():(target/'kernels'/path.name).hardlink_to(path)
  data={**control,'experimental_archive_count':count+(len(bundle) if cut else 0),'experiment_stage_count':2,'experiment_cut':'bundle' if cut else 'post_mtf'}
  (target/'control.json').write_text(json.dumps(data,indent=2)+'\n')
 print(root)
if __name__=='__main__':main()
