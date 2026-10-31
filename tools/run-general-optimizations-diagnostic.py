#!/usr/bin/env python3
"""Seven-arm general optimization pilot, one round per arm/frozen case.

Fresh original R-B0/R-B1, same-source G0 and four isolated options. Full-frame
single-call paths only; diagnostic data cannot freeze B_ref or pass PR gates.
"""
import argparse,hashlib,importlib.util,json,shutil,subprocess,uuid
from pathlib import Path
from prepare_general_helper import ARMS
ORDER=('R-B0','G0','registers','normalized','counted','radius1','R-B1')
def expected_row(proof,case,arm):
 rows=[x for x in proof['results'] if x['case']==case and x['arm']==arm]
 if len(rows)!=1 or not rows[0]['passed']:raise ValueError('unique successful own-arm proof required')
 return rows[0]
def main():
 c=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('b',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','history','fixtures','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();proof=json.loads(a.proof.read_text());history=json.loads(a.history.read_text());frozen=json.loads(a.fixtures.read_text());ref=a.reference.resolve()
 if not proof['complete'] or len(proof['results'])!=28 or not all(x['passed'] for x in proof['results']):raise ValueError('complete28-row pixel proof required')
 if not history['complete'] or len(history['results'])!=70 or not all(x['passed'] for x in history['results']):raise ValueError('complete70-frame history proof required')
 if history['pixel_proof']['sha256']!=b.sha(a.proof):raise ValueError('history belongs to another proof')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('R must remain clean')
 if subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base'] or proof['reference_base']!=frozen['source_base']:raise ValueError('R base changed')
 if b.sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common driver changed')
 for w in proof['workers'].values():
  if b.sha(w['path'])!=w['sha256']:raise ValueError('verified worker changed')
 for arm in ARMS:
  identity=proof['identities'][arm]
  if b.sha(identity['path'])!=identity['sha256']:raise ValueError('arm archive identity changed')
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'B_ref_frozen':False,'reference_base':proof['reference_base'],'source_key':proof['source_key'],'arm_options':ARMS,'workers':proof['workers'],
  'protocol':{'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,'inflight_frames':1,'pool_mib':1024,'rounds_per_arm_case':1,'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'image_dumps':False,'order_policy':'predeclared seven-arm order, rotate by two places for each case'},
  'sources':{str(v.resolve()):b.sha(v) for v in (a.proof,a.history,a.fixtures)},'controllers':{n:b.sha(c/'tools'/n) for n in ('run-general-optimizations-diagnostic.py','prepare_general_helper.py','run-wavefront-baseline.py','wavefront_metrics.py')},'cases':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 try:
  with b.awake_session() as helper:
   for index,case in enumerate(frozen['cases']):
    for n in ('input','pack'):
     if b.sha(case[n])!=case[n+'_sha256']:raise ValueError('frozen input changed')
    offset=(index*2)%len(ORDER);order=ORDER[offset:]+ORDER[:offset];row={'case':case['id'],'order':order,'arms':{}};report['cases'].append(row);save()
    for arm in order:
     b.require_awake(helper)
     if shutil.disk_usage(root).free<1024**3:raise RuntimeError('less than1GiB free; stop before next arm')
     if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>256*1024**2:raise RuntimeError('evidence budget reached')
     own=expected_row(proof,case['id'],arm);worker=Path(proof['workers'][arm]['path']);out=root/(case['id']+'-'+arm)
     b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
     result=b.run_round(worker,Path(case['pack']),Path(case['input']),'B1' if arm=='R-B1' else 'B0',out)
     row['arms'][arm]=b.compact(result,out/'round.json');save()
     phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
     if len(phases)!=2 or any(x['output_sha256']!=own['output_sha256'] for x in phases):raise RuntimeError('own-arm normal proof hash mismatch; retain attempt')
     if any(x['actual_variant']!=own['actual'] or x['aot_calls']!=1 or x['gpu_dispatches']!=own['dispatches'] for x in result['requests']):raise RuntimeError('actual general pipeline/GPU work changed')
     print(json.dumps({'case':case['id'],'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
     if not result['scores']['valid']:raise RuntimeError('invalid warm round retained')
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
