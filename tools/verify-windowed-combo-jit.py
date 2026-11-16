#!/usr/bin/env python3
"""Targeted current-source MTF JIT/AOT parity for the combination arms, odd two-window geometry."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','jit','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();proof=json.loads(a.proof.read_text());root=a.output.resolve();root.mkdir();c=Path(__file__).resolve().parents[1]
 if not proof['complete'] or len(proof['results'])!=25:raise ValueError('complete combination pixel proof required')
 report={'complete':False,'scope':__doc__,'source_key':proof['source_key'],'pixel_proof_sha256':sha(a.proof),'jit_worker':{'path':str(a.jit.resolve()),'sha256':sha(a.jit)},'jit_source_sha256':sha(c/'tools/windowed-mtf-jit.cpp'),'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  case=next(x for x in proof['cases'] if x['id']=='portra400-odd-1919x1081');folder=root/case['id'];folder.mkdir()
  for arm in ('W0','MTF'):
   worker=proof['workers'][arm]
   if sha(worker['path'])!=worker['sha256']:raise ValueError('AOT worker changed')
   left=folder/(arm+'-aot.rgba32f');right=folder/(arm+'-jit.rgba32f')
   with (folder/(arm+'-aot.jsonl')).open('w') as out,(folder/(arm+'-aot.stderr')).open('w') as err:subprocess.run([worker['path'],case['pack'],case['input'],'--dump',str(left)],stdout=out,stderr=err,check=True,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'})
   with (folder/(arm+'-jit.log')).open('w') as log:subprocess.run([str(a.jit.resolve()),case['pack'],case['input'],str(right),'1' if arm=='MTF' else '0'],stdout=log,stderr=log,check=True,timeout=600)
   r=subprocess.run([proof['compare'],str(left),str(right),'linear'],capture_output=True,text=True);comparison=json.loads(r.stdout);ok=r.returncode==0 and comparison['passed'];report['results'].append({'case':case['id'],'arm':arm,'comparison':comparison,'passed':ok});save()
   if not ok:raise ValueError('JIT/AOT mismatch; dumps retained')
   left.unlink();right.unlink();print('PASS',arm,comparison,flush=True)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
