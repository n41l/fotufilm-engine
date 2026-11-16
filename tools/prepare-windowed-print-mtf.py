#!/usr/bin/env python3
"""Isolated exact-windowed Print MTF fusion/control archives; frozen remaining 62 archives."""
import argparse,hashlib,importlib.util,json,os,re,shutil,subprocess
from pathlib import Path
from windowed_print_mtf_helper import ARMS,NAME
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def families(p):return sorted(set(re.sub(r'_v\d+','',n.decode()) for n in re.findall(rb'_kernel_(frame_[A-Za-z0-9_]+?)_s0_',Path(p).read_bytes())))
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('control','halide-root','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.output.resolve();root.mkdir();old=a.control.resolve();control=json.loads((old/'control.json').read_text())
 if shutil.disk_usage(root).free<2*1024**3:raise RuntimeError('2 GiB free required before prepare')
 for n,h in control['artifacts'].items():
  if sha(old/n)!=h:raise ValueError('frozen control artifact changed')
 for n,h in control['source'].items():
  if n.startswith(('Sources/FotufilmHalide/Graph/','Sources/FotufilmHalide/Stages/')) and sha(c/n)!=h:raise ValueError('shared film math changed')
 spec=importlib.util.spec_from_file_location('v',c/'tools/generate-aot-variants.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);t=v.Table(json.loads(v.SCHEMA.read_text()))
 indices=[len(t.variants)+len(t.windowed)+i for i,x in enumerate(t.exact_windowed) if x[0]=='color_float_realtime' and x[1]=='negative_luma']
 if len(indices)!=1:raise ValueError('one exact luma twin required')
 key=subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip();halide=a.halide_root.resolve();sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip();generator=root/'generator'
 cmd=['xcrun','clang++','-std=c++17','-O2','-isysroot',sdk,'-I'+str(halide/'include'),'-I'+str(c/'Sources/FotufilmHalide/include'),str(c/'tools/generate_halide_ios.cpp'),'-L'+str(halide/'lib'),'-lHalide','-Wl,-rpath,'+str(halide/'lib'),'-o',str(generator)]
 with (root/'generator-build.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=log)
 (root/'generator-build.json').write_text(json.dumps({'command':cmd,'source_key':key,'sha256':sha(generator)},indent=2)+'\n')
 target=root/'control';(target/'kernels').mkdir(parents=True)
 for path in (old/'kernels').iterdir():
  if path.is_file():(target/'kernels'/path.name).hardlink_to(path)
 (target/'control.json').write_text(json.dumps(control,indent=2)+'\n')
 env={**os.environ};env.pop('FOTUFILM_AOT_WAVEFRONT',None);env.pop('FOTUFILM_AOT_WAVEFRONT_TRACE',None)
 for arm,enabled in ARMS.items():
  out=root/arm;out.mkdir();args=[str(generator),str(out),'--macos','--variant='+str(indices[0]),'--windowed-print-mtf-fusion='+str(int(enabled))]
  with (out/'variant.log').open('w') as log:subprocess.run(args,check=True,stdout=log,stderr=log,env=env)
  names=families(out/(NAME+'.a'))
  if not {'frame_print_mtf_horizontal','frame_print_mtf_transmittance'}.issubset(names):raise ValueError('horizontal/transmittance stores must remain')
  if enabled and 'frame_print_mtf' in names:raise ValueError('vertical result store not removed')
  if not enabled and 'frame_print_mtf' not in names:raise ValueError('vertical result store missing from control arm')
  (out/'source-key.txt').write_text(key+'\n');(out/'identity.json').write_text(json.dumps({'kind':'windowed-print-mtf','source_key':key,'fusion':enabled,'mtf_fusion':False,'coupler_fusion':False,'windowed':True,'wavefront':False,'stage_count':1,'variant_index':indices[0],'generator_sha256':sha(generator),'archives':{x.name:sha(x) for x in out.glob('*.a')},'normalized_kernel_families':names,'static_symbol_scope':'possible compiled families, not executed dispatch count or per-kernel time'},indent=2)+'\n')
  if subprocess.check_output(['python3',str(c/'tools/aot-release.py'),'key','macos'],text=True).strip()!=key:raise ValueError('source changed during build')
  print('BUILT',arm,'index',indices[0],flush=True)
 print('BUILD',root,flush=True)
if __name__=='__main__':main()
