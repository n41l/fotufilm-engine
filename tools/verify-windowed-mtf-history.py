#!/usr/bin/env python3
"""Fourteen calls per process; UHD luma calibration stresses the active twin at HD geometry."""
import argparse,gzip,hashlib,json,os,shutil,subprocess
from pathlib import Path
from wavefront_aot_driver import build
from windowed_mtf_helper import ARMS,NAME

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','original-history','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.output.resolve();root.mkdir();proof=json.loads(a.proof.read_text());old=a.original_history.resolve();previous=json.loads((old/'verification.json').read_text());driver=c/'tools/wavefront-lifecycle.cpp';b=Path(proof['build'])
 if not proof['complete'] or len(proof['results'])!=15 or not all(x['passed'] for x in proof['results']):raise ValueError('complete main/odd proof required')
 if sha(driver)!=previous['driver_sha256'] or proof['reference_base']!=previous['reference_base']:raise ValueError('original driver or R base changed')
 rw=root/'R-runner';z=old/'R-build/runner.stage15.gz'
 with gzip.open(z,'rb') as src,rw.open('wb') as dst:shutil.copyfileobj(src,dst)
 if sha(rw)!=previous['runner_sha256']['R']:raise ValueError('frozen R worker changed')
 rw.chmod(0o755);workers={'R-B1':rw}
 for arm in ARMS:workers[arm]=build(c,b/'control/kernels',root/(arm+'-build'),driver,diagnostic_control=b/'control',diagnostic_kernels=b/arm,windowed_mtf_research=True)
 packs=[Path(next(x for x in proof['cases'] if x['id']==n)['pack']) for n in ('portra400-coffee-3840x2160','hp5plus400-coffee-1920x1080')]
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'pixel_proof':{'path':str(a.proof.resolve()),'sha256':sha(a.proof)},'driver_sha256':sha(driver),'original_history_identity':{'path':str(old/'verification.json'),'sha256':sha(old/'verification.json')},'packs':{str(x):sha(x) for x in packs},'workers':{k:{'path':str(v),'sha256':sha(v)} for k,v in workers.items()},'R_frames':[],'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save();proc=None
 try:
  for arm,w in workers.items():
   if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
   folder=root/arm;folder.mkdir();count=0
   with (folder/'events.jsonl').open('w') as log,(folder/'stderr.log').open('w') as err:
    proc=subprocess.Popen([str(w),*map(str,packs),str(folder)],stdout=subprocess.PIPE,stderr=err,text=True,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'})
    for line in proc.stdout:
     log.write(line);log.flush();e=json.loads(line)
     if e['type']!='frame' or not e['finite'] or not e['alpha_exact']:raise ValueError('invalid history event')
     frame=e['frame'];dump=folder/f'{frame}.rgba32f'
     if arm=='R-B1':
      target=folder/f'{frame}.rgba32f.gz';rawhash=sha(dump)
      with dump.open('rb') as src,gzip.open(target,'wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
      report['R_frames'].append({'event':e,'raw_sha256':rawhash,'gzip_sha256':sha(target)});save();dump.unlink()
     else:
      r=report['R_frames'][count];left=r['event']
      if any(e[k]!=left[k] for k in ('frame','width','height','seed','encoding','feature_mask','origin','actual_variant')):raise ValueError('history sequence/selector changed')
      z=root/'R-B1'/f'{frame}.rgba32f.gz';temp=folder/'R-current.rgba32f'
      if sha(z)!=r['gzip_sha256']:raise ValueError('R gzip changed')
      with gzip.open(z,'rb') as src,temp.open('wb') as dst:shutil.copyfileobj(src,dst)
      if sha(temp)!=r['raw_sha256']:raise ValueError('R pixels changed')
      result=subprocess.run([proof['compare'],str(temp),str(dump),left['encoding']],capture_output=True,text=True);comparison=json.loads(result.stdout);ok=result.returncode==0 and comparison['passed'];active=e['actual_variant']==NAME;bitwise=sha(dump)==r['raw_sha256']
      row={'arm':arm,'frame':frame,'event':e,'active':active,'comparison':comparison,'bitwise_equal_R_B1':bitwise,'output_sha256':sha(dump),'passed':ok};report['results'].append(row);save()
      if not ok or ((arm=='W0' or not active) and not bitwise):raise ValueError('history pixel disagreement; dumps retained')
      temp.unlink();dump.unlink();print('PASS',arm,frame,'active',active,flush=True)
     count+=1
    if proc.wait(timeout=600)!=0 or count!=14:raise ValueError('incomplete history worker')
   proc=None
  for arm in ARMS:
   rows=[x for x in report['results'] if x['arm']==arm]
   if sum(x['active'] for x in rows)<7 or not any(x['active'] and x['event']['encoding']=='rec709' for x in rows):raise ValueError('active/encoded twin history missing')
  report['complete']=True
 except BaseException as e:
  report['failure']=str(e)
  if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=30)
  raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
