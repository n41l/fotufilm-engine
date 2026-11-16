#!/usr/bin/env python3
"""Three balanced repeats of R-B1/W0/Fused on the active Portra UHD case only."""
import argparse,importlib.util,json,shutil,subprocess,uuid
from pathlib import Path
from windowed_mtf_helper import NAME
ORDERS=(('R-B1','W0','Fused'),('W0','Fused','R-B1'),('Fused','R-B1','W0'))
def expected_row(proof,case,arm):
 rows=[x for x in proof['results'] if x['case']==case and x['arm']==arm]
 if len(rows)!=1 or not rows[0]['passed'] or not rows[0]['active'] or rows[0]['actual']!=NAME:raise ValueError('unique successful active own-arm pixel proof required')
 return rows[0]
def main():
 c=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('baseline',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','history','jit-proof','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();proof=json.loads(a.proof.read_text());history=json.loads(a.history.read_text());jit=json.loads(a.jit_proof.read_text());ref=a.reference.resolve()
 if not proof['complete'] or len(proof['results'])!=15 or not all(x['passed'] for x in proof['results']):raise ValueError('complete15-row main/odd proof required')
 if not history['complete'] or len(history['results'])!=28 or not all(x['passed'] for x in history['results']) or history['pixel_proof']['sha256']!=b.sha(a.proof):raise ValueError('matching complete28-frame history proof required')
 if not jit['complete'] or jit.get('source_key')!=proof['source_key'] or len(jit['results'])!=2 or not all(x['passed'] for x in jit['results']):raise ValueError('complete targeted JIT/AOT parity required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen R changed')
 for w in proof['workers'].values():
  if b.sha(w['path'])!=w['sha256']:raise ValueError('verified worker changed')
 for identity in proof['identities'].values():
  if b.sha(identity['path'])!=identity['sha256']:raise ValueError('arm archive identity changed')
 case=next(x for x in proof['cases'] if x['id']=='portra400-coffee-3840x2160')
 for n in ('pack','input'):
  if b.sha(case[n])!=case[n+'_sha256']:raise ValueError('frozen input changed')
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'B_ref_frozen':False,'source_key':proof['source_key'],'reference_base':proof['reference_base'],'workers':proof['workers'],'case':case['id'],'protocol':{'orders':ORDERS,'rounds_per_arm':3,'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,'inflight_frames':1,'pool_mib':1024,'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'image_dumps':False},'sources':{str(x.resolve()):b.sha(x) for x in (a.proof,a.history,a.jit_proof)},'controllers':{n:b.sha(c/'tools'/n) for n in ('run-windowed-mtf-diagnostic.py','windowed_mtf_helper.py','run-wavefront-baseline.py','wavefront_metrics.py','wavefront-benchmark.mm')},'rounds':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 try:
  with b.awake_session() as helper:
   for index,order in enumerate(ORDERS):
    row={'index':index,'order':order,'arms':{}};report['rounds'].append(row);save()
    for arm in order:
     b.require_awake(helper)
     if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
     if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('evidence budget reached')
     own=expected_row(proof,case['id'],arm);worker=Path(proof['workers'][arm]['path']);out=root/(str(index)+'-'+arm)
     b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root));result=b.run_round(worker,Path(case['pack']),Path(case['input']),'B1',out)
     row['arms'][arm]=b.compact(result,out/'round.json');save()
     phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
     if len(phases)!=2 or any(x['output_sha256']!=own['output_sha256'] for x in phases):raise RuntimeError('own-arm normal proof hash mismatch')
     if any(x['actual_variant']!=own['actual'] or x['aot_calls']!=1 or x['gpu_dispatches']!=own['dispatches'] for x in result['requests']):raise RuntimeError('actual normal pipeline/dispatch changed')
     print(json.dumps({'round':index,'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
     if not result['scores']['valid']:raise RuntimeError('invalid warm round retained')
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
