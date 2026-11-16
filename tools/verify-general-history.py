#!/usr/bin/env python3
"""Whole-frame single-option histories against independently saved hashed R frames.

Streams each completed frame to comparison before removing successful dumps.
The active general graph retains all gates; still/exact legacy classes remain
frozen and are reported separately. No wavefront options or fault injection.
"""
import argparse,gzip,hashlib,json,os,shutil,subprocess
from pathlib import Path
from wavefront_aot_driver import build
from prepare_general_helper import ARMS

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','proof','reference-history','catalog','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--archive-workers',action='store_true')
 a=p.parse_args();root=a.output.resolve();root.mkdir();a.build=a.build.resolve();old=a.reference_history.resolve();pixels=json.loads(a.proof.read_text());data=json.loads((old/'verification.json').read_text())
 if not pixels['complete'] or not all(x['passed'] for x in pixels['results']) or pixels['reference_base']!=data['reference_base']:raise ValueError('matching complete pixel proof required')
 rframes=[json.loads(x) for x in (old/'R/events.jsonl').read_text().splitlines() if json.loads(x)['type']=='frame']
 if len(rframes)!=14 or len(data.get('reference_dump_compression',{}))!=14:raise ValueError('complete hashed R history required')
 catalog=json.loads(a.catalog.read_text());packs=[]
 for stock in ('portra400','hp5plus400'):
  row=next(x for x in catalog['fixtures'] if x['stock']==stock and x['size']=='1920x1080');path=(a.catalog.parent/row['path']).resolve()
  if sha(path)!=row['sha256'] or sha(path)!=data['pack_sha256'][path.name]:raise ValueError('history packs changed')
  packs.append(path)
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'reference_base':data['reference_base'],'R_history':{'path':str(old/'verification.json'),'sha256':sha(old/'verification.json')},'pixel_proof':{'path':str(a.proof.resolve()),'sha256':sha(a.proof)},'workers':{},'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 compare=Path(pixels['workers']['G0']['path']).parent.parent/'compare';driver=c/'tools/wavefront-lifecycle.cpp'
 if sha(driver)!=data['driver_sha256']:raise ValueError('common14-frame driver changed')
 save();proc=None
 try:
  for arm in ARMS:
   worker=build(c,a.build/'control/kernels',root/(arm+'-build'),driver,diagnostic_control=a.build/'control',diagnostic_kernels=a.build/arm,general_research=True)
   report['workers'][arm]={'path':str(worker),'sha256':sha(worker)};folder=root/arm;folder.mkdir();frames=[];save()
   with (folder/'events.jsonl').open('w') as log,(folder/'stderr.log').open('w') as err:
    proc=subprocess.Popen([str(worker),*map(str,packs),str(folder)],stdout=subprocess.PIPE,stderr=err,text=True,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'0','FOTUFILM_METAL_POOL':'1024'})
    for line in proc.stdout:
     log.write(line);log.flush();e=json.loads(line)
     if e['type']!='frame':raise ValueError('unexpected history event')
     left=rframes[len(frames)];frame=e['frame']
     if any(e[k]!=left[k] for k in ('frame','width','height','seed','encoding','feature_mask','origin')) or e['actual_mode']!=0 or '_windowed' in e['actual_variant'] or '_wavefront_' in e['actual_variant']:raise ValueError('general history mode/sequence changed')
     z=old/'R'/f'{frame}.rgba32f.gz';rp=folder/f'{frame}.rgba32f';lp=folder/'R-current.rgba32f';expected=data['reference_dump_compression'][str(frame)]
     if sha(z)!=expected['gzip_sha256']:raise ValueError('R gzip changed')
     with gzip.open(z,'rb') as src,lp.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
     if sha(lp)!=expected['raw_sha256']:raise ValueError('R history pixels changed')
     result=subprocess.run([str(compare),str(lp),str(rp),left['encoding']],capture_output=True,text=True);comparison=json.loads(result.stdout)
     passed=result.returncode==0 and comparison['passed'] and comparison['samples']==left['width']*left['height']*4 and e['finite'] and e['alpha_exact']
     active=e['actual_variant'] in ('fotufilm_halide_ios_color_float_realtime','fotufilm_halide_ios_monochrome_float_realtime')
     row={'arm':arm,'options':ARMS[arm],'frame':frame,'actual':e['actual_variant'],'uses_current_general_archive':active,'R':left,'C':e,'comparison':comparison,'R_output_sha256':sha(lp),'C_output_sha256':sha(rp),'passed':passed};report['results'].append(row);save()
     if not passed:raise ValueError('history pixel disagreement; dumps retained')
     lp.unlink();rp.unlink();frames.append(e);print('PASS',arm,'frame',frame,'active',active,flush=True)
    if proc.wait(timeout=600)!=0 or len(frames)!=14:raise ValueError('incomplete C frame-history worker')
   proc=None
   if a.archive_workers:
    z=worker.with_name('runner.gz');raw_hash=sha(worker)
    with worker.open('rb') as src,gzip.open(z,'wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst,1024*1024)
    with gzip.open(z,'rb') as src:
     h=hashlib.sha256()
     while chunk:=src.read(1024*1024):h.update(chunk)
     if h.hexdigest()!=raw_hash:raise ValueError('worker archive changed bytes')
    report['workers'][arm].update({'gzip':str(z),'gzip_sha256':sha(z),'restore':'gzip -dc ARCHIVE > PATH; chmod +x PATH; verify raw SHA256'})
    worker.unlink();save()
  report['complete']=True
 except BaseException as error:
  report['failure']=str(error)
  if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=30)
  raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
