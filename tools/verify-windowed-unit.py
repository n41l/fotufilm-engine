#!/usr/bin/env python3
"""Coupler unit-stride specialization vs original and matched off/generic controls."""
import argparse,hashlib,json,os,re,shutil,struct,subprocess
from pathlib import Path
from wavefront_aot_driver import build
from windowed_unit_helper import ARMS,NAMES

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','output','fixtures','reference'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.output.resolve();root.mkdir();a.build=a.build.resolve();ref=a.reference.resolve();frozen=json.loads(a.fixtures.read_text());rw=ref/'build/wavefront-benchmark-v2/instrumented/runner'
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base'] or sha(rw)!=frozen['worker_sha256']:raise ValueError('frozen R changed')
 if sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common driver changed')
 workers={'R-B1':rw}
 for arm,(enabled,unit) in ARMS.items():
  identity=json.loads((a.build/arm/'identity.json').read_text())
  if identity['fusion']!=enabled or identity.get('unit_stride')!=unit:raise ValueError('arm mismatch')
  workers[arm]=build(c,a.build/'control/kernels',root/arm,c/'tools/wavefront-benchmark.mm',diagnostic_control=a.build/'control',diagnostic_kernels=a.build/arm,windowed_coupler_research=True)
 compare=root/'compare';subprocess.run(['xcrun','clang++','-O2','-std=c++17',str(c/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
 cases=list(frozen['cases'])
 source=next(x for x in cases if x['id']=='portra400-coffee-3840x2160');oddroot=root/'odd-fixtures';oddroot.mkdir();header=(c/'Sources/FotufilmHalide/include/FotufilmConfigLayout.h').read_text()
 offset=lambda name:int(re.search(r'FOTUFILM_CONFIG_'+name+r' = (\d+)',header).group(1))
 for width,base_id,tag in [(1919,'portra400-coffee-1920x1080','coarse'),(65,'portra400-coffee-3840x2160','luma')]:
  base=next(x for x in cases if x['id']==base_id);pack=oddroot/(tag+'.fswp');image=oddroot/(tag+'.rgba32f');raw=bytearray(Path(base['pack']).read_bytes());h=list(struct.unpack_from('<10I',raw));h[2]=width;h[3]=1081;h[5]+=7;struct.pack_into('<10I',raw,0,*h)
  struct.pack_into('<3f',raw,40+4*offset('COUPLER_RELEASE_GAMMA'),1.7,0.8,2.3)
  if tag=='coarse':
   struct.pack_into('<f',raw,40+4*offset('COUPLER_SIGMA'),4.2);struct.pack_into('<f',raw,40+4*offset('COUPLER_RADIUS'),13)
  pack.write_bytes(raw)
  with Path(source['input']).open('rb') as src,image.open('wb') as dst:
   for y in range(1081):src.seek(y*3840*16);dst.write(src.read(width*16))
  cases.append({'id':f'portra400-{tag}-odd-{width}x1081','size':f'{width}x1081','pack':str(pack),'pack_sha256':sha(pack),'input':str(image),'input_sha256':sha(image),'scope':'crop of frozen UHD Coffee, two windows, changed seed and nonlinear release gamma [1.7,0.8,2.3]; coarse additionally sigma4.2/radius13/stride4'})
 report={'complete':False,'scope':__doc__,'performance_acceptance':False,'reference_base':frozen['source_base'],'source_key':(a.build/'W0/source-key.txt').read_text().strip(),'workers':{k:{'path':str(v),'sha256':sha(v)} for k,v in workers.items()},'build':str(a.build),'fixtures':{'path':str(a.fixtures.resolve()),'sha256':sha(a.fixtures)},'identities':{arm:{'path':str(a.build/arm/'identity.json'),'sha256':sha(a.build/arm/'identity.json')} for arm in ARMS},'cases':cases,'compare':str(compare),'results':[]}
 def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for case in cases:
   if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB disk reserve')
   for n in ('pack','input'):
    if sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
   folder=root/case['id'];folder.mkdir();left=folder/'R-B1.rgba32f';observed={}
   for arm,worker in workers.items():
    dump=left if arm=='R-B1' else folder/(arm+'.rgba32f')
    with (folder/(arm+'.jsonl')).open('w') as out,(folder/(arm+'.stderr')).open('w') as err:subprocess.run([str(worker),case['pack'],case['input'],'--dump',str(dump)],stdout=out,stderr=err,check=True,timeout=180,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0'})
    e=[json.loads(x) for x in (folder/(arm+'.jsonl')).read_text().splitlines()];call=next(x for x in e if x['type']=='call_complete');end=next(x for x in e if x['type']=='verification_complete')
    if call['status']!='success' or call['aot_calls']!=1 or '_windowed' not in call['actual_variant'] or '_wavefront_' in call['actual_variant']:raise ValueError('actual original windowed execution required')
    result=subprocess.run([str(compare),str(left),str(dump),'linear'],capture_output=True,text=True);pixels=json.loads(result.stdout);ok=result.returncode==0 and pixels['passed'];bitwise=sha(dump)==sha(left);active=call['actual_variant'] in NAMES
    row={'case':case['id'],'arm':arm,'active':active,'actual':call['actual_variant'],'aot_calls':call['aot_calls'],'dispatches':call['gpu_dispatches'],'new_buffer_allocations':call['new_buffer_allocations'],'memory':end['memory'],'comparison':pixels,'bitwise_equal_R_B1':bitwise,'output_sha256':sha(dump),'passed':ok};observed[arm]=row;report['results'].append(row);save()
    if not ok or (arm=='W0' and not bitwise) or (not active and not bitwise):raise ValueError('pixel or default identity disagreement; dumps retained')
    print('PASS',case['id'],arm,'active',active,'dispatches',call['gpu_dispatches'],'error',pixels.get('max_linear_error'),flush=True)
    if arm!='R-B1':dump.unlink()
   active=observed['Unit']['active'];windows=(int(case['size'].split('x')[1])+1079)//1080
   if observed['R-B1']['dispatches']!=observed['W0']['dispatches']:raise ValueError('off control dispatch changed')
   for arm in ('Generic','Unit'):
    if observed['W0']['dispatches']-observed[arm]['dispatches']!=(windows if active else 0):raise ValueError('expected one removed pass per active window not observed')
   left.unlink()
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
