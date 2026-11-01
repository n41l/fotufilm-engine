#!/usr/bin/env python3
"""Aggregate the final scope-correct probe cohort without mixing exploratory samples."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path
from windowed_speed_analysis import kernel_family
CPU=('allocator_inclusive','metal_new_buffer','pool_reclaim','pool_eviction_release','runtime_release_inclusive','encode_envelope','commit_cpu','wait_until_completed')
GPU=('gpu_compute_union_ms','gpu_all_commands_union_ms','gpu_span_ms','gpu_kernel_interval_sum_ms','wait_gpu_overlap_ms','submit_to_gpu_start_median_ms')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def percentile(values,p):
 a=sorted(values);x=(len(a)-1)*p;i=int(x);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)
def metric(groups,key):
 values=[[key(f) for f in group] for group in groups];flat=[v for g in values for v in g if v is not None]
 medians=[statistics.median(v for v in group if v is not None) for group in values if any(v is not None for v in group)]
 return {'process_medians':medians,'median_of_process_medians':statistics.median(medians),'pooled_median':statistics.median(flat),'pooled_p95':percentile(flat,.95),'min':min(flat),'max':max(flat),'samples':len(flat)} if flat else {'available':False}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('profile','exploratory','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();c=Path(__file__).resolve().parents[1];report=json.loads(a.profile.read_text());old=json.loads(a.exploratory.read_text());assert report['complete'] and len(report['runs'])==32
 sources={str(a.profile.resolve()):sha(a.profile),str(a.exploratory.resolve()):sha(a.exploratory),**report['sources']}
 for path,h in sources.items():assert sha(path)==h,path
 summary={};families={};artifacts={};measured=warm=kernel_count=0
 for case in sorted(set(r['case'] for r in report['runs'])):
  summary[case]={};families[case]={}
  for cell in ('R-off','R-on','BestFit-off','BestFit-on'):
   rows=[r for r in report['runs'] if r['case']==case and r['cell']==cell];assert len(rows)==4;groups=[];warm_groups=[];durations=collections.defaultdict(list);calls=collections.Counter();allocation_lengths=collections.Counter()
   for row in rows:
    path=Path(row['analysis']);assert sha(path)==row['analysis_sha256'];data=json.loads(path.read_text());sources[str(path)]=sha(path);assert sha(Path(data['path'])/'events.jsonl')==data['events_sha256']
    for name,h in data['frame_files_sha256'].items():assert sha(Path(data['path'])/name)==h
    group=[f for f in data['frames'] if f['phase']=='measurement'];w=[f for f in data['frames'] if f['phase']=='warmup'];assert len(group)==40 and len(w)==10;groups.append(group);warm_groups.append(w);measured+=len(group);warm+=len(w)
    for frame in group:
     if frame['gpu_available']:
      kernel_count+=frame['kernel_count'];raw=json.loads((Path(data['path'])/(str(frame['frame'])+'.json')).read_text());allocation_lengths.update(e['bytes'] for e in raw['cpu'] if e['kind']=='metal_new_buffer')
      for command in raw['commands']:
       if command['label'].startswith('_kernel_'):
        family=kernel_family(command['label']);durations[family].append((command['gpu_end']-command['gpu_start'])*1000);calls[family]+=1
    artifacts[str(path)]={'sha256':sha(path),'events_sha256':data['events_sha256'],'frame_files_sha256':data['frame_files_sha256']}
   enabled=cell.endswith('-on');frameflat=[f for group in groups for f in group];h=collections.Counter(f['new_buffers'] for f in frameflat)
   cell_summary={'probes':enabled,'measurement_frames':len(frameflat),'api_ms':metric(groups,lambda f:f['api_ms']),'main_thread_cpu_ms':metric(groups,lambda f:f['main_thread_cpu_ms']),'probe_flush_ms':metric(groups,lambda f:f['probe_flush_ms']),'new_buffers_per_frame_histogram':dict(h),'driver_allocation_lengths_histogram':dict(allocation_lengths) if enabled else None,'warmup_new_buffers':[[f['new_buffers'] for f in g] for g in warm_groups],'cpu_scope_ms':{k:metric(groups,lambda f,k=k:f['cpu_ms'].get(k,0)) for k in CPU} if enabled else None,'gpu_metrics_ms':{**{k:metric(groups,lambda f,k=k:f[k]) for k in GPU},'gpu_timeline_uncovered_ms':metric(groups,lambda f:f['gpu_span_ms']-f['gpu_all_commands_union_ms'])} if enabled else None,'observed_device_peak_mib':max(f['memory']['device_peak_bytes']/2**20 for f in frameflat),'max_thermal_state':max(f['memory']['thermal_state'] for f in frameflat)}
   summary[case][cell]=cell_summary
   if enabled:families[case][cell]=sorted([{'family':k,'calls':calls[k],'median_per_command_ms':statistics.median(v),'p95_per_command_ms':percentile(v,.95),'mean_per_command_ms':statistics.mean(v)} for k,v in durations.items()],key=lambda x:x['median_per_command_ms'],reverse=True)
 comparisons={}
 for case,cells in summary.items():
  val=lambda name:cells[name]['api_ms']['median_of_process_medians']
  comparisons[case]={'observed_probe_effect_api_percent':{arm:100*(val(arm+'-on')/val(arm+'-off')-1) for arm in ('R','BestFit')},'best_fit_vs_original_api_percent':{mode:100*(val('BestFit-'+mode)/val('R-'+mode)-1) for mode in ('off','on')}}
 result={'complete':True,'stage':20,'date':'2026-11-01','implementation_commits':['308ea48','c307bb3'],'reference_base':report['reference_base'],'scope':'scope-correct count-based allocator/CPU/GPU/wait probes; frozen R full AOT, independent best-fit suffix; no production/default changes','performance_acceptance':False,'B_ref_frozen':False,'production_sources_changed':False,'protocol':report['protocol'],'processes':32,'measured_frames':measured,'warmup_frames':warm,'measured_kernel_timestamps':kernel_count,'preflight_rows':24,'regression_tests':{'speed':9,'existing_resource':13},'summary':summary,'comparisons':comparisons,'decision':'Direct allocation host-call cost is small here; investigate GPU/elapsed encoding without promoting defaults or claiming causality.','kernel_command_families':families,'sources':sources,'per_process_artifacts':artifacts,'profile_report':str(a.profile.resolve()),'excluded_exploratory_report':str(a.exploratory.resolve()),'exploratory_included_in_final_summary':False,'limitations':['GPU intervals overlap. Their sum is not elapsed GPU time; union is reported execution coverage, not active cycles/utilization.','CPU wait overlaps GPU execution. Reclaim/eviction and Metal allocation scopes are nested in inclusive allocation; encoding is an elapsed envelope, not active CPU compute.','Explicit waitUntilCompleted covers that method only; implicit driver blocking and OS descheduling are not separately attributed.','Probe/off comparisons include timing/scheduling and trace I/O effects; no exact correction is subtracted.','Count-based10+40-frame runs differ from stage19 time-window benchmark; no cross-campaign splicing or acceptance.','Driver allocation CPU wall time does not account for deferred mapping/initialization elsewhere.']}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'processes':32,'frames':measured,'kernel_timestamps':kernel_count,'comparisons':comparisons},indent=2))
if __name__=='__main__':main()
