#!/usr/bin/env python3
"""Current-source JIT/AOT parity for both twins, nonlinear release and odd two-window geometry."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','jit','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();proof=json.loads(a.proof.read_text());root=a.output.resolve();root.mkdir();c=Path(__file__).resolve().parents[1]
 if not proof['complete'] or len(proof['results'])!=18:raise ValueError('complete independent pixel proof required')
 report={'complete':False,'scope':__doc__,'source_key':proof['source_key'],'pixel_proof_sha256':sha(a.proof),'jit_worker':{'path':str(a.jit.resolve()),'sha256':sha(a.jit)},'jit_source_sha256':sha(c/'tools/windowed-coupler-jit.cpp'),'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for case_id in ('portra400-coarse-odd-1919x1081','portra400-luma-odd-65x1081'):
   case=next(x for x in proof['cases'] if x['id']==case_id);folder=root/case_id;folder.mkdir()
   for arm in ('W0','Fused'):
    worker=proof['workers'][arm]
    if sha(worker['path'])!=worker['sha256']:raise ValueError('AOT worker changed')
    left=folder/(arm+'-aot.rgba32f');right=folder/(arm+'-jit.rgba32f')
    with (folder/(arm+'-aot.jsonl')).open('w') as out,(folder/(arm+'-aot.stderr')).open('w') as err:subprocess.run([worker['path'],case['pack'],case['input'],'--dump',str(left)],stdout=out,stderr=err,check=True,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'})
    with (folder/(arm+'-jit.log')).open('w') as log:subprocess.run([str(a.jit.resolve()),case['pack'],case['input'],str(right),'1' if arm=='Fused' else '0'],stdout=log,stderr=log,check=True,timeout=600)
    p=subprocess.run([proof['compare'],str(left),str(right),'linear'],capture_output=True,text=True);comparison=json.loads(p.stdout);ok=p.returncode==0 and comparison['passed'];report['results'].append({'case':case_id,'arm':arm,'comparison':comparison,'passed':ok});save()
    if not ok:raise ValueError('JIT/AOT mismatch; dumps retained')
    left.unlink();right.unlink();print('PASS',case_id,arm,comparison,flush=True)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
if __name__=='__main__':main()
