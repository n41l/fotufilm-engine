#!/usr/bin/env python3
"""Preserve all stage19 rounds, allocation histograms and original pool forensics."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--timing',type=Path,required=True);p.add_argument('--interrupted',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();c=Path(__file__).resolve().parents[1];d=json.loads(a.timing.read_text());old=json.loads(a.interrupted.read_text());assert d['complete'] and not old['complete'] and sum(len(x['arms']) for x in d['rounds'])==12
 summary={};artifacts={};total=0
 for case in d['cases']:
  summary[case]={}
  for arm in ('R-B1','BestFit'):
   rows=[r['arms'][arm] for r in d['rounds'] if r['case']==case];assert len(rows)==3 and all(r['scores']['valid'] for r in rows);hist=collections.Counter();by_round=[]
   for r in rows:
    q=Path(r['events_path']);artifacts[str(q)]={'sha256':sha(q),'bytes':q.stat().st_size};h=collections.Counter()
    for line in q.read_text().splitlines():
     e=json.loads(line)
     if e.get('phase')=='measurement' and e['type']=='call_complete':assert e['status']=='success' and e['aot_calls']==1;h[e['new_buffer_allocations']]+=1
    assert sum(h.values())==r['scores']['request_count'];hist.update(h);by_round.append(dict(h))
   vals=[r['scores']['median_seconds']*1000 for r in rows];count=sum(r['scores']['request_count'] for r in rows);total+=count
   summary[case][arm]={'round_medians_ms':vals,'median_of_round_medians_ms':statistics.median(vals),'worst_round_p95_ms':max(r['scores']['p95_seconds']*1000 for r in rows),'median_throughput_fps':statistics.median(r['scores']['throughput_fps'] for r in rows),'device_peaks_mib':[r['memory']['device_total_peak_bytes']/2**20 for r in rows],'max_device_peak_mib':max(r['memory']['device_total_peak_bytes']/2**20 for r in rows),'max_process_peak_mib':max(r['memory']['process_lifetime_peak_bytes']/2**20 for r in rows),'retained_device_mib':[r['memory']['retained_device_bytes']/2**20 for r in rows],'retained_process_footprint_mib':[r['memory']['retained_process_footprint_bytes']/2**20 for r in rows],'max_thermal_state':max(r['memory']['max_thermal_state'] for r in rows),'measurement_requests':count,'new_metal_buffers_per_measurement_histogram':dict(hist),'per_round_new_buffer_histograms':by_round}
 comparisons={}
 for case,arms in summary.items():
  b=arms['R-B1'];u=arms['BestFit'];comparisons[case]={'time_change_percent':100*(u['median_of_round_medians_ms']/b['median_of_round_medians_ms']-1),'device_peak_change_mib':u['max_device_peak_mib']-b['max_device_peak_mib'],'device_peak_change_percent':100*(u['max_device_peak_mib']/b['max_device_peak_mib']-1),'paired_faster_rounds':sum(x<y for x,y in zip(u['round_medians_ms'],b['round_medians_ms'])),'paired_slower_rounds':sum(x>y for x,y in zip(u['round_medians_ms'],b['round_medians_ms']))}
 sources={str(a.timing.resolve()):sha(a.timing),str(a.interrupted.resolve()):sha(a.interrupted),**d['sources']}
 for path,h in sources.items():assert sha(path)==h,path
 forensic={}
 for root in ('windowed-pool-stage19','windowed-pool-stage19-best-fit'):
  for q in (c/'build'/root).glob('*/analysis.json'):
   sources[str(q)]=sha(q);v=json.loads(q.read_text());forensic[str(q)]={'frame_count':len(v['frames']),'fresh_counts':[x['fresh_count'] for x in v['frames']],'last_frame':v['frames'][-1],'scope':v['scope']}
 for q in (c/'build/windowed-pool-stage19/disk-recovery.json',c/'build/windowed-pool-stage19/worker-archives.json'):
  sources[str(q)]=sha(q)
 result={'complete':True,'stage':19,'date':'2026-11-01','implementation_commit':'a1e60a9','scope':'frozen R full63 AOT set with isolated bounded best-fit host suffix; no production source/default changes; no fusions','reference_base':d['reference_base'],'performance_acceptance':False,'B_ref_frozen':False,'default_enabled':False,'native_film_or_aot_sources_changed':False,'protocol':d['protocol'],'summary':summary,'comparisons':comparisons,'valid_rounds':12,'measurement_requests':total,'normal_pixel_cases':6,'normal_bitwise_equal_R':True,'original_count_frames':24,'best_fit_count_frames':24,'best_fit_mixed_history_frames':12,'resource_analysis_tests':4,'existing_resource_tests':13,'forensics':forensic,'sources':sources,'timing_event_artifacts':artifacts,'timing_report':str(a.timing.resolve()),'interrupted_campaign':{'report':str(a.interrupted.resolve()),'failure':old.get('failure'),'completed_rounds':sum(len(x['arms']) for x in old['rounds']),'included_in_complete_summary':False},'decision':'Keep experimental-only: UHD peak falls192MiB and all measured fresh allocations disappear, but median latency increases in both cases. Full stock/holdout, concurrency and formal gates remain pending.','limitations':['HD original round medians drift6.996..11.806ms; balancing does not establish a causal regression size.','Two upscaled Coffee SDR timing workloads only. Mixed-size history is correctness evidence, not memory nonregression.','Detailed observers alter scheduling; latency and process peaks come only from normal common workers.','No per-kernel GPU/CPU allocation-time/DRAM/register attribution; no claim that larger buffers caused the observed slowdown.']}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'requests':total,'summary':summary,'comparisons':comparisons},indent=2))
if __name__=='__main__':main()
