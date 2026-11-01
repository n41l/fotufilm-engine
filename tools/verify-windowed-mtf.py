#!/usr/bin/env python3
"""Original windowed vs same-source W0/Fused: pixels, actual dispatches and allocations."""
import argparse,hashlib,json,os,shutil,struct,subprocess
from pathlib import Path
from wavefront_aot_driver import build
from windowed_mtf_helper import ARMS,NAME

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','output','fixtures','reference'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.output.resolve();root.mkdir();a.build=a.build.resolve();ref=a.reference.resolve();frozen=json.loads(a.fixtures.read_text());rw=ref/'build/wavefront-benchmark-v2/instrumented/runner'
 if subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base'] or sha(rw)!=frozen['worker_sha256']:raise ValueError('frozen R changed')
 if sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:raise ValueError('common driver changed')
 workers={'R-B1':rw}
 for arm,bits in ARMS.items():
  identity=json.loads((a.build/arm/'identity.json').read_text())
  if identity['fusion']!=bits:raise ValueError('arm mismatch')
  workers[arm]=build(c,a.build/'control/kernels',root/arm,c/'tools/wavefront-benchmark.mm',diagnostic_control=a.build/'control',diagnostic_kernels=a.build/arm,windowed_mtf_research=True)
 compare=root/'compare';subprocess.run(['xcrun','clang++','-O2','-std=c++17',str(c/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
 cases=list(frozen['cases'])
 base=next(x for x in cases if x['id']=='portra400-coffee-3840x2160');oddroot=root/'odd-fixture';oddroot.mkdir();pack=oddroot/'odd.fswp';image=oddroot/'odd.rgba32f';raw=bytearray(Path(base['pack']).read_bytes());h=list(struct.unpack_from('<10I',raw));h[2]=1919;h[3]=1081;h[5]+=7;struct.pack_into('<10I',raw,0,*h);pack.write_bytes(raw)
 with Path(base['input']).open('rb') as src,image.open('wb') as dst:
  for y in range(1081):src.seek(y*3840*16);dst.write(src.read(1919*16))
 cases.append({'id':'portra400-odd-1919x1081','size':'1919x1081','pack':str(pack),'pack_sha256':sha(pack),'input':str(image),'input_sha256':sha(image),'scope':'crop of frozen Coffee, UHD-calibrated config, changed geometry/seed; two windows'})
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
    result=subprocess.run([str(compare),str(left),str(dump),'linear'],capture_output=True,text=True);pixels=json.loads(result.stdout);ok=result.returncode==0 and pixels['passed'];bitwise=sha(dump)==sha(left);active=call['actual_variant']==NAME
    row={'case':case['id'],'arm':arm,'active':active,'actual':call['actual_variant'],'aot_calls':call['aot_calls'],'dispatches':call['gpu_dispatches'],'new_buffer_allocations':call['new_buffer_allocations'],'memory':end['memory'],'comparison':pixels,'bitwise_equal_R_B1':bitwise,'output_sha256':sha(dump),'passed':ok};observed[arm]=row;report['results'].append(row);save()
    if not ok or (arm=='W0' and not bitwise) or (not active and not bitwise):raise ValueError('pixel or default identity disagreement; dumps retained')
    print('PASS',case['id'],arm,'active',active,'dispatches',call['gpu_dispatches'],'error',pixels.get('max_linear_error'),flush=True)
    if arm!='R-B1':dump.unlink()
   active=observed['Fused']['active'];windows=(int(case['size'].split('x')[1])+1079)//1080
   if observed['R-B1']['dispatches']!=observed['W0']['dispatches'] or observed['W0']['dispatches']-observed['Fused']['dispatches']!=(2*windows if active else 0):raise ValueError('expected two removed passes per active window not observed')
   left.unlink()
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
