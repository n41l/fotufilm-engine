#!/usr/bin/env python3
"""Reproduce isolated best-fit workers, six-case normal proof and count-based histories."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from wavefront_aot_driver import build
from windowed_pool_analysis import analyze

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('reference','proof','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();r=a.reference.resolve();root=a.output.resolve();root.mkdir();proof=json.loads(a.proof.read_text());report={'complete':False,'performance_acceptance':False,'reference_base':proof['reference_base'],'runs':[]}
 if subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen reference changed')
 def reserve(extra=0):
  if shutil.disk_usage(root).free<1024**3+extra:raise RuntimeError('1 GiB reserve')
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 reserve();save();workers={};env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'};env.pop('DYLD_INSERT_LIBRARIES',None)
 try:
  for label in ('light','detail','normal'):
   detail=label=='detail';driver=c/('tools/windowed-pool-driver.mm' if detail else 'tools/wavefront-benchmark.mm' if label=='normal' else 'tools/wavefront-resource-driver.mm')
   defs=tuple('-D'+n+'=wf_original_'+n for n in ('commit_command_buffer','retain_ns_object','release_ns_object'))+('-Dnew_buffer=wf_frozen_new_buffer','-DWF_POOL_ALLOCATOR_ENTRY=wf_original_new_buffer') if detail else ('-Dnew_buffer=wf_original_new_buffer',)
   workers[label]=build(r,r/'build/wavefront-macos',root/label,driver,definitions=('-I'+str(c/'tools'),),driver_definitions=() if label=='normal' else ('-DWF_RESOURCE_CANDIDATE=0','-DWF_RESOURCE_OBSERVER='+str(int(detail))),shim_definitions=defs,resource_hooks=detail,adapter=c/'tools/windowed-pool-observer.mm' if detail else None,shim_suffix=c/('tools/windowed-pool-best-fit-observed.inc' if detail else 'tools/windowed-pool-best-fit.inc'))
  report['workers']={n:{'path':str(w),'sha256':sha(w)} for n,w in workers.items()};save()
  def expected(case):return next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1')
  for case in proof['cases']:
   for n in ('pack','input'):
    if sha(case[n])!=case[n+'_sha256']:raise ValueError('frozen fixture changed')
  groups=[(case['id']+'-'+label,[case]*6,label) for case in proof['cases'] if case['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160') for label in ('light','detail')]+[('mixed-history',proof['cases']+list(reversed(proof['cases'])),'detail')]
  for label,cases,worker in groups:
   reserve();out=root/label;out.mkdir();plan={'dump':False,'actions':[{'type':'frame','id':x['id'],'pack':x['pack'],'input':x['input'],'mode':'B1','expected_mode':0,'expected_sha256':expected(x)['output_sha256']} for x in cases]+[{'type':'idle','seconds':0}]};(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
   with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([str(workers[worker]),str(out/'plan.json'),str(out)],env=env,stdout=log,stderr=err,check=True,timeout=300)
   events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];frames=[x for x in events if x['type']=='resource_frame'];assert events[-1]['type']=='resource_complete' and len(frames)==len(cases)
   for case,e in zip(cases,frames):
    own=expected(case);assert e['status']=='success' and e['output_sha256']==own['output_sha256'] and e['actual_variant']==own['actual'] and e['gpu_dispatches']==own['dispatches'] and e['aot_calls']==1
   if worker=='detail':(out/'analysis.json').write_text(json.dumps(analyze(json.loads((out/'resource-trace.json').read_text()),json.loads((out/'pool-attempts.json').read_text())),indent=2)+'\n')
   report['runs'].append({'label':label,'path':str(out),'frames':frames,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()}});save();print('PASS',label,flush=True)
  normal={'complete':False,'worker':report['workers']['normal'],'suffix_sha256':sha(c/'tools/windowed-pool-best-fit.inc'),'results':[]}
  for case in proof['cases']:
   reserve(Path(case['input']).stat().st_size);out=root/('normal-'+case['id']);out.mkdir();dump=out/'output.rgba32f'
   with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([str(workers['normal']),case['pack'],case['input'],'--dump',str(dump)],env=env,stdout=log,stderr=err,check=True,timeout=180)
   events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];call=next(x for x in events if x['type']=='call_complete');own=expected(case);digest=sha(dump);ok=digest==own['output_sha256'] and call['status']=='success' and call['actual_variant']==own['actual'] and call['aot_calls']==1 and call['gpu_dispatches']==own['dispatches'];normal['results'].append({'case':case['id'],'passed':ok,'output_sha256':digest});assert ok;dump.unlink()
  normal['complete']=True;(root/'normal-proof.json').write_text(json.dumps(normal,indent=2)+'\n');report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
