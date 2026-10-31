#!/usr/bin/env python3
"""Full-pixel R / two-stage / three-stage / traced-three-stage diagnostic proof."""
import argparse,importlib.util,json,os,subprocess,hashlib
from pathlib import Path
c=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
for name in ('build','output','fixtures','reference-worker'):p.add_argument('--'+name,required=True,type=Path)
a=p.parse_args();a.build=a.build.resolve()
s=importlib.util.spec_from_file_location('d',c/'tools/wavefront_aot_driver.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
out=a.output.resolve();out.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen=json.loads(a.fixtures.read_text());ref=a.reference_worker.resolve()
assert sha(ref)==frozen['worker_sha256']
workers={}
for stage,trace in ((2,False),(3,False),(3,True)):
 key=str(stage)+('trace' if trace else '')
 workers[key]=m.build(c,a.build/f'control-{stage}/kernels',out/key,c/'tools/wavefront-benchmark.mm',
  definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1',)+(('-DFOTUFILM_THREE_STAGE_RESEARCH=1',) if stage==3 else ()),
  driver_definitions=('-Dfotufilm_halide_metal_process_linear_float=fotufilm_wavefront_bench_process_linear_float',),
  adapter=c/'tools/wavefront-benchmark-adapter.cpp',
  adapter_definitions=('-DFOTUFILM_WAVEFRONT_RUNTIME_BAND=1',)+(('-DFOTUFILM_WAVEFRONT_TRACE=1','-x','objective-c++','-fblocks') if trace else ()),
  diagnostic_control=a.build/f'control-{stage}',
  diagnostic_kernels=a.build/('three-normal' if stage==3 else 'two-normal'),
  trace_overrides=sorted((a.build/'three-trace').glob('*.a')) if trace else ())
compare=out/'compare';subprocess.run(['xcrun','clang++','-O2','-std=c++17',str(c/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
report={'complete':False,'scope':'full-film three-stage prototype, two call-scoped GPU row caches; mixed legacy diagnostic only',
 'stage_count':3,'performance_acceptance':False,'workers':{k:{'path':str(p),'sha256':sha(p)} for k,p in workers.items()},'results':[]}
def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
save()
try:
 for case in frozen['cases']:
  for name in ('input','pack'):
   if sha(case[name])!=case[name+'_sha256']:raise ValueError('frozen fixture changed')
  folder=out/case['id'];folder.mkdir()
  left=folder/'R.rgba32f'
  with (folder/'R.jsonl').open('w') as stdout,(folder/'R.stderr').open('w') as stderr:
   subprocess.run([str(ref),case['pack'],case['input'],'--dump',str(left)],check=True,stdout=stdout,stderr=stderr,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0'},timeout=120)
  for key,worker in workers.items():
   right=folder/(key+'.rgba32f')
   with (folder/(key+'.jsonl')).open('w') as stdout,(folder/(key+'.stderr')).open('w') as stderr:
    subprocess.run([str(worker),case['pack'],case['input'],'--dump',str(right)],check=True,stdout=stdout,stderr=stderr,
     env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0','FOTUFILM_WAVEFRONT_BENCH_ROWS':'512','FOTUFILM_METAL_POOL':'1024'},timeout=120)
   result=subprocess.run([str(compare),str(left),str(right),'linear'],capture_output=True,text=True);pixels=json.loads(result.stdout)
   events=list(map(json.loads,(folder/(key+'.jsonl')).read_text().splitlines()));call=next(x for x in events if x['type']=='call_complete')
   passed=result.returncode==0 and pixels['passed'] and call['status']=='success' and '_wavefront_' in call['actual_variant']
   report['results'].append({'case':case['id'],'worker':key,'comparison':pixels,'actual':call['actual_variant'],'dispatches':call['gpu_dispatches'],'aot_calls':call['aot_calls'],
    'R_output_sha256':sha(left),'C_output_sha256':sha(right),'passed':passed});save()
   print(case['id'],key,'passed',passed,pixels,flush=True)
   if not passed:raise AssertionError('full-pixel prototype disagreement; failed output retained')
   right.unlink()
  left.unlink()
 report['complete']=True
except BaseException as error:report['failure']=str(error);raise
finally:save()
print(out/'report.json',flush=True)
