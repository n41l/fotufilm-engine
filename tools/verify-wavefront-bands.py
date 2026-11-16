#!/usr/bin/env python3
"""Direct original-B1 pixels, old-512 parity and actual A/F trace for band512/1080.

Diagnostic mixed legacy/private AOT build; no release or performance acceptance.
"""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
from wavefront_aot_driver import build

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','output','fixtures','reference','prior-proof'):p.add_argument('--'+n,required=True,type=Path)
 p.add_argument('--reuse-workers',type=Path)
 a=p.parse_args();root=a.output.resolve();root.mkdir();a.build=a.build.resolve();ref=a.reference.resolve()
 fixtures=json.loads(a.fixtures.read_text());prior=json.loads(a.prior_proof.read_text())
 if not prior['complete'] or not all(x['passed'] for x in prior['results']):raise ValueError('complete prior512 proof required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('R must remain clean')
 if subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=fixtures['source_base']:raise ValueError('R base changed')
 rw=ref/'build/wavefront-benchmark-v2/instrumented/runner'
 if sha(rw)!=fixtures['worker_sha256'] or sha(c/'tools/wavefront-benchmark.mm')!=fixtures['tool_sources']['wavefront-benchmark.mm']:raise ValueError('frozen R/common driver changed')
 workers={}
 reuse=json.loads(a.reuse_workers.read_text()) if a.reuse_workers else None
 if reuse:
  for n,h in reuse['host_sources'].items():
   if sha(c/n)!=h:raise ValueError('reused worker host changed')
  if reuse['aot_source_key']!=(a.build/'bundle-normal/source-key.txt').read_text().strip():raise ValueError('reused worker AOT changed')
 for trace in (False,True):
  key='bundletrace' if trace else 'bundle'
  if reuse:
   workers[key]=Path(reuse['workers'][key]['path'])
   if sha(workers[key])!=reuse['workers'][key]['sha256']:raise ValueError('reused worker changed')
   continue
  workers[key]=build(c,a.build/'control-bundle/kernels',root/key,c/'tools/wavefront-benchmark.mm',
   definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1','-DFOTUFILM_BUNDLE_RESEARCH=1'),
   driver_definitions=('-Dfotufilm_halide_metal_process_linear_float=fotufilm_wavefront_bench_process_linear_float',),
   adapter=c/'tools/wavefront-benchmark-adapter.cpp',
   adapter_definitions=('-DFOTUFILM_WAVEFRONT_RUNTIME_BAND=1',)+(('-DFOTUFILM_WAVEFRONT_TRACE=1','-x','objective-c++','-fblocks') if trace else ()),
   diagnostic_control=a.build/'control-bundle',diagnostic_kernels=a.build/'bundle-normal',
   trace_overrides=sorted((a.build/'bundle-trace').glob('*.a')) if trace else ())
 compare=root/'compare';subprocess.run(['xcrun','clang++','-O2','-std=c++17',str(c/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
 spec=importlib.util.spec_from_file_location('trace',c/'tools/verify-wavefront-bundle-trace.py');tr=importlib.util.module_from_spec(spec);spec.loader.exec_module(tr)
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'B_ref_frozen':False,'bands':[512,1080],'numerical_contract':'unchanged linear max <=1e-5, encoded <1/255, finite, exact alpha; normal512 must retain prior hash; trace and1080 bitwise equality is recorded separately',
  'reused_workers_from':str(a.reuse_workers.resolve()) if a.reuse_workers else None,
  'reference_base':fixtures['source_base'],'workers':{k:{'path':str(v),'sha256':sha(v)} for k,v in {**workers,'R-B1':rw}.items()},
  'sources':{str(v.resolve()):sha(v) for v in (a.fixtures,a.prior_proof,c/'tools/verify-wavefront-bands.py',c/'tools/verify-wavefront-bundle-trace.py')},
  'aot_source_key':(a.build/'bundle-normal/source-key.txt').read_text().strip(),
  'host_sources':{n:sha(c/n) for n in ('Sources/FotufilmHalide/FotufilmHalideIOS.cpp','Sources/FotufilmHalide/FotufilmHalideWavefront.h','Sources/FotufilmHalide/FotufilmWavefrontAdmission.h','tools/wavefront-bundle-scheduler.h','tools/wavefront-benchmark-adapter.cpp','tools/wavefront_aot_driver.py')},
  'build_provenance':{str(v):sha(v) for v in (a.build/'generator-build.json',a.build/'bundle-normal/identity.json',a.build/'bundle-trace/identity.json',a.build/'control-bundle/control.json')},'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for case in fixtures['cases']:
   for n in ('input','pack'):
    if sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
   folder=root/case['id'];folder.mkdir();left=folder/'R-B1.rgba32f'
   def run(worker,key,dump,band):
    stdout=folder/(key+'.jsonl');stderr=folder/(key+'.stderr')
    with stdout.open('w') as out,stderr.open('w') as err:
     subprocess.run([str(worker),case['pack'],case['input'],'--dump',str(dump)],check=True,stdout=out,stderr=err,timeout=180,
      env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1' if key=='R-B1' else '0','FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0','FOTUFILM_WAVEFRONT_BENCH_ROWS':str(band)})
    call=next(x for x in map(json.loads,stdout.read_text().splitlines()) if x['type']=='call_complete')
    if call['status']!='success' or call['gpu_dispatches']<1:raise ValueError('actual successful GPU call missing')
    return call,stderr
   rc,_=run(rw,'R-B1',left,512)
   if '_windowed' not in rc['actual_variant'] or rc['aot_calls']!=1:raise ValueError('original windowed did not execute')
   old=next(x for x in prior['results'] if x['case']==case['id'] and x['worker']=='bundle')['C_output_sha256']
   hashes=[]
   for band in (512,1080):
    for key,worker in workers.items():
     name=f'{key}-{band}';right=folder/(name+'.rgba32f');call,stderr=run(worker,name,right,band)
     if '_wavefront_bundle_' not in call['actual_variant'] or not call['actual_variant'].endswith('_'+str(band)):raise ValueError('requested band/cut did not execute')
     comparison=subprocess.run([str(compare),str(left),str(right),'linear'],capture_output=True,text=True);pixels=json.loads(comparison.stdout)
     h=sha(right);hashes.append(h);checks={}
     if key=='bundletrace':
      w,height=map(int,case['size'].split('x'));checks=tr.analyze(stderr.read_text().splitlines(),w,height,call['aot_calls'],call['gpu_dispatches'],band)
     passed=comparison.returncode==0 and pixels['passed'] and (band!=512 or key!='bundle' or h==old) and (key!='bundletrace' or checks['passed'])
     row={'case':case['id'],'band':band,'worker':key,'comparison':pixels,'actual':call['actual_variant'],'aot_calls':call['aot_calls'],'dispatches':call['gpu_dispatches'],
      'R_B1_output_sha256':sha(left),'C_output_sha256':h,'prior512_output_sha256':old,'bitwise_equal_prior512':h==old,'bitwise_equal_original':h==sha(left),'trace':checks,'stderr_sha256':sha(stderr),'passed':passed}
     report['results'].append(row);save();print(json.dumps({k:row[k] for k in ('case','band','worker','aot_calls','dispatches','passed')}),flush=True)
     if not passed:raise ValueError('pixel, old512 or actual trace disagreement; dumps retained')
     right.unlink()
   left.unlink()
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
