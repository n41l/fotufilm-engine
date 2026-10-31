#!/usr/bin/env python3
"""Collect three fresh-process B/E pairs only after a stable clean-R baseline is frozen.

This reports primary nonregression, not final PR acceptance. Band tuning, holdouts,
local intermediate attribution and same-process resource rotation are separate gates.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import uuid

spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
METRICS=('device_total_peak_bytes','process_lifetime_peak_bytes','retained_device_bytes','retained_process_footprint_bytes')


def validate_protocol(baseline, verification, fixtures, *, band, R_sha, E_sha, fixture_sha, common_sha, stats_sha, environment):
    if not baseline.get('complete') or not baseline.get('B_ref_frozen'):
        raise ValueError('stable frozen clean-R B_ref is required before collecting E scores')
    frozen=baseline['frozen_cases']
    if frozen.get('environment')!=environment:raise ValueError('Mac, OS, boot or toolchain changed; freeze a fresh R baseline')
    if frozen.get('pilot') or baseline.get('thermal_review_required') or baseline.get('timing_review_required'):
        raise ValueError('baseline still requires review')
    if band not in (64,128,256):raise ValueError('unsupported preselected band')
    expected={'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'retained_idle_seconds':5,'idle_pool_mib':1024,'inflight_frames':1}
    if any(frozen.get(k)!=v for k,v in expected.items()):raise ValueError('measurement protocol changed')
    if not verification.get('complete') or not verification.get('normal_experimental_kernel_coverage'):
        raise ValueError('complete non-traced E verification is required')
    if any(not r['comparison']['passed'] for r in verification['results']):raise ValueError('candidate pixels failed')
    if fixture_sha!=verification['frozen_cases_sha256']:raise ValueError('verification fixtures changed')
    if frozen['source_base']!=verification['reference_base'] or frozen['source_base']!=fixtures['source_base']:
        raise ValueError('reference base changed')
    if R_sha!=frozen['worker_sha256'] or R_sha!=verification['R_worker_sha256'] or R_sha!=fixtures['worker_sha256']:
        raise ValueError('R worker changed')
    if E_sha!=verification['C_worker_sha256'].get(f'E_{band}'):raise ValueError('E worker is not the verified non-traced binary')
    if common_sha!=frozen['tool_sources']['wavefront-benchmark.mm'] or common_sha!=verification['common_driver_sha256']:
        raise ValueError('common measurement driver changed')
    if stats_sha!=frozen['tool_sources']['wavefront_metrics.py']:raise ValueError('statistical math changed')
    if frozen['cases']!=fixtures['cases']:raise ValueError('input, pack or case identities changed')
    ids={c['id'] for c in frozen['cases']}
    if len(ids)!=4 or set(baseline['cases'])!=ids:raise ValueError('four original main cases required')
    covered={r['case'] for r in verification['results'] if r['candidate']==f'E_{band}'}
    if covered!=ids:raise ValueError('normal E main-case coverage missing')
    for entry in baseline['cases'].values():
        mode=entry.get('B_ref')
        if mode not in ('B0','B1') or len(entry['arms'][mode])!=6 or len(entry['arms'].get('B0',[]))<3 or len(entry['arms'].get('B1',[]))<3:
            raise ValueError('baseline selection/calibration incomplete')
        if not entry.get('memory_stable') or entry.get('timing_review_required'):
            raise ValueError('baseline memory/timing requires review')
        if any(not r['scores']['valid'] for arm in entry['arms'].values() for r in arm):
            raise ValueError('invalid baseline round')
        if mode!=max(('B0','B1'),key=lambda arm:statistics.median(r['scores']['throughput_fps'] for r in entry['arms'][arm][:3])):
            raise ValueError('B_ref was not selected from the faster original R medians')
        for metric in METRICS:
            e=entry['memory_epsilon'][metric];values=[r['memory'][metric] for r in entry['arms'][mode]]
            cap=min(4*1024*1024,min(values)*.02);measured=max(abs(values[i]-values[i+1]) for i in (0,2,4))
            if not e['stable'] or e['epsilon_bytes']!=measured or e['cap_bytes']!=cap or measured>cap:
                raise ValueError('unstable or changed memory epsilon')


def assess(arms, epsilon):
    def aggregate(rounds):
        return {'median_seconds':statistics.median(r['scores']['median_seconds'] for r in rounds),
                'p95_seconds':max(r['scores']['p95_seconds'] for r in rounds),
                'throughput_fps':statistics.median(r['scores']['throughput_fps'] for r in rounds)}
    if any(len(arms[k])!=3 or any(not r['scores']['valid'] for r in arms[k]) for k in ('B','E')):
        raise ValueError('three valid B/E pairs required')
    R,E=aggregate(arms['B']),aggregate(arms['E'])
    speed={'median':E['median_seconds']<=R['median_seconds']*1.05,
           'p95':E['p95_seconds']<=R['p95_seconds']*1.10,
           'throughput':E['throughput_fps']>=R['throughput_fps']*.95}
    memory={}
    for metric in METRICS:
        tolerance=epsilon[metric]['epsilon_bytes']
        deltas=[e['memory'][metric]-r['memory'][metric] for r,e in zip(arms['B'],arms['E'])]
        values=[r['memory'][metric] for r in arms['B']]
        memory[metric]={'E_minus_R_bytes':deltas,'frozen_epsilon_bytes':tolerance,
                        'passed':max(deltas)<=tolerance,'R_range_stable':max(values)-min(values)<=tolerance}
    rates=[r['scores']['throughput_fps'] for r in arms['B']]
    drift=max(rates)/min(rates)-1
    thermal=max(r['memory']['max_thermal_state'] for rounds in arms.values() for r in rounds)
    review=drift>.05 or thermal>=2 or any(not m['R_range_stable'] for m in memory.values())
    return {'B':R,'E':E,'speed_nonregression':speed,'total_memory_nonregression':memory,
            'matched_R_timing_drift_ratio':drift,'max_thermal_state':thermal,'environment_review_required':review,
            'primary_nonregression':all(speed.values()) and all(m['passed'] for m in memory.values()) and not review,
            'median_improvement_at_least_10pct':E['median_seconds']<=R['median_seconds']*.9,
            'local_intermediate_peak_reduction':None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','reference-worker','worker','baseline-report','normal-verification','verification-fixtures','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--band',required=True,type=int)
    parser.add_argument('--resume',type=Path)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
    baseline=json.loads(args.baseline_report.read_text());verification=json.loads(args.normal_verification.read_text())
    fixtures=json.loads(args.verification_fixtures.read_text())
    if args.reference.resolve()==repo or subprocess.check_output(['git','-C',str(args.reference),'status','--porcelain'],text=True):
        raise ValueError('R must remain a separate clean checkout')
    if subprocess.check_output(['git','-C',str(args.reference),'rev-parse','HEAD'],text=True).strip()!=baseline['frozen_cases']['source_base']:
        raise ValueError('reference base changed')
    environment=b.environment_snapshot()
    validate_protocol(baseline,verification,fixtures,band=args.band,R_sha=b.sha(args.reference_worker),E_sha=b.sha(args.worker),
        fixture_sha=b.sha(args.verification_fixtures),common_sha=b.sha(repo/'tools/wavefront-benchmark.mm'),stats_sha=b.sha(repo/'tools/wavefront_metrics.py'),environment=environment)
    for case in fixtures['cases']:
        for key in ('input','pack'):
            if b.sha(case[key])!=case[key+'_sha256']:raise ValueError('frozen fixture changed')
    freeze={'baseline_report_sha256':b.sha(args.baseline_report),'verification_report_sha256':b.sha(args.normal_verification),
            'fixtures_sha256':b.sha(args.verification_fixtures),'R_worker_sha256':b.sha(args.reference_worker),
            'E_worker_sha256':b.sha(args.worker),'band':args.band,'environment':environment,'case_order':[c['id'] for c in fixtures['cases']],
            'controller_sha256':b.sha(Path(__file__)),'collector_sha256':b.sha(Path(b.__file__)),
            'stats_sha256':b.sha(repo/'tools/wavefront_metrics.py')}
    run=args.resume.resolve() if args.resume else args.output.resolve()/uuid.uuid4().hex[:12]
    if args.resume:
        if json.loads((run/'frozen-comparison.json').read_text())!=freeze:raise ValueError('resume identity changed')
        if (run/'report.json').exists():(run/'report.json').rename(run/f'report-before-resume-{uuid.uuid4().hex[:8]}.json')
    else:run.mkdir(parents=True);b.atomic_json(run/'frozen-comparison.json',freeze)
    args.output.mkdir(parents=True,exist_ok=True)
    report={'scope':__doc__,'frozen_comparison':freeze,'cases':{},'complete':False,'performance_acceptance':False,
            'missing_final_gates':['band tuning and holdouts','local intermediate attribution','same-process resource rotation','final PR review']}
    def checkpoint():
        b.atomic_json(run/'report.json',report);b.atomic_json(args.output/'latest.json',{'report':str(run/'report.json')})
    try:
        for case in fixtures['cases']:
            reference=baseline['cases'][case['id']];arms={'B':[],'E':[]};entry={'B_ref':reference['B_ref'],'arms':arms}
            report['cases'][case['id']]=entry
            for index in range(3):
                for arm in (('B','E') if index%2==0 else ('E','B')):
                    mode=reference['B_ref'] if arm=='B' else 'E';root=run/case['id']/f'{arm}-{index}'
                    attempts=[root,*sorted(root.parent.glob(root.name+'-retry-*'))]
                    recovered=[(p,b.recover_round(p,mode,case['input'])) for p in attempts if (p/'round.json').exists()]
                    if len(recovered)>1:raise ValueError('multiple completed attempts need review')
                    if recovered:result=recovered[0][1]
                    else:
                        if shutil.disk_usage(run).free<2*1024**3:raise RuntimeError('less than 2 GiB free; checkpoint saved')
                        if root.exists():
                            report.setdefault('interrupted_attempts',[]).append(str(root));root=root.with_name(root.name+'-retry-'+uuid.uuid4().hex[:8])
                        worker=args.reference_worker if arm=='B' else args.worker
                        root.parent.mkdir(parents=True,exist_ok=True)
                        b.atomic_json(root.with_name(root.name+'-environment.json'),b.environment_observation(run))
                        full=b.run_round(worker.resolve(),Path(case['pack']),Path(case['input']),mode,root,
                                         expected_band=args.band if arm=='E' else None)
                        result=b.compact(full,root/'round.json')
                    arms[arm].append(result);checkpoint()
                    print(json.dumps({'case':case['id'],'arm':arm,'pair':index,'scores':result['scores'],'memory':result['memory']}),flush=True)
                    if not result['scores']['valid']:raise RuntimeError('invalid round; preserved and not replaceable')
            entry['assessment']=assess(arms,reference['memory_epsilon']);checkpoint()
        report['complete']=True
        report['all_primary_nonregression']=all(c['assessment']['primary_nonregression'] for c in report['cases'].values())
        report['any_median_improvement_at_least_10pct']=any(c['assessment']['median_improvement_at_least_10pct'] for c in report['cases'].values())
    except BaseException as error:report['failure']=str(error);raise
    finally:checkpoint()
    print('REPORT',run/'report.json',flush=True)


if __name__=='__main__':main()
