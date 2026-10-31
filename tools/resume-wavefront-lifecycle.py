#!/usr/bin/env python3
"""Repeat a C frame-history process, streaming comparisons against verified saved R.

Retains the failed attempt. Compress/decompress only between completed synchronous
frames; no timing score is produced. The C worker and R hashes stay frozen.
"""
import argparse,gzip,hashlib,json,os,shutil,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('failed-run','output','catalog'):p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();old=a.failed_run.resolve();root=a.output.resolve();root.mkdir();(root/'C').mkdir();data=json.loads((old/'verification.json').read_text())
 rframes=[json.loads(x) for x in (old/'R/events.jsonl').read_text().splitlines() if json.loads(x)['type']=='frame']
 if len(rframes)!=14 or len(data.get('reference_dump_compression',{}))!=14:raise ValueError('14 complete hashed R frames required')
 worker=old/'C-build/runner';compare=old/'compare'
 if sha(worker)!=data['runner_sha256']['C']:raise ValueError('C worker changed')
 catalog=json.loads(a.catalog.read_text());packs=[]
 for stock in ('portra400','hp5plus400'):
  f=next(x for x in catalog['fixtures'] if x['stock']==stock and x['size']=='1920x1080');path=(a.catalog.parent/f['path']).resolve()
  if sha(path)!=f['sha256'] or sha(path)!=data['pack_sha256'][path.name]:raise ValueError('pack changed')
  packs.append(path)
 report={**{k:data[k] for k in ('reference_base','driver_sha256','runner_sha256','stage_count','cut','failure_edge')},'scope':__doc__,'complete':False,'performance_acceptance':False,
  'prior_attempt':{'path':str(old/'verification.json'),'sha256':sha(old/'verification.json')},'results':[],'events':[]}
 def save():(root/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 save();proc=None
 try:
  with (root/'events.jsonl').open('w') as out,(root/'stderr.log').open('w') as err:
   proc=subprocess.Popen([str(worker),*map(str,packs),str(root/'C')],stdout=subprocess.PIPE,stderr=err,text=True,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0','FOTUFILM_METAL_POOL':'1024'})
   for line in proc.stdout:
    out.write(line);out.flush();e=json.loads(line);report['events'].append(e)
    if e['type']!='frame':save();continue
    idx=len(report['results']);left=rframes[idx]
    if e['frame']!=left['frame'] or any(e[k]!=left[k] for k in ('width','height','seed','encoding','feature_mask','origin')):raise ValueError('frame history changed')
    frame=e['frame'];expected=frame<4 or frame==9 or frame==12 or frame==13
    if e['actual_mode']!=int(expected) or ('_wavefront_' in e['actual_variant'])!=expected or not e['finite'] or not e['alpha_exact']:raise ValueError('actual mode or finite/alpha guard failed')
    z=old/'R'/f'{frame}.rgba32f.gz';proof=data['reference_dump_compression'][str(frame)]
    if sha(z)!=proof['gzip_sha256']:raise ValueError('saved R changed')
    lp=root/'R-current.rgba32f';rp=root/'C'/f'{frame}.rgba32f'
    with gzip.open(z,'rb') as src,lp.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
    if sha(lp)!=proof['raw_sha256']:raise ValueError('R pixels changed')
    r=subprocess.run([str(compare),str(lp),str(rp),left['encoding']],capture_output=True,text=True);pixels=json.loads(r.stdout)
    passed=r.returncode==0 and pixels['passed'] and pixels['samples']==left['width']*left['height']*4
    report['results'].append({'R':left,'C':e,'R_output_sha256':sha(lp),'C_output_sha256':sha(rp),'comparison':pixels,'passed':passed});save()
    if not passed:raise ValueError('pixels failed; dumps preserved')
    lp.unlink();rp.unlink();print('PASS frame',frame,e['actual_variant'],flush=True)
   if proc.wait(timeout=600)!=0:raise ValueError('C frame-history worker failed')
  ev=report['events']
  if len(report['results'])!=14 or not any(x['type']=='invalid_options' and x['passed'] and x['checks']==4 for x in ev) or not any(x['type']=='injected_failure' and x['passed'] and x['drained'] for x in ev):raise ValueError('history/options/fault-drain evidence missing')
  report['complete']=True
 except BaseException as e:
  report['failure']=str(e)
  if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=30)
  raise
 finally:save()
 print('REPORT',root/'verification.json',flush=True)
if __name__=='__main__':main()
