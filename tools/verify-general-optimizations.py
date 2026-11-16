#!/usr/bin/env python3
"""Independent frozen R-B0/R-B1 and whole-frame general single-option pixel proof.

Only the two current declared general archives replace frozen legacy kernels.
All arms retain one AOT call, full feature graph, original precision and geometry.
"""
import argparse,hashlib,json,os,subprocess,shutil
from pathlib import Path
from wavefront_aot_driver import build
from prepare_general_helper import ARMS

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','output','fixtures','reference'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--reuse-workers',type=Path)
 a=p.parse_args();root=a.output.resolve();root.mkdir();a.build=a.build.resolve();ref=a.reference.resolve();frozen=json.loads(a.fixtures.read_text());rw=ref/'build/wavefront-benchmark-v2/instrumented/runner'
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('R must remain clean')
 if subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base'] or sha(rw)!=frozen['worker_sha256']:raise ValueError('R identity changed')
 if sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common driver changed')
 workers={}
 reuse=json.loads(a.reuse_workers.read_text()) if a.reuse_workers else None
 for arm,bits in ARMS.items():
  identity=json.loads((a.build/arm/'identity.json').read_text())
  if identity['optimizations']!=bits or identity['windowed'] or identity['wavefront']:raise ValueError('general arm identity mismatch')
  if reuse:
   workers[arm]=Path(reuse['workers'][arm]['path'])
   if sha(workers[arm])!=reuse['workers'][arm]['sha256'] or reuse['source_key']!=(a.build/arm/'source-key.txt').read_text().strip():raise ValueError('reused worker changed')
   continue
  workers[arm]=build(c,a.build/'control/kernels',root/arm,c/'tools/wavefront-benchmark.mm',diagnostic_control=a.build/'control',diagnostic_kernels=a.build/arm,general_research=True)
 compare=root/'compare';subprocess.run(['xcrun','clang++','-O2','-std=c++17',str(c/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'B_ref_frozen':False,'reference_base':frozen['source_base'],
  'workers':{k:{'path':str(v),'sha256':sha(v)} for k,v in {**workers,'R-B0':rw,'R-B1':rw}.items()},
  'reused_workers_from':str(a.reuse_workers.resolve()) if a.reuse_workers else None,'source_key':(a.build/'G0/source-key.txt').read_text().strip(),'arm_options':ARMS,'sources':{str(v.resolve()):sha(v) for v in (a.fixtures,c/'tools/wavefront_aot_driver.py',c/'tools/verify-general-optimizations.py',c/'Sources/FotufilmHalide/FotufilmHalideIOS.cpp')},
  'identities':{arm:{'path':str(a.build/arm/'identity.json'),'sha256':sha(a.build/arm/'identity.json')} for arm in ARMS},'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for case in frozen['cases']:
   if shutil.disk_usage(root).free<512*1024**2:raise RuntimeError('less than512MiB free before pixel case; evidence retained')
   for n in ('input','pack'):
    if sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
   folder=root/case['id'];folder.mkdir();left=folder/'R-B0.rgba32f'
   for arm,worker in [('R-B0',rw),('R-B1',rw),*workers.items()]:
    dump=left if arm=='R-B0' else folder/(arm+'.rgba32f')
    with (folder/(arm+'.jsonl')).open('w') as out,(folder/(arm+'.stderr')).open('w') as err:
     subprocess.run([str(worker),case['pack'],case['input'],'--dump',str(dump)],check=True,stdout=out,stderr=err,timeout=180,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1' if arm=='R-B1' else '0','FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0'})
    events=list(map(json.loads,(folder/(arm+'.jsonl')).read_text().splitlines()));call=next(x for x in events if x['type']=='call_complete')
    actual=call['actual_variant'];correct=('_windowed' in actual) if arm=='R-B1' else actual in ('fotufilm_halide_ios_color_float_realtime','fotufilm_halide_ios_monochrome_float_realtime')
    if call['status']!='success' or call['aot_calls']!=1 or call['gpu_dispatches']<1 or not correct:raise ValueError('actual requested general/windowed GPU execution missing')
    if arm=='R-B0':
     pixels={'passed':True,'samples':4*int(case['size'].split('x')[0])*int(case['size'].split('x')[1]),'max_linear_error':0,'finite':True,'alpha_exact':True}
    else:
     r=subprocess.run([str(compare),str(left),str(dump),'linear'],capture_output=True,text=True);pixels=json.loads(r.stdout)
     pixels['passed']=pixels['passed'] and r.returncode==0
    row={'case':case['id'],'arm':arm,'options':ARMS.get(arm),'actual':actual,'aot_calls':call['aot_calls'],'dispatches':call['gpu_dispatches'],'comparison':pixels,'output_sha256':sha(dump),'R_B0_output_sha256':sha(left),'bitwise_equal_R_B0':sha(dump)==sha(left),'passed':pixels['passed']}
    report['results'].append(row);save();print(json.dumps({k:row[k] for k in ('case','arm','dispatches','bitwise_equal_R_B0','passed')}),flush=True)
    if not row['passed']:raise ValueError('pixel proof failed; dumps retained')
    if arm!='R-B0':dump.unlink()
   left.unlink()
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
