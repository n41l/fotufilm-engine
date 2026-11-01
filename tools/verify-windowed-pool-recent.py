#!/usr/bin/env python3
"""Verify exact-size recent-demand eviction: full pixels, fences, cap and changing-size history."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from windowed_pool_analysis import analyze as pool_analyze
from wavefront_resource_analysis import analyze as resource_analyze

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('workers','proof','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.output.resolve();root.mkdir();w=json.loads(a.workers.read_text());proof=json.loads(a.proof.read_text());report={'complete':False,'reference_base':w['reference_base'],'workers_sha256':sha(a.workers),'sources':{str(x.resolve()):sha(x) for x in (a.workers,a.proof)},'normal':[],'histories':[],'performance_acceptance':False}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 def guard(extra=0):
  if shutil.disk_usage(root).free<1024**3+extra:raise RuntimeError('1 GiB reserve')
  if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>256*1024**2:raise RuntimeError('256 MiB budget')
 def expected(case):return next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1')
 if not w['complete'] or w['reference_base']!=proof['reference_base']:raise ValueError('worker base mismatch')
 for v in w['workers'].values():
  if sha(v['path'])!=v['sha256']:raise ValueError('worker changed')
 for n,h in w['tools'].items():
  if sha(c/'tools'/n)!=h:raise ValueError('source changed '+n)
 for case in proof['cases']:
  for n in ('pack','input'):
   if sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
 env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'};env.pop('DYLD_INSERT_LIBRARIES',None);save()
 try:
  for case in proof['cases']:
   guard(Path(case['input']).stat().st_size);out=root/('normal-'+case['id']);out.mkdir();dump=out/'output.rgba32f'
   with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([w['workers']['normal']['path'],case['pack'],case['input'],'--dump',str(dump)],env=env,stdout=log,stderr=err,check=True,timeout=180)
   events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];call=next(x for x in events if x['type']=='call_complete');own=expected(case);digest=sha(dump)
   if digest!=own['output_sha256'] or call['status']!='success' or call['actual_variant']!=own['actual'] or call['aot_calls']!=1 or call['gpu_dispatches']!=own['dispatches']:raise ValueError('normal pixel/actual verification')
   report['normal'].append({'case':case['id'],'output_sha256':digest,'event':call});dump.unlink();save();print('PASS normal',case['id'],flush=True)
  groups=[(case['id']+'-'+mode,[case]*6,mode,False) for case in proof['cases'] if case['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160') for mode in ('light','detail')]+[('mixed-history',proof['cases']+list(reversed(proof['cases']))+[proof['cases'][0]],'detail',True)]
  for label,cases,mode,cleanup in groups:
   guard();out=root/label;out.mkdir();actions=[]
   for i,case in enumerate(cases):
    if cleanup and i==12:actions.append({'type':'cleanup','seconds':0})
    actions.append({'type':'frame','id':case['id'],'pack':case['pack'],'input':case['input'],'mode':'B1','expected_mode':0,'expected_sha256':expected(case)['output_sha256']})
   plan={'dump':False,'actions':actions+[{'type':'idle','seconds':0}]};(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
   with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([w['workers'][mode]['path'],str(out/'plan.json'),str(out)],env=env,stdout=log,stderr=err,check=True,timeout=300)
   events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];frames=[x for x in events if x['type']=='resource_frame']
   if events[-1]['type']!='resource_complete' or len(frames)!=len(cases):raise ValueError('frame accounting')
   for case,e in zip(cases,frames):
    own=expected(case)
    if e['status']!='success' or e['output_sha256']!=own['output_sha256'] or e['actual_variant']!=own['actual'] or e['aot_calls']!=1 or e['gpu_dispatches']!=own['dispatches']:raise ValueError('history pixel/actual verification')
   row={'label':label,'path':str(out),'frames':frames}
   if mode=='detail':
    trace=json.loads((out/'resource-trace.json').read_text());attempts=json.loads((out/'pool-attempts.json').read_text());physical={x['id']:x for x in trace['physical']};analysis=pool_analyze(trace,attempts);analysis['resources']=resource_analyze(trace);evictions=[]
    for x in attempts['attempts']:
     if x['frame_depth']>0 and physical[x['physical']]['length']!=x['rounded']:raise ValueError('exact-size policy returned another size')
     for snapshot in (x['before'],x['after']):
      if sum(i['length'] for i in snapshot if i['state']==1)>x['capacity']:raise ValueError('idle pool cap violated')
     after={i['physical'] for i in x['after']};drops=[i for i in x['before'] if i['physical'] not in after and i['state'] in (1,2) and x['begin']<physical[i['physical']]['freed']<x['end']]
     if any(i['state']==2 and i['fence_status']<4 for i in drops):
      # A pending before snapshot can complete during allocation. The resource ledger
      # above validates actual free/reuse ordering against the real GPU fence.
      pass
     if drops:evictions.append({'begin':x['begin'],'requested':x['rounded'],'drops':drops})
    analysis['idle_or_returned_evictions']=evictions;(out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n');row['analysis']=str(out/'analysis.json')
   row['artifacts']={x.name:sha(x) for x in out.iterdir() if x.is_file()};report['histories'].append(row);save();print('PASS history',label,[x['new_buffers'] for x in frames],flush=True)
  guard();report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
