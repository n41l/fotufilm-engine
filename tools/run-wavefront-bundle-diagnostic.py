#!/usr/bin/env python3
"""One paired pilot per frozen case: original E2 versus two-stage bundled cut.

Diagnostic only. A repeated campaign follows only if complete costs warrant it;
this pilot cannot freeze B_ref or pass PR gates. No image dumps or cache purge.
"""
import argparse,importlib.util,json,os,shutil,uuid
from pathlib import Path

def main():
 c=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('b',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('proof','trace','fixtures','output'):p.add_argument('--'+name,required=True,type=Path)
 a=p.parse_args();proof=json.loads(a.proof.read_text());trace=json.loads(a.trace.read_text());frozen=json.loads(a.fixtures.read_text())
 if not proof['complete'] or not all(x['passed'] for x in proof['results']) or not trace['passed']:raise ValueError('complete pixel/trace proofs required')
 if b.sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common timed driver changed')
 workers={k:Path(proof['workers'][k]['path']) for k in ('2','bundle')}
 for k,v in workers.items():
  if b.sha(v)!=proof['workers'][k]['sha256']:raise ValueError('verified worker changed')
 for case in frozen['cases']:
  for name in ('input','pack'):
   if b.sha(case[name])!=case[name+'_sha256']:raise ValueError('fixture changed')
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
 report={'scope':__doc__,'complete':False,'performance_acceptance':False,'B_ref_frozen':False,
  'protocol':{'band_rows':512,'light_ring_rows':2048,'producer_margin':360,'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,
   'inflight_frames':1,'pool_mib':1024,'pairs_per_case':1,'minimum_free_bytes':1024**3,'evidence_budget_bytes':128*1024**2,'image_dumps':False,
   'order_policy':'alternate old/new by case; one paired pilot, no causal or acceptance claim'},
  'workers':{k:{'path':str(v),'sha256':b.sha(v)} for k,v in workers.items()},
  'sources':{str(x.resolve()):b.sha(x) for x in (a.proof,a.trace,a.fixtures)},
  'controllers':{x:b.sha(c/'tools'/x) for x in ('run-wavefront-bundle-diagnostic.py','run-wavefront-baseline.py','wavefront_metrics.py')},'cases':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 try:
  with b.awake_session() as helper:
   for index,case in enumerate(frozen['cases']):
    row={'case':case['id'],'order':['2','bundle'] if index%2==0 else ['bundle','2'],'arms':{}};report['cases'].append(row);save()
    fields=next(x for x in trace['results'] if x['case']==case['id'])['fields'];heights=[x['height'] for x in fields]
    for arm in row['order']:
     b.require_awake(helper)
     if shutil.disk_usage(root).free<1024**3:raise RuntimeError('less than 1 GiB free; pilot stopped before another worker')
     if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>128*1024**2:raise RuntimeError('pilot evidence budget reached')
     out=root/(case['id']+'-'+arm);b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
     result=b.run_round(workers[arm],Path(case['pack']),Path(case['input']),'E',out,expected_band=512,expected_ring_rows=2048,
      expected_cut='bundle' if arm=='bundle' else 'post_mtf',expected_field_rows=heights if arm=='bundle' else None)
     row['arms'][arm]=b.compact(result,out/'round.json');save()
     expected=next(x['C_output_sha256'] for x in proof['results'] if x['case']==case['id'] and x['worker']==arm)
     phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
     if len(phases)!=2 or any(x['output_sha256']!=expected for x in phases):raise RuntimeError('own-arm verified output hash mismatch; attempt retained')
     print(json.dumps({'case':case['id'],'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
     if not result['scores']['valid']:raise RuntimeError('invalid pilot round retained')
    row['observed_median_reduction']=1-row['arms']['bundle']['scores']['median_seconds']/row['arms']['2']['scores']['median_seconds'];save()
  report['complete']=True
 except BaseException as error:report['failure']=str(error);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
