#!/usr/bin/env python3
"""Summarize complete resource diagnostics without asserting a formal PR gate."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

METRICS=('device_total_peak_bytes','process_lifetime_peak_bytes','retained_device_bytes','retained_process_footprint_bytes')


def summarize(d):
    if not d['complete']:raise ValueError('complete resource campaign required')
    cases=[]
    for case,entry in d['primary'].items():
        modes={}
        for mode,arm in entry.items():
            rows=arm['processes'];detail=d['detailed'][case+'-'+mode]['attribution']
            if not detail['fully_classified_halide_leases']:raise ValueError('unclassified Halide resources remain')
            peaks=detail['frames']
            modes[mode]={'processes':len(rows),'metrics':{key:{'min':min(r['metrics'][key] for r in rows),
                'median':statistics.median(r['metrics'][key] for r in rows),'max':max(r['metrics'][key] for r in rows)} for key in METRICS},
                'cold_process':{'device_peak_bytes':max(r['frames'][0]['memory']['device_peak_bytes'] for r in rows),
                    'process_lifetime_peak_bytes':max(r['frames'][0]['memory']['process_lifetime_peak_bytes'] for r in rows)},
                'working_logical_requested_peak':max(f['logical']['working_combined']['requested'] for f in peaks),
                'working_logical_allocated_peak':max(f['logical']['working_combined']['allocated'] for f in peaks),
                'working_GPU_safe_allocated_upper_bound':max(f['gpu_safe_upper_bound']['working_combined']['allocated'] for f in peaks),
                'AOT_intermediate_requested_peak':max(f['logical'].get('AOT_intermediate',{}).get('requested',0) for f in peaks),
                'frontier_configuration_requested_peak':max(f['logical'].get('frontier_and_configuration',{}).get('requested',0) for f in peaks)}
            if 'epsilon' in arm:modes[mode]['epsilon']=arm['epsilon']
        comparisons={}
        for emode in ('E64','E128','E256'):
            comparisons[emode]={}
            for ref in ('B0','B1'):
                comparison={}
                for metric in METRICS:
                    epsilon=modes[ref]['epsilon'][metric]
                    delta=modes[emode]['metrics'][metric]['max']-modes[ref]['metrics'][metric]['min']
                    comparison[metric]={'worst_observed_difference_bytes':delta,'R_epsilon_bytes':epsilon['epsilon_bytes'],
                        'R_calibration_stable':epsilon['stable'],
                        'all_observed_within_R_plus_epsilon':epsilon['stable'] and delta<=epsilon['epsilon_bytes']}
                comparison['working_logical_requested_reduction_ratio']=1-modes[emode]['working_logical_requested_peak']/modes[ref]['working_logical_requested_peak']
                comparisons[emode][ref]=comparison
        cases.append({'case':case,'modes':modes,'diagnostic_comparisons':comparisons})
    rotations={}
    for arm,data in d['rotation'].items():
        light=data['light'];detail=data['detail']['attribution']
        # Full light-worker phase observations are retained in its JSONL; no observer footprint is used.
        events=[json.loads(line) for line in (Path(light['directory'])/'events.jsonl').read_text().splitlines()]
        snapshots=[{'type':x['type'],'frame':x['frame'],'device_bytes':x['memory']['device_current_bytes'],
            'footprint_bytes':x['memory']['process_footprint_bytes']} for x in events if x['type'] in ('idle','cleanup')]
        rotations[arm]={'frames':len(light['frames']),'actual_E_frames':sum(x['actual_mode']==1 for x in light['frames']),
            'phase_snapshots':snapshots,'frame_intermediates_released':detail['frame_intermediates_released'],
            'pool_idle_within_original_cap':detail['pool_idle_within_original_cap'],
            'fully_classified_halide_leases':detail['fully_classified_halide_leases'],
            'cleanup_pool_allocated_bytes':[sum(m['pool_allocated_bytes'].values()) for m in detail['snapshots'] if m['name']=='cleanup']}
    return {'complete':True,'B_ref_frozen':False,'performance_acceptance':False,
        'cases':cases,'rotation':rotations,'oracle_comparisons':len(d['rotation_oracle']),
        'max_rotation_linear_error':max(x['comparison']['max_linear_error'] for x in d['rotation_oracle']),
        'scope':'resource diagnosis only; reference timing is not frozen; logical working set is AOT intermediates plus frontier/configuration',
        'limitations':['No E FPS/latency score was collected.',
            'AOT intermediate attribution is not a named-edge spatial-local decomposition, so the formal local-memory benefit gate remains unassessed.',
            'GPU-safe allocation intervals are conservative CPU-observation bounds.',
            'Only light workers supply device-total and process-footprint results.',
            'Worst observed differences compare maximum E with minimum R; both B0/B1 references are retained.']}


def markdown(d):
    mib=1024**2
    lines=['# Wavefront resource diagnosis','',d['scope'],'',
        '| Case | Mode | Logical working MiB | Max device peak MiB | Max process lifetime peak MiB | Max retained device MiB |',
        '| --- | --- | --- | --- | --- | --- |']
    for c in d['cases']:
        for mode,m in c['modes'].items():
            lines.append(f"| {c['case']} | {mode} | {m['working_logical_requested_peak']/mib:.2f} | {m['metrics']['device_total_peak_bytes']['max']/mib:.2f} | {m['metrics']['process_lifetime_peak_bytes']['max']/mib:.2f} | {m['metrics']['retained_device_bytes']['max']/mib:.2f} |")
    lines+=['','All values describe this diagnostic cohort. No formal memory/speed/PR acceptance is asserted.','']
    lines+=['- '+x for x in d['limitations']]
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('summary already exists')
    result=summarize(json.loads(a.report.read_text()));result['report_sha256']=hashlib.sha256(a.report.read_bytes()).hexdigest()
    a.output.mkdir(parents=True);(a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(a.output/'summary.md').write_text(markdown(result));print(markdown(result))


if __name__=='__main__':main()
