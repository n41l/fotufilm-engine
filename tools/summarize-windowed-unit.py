#!/usr/bin/env python3
"""Aggregate the complete stage18 diagnostic without filtering requests or rounds."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--timing',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();c=Path(__file__).resolve().parents[1]
 d=json.loads(a.timing.read_text());assert d['complete'] and len(d['rounds'])==6
 sources={str(a.timing.resolve()):sha(a.timing),**d['sources']};proofs={}
 for path,h in d['sources'].items():
  assert sha(path)==h;proofs[Path(path).parent.name]=json.loads(Path(path).read_text())
 summary={};artifacts={};total=0
 for case in d['cases']:
  summary[case]={}
  for arm in ('R-B1','Generic','Unit'):
   rows=[r['arms'][arm] for r in d['rounds'] if r['case']==case];assert len(rows)==3 and all(r['scores']['valid'] for r in rows)
   hist=collections.Counter();by_round=[]
   for r in rows:
    events=Path(r['events_path']);artifacts[str(events)]={'sha256':sha(events),'bytes':events.stat().st_size};h=collections.Counter();dispatch=collections.Counter()
    for line in events.read_text().splitlines():
     e=json.loads(line)
     if e.get('phase')=='measurement' and e['type']=='call_complete':
      assert e['status']=='success' and e['aot_calls']==1;h[e['new_buffer_allocations']]+=1;dispatch[e['gpu_dispatches']]+=1
    assert sum(h.values())==r['scores']['request_count'];hist.update(h);by_round.append({'allocations':dict(h),'dispatches':dict(dispatch)})
   vals=[r['scores']['median_seconds']*1000 for r in rows];count=sum(r['scores']['request_count'] for r in rows);total+=count
   summary[case][arm]={'round_medians_ms':vals,'median_of_round_medians_ms':statistics.median(vals),'worst_round_p95_ms':max(r['scores']['p95_seconds']*1000 for r in rows),'median_throughput_fps':statistics.median(r['scores']['throughput_fps'] for r in rows),'device_peaks_mib':[r['memory']['device_total_peak_bytes']/2**20 for r in rows],'max_device_peak_mib':max(r['memory']['device_total_peak_bytes']/2**20 for r in rows),'max_process_peak_mib':max(r['memory']['process_lifetime_peak_bytes']/2**20 for r in rows),'retained_process_footprint_mib':[r['memory']['retained_process_footprint_bytes']/2**20 for r in rows],'retained_device_mib':[r['memory']['retained_device_bytes']/2**20 for r in rows],'max_thermal_state':max(r['memory']['max_thermal_state'] for r in rows),'measurement_requests':count,'measurement_new_metal_buffer_allocations_histogram':dict(hist),'per_round_allocation_and_dispatch':by_round}
 ratios={}
 for case,arms in summary.items():
  u=arms['Unit'];ratios[case]={n:{'unit_time_change_percent':100*(u['median_of_round_medians_ms']/arms[n]['median_of_round_medians_ms']-1),'unit_device_peak_change_mib':u['max_device_peak_mib']-arms[n]['max_device_peak_mib']} for n in ('R-B1','Generic')}
 history=next(x for n,x in proofs.items() if 'history' in n);proof=next(x for n,x in proofs.items() if n=='windowed-unit-stage18-proof');jit=next(x for n,x in proofs.items() if 'jit' in n)
 v=c/'build/windowed-unit-stage18-validation/validation.json';rej=c/'build/windowed-unit-stage18/generator-rejections.json';sources[str(v)]=sha(v);sources[str(rej)]=sha(rej)
 result={'complete':True,'stage':18,'date':'2026-11-01','scope':'isolated Coupler stride1 specialization; Generic and Unit fuse release, MTF off; W0 correctness only','implementation_commit':'8df5f7c','source_key':d['source_key'],'reference_base':d['reference_base'],'performance_acceptance':False,'B_ref_frozen':False,'current_source_release_set':False,'fresh_archives_per_arm':2,'frozen_archives_per_arm':61,'unchanged_graph_and_stage_math':True,'window_rows':1080,'aot_calls_per_frame':1,'protocol':d['protocol'],'summary':summary,'comparisons':ratios,'measurement_requests':total,'valid_rounds':18,'pixel_proof_rows':24,'independent_pixel_comparisons':18,'all_direct_rows_bitwise_R':all(x['bitwise_equal_R_B1'] for x in proof['results']),'history_comparisons':42,'active_fresh_history_comparisons':sum(x['active'] for x in history['results']),'all_history_bitwise_R':all(x['bitwise_equal_R_B1'] for x in history['results']),'jit_comparisons':6,'jit_worst_linear_error':max(x['comparison']['max_linear_error'] for x in jit['results']),'bound_kernel_checks':history['kernel_checks'],'generated_metal_sha256':history['generated_metal_sha256'],'validation':json.loads(v.read_text()),'generator_rejections':json.loads(rej.read_text()),'sources':sources,'timing_report':str(a.timing.resolve()),'timing_event_artifacts':artifacts,'limitations':['HD original round medians drift from7.11 to13.37ms; balanced ordering does not establish a stable causal effect.','UHD Unit is1.94% faster than R by median, but1.56% slower than same-source Generic; no demonstrated specialization gain.','Two upscaled Coffee SDR workloads; no all-stock/holdout or complete current-source release parity.','No per-kernel GPU time, physical register/spill or DRAM traffic measurements.'],'decision':'Keep fusion and unit specialization default off. Unit removes actual stride1 reduction loops but does not demonstrate an end-to-end performance or memory benefit over Generic.'}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'summary':summary,'comparisons':ratios,'requests':total},indent=2))
if __name__=='__main__':main()
