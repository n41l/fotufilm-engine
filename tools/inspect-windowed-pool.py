#!/usr/bin/env python3
"""Bounded original-windowed allocation forensics; no pool policy changes or speed scores."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from wavefront_aot_driver import build

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('reference','proof','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();r=a.reference.resolve();root=a.output.resolve();root.mkdir();proof=json.loads(a.proof.read_text())
 if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
 if subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen R changed')
 tools=['windowed-pool-shim.inc','windowed-pool-driver.mm','windowed-pool-observer.mm','wavefront-resource-observer.mm','wavefront-resource-shim.inc','wavefront-resource-driver.mm','wavefront-benchmark.mm','wavefront_aot_driver.py']
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'pool_policy_changed':False,'reference_base':proof['reference_base'],'proof':{'path':str(a.proof.resolve()),'sha256':sha(a.proof)},'tools':{n:sha(c/'tools'/n) for n in tools},'workers':{},'runs':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for detail in (False,True):
   label='detail' if detail else 'light';worker=build(r,r/'build/wavefront-macos',root/label,c/('tools/windowed-pool-driver.mm' if detail else 'tools/wavefront-resource-driver.mm'),definitions=('-I'+str(c/'tools'),),driver_definitions=('-DWF_RESOURCE_CANDIDATE=0','-DWF_RESOURCE_OBSERVER='+str(int(detail))),shim_definitions=tuple('-D'+n+'=wf_original_'+n for n in ('new_buffer','commit_command_buffer','retain_ns_object','release_ns_object')) if detail else (),resource_hooks=detail,adapter=c/'tools/windowed-pool-observer.mm' if detail else None,shim_suffix=c/'tools/windowed-pool-shim.inc' if detail else None)
   report['workers'][label]={'path':str(worker),'sha256':sha(worker)};save()
  env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'};env.pop('DYLD_INSERT_LIBRARIES',None)
  for case in [x for x in proof['cases'] if x['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160')]:
   expected=next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1');assert expected['passed']
   for n in ('pack','input'):
    if sha(case[n])!=case[n+'_sha256']:raise ValueError('input changed')
   for label in ('light','detail'):
    if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
    out=root/(case['id']+'-'+label);out.mkdir();plan={'dump':False,'actions':[{'type':'frame','id':case['id'],'pack':case['pack'],'input':case['input'],'mode':'B1','expected_mode':0,'expected_sha256':expected['output_sha256']} for _ in range(6)]+[{'type':'idle','seconds':0}]};(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([report['workers'][label]['path'],str(out/'plan.json'),str(out)],stdout=log,stderr=err,env=env,check=True,timeout=180)
    events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];frames=[e for e in events if e['type']=='resource_frame'];assert len(frames)==6 and events[-1]['type']=='resource_complete'
    assert all(e['status']=='success' and e['output_sha256']==expected['output_sha256'] and e['actual_variant']==expected['actual'] and e['aot_calls']==1 and e['gpu_dispatches']==expected['dispatches'] for e in frames)
    if label=='detail':
     trace=json.loads((out/'resource-trace.json').read_text());assert not trace['errors'];assert all(f['status']==4 and f['delivered'] for f in trace['fences'])
    row={'case':case['id'],'observer':label,'path':str(out),'frames':frames,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()}};report['runs'].append(row);save();print('PASS',case['id'],label,'new',[f['new_buffers'] for f in frames],flush=True)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
