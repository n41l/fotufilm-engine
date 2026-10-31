#!/usr/bin/env python3
"""Offline analysis of preserved serial R rounds. No GPU work or score replacement.

API-envelope time includes CPU, GPU waits and descheduling. Its complement includes
worker bookkeeping and logging. Neither is a GPU-duration measurement.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from wavefront_metrics import summarize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def distribution(values):
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError('nonempty finite observations required')
    values=sorted(values)
    return {'min':values[0],'median':statistics.median(values),
            'mean':statistics.mean(values),'p95':values[math.ceil(.95*len(values))-1],
            'max':values[-1]}


def partition(requests, t0, t1):
    """Clip nonoverlapping synchronous API intervals to [t0,t1)."""
    if not math.isfinite(t0) or not math.isfinite(t1) or t1<=t0:
        raise ValueError('invalid partition window')
    intervals=sorted((r['started_at'],r['completed_at']) for r in requests)
    previous=None;active=0
    for start,end in intervals:
        if not all(isinstance(v,(float,int)) and math.isfinite(v) for v in (start,end)) or end<start:
            raise ValueError('invalid API interval')
        if previous is not None and start<previous:raise ValueError('overlapping API calls')
        previous=end
        active+=max(0,min(end,t1)-max(start,t0))
    return {'api_envelope_seconds':active,'outside_api_seconds':max(0,t1-t0-active),
            'outside_api_fraction':max(0,1-active/(t1-t0))}


def pearson(xs, ys):
    if len(xs)!=len(ys) or len(xs)<3:return None
    xbar,ybar=statistics.mean(xs),statistics.mean(ys)
    xx=sum((x-xbar)**2 for x in xs);yy=sum((y-ybar)**2 for y in ys)
    return sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys))/math.sqrt(xx*yy) if xx and yy else None


def analyze_round(path):
    path=Path(path).resolve();r=json.loads(path.read_text())
    if not r['scores']['valid']:raise ValueError('invalid rounds cannot enter this valid-cohort analysis')
    windows=[e for e in r['phase_events'] if e['type']=='window']
    if len(windows)!=1:raise ValueError('exactly one measurement window required')
    w=windows[0];scores=summarize({**w,'requests':r['requests']})
    if not scores['valid']:raise ValueError('preserved request accounting no longer validates')
    for key in ('request_count','success_in_window','median_seconds','p95_seconds','throughput_fps'):
        if scores[key]!=r['scores'][key]:raise ValueError('saved score disagrees with original requests')
    q=sorted((x for x in r['requests'] if x['phase']=='measurement'),key=lambda x:x['started_at'])
    times=[x['completed_at']-x['started_at'] for x in q]
    median=statistics.median(times)
    bins=[]
    for index in range(6):
        lo=w['t0']+index*5;hi=lo+5
        starts=[x for x in q if lo<=x['started_at']<hi]
        durations=[x['completed_at']-x['started_at'] for x in starts]
        bins.append({'offset_seconds':index*5,'requests_started':len(starts),
            'completions_fps':sum(lo<=x['completed_at']<hi for x in q)/5,
            'latency_seconds':distribution(durations) if durations else None,
            **partition(q,lo,hi)})
    envpath=path.parent.with_name(path.parent.name+'-environment.json')
    env=json.loads(envpath.read_text()) if envpath.exists() else None
    hashes=[x['output_sha256'] for x in r['phase_events'] if x['type'] in ('warmup_complete','measurement_complete')]
    if len(hashes)!=2 or hashes[0]!=hashes[1]:raise ValueError('fixed output changed within round')
    return {'round_path':str(path),'sha256':sha(path),'mode':r['requested_mode'],
        'window':w,'scores':scores,'latency_seconds':distribution(times),
        **partition(q,w['t0'],w['t1']),
        'calls_above_twice_median':sum(t>2*median for t in times),
        'seconds_in_calls_above_twice_median':sum(t for t in times if t>2*median),
        'thermal_states':sorted({x['thermal_state'] for x in q}),
        'thermal_counts':{str(s):sum(x['thermal_state']==s for x in q) for s in sorted({x['thermal_state'] for x in q})},
        'new_buffer_allocations_per_call':{'min':min(x['new_buffer_allocations'] for x in q),
            'max':max(x['new_buffer_allocations'] for x in q),'total':sum(x['new_buffer_allocations'] for x in q)},
        'gpu_dispatch_counts':sorted({x['gpu_dispatches'] for x in q}),
        'aot_call_counts':sorted({x['aot_calls'] for x in q}),
        'actual_variants':sorted({x['actual_variant'] for x in q}),
        'output_sha256':hashes[0],'environment_before':env,'five_second_bins':bins}


def analyze(report):
    report=Path(report).resolve();d=json.loads(report.read_text())
    if not d['complete']:raise ValueError('complete campaign required; incomplete data remain preserved')
    cases=[];timeline=[]
    for case,entry in d['cases'].items():
        arms={}
        for mode,rounds in entry['arms'].items():
            rows=[analyze_round(r['round_path']) for r in rounds]
            if not rows:continue
            variants={tuple(r['actual_variants']) for r in rows}
            dispatches={tuple(r['gpu_dispatch_counts']) for r in rows}
            hashes={r['output_sha256'] for r in rows}
            if len(hashes)!=1:raise ValueError('fixed-input output changed between same-arm rounds')
            fps=[r['scores']['throughput_fps'] for r in rows]
            loads=[r['environment_before'].get('load_average',[None])[0] if r['environment_before'] else None for r in rows]
            arms[mode]={'round_count':len(rows),'throughput_fps':fps,
                'throughput_range_ratio':max(fps)/min(fps)-1,
                'round_api_mean_seconds':[r['latency_seconds']['mean'] for r in rows],
                'round_api_median_seconds':[r['latency_seconds']['median'] for r in rows],
                'outside_api_fraction_max':max(r['outside_api_fraction'] for r in rows),
                'new_buffers_per_call_min':min(r['new_buffer_allocations_per_call']['min'] for r in rows),
                'new_buffers_per_call_max':max(r['new_buffer_allocations_per_call']['max'] for r in rows),
                'constant_actual_variant':len(variants)==1 and len(next(iter(variants)))==1,
                'constant_dispatch_count':len(dispatches)==1 and len(next(iter(dispatches)))==1,
                'thermal_states':sorted({s for r in rows for s in r['thermal_states']}),
                'pre_round_load_vs_fps_pearson':pearson(loads,fps) if all(x is not None for x in loads) else None,
                'rounds':rows}
            timeline.extend({'case':case,'mode':mode,'round_path':r['round_path'],
                'window_start':r['window']['t0'],'fps':r['scores']['throughput_fps'],
                'mean_api_ms':1000*r['latency_seconds']['mean'],
                'outside_api_percent':100*r['outside_api_fraction'],
                'pre_round_load':r['environment_before'].get('load_average') if r['environment_before'] else None} for r in rows)
        cases.append({'case':case,'arms':arms})
    timeline.sort(key=lambda r:r['window_start'])
    return {'source_report':str(report),'source_report_sha256':sha(report),
        'analysis_source_sha256':sha(__file__),'rounds_analyzed':len(timeline),'cases':cases,'timeline':timeline,
        'scope':'offline diagnostics; original scores and stability decisions are unchanged',
        'limitations':['API-envelope duration is wall time, not GPU duration or CPU utilization.',
            'Outside-API time includes logging, validation, autorelease and scheduling gaps.',
            'Environment snapshots precede rounds; they are not per-frame load observations.',
            'Coarse thermal states and round correlations do not establish a cause.',
            'Fixed buffers/dispatch counts do not prove fixed GPU frequency, memory traffic or execution time.']}


def markdown(d):
    lines=['# Wavefront reference stability diagnostics','',d['scope'],'',
        '| Case | Arm | Rounds | FPS range drift | Max outside API | New buffers/call | Thermal states |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for case in d['cases']:
        for mode,a in case['arms'].items():
            lines.append(f"| {case['case']} | {mode} | {a['round_count']} | {100*a['throughput_range_ratio']:.2f}% | {100*a['outside_api_fraction_max']:.3f}% | {a['new_buffers_per_call_min']}–{a['new_buffers_per_call_max']} | {a['thermal_states']} |")
    lines+=['','Every scored request is retained. Five-second bins and complete latency distributions are in the JSON.','']
    lines.extend('- '+s for s in d['limitations'])
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('analysis output already exists; refusing to replace evidence')
    d=analyze(a.report);a.output.mkdir(parents=True)
    (a.output/'analysis.json').write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
    (a.output/'analysis.md').write_text(markdown(d))
    print(markdown(d))


if __name__=='__main__':main()
