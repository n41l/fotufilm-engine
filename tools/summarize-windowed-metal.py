#!/usr/bin/env python3
"""Summarize the final per-method cohort; all cells and all method intervals are retained."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path
def metric(groups,get):
 values=[[get(f) for f in group] for group in groups];flat=[v for g in values for v in g if v is not None];medians=[statistics.median(v for v in group if v is not None) for group in values if any(v is not None for v in group)]
 if not flat:return {'available':False}
 a=sorted(flat);x=(len(a)-1)*.95;i=int(x);p95=a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)
 return {'process_medians':medians,'median_of_process_medians':statistics.median(medians),'pooled_median':statistics.median(flat),'pooled_p95':p95,'min':min(flat),'max':max(flat),'samples':len(flat)}
METHODS=('command_create_native','command_create','encoder_create','function_lookup','pipeline_create','pipeline_bind','buffer_bind','bytes_bind','threadgroup_memory','dispatch','end_encoding','command_commit')
EXTRA=('encoding_native_covered_ms','encoding_residual_ms','encoding_ms','native_factory_previous_gpu_overlap_ms')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];d=json.loads(a.profile.read_text());assert d['complete'] and len(d['runs'])==72
 sources={str(a.profile.resolve()):sha(a.profile),**d['sources']};summary={};artifacts={};frames=warm=kernels=method_kernels=0
 for path,h in sources.items():assert sha(path)==h,path
 cells=['R-off','R-basic','R-detail','BestFit-off','BestFit-basic','BestFit-detail']
 for case in sorted(set(r['case'] for r in d['runs'])):
  summary[case]={}
  for cell in cells:
   rows=[r for r in d['runs'] if r['case']==case and r['cell']==cell];assert len(rows)==6;groups=[];pending=collections.Counter();limits=collections.Counter();lengths=collections.Counter();by_family=collections.defaultdict(list)
   for row in rows:
    path=Path(row['analysis']);assert sha(path)==row['analysis_sha256'];data=json.loads(path.read_text());assert sha(Path(data['path'])/'events.jsonl')==data['events_sha256'];groups.append([f for f in data['frames'] if f['phase']=='measurement']);assert len(groups[-1])==12;w=[f for f in data['frames'] if f['phase']=='warmup'];assert len(w)==10;warm+=len(w)
    for name,h in data['frame_files_sha256'].items():assert sha(Path(data['path'])/name)==h
    artifacts[str(path)]={'sha256':sha(path),'events_sha256':data['events_sha256'],'frame_files_sha256':data['frame_files_sha256']}
    for f in groups[-1]:
     frames+=1;kernels+=f.get('kernel_count',0)
     if f['methods_available']:
      method_kernels+=f['kernel_count'];pending.update({int(k):v for k,v in f['factory_callback_pending_histogram'].items()});limits.update({int(k):v for k,v in f['observed_queue_limit_histogram'].items()});lengths.update({int(k):v for k,v in f['bound_buffer_length_histogram'].items()})
      for cmd in f['per_command']:
       if cmd['label'].startswith('_kernel_'):by_family[cmd['family']].append(cmd['methods_ms']['command_create_native'])
   active=cell.endswith('-detail');base_on=not cell.endswith('-off');flat=[f for group in groups for f in group]
   r={'measurement_frames':len(flat),'api_ms':metric(groups,lambda f:f['api_ms']),'main_thread_cpu_ms':metric(groups,lambda f:f['main_thread_cpu_ms']),'new_buffers_per_frame_histogram':dict(collections.Counter(f['new_buffers'] for f in flat)),'max_thermal_state':max(f['memory']['thermal_state'] for f in flat),'methods_available':active,'base_probes':base_on}
   if base_on:r['base_cpu_ms']={k:metric(groups,lambda f,k=k:f['cpu_ms'].get(k,0)) for k in ('allocator_inclusive','encode_envelope','wait_until_completed','commit_cpu')};r['gpu_ms']={k:metric(groups,lambda f,k=k:f[k]) for k in ('gpu_compute_union_ms','gpu_span_ms','wait_gpu_overlap_ms')}
   if active:
    r.update({'method_ms':{k:metric(groups,lambda f,k=k:f['method_ms'].get(k,0)) for k in METHODS},'encoding_metrics_ms':{k:metric(groups,lambda f,k=k:f[k]) for k in EXTRA},'factory_wrapper_delta_ms':metric(groups,lambda f:f['method_ms']['command_create']-f['method_ms']['command_create_native']),'callback_pending_histogram':dict(pending),'queue_limits':dict(limits),'bound_buffer_lengths_histogram':dict(lengths),'unlinked_method_events':sum(f['unlinked_method_events'] for f in flat),'unlinked_native_commits':sum(f['unlinked_native_commits'] for f in flat),'next_kernel_factory_intervals':[{'family':k,'calls':len(v),'median_ms':statistics.median(v),'max_ms':max(v)} for k,v in sorted(by_family.items(),key=lambda x:statistics.median(x[1]),reverse=True)]})
   summary[case][cell]=r
 comparisons={}
 for case,cells in summary.items():
  val=lambda cell:cells[cell]['api_ms']['median_of_process_medians']
  comparisons[case]={'best_fit_vs_original_api_percent':{mode:100*(val('BestFit-'+mode)/val('R-'+mode)-1) for mode in ('off','basic','detail')},'detail_vs_basic_api_percent':{arm:100*(val(arm+'-detail')/val(arm+'-basic')-1) for arm in ('R','BestFit')}}
 for path in (root/'build/windowed-metal-stage21-storage.json',root/'build/windowed-metal-stage21-storage-2.json',root/'build/windowed-metal-stage21-v3/source-snapshot.json',root.parent/'reference/Sources/FotufilmHalide/FotufilmHalideIOS.cpp',Path('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLDevice.h')):sources[str(path)]=sha(path)
 result={'complete':True,'stage':21,'date':'2026-11-01','implementation_commit':'d687796','reference_base':d['reference_base'],'scope':'frozen R full AOT plus independent bounded-best-fit suffix; no production/default/queue-capacity changes','performance_acceptance':False,'B_ref_frozen':False,'production_sources_changed':False,'processes':72,'measured_frames':frames,'warmup_frames':warm,'measured_kernel_timestamps':kernels,'detailed_kernel_method_links':method_kernels,'preflight_processes':36,'tests':{'method':8,'base_probe':9,'resource':13},'protocol':d['protocol'],'summary':summary,'comparisons':comparisons,'profile_report':str(a.profile.resolve()),'sources':sources,'per_process_artifacts':artifacts,'decision':'Native commandBuffer acquisition is the large measured elapsed interval, consistent with original depth4 host backpressure. BestFit is faster in all three modes in this short cohort; earlier latency direction is not a stable intrinsic regression. Defaults remain unchanged.','limitations':['Method wall time includes blocking/descheduling; frame main-thread CPU time is not per-method active CPU.','Outer/native factory timers are nested, and GPU execution overlaps factory/explicit wait. Do not add them.','Callback pending includes notification lag and is not exact GPU occupancy. Source and queue construction independently confirm actual capacity4.','Next-command labels identify what will be encoded, not which older kernel caused acquisition to wait.','Short10+12-frame six-process medians do not replace stage19 time-window acceptance. No cross-campaign splicing or exact observer correction.','Increasing queue capacity is not tested and can move waits or increase intermediate memory.']}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'frames':frames,'warm':warm,'kernels':kernels,'detailed_kernel_links':method_kernels,'comparisons':comparisons},indent=2))
if __name__=='__main__':main()
