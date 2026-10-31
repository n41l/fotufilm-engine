#!/usr/bin/env python3
"""Bounded R-B1 / two-stage / three-stage warm timing; never a PR gate.

One fresh process per arm per frozen case. No dumps, compilation or cache purge.
The named R-B1 arm is not a frozen best baseline. Retain every attempt.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import uuid


def main():
    c=Path(__file__).resolve().parents[1]
    s=importlib.util.spec_from_file_location('baseline',c/'tools/run-wavefront-baseline.py')
    b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('proof','fixtures','reference-report','reference-worker','output'):
        p.add_argument('--'+arg,required=True,type=Path)
    a=p.parse_args()
    proof=json.loads(a.proof.read_text());frozen=json.loads(a.fixtures.read_text())
    previous=json.loads(a.reference_report.read_text())
    if not proof['complete'] or not all(x['passed'] for x in proof['results']):
        raise ValueError('complete independent numerical proof required')
    if b.sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:
        raise ValueError('common timed driver changed')
    workers={'R-B1':a.reference_worker.resolve(),**{k:Path(proof['workers'][k]['path']) for k in ('2','3')}}
    if b.sha(workers['R-B1'])!=frozen['worker_sha256']:
        raise ValueError('frozen reference worker changed')
    for k in ('2','3'):
        if b.sha(workers[k])!=proof['workers'][k]['sha256']:raise ValueError('verified candidate worker changed')
    expected={}
    for case in frozen['cases']:
        for name in ('input','pack'):
            if b.sha(case[name])!=case[name+'_sha256']:raise ValueError('fixture changed')
        cid=case['id'];expected[cid]={}
        for k in ('2','3'):
            expected[cid][k]=next(x['C_output_sha256'] for x in proof['results'] if x['case']==cid and x['worker']==k)
        hashes={e['output_sha256'] for r in previous['cases'][cid]['arms']['B1']
            for e in r['phase_events'] if e['type'] in ('warmup_complete','measurement_complete')}
        if len(hashes)!=1:raise ValueError('reference output was not deterministic')
        expected[cid]['R-B1']=hashes.pop()
    root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    report={'scope':__doc__,'complete':False,'performance_acceptance':False,'B_ref_frozen':False,
        'protocol':{'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'idle_seconds':5,
            'band_rows':512,'light_ring_rows':2048,'three_stage_log_ring_rows':1024,
            'rounds_per_case_arm':1,'inflight_frames':1,'pool_mib':1024,'image_dumps':False,
            'minimum_free_bytes':1024**3,'evidence_budget_bytes':128*1024**2,
            'order_policy':'predeclared rotating order, final case reverses E pair; not a balanced repeated campaign'},
        'source_reports':{str(x.resolve()):b.sha(x) for x in (a.proof,a.fixtures,a.reference_report)},
        'controllers':{x:b.sha(c/'tools'/x) for x in ('run-wavefront-stage-diagnostic.py','run-wavefront-baseline.py','wavefront_metrics.py')},
        'workers':{k:{'path':str(v),'sha256':b.sha(v)} for k,v in workers.items()},'cases':[]}
    def save():
        b.atomic_json(root/'report.json',report)
        b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
    save();print('RUN',root,flush=True)
    orders=(('R-B1','2','3'),('2','3','R-B1'),('3','R-B1','2'),('R-B1','3','2'))
    try:
        with b.awake_session() as helper:
            for index,case in enumerate(frozen['cases']):
                row={'case':case['id'],'order':orders[index],'arms':{}};report['cases'].append(row);save()
                for arm in row['order']:
                    b.require_awake(helper)
                    if shutil.disk_usage(root).free<1024**3:raise RuntimeError('less than 1 GiB free; stopped before another worker')
                    if sum(x.stat().st_size for x in root.rglob('*') if x.is_file())>128*1024**2:
                        raise RuntimeError('bounded evidence budget reached')
                    out=root/(case['id']+'-'+arm)
                    b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
                    result=b.run_round(workers[arm],Path(case['pack']),Path(case['input']),
                        'B1' if arm=='R-B1' else 'E',out,
                        **({} if arm=='R-B1' else {'expected_band':512,'expected_ring_rows':2048,'expected_stage_count':int(arm)}))
                    phases=[e for e in result['phase_events'] if e['type'] in ('warmup_complete','measurement_complete')]
                    row['arms'][arm]=b.compact(result,out/'round.json');save()
                    if len(phases)!=2 or any(e['output_sha256']!=expected[case['id']][arm] for e in phases):
                        raise RuntimeError('verified own-arm output hash mismatch; attempt retained')
                    print(json.dumps({'case':case['id'],'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
                    if not result['scores']['valid']:raise RuntimeError('invalid diagnostic round retained')
                row['three_vs_two_median_reduction']=1-row['arms']['3']['scores']['median_seconds']/row['arms']['2']['scores']['median_seconds']
                for arm in ('2','3'):
                    row[arm+'_vs_R_B1_median_reduction']=1-row['arms'][arm]['scores']['median_seconds']/row['arms']['R-B1']['scores']['median_seconds']
                save()
        report['complete']=True
    except BaseException as error:
        report['failure']=str(error);raise
    finally:save()
    print('REPORT',root/'report.json',flush=True)


if __name__=='__main__':main()
