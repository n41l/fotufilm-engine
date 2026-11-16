#!/usr/bin/env python3
"""Shared fourteen-call fixture crossing stride1/4/1/2, with actual Metal branch checks."""
import argparse,gzip,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from wavefront_aot_driver import build
from windowed_unit_helper import ARMS,NAMES

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def metal_functions(folder):
 result={};sources={}
 for log in folder.glob('*.log'):
  paths=set(re.findall(r'/tmp/metal\w+\.metal',log.read_text()))
  for source in paths:
   path=Path(source);text=path.read_text();sources[source]=sha(path)
   for m in re.finditer(r'kernel void (\w+)\([\s\S]*?\} // kernel \1',text):
    if re.search(r'_kernel_frame_coupler_diffused_.*_down_',m.group(1)):
     result[m.group(1)]={'for_statements':len(re.findall(r'\bfor\s*\(',m.group(0))),'has_box_sum':'_down_sum' in m.group(0) or '_generic_down_sum' in m.group(0),'source':source}
 return result,sources

def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('proof','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();proof=json.loads(a.proof.read_text());root=a.output.resolve();root.mkdir();ref=a.reference.resolve();b=Path(proof['build']);driver=c/'tools/windowed-unit-history.cpp';observer=b/'kernel-observer.dylib'
 if not proof['complete'] or len(proof['results'])!=24:raise ValueError('complete24-row pixel proof required')
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True):raise ValueError('R must remain clean')
 workers={'R-B1':build(ref,ref/'build/wavefront-macos',root/'R-build',driver)}
 for arm in ARMS:workers[arm]=build(c,b/'control/kernels',root/(arm+'-build'),driver,diagnostic_control=b/'control',diagnostic_kernels=b/arm,windowed_coupler_research=True)
 packs=[Path(next(x for x in proof['cases'] if x['id']==n)['pack']) for n in ('portra400-coffee-3840x2160','hp5plus400-coffee-1920x1080')]
 kernels={};sources={}
 for arm in ('Generic','Unit'):kernels[arm],sources[arm]=metal_functions(b/arm)
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'reference_base':proof['reference_base'],'pixel_proof':{'path':str(a.proof.resolve()),'sha256':sha(a.proof)},'driver_sha256':sha(driver),'observer_sha256':sha(observer),'packs':{str(x):sha(x) for x in packs},'workers':{k:{'path':str(v),'sha256':sha(v)} for k,v in workers.items()},'generated_metal_sha256':sources,'R_frames':[],'results':[],'kernel_checks':[],'streaming':'each worker awaits stdin acknowledgment after one completed dumped frame'}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save();proc=None
 try:
  for arm,w in workers.items():
   if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
   folder=root/arm;folder.mkdir();count=0;frames=[]
   env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024','FOTUFILM_HISTORY_ACK':'1'}
   if arm in kernels:env.update({'DYLD_INSERT_LIBRARIES':str(observer),'FOTUFILM_UNIT_KERNEL_OBSERVER':'1'})
   with (folder/'events.jsonl').open('w') as log,(folder/'stderr.log').open('w') as err:
    proc=subprocess.Popen([str(w),*map(str,packs),str(folder)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,env=env)
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
      result=subprocess.run([proof['compare'],str(temp),str(dump),left['encoding']],capture_output=True,text=True);comparison=json.loads(result.stdout);ok=result.returncode==0 and comparison['passed'];active=e['actual_variant'] in NAMES;bitwise=sha(dump)==r['raw_sha256']
      report['results'].append({'arm':arm,'frame':frame,'event':e,'active':active,'comparison':comparison,'bitwise_equal_R_B1':bitwise,'output_sha256':sha(dump),'passed':ok});save()
      if not ok or ((arm=='W0' or not active) and not bitwise):raise ValueError('history pixel disagreement; dumps retained')
      temp.unlink();dump.unlink();print('PASS',arm,frame,'active',active,flush=True)
     frames.append(e);count+=1;proc.stdin.write('\n');proc.stdin.flush()
    if proc.wait(timeout=600)!=0 or count!=14:raise ValueError('incomplete history worker')
   proc=None
   if arm in kernels:
    text=(folder/'stderr.log').read_text()
    if 'UNIT_OBSERVER_READY' not in text:raise ValueError('Metal observer did not load')
    observed={};sigmas={};current=None
    for line in text.splitlines():
     m=re.match(r'UNIT_FRAME (\d+) sigma=(\S+)',line)
     if m:current=int(m[1]);sigmas[current]=float(m[2]);observed[current]=[]
     elif line.startswith('UNIT_GPU_KERNEL '):observed[current].append(line.split()[1])
    for e in frames:
     frame=e['frame']
     if e['actual_variant'] not in NAMES:continue
     names=observed.get(frame,[])
     if not names or any(n not in kernels[arm] for n in names):raise ValueError('actual selected Coupler kernel missing from generated source')
     unit=arm=='Unit' and sigmas[frame]<2
     checks=[kernels[arm][n] for n in names]
     if any((x['for_statements']==0)!=unit or (unit and x['has_box_sum']) for x in checks):raise ValueError('actual stride branch did not remove/preserve box reduction')
     report['kernel_checks'].append({'arm':arm,'frame':frame,'sigma':sigmas[frame],'unit_branch':unit,'actual_kernels':names,'generated_properties':checks,'passed':True});save()
   z=w.with_name('runner.gz');rawhash=sha(w)
   with w.open('rb') as src,gzip.open(z,'wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst)
   with gzip.open(z,'rb') as src:
    digest=hashlib.sha256()
    while chunk:=src.read(1024*1024):digest.update(chunk)
   if digest.hexdigest()!=rawhash:raise ValueError('lossless history archive changed bytes')
   report['workers'][arm].update({'gzip':str(z),'gzip_sha256':sha(z),'restore':'gzip -dc ARCHIVE > PATH; chmod +x PATH; verify raw SHA256'});w.unlink();save()
  if len(report['results'])!=42 or len(report['kernel_checks'])!=16:raise ValueError('complete42 comparisons and16 actual-kernel checks required')
  if not any(x['arm']=='Unit' and x['unit_branch'] for x in report['kernel_checks']) or not any(x['arm']=='Unit' and not x['unit_branch'] for x in report['kernel_checks']):raise ValueError('stride transition coverage missing')
  report['complete']=True
 except BaseException as e:
  report['failure']=str(e)
  if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=30)
  raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
