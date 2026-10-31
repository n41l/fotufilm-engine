#!/usr/bin/env python3
"""Reverse-order repeat of the known cleanup-overlapped Portra 1080p diagnosis.

Retains the source campaign; never replaces a round or declares formal acceptance.
"""
import argparse,importlib.util,json,shutil,subprocess,uuid
from pathlib import Path

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 c=Path(__file__).resolve().parents[1];b=module('baseline',c/'tools/run-wavefront-baseline.py');diag=module('diag',c/'tools/run-wavefront-latency-diagnostic.py')
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('source-report','fixtures','verification','baseline-report','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();source=json.loads(a.source_report.read_text());f=json.loads(a.fixtures.read_text());v=json.loads(a.verification.read_text());old=json.loads(a.baseline_report.read_text())
 if not source['complete'] or source['performance_acceptance'] or source['protocol']['ring_rows']!=2048:raise ValueError('matching completed diagnostic required')
 for path in (a.fixtures,a.verification,a.baseline_report):
  if source['source_reports'][str(path.resolve())]!=b.sha(path):raise ValueError('source report input changed')
 for name,row in source['workers'].items():
  if b.sha(row['path'])!=row['sha256']:raise ValueError('source worker changed')
 case=next(x for x in f['cases'] if x['id']=='portra400-coffee-1920x1080')
 for name in ('input','pack'):
  if b.sha(case[name])!=case[name+'_sha256']:raise ValueError('fixture changed')
 root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
 report={'scope':__doc__,'complete':False,'performance_acceptance':False,'B_ref_frozen':False,'band_selected':None,
  'source_report':str(a.source_report.resolve()),'source_report_sha256':b.sha(a.source_report),'case':case['id'],
  'reason':'controller cache removal overlapped first source E256 window; reverse-order clean follow-up, original retained',
  'protocol':source['protocol']|{'pair_order':{'512':['R','E'],'256':['E','R']}},'workers':source['workers'],
  'source_sha256':b.sha(Path(__file__)),'pairs':[]}
 def save():b.atomic_json(root/'report.json',report);b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
 save();print('RUN',root,flush=True)
 try:
  with b.awake_session() as helper:
   for band in (512,256):
    pair={'band':band};report['pairs'].append(pair)
    for arm in (('R','E') if band==512 else ('E','R')):
     b.require_awake(helper)
     if shutil.disk_usage(root).free<2*1024**3:raise RuntimeError('less than 2 GiB free')
     out=root/f'{band}-{arm}';b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
     result=b.run_round(Path(source['workers']['R' if arm=='R' else f'E{band}']['path']),Path(case['pack']),Path(case['input']),
      'B1' if arm=='R' else 'E',out,expected_band=None if arm=='R' else band,expected_ring_rows=2048)
     expected=(next(e['output_sha256'] for e in old['cases'][case['id']]['arms']['B1'][0]['phase_events'] if e['type']=='measurement_complete') if arm=='R'
      else next(x['C_output_sha256'] for x in v['results'] if x['case']==case['id'] and x['candidate']==f'E_{band}'))
     phases=[e for e in result['phase_events'] if e['type'] in ('warmup_complete','measurement_complete')]
     if len(phases)!=2 or any(e['output_sha256']!=expected for e in phases):raise RuntimeError('own-arm frozen pixel hash mismatch')
     pair[arm]=b.compact(result,out/'round.json');save();print(json.dumps({'band':band,'arm':arm,'scores':result['scores']}),flush=True)
     if not result['scores']['valid']:raise RuntimeError('invalid follow-up round retained without replacement')
   report['assessment']=diag.summarize_pairs(report['pairs'],expected_bands=(512,256));report['complete']=True
 except BaseException as error:report['failure']=str(error);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)

if __name__=='__main__':main()
