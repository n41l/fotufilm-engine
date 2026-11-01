#!/usr/bin/env python3
"""Build exact-size recent-demand eviction, normal and read-only resource workers."""
import argparse,hashlib,json,subprocess,shutil
from pathlib import Path
from wavefront_aot_driver import build
from windowed_pool_recent import REPLACEMENTS

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('reference','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();r=a.reference.resolve();root=a.output.resolve();root.mkdir()
 if subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True):raise ValueError('frozen R dirty')
 if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB reserve')
 report={'complete':False,'reference_base':subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip(),'workers':{},'tools':{},'replacements':REPLACEMENTS}
 def save():(root/'workers.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for label in ('normal','light','detail'):
   detail=label=='detail';driver=c/('tools/windowed-pool-driver.mm' if detail else 'tools/wavefront-benchmark.mm' if label=='normal' else 'tools/wavefront-resource-driver.mm');suffix=root/(label+'-suffix.inc');suffix.write_text('#include "windowed-pool-recent.inc"\n'+('#include "windowed-pool-shim.inc"\n' if detail else ''))
   defs=tuple('-D'+n+'=wf_original_'+n for n in ('commit_command_buffer','retain_ns_object','release_ns_object'))+('-Dnew_buffer=wf_frozen_new_buffer','-DWF_POOL_ALLOCATOR_ENTRY=wf_original_new_buffer') if detail else ('-Dnew_buffer=wf_frozen_new_buffer',)
   w=build(r,r/'build/wavefront-macos',root/label,driver,definitions=('-I'+str(c/'tools'),),driver_definitions=() if label=='normal' else ('-DWF_RESOURCE_CANDIDATE=0','-DWF_RESOURCE_OBSERVER='+str(int(detail))),shim_definitions=defs,shim_prefix=c/'tools/windowed-pool-recent-prefix.inc',shim_replacements=REPLACEMENTS,shim_suffix=suffix,resource_hooks=detail,adapter=c/'tools/windowed-pool-observer.mm' if detail else None)
   report['workers'][label]={'path':str(w),'sha256':sha(w),'generated_shim':json.loads((root/label/'diagnostic-shim.json').read_text())};save();print('BUILT',label,flush=True)
  names=['prepare-windowed-pool-recent.py','windowed_pool_recent.py','windowed-pool-recent.h','windowed-pool-recent-prefix.inc','windowed-pool-recent.inc','wavefront_aot_driver.py','wavefront-benchmark.mm','wavefront-resource-driver.mm','wavefront-resource-observer.mm','wavefront-resource-shim.inc','windowed-pool-driver.mm','windowed-pool-observer.mm','windowed-pool-shim.inc']
  snap=root/'sources';snap.mkdir()
  for n in names:report['tools'][n]=sha(c/'tools'/n);shutil.copy2(c/'tools'/n,snap/n)
  report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
if __name__=='__main__':main()
