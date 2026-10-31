#!/usr/bin/env python3
"""Three-arm pilot: original windowed1080 vs same-build bundle512/bundle1080.

One round per case/arm; no causal, stable-B_ref or performance acceptance claim.
"""
import argparse,importlib.util,json,shutil,subprocess,uuid
from pathlib import Path

def main():
 c=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('baseline',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','fixtures','reference','output'):p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();proof=json.loads(a.proof.read_text());frozen=json.loads(a.fixtures.read_text());ref=a.reference.resolve()
 if not proof['complete'] or len(proof['results'])!=16 or not all(x['passed'] for x in proof['results']):raise ValueError('all16 pixel/trace proofs required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('R must remain clean')
 if subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('R changed')
 if b.sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common driver changed')
 for key in ('bundle','R-B1'):
  if b.sha(Path(proof['workers'][key]['path']))!=proof['workers'][key]['sha256']:raise ValueError('verified worker changed')
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
 report={'scope':__doc__,'complete':False,'performance_acceptance':False,'B_ref_frozen':False,'reference_base':proof['reference_base'],
  'protocol':{'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,'inflight_frames':1,'pool_mib':1024,'bands':[512,1080],
   'light_ring_rows':2048,'producer_margin':360,'rounds_per_arm_case':1,'minimum_free_bytes':1024**3,'image_dumps':False,'evidence_budget_bytes':128*1024**2},
  'workers':proof['workers'],'proof':{'path':str(a.proof.resolve()),'sha256':b.sha(a.proof)},'fixtures':{'path':str(a.fixtures.resolve()),'sha256':b.sha(a.fixtures)},
  'controllers':{n:b.sha(c/'tools'/n) for n in ('run-wavefront-bands-diagnostic.py','run-wavefront-baseline.py','wavefront_metrics.py')},'cases':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 orders=(('R-B1','E512','E1080'),('E512','E1080','R-B1'),('E1080','R-B1','E512'),('E1080','E512','R-B1'))
 try:
  with b.awake_session() as helper:
   for index,case in enumerate(frozen['cases']):
    for n in ('input','pack'):
     if b.sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
    row={'case':case['id'],'order':orders[index],'arms':{}};report['cases'].append(row);save()
    for arm in row['order']:
     b.require_awake(helper)
     if shutil.disk_usage(root).free<1024**3:raise RuntimeError('less than1GiB free; stopped before next arm')
     if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>128*1024**2:raise RuntimeError('evidence budget reached')
     band=int(arm[1:]) if arm.startswith('E') else None;worker=Path(proof['workers']['bundle' if band else 'R-B1']['path']);out=root/(case['id']+'-'+arm)
     b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
     r=next(x for x in proof['results'] if x['case']==case['id'] and x['worker']=='bundletrace' and x['band']==(band or 1080))
     heights=[f['height'] for f in r['trace']['fields']]
     result=b.run_round(worker,Path(case['pack']),Path(case['input']),'E' if band else 'B1',out,
      **({'expected_band':band,'expected_ring_rows':2048,'expected_cut':'bundle','expected_field_rows':heights} if band else {}))
     row['arms'][arm]=b.compact(result,out/'round.json');save()
     expected=r['C_output_sha256'] if band else r['R_B1_output_sha256'];phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
     if len(phases)!=2 or any(x['output_sha256']!=expected for x in phases):raise RuntimeError('own-arm verified phase hash mismatch')
     print(json.dumps({'case':case['id'],'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
     if not result['scores']['valid']:raise RuntimeError('invalid round retained')
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
