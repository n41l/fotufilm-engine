#!/usr/bin/env python3
"""Preflight or count-based probe/off calibration of allocator, encoding, GPU and waits."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from windowed_speed_analysis import analyze
ORDERS=[['R-off','R-on','BestFit-off','BestFit-on'],['R-on','BestFit-off','BestFit-on','R-off'],['BestFit-off','BestFit-on','R-off','R-on'],['BestFit-on','R-off','R-on','BestFit-off']]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def execute(worker,case,own,out,enabled,warm,measured,env):
 if shutil.disk_usage(out.parent).free<1024**3:raise RuntimeError('1 GiB reserve')
 out.mkdir()
 with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([worker,case['pack'],case['input'],str(out),str(int(enabled)),str(warm),str(measured)],env=env,stdout=log,stderr=err,check=True,timeout=180)
 events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];frames=[x for x in events if x['type']=='frame'];hashes=[x for x in events if x['type']=='phase_hash']
 if events[-1]['type']!='complete' or len(frames)!=warm+measured or len(hashes)!=(2 if warm else 1) or any(x['output_sha256']!=own['output_sha256'] for x in hashes):raise ValueError('full output hash/phase coverage')
 metrics=[]
 for frame in frames:
  if frame['actual_variant']!=own['actual'] or frame['aot_calls']!=1 or frame['dispatches']!=own['dispatches']:raise ValueError('actual original pipeline changed')
  metric=analyze(json.loads((out/(str(frame['frame'])+'.json')).read_text()),frame['dispatches'],frame['new_buffers']);metric.update({'frame':frame['frame'],'phase':frame['phase'],'main_thread_cpu_ms':frame['main_thread_cpu_ms'],'new_buffers':frame['new_buffers'],'memory':frame['memory']});metrics.append(metric)
 result={'path':str(out),'probes':enabled,'frames':metrics,'events_sha256':sha(out/'events.jsonl'),'frame_files_sha256':{str(x['frame'])+'.json':sha(out/(str(x['frame'])+'.json')) for x in frames}}
 (out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('workers','proof','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--preflight',action='store_true');p.add_argument('--preflight-proof',type=Path);a=p.parse_args();root=a.output.resolve();root.mkdir();workers=json.loads(a.workers.read_text());proof=json.loads(a.proof.read_text());r=a.reference.resolve()
 if not workers['complete'] or workers['reference_base']!=proof['reference_base'] or subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen reference identity')
 for w in workers['workers'].values():
  if sha(w['path'])!=w['sha256']:raise ValueError('worker changed')
 for n,h in workers['tools'].items():
  if sha(c/'tools'/n)!=h:raise ValueError('worker source changed')
 if not a.preflight:
  if not a.preflight_proof:raise ValueError('preflight proof required')
  pre=json.loads(a.preflight_proof.read_text())
  if not pre['complete'] or len(pre['runs'])!=24 or pre['workers_sha256']!=sha(a.workers):raise ValueError('24 matching preflight rows required')
 cases=proof['cases'] if a.preflight else [x for x in proof['cases'] if x['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160')]
 for case in cases:
  for n in ('pack','input'):
   if sha(case[n])!=case[n+'_sha256']:raise ValueError('frozen input changed')
 report={'complete':False,'stage':20,'scope':__doc__,'performance_acceptance':False,'reference_base':workers['reference_base'],'workers_sha256':sha(a.workers),'proof_sha256':sha(a.proof),'sources':{str(x.resolve()):sha(x) for x in [a.workers,a.proof,*([a.preflight_proof] if a.preflight_proof else [])]},'protocol':{'preflight':a.preflight,'warm_frames':0 if a.preflight else 10,'measured_frames':1 if a.preflight else 40,'repeats':1 if a.preflight else 4,'orders_hd':ORDERS,'orders_uhd':[list(reversed(x)) for x in ORDERS],'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'pool_mib':1024,'inflight_frames':1,'dumps':False},'controllers':{n:sha(c/'tools'/n) for n in ('run-windowed-speed.py','windowed_speed_analysis.py')},'runs':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save();env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'};env.pop('DYLD_INSERT_LIBRARIES',None)
 try:
  for case in cases:
   orders=[ORDERS[0]] if a.preflight else report['protocol']['orders_hd' if '1920' in case['id'] else 'orders_uhd']
   own=next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1')
   for index,order in enumerate(orders):
    for cell in order:
     if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('evidence budget')
     arm,mode=cell.split('-');out=root/(case['id']+'-'+str(index)+'-'+cell);result=execute(workers['workers'][arm]['path'],case,own,out,mode=='on',report['protocol']['warm_frames'],report['protocol']['measured_frames'],env);report['runs'].append({'case':case['id'],'index':index,'cell':cell,'analysis':str(out/'analysis.json'),'analysis_sha256':sha(out/'analysis.json')});save();print('PASS',case['id'],index,cell,flush=True)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
