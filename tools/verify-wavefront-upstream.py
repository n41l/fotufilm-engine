#!/usr/bin/env python3
"""Verify the frozen upstream windowed arm directly against the bundled E2 worker.

Uses already-built, hash-verified workers; successful temporary dumps are removed.
Original general R pixel proof is retained independently by the candidate report.
"""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path

def main():
 c=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('b',c/'tools/run-wavefront-baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('candidate-proof','reference','reference-worker','fixtures','compare','output'):p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();proof=json.loads(a.candidate_proof.read_text());frozen=json.loads(a.fixtures.read_text());ref=a.reference.resolve();worker=a.reference_worker.resolve();cw=Path(proof['workers']['bundle']['path'])
 if not proof['complete'] or not all(x['passed'] for x in proof['results']):raise ValueError('complete candidate general-R pixel proof required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('reference must remain clean')
 base=subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()
 if base!=frozen['source_base'] or b.sha(worker)!=frozen['worker_sha256'] or b.sha(cw)!=proof['workers']['bundle']['sha256']:raise ValueError('frozen reference/candidate identity changed')
 out=a.output.resolve();out.mkdir(parents=True)
 report={'scope':__doc__,'complete':False,'performance_acceptance':False,'reference_base':base,
  'workers':{'R':{'path':str(worker),'sha256':b.sha(worker)},'bundle':{'path':str(cw),'sha256':b.sha(cw)}},
  'source_reports':{str(x.resolve()):b.sha(x) for x in (a.candidate_proof,a.fixtures)},'compare':{'path':str(a.compare.resolve()),'sha256':b.sha(a.compare)},'results':[]}
 def save():b.atomic_json(out/'report.json',report)
 save()
 try:
  for case in frozen['cases']:
   for n in ('input','pack'):
    if b.sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
   folder=out/case['id'];folder.mkdir();dumps={}
   for label,w in (('R-B1',worker),('bundle',cw)):
    dump=folder/(label+'.rgba32f');dumps[label]=dump
    with (folder/(label+'.jsonl')).open('w') as stdout,(folder/(label+'.stderr')).open('w') as stderr:
     subprocess.run([str(w),case['pack'],case['input'],'--dump',str(dump)],check=True,stdout=stdout,stderr=stderr,timeout=120,
      env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1' if label=='R-B1' else '0','FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0','FOTUFILM_WAVEFRONT_BENCH_ROWS':'512'})
    events=[json.loads(x) for x in (folder/(label+'.jsonl')).read_text().splitlines()];call=next(x for x in events if x['type']=='call_complete')
    valid=(call['status']=='success' and call['gpu_dispatches']>=call['aot_calls']>=1)
    valid=valid and (('_windowed' in call['actual_variant'] and '_wavefront_' not in call['actual_variant'] and call['aot_calls']==1) if label=='R-B1' else ('_wavefront_bundle_' in call['actual_variant']))
    if not valid:raise ValueError('requested original/new pipeline did not execute')
   result=subprocess.run([str(a.compare),str(dumps['R-B1']),str(dumps['bundle']),'linear'],capture_output=True,text=True);pixels=json.loads(result.stdout)
   expected=next(x['C_output_sha256'] for x in proof['results'] if x['case']==case['id'] and x['worker']=='bundle')
   passed=result.returncode==0 and pixels['passed'] and b.sha(dumps['bundle'])==expected
   row={'case':case['id'],'comparison':pixels,'R_B1_output_sha256':b.sha(dumps['R-B1']),'C_output_sha256':b.sha(dumps['bundle']),'passed':passed}
   report['results'].append(row);save();print(case['id'],row,flush=True)
   if not passed:raise ValueError('direct original-windowed pixel disagreement; dumps retained')
   for dump in dumps.values():dump.unlink()
  report['complete']=True
 except BaseException as error:report['failure']=str(error);raise
 finally:save()
 print('REPORT',out/'report.json',flush=True)
if __name__=='__main__':main()
