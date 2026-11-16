#!/usr/bin/env python3
"""Original vs isolated bounded best-fit, three fresh-process repeats per HD/UHD case."""
import argparse,importlib.util,json,shutil,subprocess,uuid
from pathlib import Path

def main():
 c=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('b',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','candidate-proof','forensics','best-fit-history','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();proof=json.loads(a.proof.read_text());cp=json.loads(a.candidate_proof.read_text());f=json.loads(a.forensics.read_text());h=json.loads(a.best_fit_history.read_text());ref=a.reference.resolve()
 if not (cp['complete'] and f['complete'] and h['complete']) or len(cp['results'])!=6 or not all(x['passed'] for x in cp['results']):raise ValueError('full six-case normal proof and completed resource/history checks required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen reference changed')
 workers={'R-B1':proof['workers']['R-B1'],'BestFit':cp['worker']}
 for w in workers.values():
  if b.sha(w['path'])!=w['sha256']:raise ValueError('verified worker changed')
 if b.sha(c/'tools/windowed-pool-best-fit.inc')!=cp['suffix_sha256']:raise ValueError('pool policy source changed')
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True);cases=[x for x in proof['cases'] if x['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160')]
 for case in cases:
  for n in ('pack','input'):
   if b.sha(case[n])!=case[n+'_sha256']:raise ValueError('frozen input changed')
 report={'complete':False,'performance_acceptance':False,'B_ref_frozen':False,'scope':__doc__,'reference_base':proof['reference_base'],'workers':workers,'cases':[x['id'] for x in cases],'protocol':{'rounds_per_arm_case':3,'orders_hd':[['R-B1','BestFit'],['BestFit','R-B1'],['R-B1','BestFit']],'orders_uhd':[['BestFit','R-B1'],['R-B1','BestFit'],['BestFit','R-B1']],'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,'inflight_frames':1,'pool_mib':1024,'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'image_dumps':False},'sources':{str(x.resolve()):b.sha(x) for x in (a.proof,a.candidate_proof,a.forensics,a.best_fit_history)},'controllers':{n:b.sha(c/'tools'/n) for n in ('run-windowed-pool-diagnostic.py','run-wavefront-baseline.py','wavefront_metrics.py','wavefront-benchmark.mm','windowed-pool-best-fit.inc')},'rounds':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 try:
  with b.awake_session() as helper:
   for case in cases:
    for index,order in enumerate(report['protocol']['orders_hd' if '1920' in case['id'] else 'orders_uhd']):
     row={'case':case['id'],'index':index,'order':order,'arms':{}};report['rounds'].append(row);save()
     for arm in order:
      b.require_awake(helper)
      if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
      if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('evidence budget')
      own=next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1');out=root/(case['id']+'-'+str(index)+'-'+arm);b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root));result=b.run_round(Path(workers[arm]['path']),Path(case['pack']),Path(case['input']),'B1',out);row['arms'][arm]=b.compact(result,out/'round.json');save()
      phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
      if len(phases)!=2 or any(x['output_sha256']!=own['output_sha256'] for x in phases):raise RuntimeError('normal hash disagreement')
      if any(x['actual_variant']!=own['actual'] or x['aot_calls']!=1 or x['gpu_dispatches']!=own['dispatches'] for x in result['requests']):raise RuntimeError('normal pipeline changed')
      print(json.dumps({'case':case['id'],'index':index,'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
      if not result['scores']['valid']:raise RuntimeError('invalid round retained')
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
