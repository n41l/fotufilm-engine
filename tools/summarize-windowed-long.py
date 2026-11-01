#!/usr/bin/env python3
"""Aggregate independent stage22 process medians; preserve all rounds and observer modes."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path
median=statistics.median

def summarize(path):
 report=json.loads(path.read_text())
 if not report['complete'] or len(report['runs'])!=16:raise ValueError('complete sixteen-process cohort required')
 rows=[]
 for run in report['runs']:
  rr=json.loads(Path(run['round_path']).read_text());requests=[x for x in rr['requests'] if x['phase']=='measurement'];frames=[x for x in json.loads(Path(run['samples_path']).read_text())['samples'] if x['phase']=='measurement'];window=next(x for x in rr['phase_events'] if x['type']=='window')
  if not rr['scores']['valid']:raise ValueError('invalid process')
  row={'index':run['index'],'cell':run['cell'],'api_ms':1000*rr['scores']['median_seconds'],'p95_ms':1000*rr['scores']['p95_seconds'],'throughput_fps':rr['scores']['throughput_fps'],'frames':len(requests),'sampled_frames':len(frames),'new_buffers_histogram':dict(collections.Counter(x['new_buffer_allocations'] for x in requests)),'thermal_histogram':dict(collections.Counter(x['thermal_state'] for x in requests)),'device_peak_mib':rr['memory']['device_total_peak_bytes']/1024**2,'process_peak_mib':rr['memory']['process_lifetime_peak_bytes']/1024**2,'environment_before':run['environment_before'],'environment_after':run['environment_after']}
  row['five_second_bins_ms']=[median([1000*(r['completed_at']-r['started_at']) for r in requests if i<=r['started_at']-window['t0']<i+5]) for i in range(0,30,5)]
  if frames:
   row.update({'sample_api_ms':median(x['api_protocol_ms'] for x in frames),'main_thread_cpu_ms':median(x['main_thread_cpu_ms'] for x in frames),'gpu_union_ms':median(x['gpu_compute_union_ms'] for x in frames),'gpu_span_ms':median(x['gpu_span_ms'] for x in frames),'allocation_ms':median(x['cpu_ms'].get('allocator_inclusive',0) for x in frames),'metal_new_buffer_ms':median(x['cpu_ms'].get('metal_new_buffer',0) for x in frames),'explicit_wait_ms':median(x['cpu_ms']['wait_until_completed'] for x in frames),'encoding_ms':median(x['encoding_ms'] for x in frames),'native_factory_ms':median(x['method_ms']['command_create_native'] for x in frames),'pipeline_create_ms':median(x['method_ms']['pipeline_create'] for x in frames),'native_factory_previous_gpu_overlap_ms':median(x['native_factory_previous_gpu_overlap_ms'] for x in frames),'encoding_residual_ms':median(x['encoding_residual_ms'] for x in frames),'trace_write_ms':median(x['trace_write_ms'] for x in frames),'trace_write_total_ms':sum(x['trace_write_ms'] for x in frames),'trace_api_bracket_delta_us':median((x['api_ms']-x['api_protocol_ms'])*1000 for x in frames),'sample_new_buffers_histogram':dict(collections.Counter(x['new_buffers'] for x in frames))})
   row['unsampled_api_ms']=median(1000*(r['completed_at']-r['started_at']) for r in requests if not r['probe_sample']['sampled'])
   row['factory_pending_histogram']=dict(sum((collections.Counter(x['factory_callback_pending_histogram']) for x in frames),collections.Counter()))
  rows.append(row)
 groups={}
 keys=['api_ms','p95_ms','throughput_fps','device_peak_mib','process_peak_mib','sample_api_ms','unsampled_api_ms','main_thread_cpu_ms','gpu_union_ms','gpu_span_ms','allocation_ms','metal_new_buffer_ms','explicit_wait_ms','encoding_ms','native_factory_ms','pipeline_create_ms','native_factory_previous_gpu_overlap_ms','encoding_residual_ms','trace_write_ms','trace_write_total_ms','trace_api_bracket_delta_us']
 for cell in dict.fromkeys(r['cell'] for r in rows):
  subset=[x for x in rows if x['cell']==cell];groups[cell]={k:median(x[k] for x in subset) for k in keys if k in subset[0]};groups[cell]['frames']=sum(x['frames'] for x in subset);groups[cell]['sampled_frames']=sum(x['sampled_frames'] for x in subset);groups[cell]['new_buffers_histogram']=dict(sum((collections.Counter(x['new_buffers_histogram']) for x in subset),collections.Counter()));groups[cell]['thermal_histogram']=dict(sum((collections.Counter(x['thermal_histogram']) for x in subset),collections.Counter()))
 comparisons={}
 for mode in ('normal','trace'):
  a,b=groups['R-'+mode],groups['BestFit-'+mode];pairs=[]
  for i in range(4):
   ra=next(x for x in rows if x['index']==i and x['cell']=='R-'+mode);rb=next(x for x in rows if x['index']==i and x['cell']=='BestFit-'+mode);pairs.append({'repeat':i,'delta_ms':rb['api_ms']-ra['api_ms'],'delta_percent':100*(rb['api_ms']/ra['api_ms']-1)})
  comparisons[mode]={'median_aggregate_delta_ms':b['api_ms']-a['api_ms'],'median_aggregate_delta_percent':100*(b['api_ms']/a['api_ms']-1),'pairs':pairs}
 return {'stage':22,'complete':True,'source':str(path.resolve()),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'aggregation':'median of independent process medians; p95 entry is median of process p95s','performance_acceptance':False,'groups':groups,'comparisons':comparisons,'processes':rows,'limitations':['four repeats, one UHD fixed input, same Mac background session','traces sample one frame per second; hooks and trace I/O can alter scheduling','thermal/load observations do not establish GPU clock or other-process GPU use','CPU wall, waits and GPU intervals overlap; do not add them']}
def main():
 p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=summarize(a.report);a.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps({'groups':v['groups'],'comparisons':v['comparisons']},indent=2))
if __name__=='__main__':main()
