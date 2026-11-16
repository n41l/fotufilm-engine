#!/usr/bin/env python3
"""Build frozen-R allocator/GPU/wait probes; generated shim transformations are explicit."""
import argparse,hashlib,json,subprocess,shutil
from pathlib import Path
from wavefront_aot_driver import build
REPLACEMENTS=[('void reclaim_returned() {','void reclaim_returned() {\n    WfSpeedScope wf_speed_reclaim("pool_reclaim");',1),('send(static_cast<id>(entry.buffer), "release");','{ WfSpeedScope wf_speed_eviction("pool_eviction_release"); send(static_cast<id>(entry.buffer), "release"); }',1)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=a.reference.resolve();root=a.output.resolve();root.mkdir()
 if subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True):raise ValueError('frozen R dirty')
 if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB reserve')
 report={'complete':False,'reference_base':subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip(),'replacements':REPLACEMENTS,'workers':{}}
 def save():(root/'workers.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  for arm in ('R','BestFit'):
   defs=('-Dcommit_command_buffer=wf_original_commit_command_buffer','-Drelease_ns_object=wf_original_release_ns_object')+(('-Dnew_buffer=wf_frozen_new_buffer','-DWF_POOL_ALLOCATOR_ENTRY=wf_original_new_buffer') if arm=='BestFit' else ('-Dnew_buffer=wf_original_new_buffer',))
   w=build(r,r/'build/wavefront-macos',root/arm,c/'tools/windowed-speed-driver.mm',definitions=('-I'+str(c/'tools'),),shim_definitions=defs,shim_prefix=c/'tools/windowed-speed-prefix.inc',shim_replacements=REPLACEMENTS,shim_suffix=c/('tools/windowed-pool-best-fit.inc' if arm=='BestFit' else 'tools/windowed-speed-empty.inc'),adapter=c/'tools/windowed-speed-probe.mm');report['workers'][arm]={'path':str(w),'sha256':sha(w),'generated_shim':json.loads((root/arm/'diagnostic-shim.json').read_text())};save();print('BUILT',arm,flush=True)
  report['tools']={n:sha(c/'tools'/n) for n in ('prepare-windowed-speed.py','windowed-speed-driver.mm','windowed-speed-probe.mm','windowed-speed-probe.h','windowed-speed-prefix.inc','windowed-speed-empty.inc','windowed-pool-best-fit.inc','wavefront_aot_driver.py','wavefront-benchmark.mm')};report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save()
if __name__=='__main__':main()
