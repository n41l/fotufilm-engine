#!/usr/bin/env python3
"""Six-level-cell method attribution: original/best-fit x off/basic/detail; separate stage21 cohort."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
from windowed_metal_analysis import analyze_methods
s=importlib.util.spec_from_file_location('base',Path(__file__).with_name('run-windowed-speed.py'));base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
CELLS=['R-off','R-basic','R-detail','BestFit-off','BestFit-basic','BestFit-detail'];ORDERS=[CELLS[i:]+CELLS[:i] for i in range(6)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('workers','proof','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--preflight',action='store_true');p.add_argument('--preflight-proof',type=Path);a=p.parse_args();root=a.output.resolve();root.mkdir();workers=json.loads(a.workers.read_text());proof=json.loads(a.proof.read_text());r=a.reference.resolve()
 if not workers['complete'] or workers['reference_base']!=proof['reference_base'] or subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen reference identity')
 for w in workers['workers'].values():
  if sha(w['path'])!=w['sha256']:raise ValueError('worker changed')
 for name,h in workers['tools'].items():
  if sha(c/'tools'/name)!=h:raise ValueError('worker source changed')
 if not a.preflight:
  if not a.preflight_proof:raise ValueError('preflight proof required')
  pre=json.loads(a.preflight_proof.read_text())
  if not pre['complete'] or len(pre['runs'])!=36 or pre['workers_sha256']!=sha(a.workers):raise ValueError('36 matching preflight processes required')
 cases=proof['cases'] if a.preflight else [x for x in proof['cases'] if x['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160')]
 for case in cases:
  for name in ('pack','input'):
   if sha(case[name])!=case[name+'_sha256']:raise ValueError('fixture changed')
 report={'complete':False,'stage':21,'scope':__doc__,'performance_acceptance':False,'reference_base':workers['reference_base'],'workers_sha256':sha(a.workers),'sources':{str(x.resolve()):sha(x) for x in [a.workers,a.proof,*([a.preflight_proof] if a.preflight_proof else [])]},'controllers':{n:sha(c/'tools'/n) for n in ('run-windowed-metal.py','run-windowed-speed.py','windowed_metal_analysis.py','windowed_speed_analysis.py')},'protocol':{'preflight':a.preflight,'warm_frames':0 if a.preflight else 10,'measured_frames':1 if a.preflight else 12,'repeats':1 if a.preflight else 6,'orders_hd':ORDERS,'orders_uhd':[list(reversed(x)) for x in ORDERS],'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'pool_mib':1024,'queue_limit_unchanged':4,'inflight_frames':1,'dumps':False},'runs':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save();env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'};env.pop('DYLD_INSERT_LIBRARIES',None)
 try:
  for case in cases:
   orders=[ORDERS[0]] if a.preflight else report['protocol']['orders_hd' if '1920' in case['id'] else 'orders_uhd'];own=next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1')
   for index,order in enumerate(orders):
    for cell in order:
     if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB reserve')
     if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('evidence budget')
     arm,mode=cell.split('-');out=root/(case['id']+'-'+str(index)+'-'+cell);result=base.execute(workers['workers'][arm]['path'],case,own,out,mode!='off',report['protocol']['warm_frames'],report['protocol']['measured_frames'],{**env,'FOTUFILM_METAL_METHOD_PROBES':str(int(mode=='detail'))})
     for frame in result['frames']:
      raw=json.loads((out/(str(frame['frame'])+'.json')).read_text());frame.update(analyze_methods(raw))
      if frame['methods_available']!=(mode=='detail'):raise ValueError('method mode changed')
     result['cell']=cell;(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');report['runs'].append({'case':case['id'],'index':index,'cell':cell,'analysis':str(out/'analysis.json'),'analysis_sha256':sha(out/'analysis.json')});save();print('PASS',case['id'],index,cell,flush=True)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
