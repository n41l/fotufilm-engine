#!/usr/bin/env python3
"""Independent process medians for the fixed stage23 cohort; no cross-stage scores."""
import argparse,collections,json,statistics,hashlib
from pathlib import Path
M=statistics.median

def summarize(path):
 r=json.loads(path.read_text())
 if not r['complete'] or len(r['runs'])!=18 or not all(x['valid'] for x in r['runs']):raise ValueError('complete eighteen-round cohort required')
 rows=[]
 for row in r['runs']:
  rr=json.loads(Path(row['round_path']).read_text());req=[x for x in rr['requests'] if x['phase']=='measurement'];window=next(x for x in rr['phase_events'] if x['type']=='window');metrics={'api_ms':rr['scores']['median_seconds']*1000,'p95_ms':rr['scores']['p95_seconds']*1000,'throughput_fps':rr['scores']['throughput_fps'],'device_peak_mib':rr['memory']['device_total_peak_bytes']/1024**2,'process_peak_mib':rr['memory']['process_lifetime_peak_bytes']/1024**2,'retained_device_mib':rr['memory']['retained_device_bytes']/1024**2}
  rows.append({'case':row['case'],'index':row['index'],'arm':row['arm'],**metrics,'frames':len(req),'new_buffers_histogram':dict(collections.Counter(x['new_buffer_allocations'] for x in req)),'thermal_histogram':dict(collections.Counter(x['thermal_state'] for x in req)),'environment_before':row['environment_before'],'environment_after':row['environment_after'],'five_second_bins_ms':[M([1000*(x['completed_at']-x['started_at']) for x in req if t<=x['started_at']-window['t0']<t+5]) for t in range(0,30,5)]})
 groups={};comparisons={}
 for case in r['cases']:
  groups[case]={}
  for arm in ('R','BestFit','Recent'):
   a=[x for x in rows if x['case']==case and x['arm']==arm];g={k:M(x[k] for x in a) for k in metrics};g.update({'worst_p95_ms':max(x['p95_ms'] for x in a),'frames':sum(x['frames'] for x in a),'new_buffers_histogram':dict(sum((collections.Counter(x['new_buffers_histogram']) for x in a),collections.Counter())),'thermal_histogram':dict(sum((collections.Counter(x['thermal_histogram']) for x in a),collections.Counter()))});groups[case][arm]=g
  comparisons[case]={}
  for arm in ('BestFit','Recent'):
   g=groups[case];pairs=[]
   for i in range(3):
    a=next(x for x in rows if x['case']==case and x['index']==i and x['arm']=='R');b=next(x for x in rows if x['case']==case and x['index']==i and x['arm']==arm);pairs.append({'repeat':i,'delta_ms':b['api_ms']-a['api_ms'],'delta_percent':100*(b['api_ms']/a['api_ms']-1)})
   comparisons[case][arm]={'aggregate_delta_ms':g[arm]['api_ms']-g['R']['api_ms'],'aggregate_delta_percent':100*(g[arm]['api_ms']/g['R']['api_ms']-1),'pairs':pairs}
 return {'complete':True,'stage':23,'source':str(path.resolve()),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'performance_acceptance':False,'aggregation':'median of three process medians per arm/case; worst process p95 also preserved','groups':groups,'comparisons':comparisons,'processes':rows,'limitations':['one HD and one UHD fixed input on a changing background session','three cyclic position-balanced orders, not predecessor-balanced within a size','one concrete recent-frequency/LRU-tie policy; not all eviction policies','no detailed timing probes; resource histories are a separate correctness cohort']}
def main():
 p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=summarize(a.report);a.output.write_text(json.dumps(s,indent=2)+'\n');print(json.dumps({'groups':s['groups'],'comparisons':s['comparisons']},indent=2))
if __name__=='__main__':main()
