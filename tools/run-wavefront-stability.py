#!/usr/bin/env python3
"""Run six consecutive fresh-process rounds of one clean-R arm for diagnosis.

The common worker, 5/30/2-second timing, single in-flight frame, 1 GiB pool and
5%/original-memory caps remain unchanged. This never freezes a B_ref or scores E.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
METRICS=('device_total_peak_bytes','process_lifetime_peak_bytes','retained_device_bytes','retained_process_footprint_bytes')


def assessment(rounds):
    if len(rounds)!=6 or any(not r['scores']['valid'] for r in rounds):
        raise ValueError('six valid fixed-arm rounds required')
    fps=[r['scores']['throughput_fps'] for r in rounds]
    epsilon={}
    for metric in METRICS:
        values=[r['memory'][metric] for r in rounds]
        pairs=[abs(values[i]-values[i+1]) for i in (0,2,4)]
        cap=min(4*1024*1024,min(values)*.02)
        epsilon[metric]={'epsilon_bytes':max(pairs),'cap_bytes':cap,'pairs':pairs,'stable':max(pairs)<=cap}
    timing=max(fps)/min(fps)-1
    thermal=any(r['memory']['max_thermal_state']>=2 for r in rounds)
    return {'throughput_range_ratio':timing,'timing_review_required':timing>.05,
        'memory_epsilon':epsilon,'memory_stable':all(e['stable'] for e in epsilon.values()),
        'thermal_review_required':thermal,
        'stable_under_diagnostic_protocol':timing<=.05 and not thermal and all(e['stable'] for e in epsilon.values()),
        'B_ref_frozen':False,'performance_acceptance':False}


def validate_source(source, reference, worker, case_id):
    if not source.get('complete'):raise ValueError('complete source campaign required')
    frozen=source['frozen_cases']
    if subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True).strip():
        raise ValueError('reference source must be clean')
    if subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base']:
        raise ValueError('reference base changed')
    if b.sha(worker)!=frozen['worker_sha256']:raise ValueError('common reference worker changed')
    for name in ('run-wavefront-baseline.py','wavefront-benchmark.mm','wavefront_metrics.py'):
        if b.sha(Path(__file__).with_name(name))!=frozen['tool_sources'][name]:raise ValueError('measurement source changed: '+name)
    matches=[c for c in frozen['cases'] if c['id']==case_id]
    if len(matches)!=1:raise ValueError('one frozen source case required')
    case=matches[0]
    for key in ('pack','input'):
        if b.sha(case[key])!=case[key+'_sha256']:raise ValueError('frozen input changed')
    return frozen,case


def main(helper):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source-report','reference','worker','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--case',required=True);p.add_argument('--mode',choices=('B0','B1'),default='B1')
    a=p.parse_args();reference=a.reference.resolve();worker=a.worker.resolve()
    if reference==Path(__file__).resolve().parents[1]:raise ValueError('separate clean reference required')
    source=json.loads(a.source_report.read_text());frozen,case=validate_source(source,reference,worker,a.case)
    run=a.output.resolve()/uuid.uuid4().hex[:12]
    run.mkdir(parents=True)
    rounds=[]
    protocol={**{key:frozen[key] for key in ('source_base','worker_sha256','seed','idle_pool_mib','inflight_frames',
        'warmup_seconds','window_seconds','tail_seconds','retained_idle_seconds','process_isolation','score_aggregation')},
        'pilot':True,'diagnostic_only':True,'cases':[case],
        'environment':b.environment_snapshot(),'idle_sleep_prevention':'controller-scoped caffeinate -i',
        'source_report':str(a.source_report.resolve()),'source_report_sha256':b.sha(a.source_report),
        'case_order':'six consecutive fresh processes of the fixed case and fixed original arm',
        'rounds':6,'mode':a.mode,'tool_sources':{name:b.sha(Path(__file__).with_name(name)) for name in
            ('run-wavefront-stability.py','run-wavefront-baseline.py','wavefront-benchmark.mm','wavefront_metrics.py')}}
    report={'frozen_cases':protocol,'cases':{case['id']:{'arms':{a.mode:rounds}}},
        'complete':False,'B_ref_frozen':False,'performance_acceptance':False,'diagnostic_only':True}
    def checkpoint():
        b.atomic_json(run/'report.json',report)
        b.atomic_json(a.output.resolve()/'latest.json',{'run':str(run),'report':str(run/'report.json')})
    b.atomic_json(run/'frozen-cases.json',protocol);checkpoint()
    print('RUN',run,flush=True)
    try:
        for index in range(6):
            b.require_awake(helper)
            if shutil.disk_usage(run).free<2*1024**3:raise RuntimeError('less than 2 GiB free')
            root=run/case['id']/f'{a.mode}-{index}';root.parent.mkdir(parents=True,exist_ok=True)
            b.atomic_json(root.with_name(root.name+'-environment.json'),b.environment_observation(run))
            result=b.run_round(worker,case['pack'],case['input'],a.mode,root)
            rounds.append(b.compact(result,root/'round.json'));checkpoint()
            b.atomic_json(root.with_name(root.name+'-after-environment.json'),b.environment_observation(run))
            print(json.dumps({'round':index,'scores':result['scores'],'memory':result['memory']}),flush=True)
            if not result['scores']['valid']:raise RuntimeError('invalid round preserved; no replacement attempt permitted')
        b.require_awake(helper);report['assessment']=assessment(rounds);report['complete']=True
    except BaseException as error:
        report['failure']=str(error)
        raise
    finally:checkpoint()
    print('REPORT',run/'report.json',flush=True)
    return 0


if __name__=='__main__':
    with b.awake_session() as helper:raise SystemExit(main(helper))
