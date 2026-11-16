#!/usr/bin/env python3
"""Stage23: original, BestFit and exact-size recent-demand eviction; normal driver only."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
s=importlib.util.spec_from_file_location('base',Path(__file__).with_name('run-wavefront-baseline.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ORDERS=[['R','BestFit','Recent'],['BestFit','Recent','R'],['Recent','R','BestFit']]
def sha(p):return b.sha(p)
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('workers','proof','candidate-proof','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();w=json.loads(a.workers.read_text());proof=json.loads(a.proof.read_text());cp=json.loads(a.candidate_proof.read_text());r=a.reference.resolve();root=a.output.resolve();root.mkdir()
 if not w['complete'] or not cp['complete'] or cp['workers_sha256']!=sha(a.workers) or len(cp['normal'])!=6 or len(cp['histories'])!=5:raise ValueError('six normal and five resource/history proofs required')
 if subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=w['reference_base'] or w['reference_base']!=proof['reference_base']:raise ValueError('frozen R changed')
 normal_path=c/'build/windowed-pool-stage19-performance/normal-proof.json';normal=json.loads(normal_path.read_text());bf_meta=json.loads((c/'build/windowed-pool-stage19-performance/worker.json').read_text());workers={'R':proof['workers']['R-B1'],'BestFit':bf_meta,'Recent':w['workers']['normal']}
 if not normal['complete'] or normal['worker']['sha256']!=bf_meta['sha256'] or len(normal['results'])!=6 or not all(x['passed'] and x['bitwise_equal_R'] for x in normal['results']):raise ValueError('BestFit original normal proof missing')
 for v in workers.values():
  if sha(v['path'])!=v['sha256']:raise ValueError('worker changed')
 for n,h in w['tools'].items():
  if sha(c/'tools'/n)!=h:raise ValueError('source changed '+n)
 cases=[x for x in proof['cases'] if x['id'] in ('portra400-coffee-1920x1080','portra400-coffee-3840x2160')]
 for case in cases:
  for n in ('pack','input'):
   if sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
 report={'complete':False,'stage':23,'performance_acceptance':False,'reference_base':w['reference_base'],'workers':workers,'cases':[x['id'] for x in cases],'sources':{str(x.resolve()):sha(x) for x in (a.workers,a.proof,a.candidate_proof,normal_path)},'controllers':{n:sha(c/'tools'/n) for n in ('run-windowed-pool-recent.py','run-wavefront-baseline.py','wavefront_metrics.py','wavefront-benchmark.mm')},'protocol':{'orders_hd':ORDERS,'orders_uhd':[list(reversed(x)) for x in ORDERS],'repeats_per_case':3,'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,'pool_mib':1024,'queue_capacity':4,'inflight_frames':1,'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'normal_driver':True,'detailed_probes':False,'scope':'one HD and one UHD fixed fixture; three cyclic position-balanced orders, reverse at UHD; not predecessor-balanced within either size'},'runs':[]}
 def save():b.atomic_json(root/'report.json',report)
 def guard():
  if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
  if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>256*1024**2:raise RuntimeError('256 MiB evidence budget')
 save()
 try:
  with b.awake_session() as awake:
   for case in cases:
    own=next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1');orders=report['protocol']['orders_hd' if '1920' in case['id'] else 'orders_uhd']
    for index,order in enumerate(orders):
     for arm in order:
      b.require_awake(awake);guard();worker=workers[arm]
      if sha(worker['path'])!=worker['sha256']:raise ValueError('worker changed between rounds')
      out=root/(case['id']+'-'+str(index)+'-'+arm);row={'case':case['id'],'index':index,'arm':arm,'round_path':str(out/'round.json'),'environment_before':b.environment_observation(root),'valid':False};report['runs'].append(row);save()
      result=b.run_round(worker['path'],case['pack'],case['input'],'B1',out);row.update({'scores':result['scores'],'memory':result['memory'],'environment_after':b.environment_observation(root)});save()
      if not result['scores']['valid']:raise ValueError('invalid round preserved')
      phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
      if len(phases)!=2 or any(x['output_sha256']!=own['output_sha256'] for x in phases):raise ValueError('full output phase hash mismatch')
      if any(x['actual_variant']!=own['actual'] or x['aot_calls']!=1 or x['gpu_dispatches']!=own['dispatches'] for x in result['requests']):raise ValueError('actual pipeline changed')
      row['valid']=True;save();guard();print('PASS',case['id'],index,arm,result['scores'],flush=True)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
