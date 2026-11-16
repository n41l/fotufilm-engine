#!/usr/bin/env python3
"""Bounded contemporaneous upstream general/default-windowed versus new E2 pilot.

One warm round per arm per frozen case; never freezes B_ref or passes PR gates.
R-B0 is upstream general, R-B1 is the original enabled-window selector on these
eligible cases. Retain both controls and every unsuccessful attempt.
"""
import argparse,importlib.util,json,shutil,subprocess,uuid
from pathlib import Path
def main():
 c=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('baseline',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','upstream-proof','trace','fixtures','reference','output'):p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();proof=json.loads(a.proof.read_text());up=json.loads(a.upstream_proof.read_text());tr=json.loads(a.trace.read_text());frozen=json.loads(a.fixtures.read_text());ref=a.reference.resolve()
 for d in (proof,up):
  if not d['complete'] or len(d['results'])<4 or not all(x['passed'] for x in d['results']):raise ValueError('complete direct general/windowed pixel proofs required')
 if not tr['passed']:raise ValueError('complete bundled trace proof required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('R must remain clean')
 base=subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()
 if base!=frozen['source_base'] or base!=up['reference_base']:raise ValueError('reference base changed')
 if b.sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common timed driver changed')
 workers={'R-B0':Path(up['workers']['R']['path']),'R-B1':Path(up['workers']['R']['path']),'bundle':Path(proof['workers']['bundle']['path'])}
 if b.sha(workers['R-B0'])!=frozen['worker_sha256'] or b.sha(workers['R-B0'])!=up['workers']['R']['sha256'] or b.sha(workers['bundle'])!=proof['workers']['bundle']['sha256']:raise ValueError('frozen workers changed')
 expected={}
 for case in frozen['cases']:
  for n in ('input','pack'):
   if b.sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
  cp=next(x for x in proof['results'] if x['case']==case['id'] and x['worker']=='bundle');rp=next(x for x in up['results'] if x['case']==case['id'])
  if cp['C_output_sha256']!=rp['C_output_sha256']:raise ValueError('candidate pixel proof disagreement')
  expected[case['id']]={'R-B0':cp['R_output_sha256'],'R-B1':rp['R_B1_output_sha256'],'bundle':cp['C_output_sha256']}
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
 report={'scope':__doc__,'complete':False,'performance_acceptance':False,'B_ref_frozen':False,'reference_base':base,
  'protocol':{'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,'inflight_frames':1,'pool_mib':1024,
   'candidate_band_rows':512,'candidate_light_ring_rows':2048,'candidate_producer_margin':360,'rounds_per_case_arm':1,'image_dumps':False,
   'minimum_free_bytes':1024**3,'evidence_budget_bytes':128*1024**2,'order_policy':'predeclared rotating three-arm order; fourth case reverses original arms; single-round diagnostic only'},
  'workers':{k:{'path':str(v),'sha256':b.sha(v)} for k,v in workers.items()},
  'source_reports':{str(x.resolve()):b.sha(x) for x in (a.proof,a.upstream_proof,a.trace,a.fixtures)},
  'controllers':{n:b.sha(c/'tools'/n) for n in ('run-wavefront-upstream-diagnostic.py','run-wavefront-baseline.py','wavefront_metrics.py')},'cases':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 orders=(('R-B0','R-B1','bundle'),('R-B1','bundle','R-B0'),('bundle','R-B0','R-B1'),('bundle','R-B1','R-B0'))
 try:
  with b.awake_session() as helper:
   for index,case in enumerate(frozen['cases']):
    row={'case':case['id'],'order':orders[index],'arms':{}};report['cases'].append(row);save()
    fields=next(x['fields'] for x in tr['results'] if x['case']==case['id']);heights=[x['height'] for x in fields]
    for arm in row['order']:
     b.require_awake(helper)
     if shutil.disk_usage(root).free<1024**3:raise RuntimeError('less than 1 GiB free; diagnostic stopped before next arm')
     if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>128*1024**2:raise RuntimeError('bounded evidence budget reached')
     out=root/(case['id']+'-'+arm);b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
     result=b.run_round(workers[arm],Path(case['pack']),Path(case['input']),'E' if arm=='bundle' else arm[2:],out,
      **({'expected_band':512,'expected_ring_rows':2048,'expected_cut':'bundle','expected_field_rows':heights} if arm=='bundle' else {}))
     row['arms'][arm]=b.compact(result,out/'round.json');save()
     phases=[x for x in result['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
     if len(phases)!=2 or any(x['output_sha256']!=expected[case['id']][arm] for x in phases):raise RuntimeError('verified own-arm output hash mismatch; attempt retained')
     print(json.dumps({'case':case['id'],'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
     if not result['scores']['valid']:raise RuntimeError('invalid original/candidate round retained')
    for original in ('R-B0','R-B1'):
     old=row['arms'][original];new=row['arms']['bundle'];row['bundle_vs_'+original]={
      'observed_median_reduction':1-new['scores']['median_seconds']/old['scores']['median_seconds'],
      'throughput_ratio':new['scores']['throughput_fps']/old['scores']['throughput_fps'],
      'device_peak_change_bytes':new['memory']['device_total_peak_bytes']-old['memory']['device_total_peak_bytes'],
      'thermal_states_differ':new['memory']['max_thermal_state']!=old['memory']['max_thermal_state']}
    save()
  report['complete']=True
 except BaseException as error:report['failure']=str(error);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
