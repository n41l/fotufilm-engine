#!/usr/bin/env python3
"""Repeat the frozen light-worker rotation for phase-specific R/R calibration.

Preserves the original mixed-mode request sequence. No timing scores or acceptance.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import uuid

spec=importlib.util.spec_from_file_location('resource',Path(__file__).with_name('verify-wavefront-resources.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


def phase_metrics(record):
    events=[json.loads(x) for x in (Path(record['directory'])/'events.jsonl').read_text().splitlines()]
    final=events[-1];values={'overall.device_peak':final['gpu_total_peak_bytes'],
        'overall.process_lifetime_peak':final['memory']['process_lifetime_peak_bytes']}
    for event in events:
        if event['type'] in ('idle','cleanup'):
            key=f'{event["type"]}.{event["frame"]}'
            values[key+'.device']=event['memory']['device_current_bytes']
            values[key+'.footprint']=event['memory']['process_footprint_bytes']
    return values


def compare(R,E):
    if len(R)!=6 or len(E)!=3:raise ValueError('six R and three C processes required')
    keys=set(R[0])
    if any(set(row)!=keys for row in [*R,*E]):raise ValueError('rotation phase coverage changed')
    result={}
    for key in sorted(keys):
        rv=[row[key] for row in R];ev=[row[key] for row in E]
        pairs=[abs(rv[i]-rv[i+1]) for i in (0,2,4)];epsilon=max(pairs);cap=min(4*1024**2,min(rv)*.02)
        difference=max(ev)-min(rv)
        result[key]={'R_values':rv,'C_values':ev,'R_BB_pairs':pairs,'epsilon_bytes':epsilon,
            'cap_bytes':cap,'R_stable':epsilon<=cap,'worst_difference_bytes':difference,
            'all_observed_within_R_plus_epsilon':epsilon<=cap and difference<=epsilon}
    return result


def main(helper):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source-report','workers','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();source=json.loads(a.source_report.read_text());workers=json.loads(a.workers.read_text())
    identity=json.loads(a.workers.with_name('identity.json').read_text())
    if not source['complete'] or identity!=source['worker_identity']:raise ValueError('complete matching source campaign required')
    for name,path in workers.items():
        if v.b.sha(path)!=identity['workers'][name]:raise ValueError('worker changed')
    root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    report={'scope':'light-worker memory calibration for the unchanged rotation; no timing scores',
        'source_report_sha256':v.b.sha(a.source_report),'source_report':str(a.source_report.resolve()),
        'worker_identity':identity,'R':[],'C':[],'complete':False,'B_ref_frozen':False,'performance_acceptance':False}
    def checkpoint():
        v.b.atomic_json(root/'report.json',report);v.b.atomic_json(a.output.resolve()/'latest.json',{'root':str(root),'report':str(root/'report.json')})
    checkpoint();print('RUN',root,flush=True)
    try:
        for label,arm,count,worker in (('R','R_B1',6,workers['R_light']),('C','C_mix',3,workers['C_light'])):
            plan=json.loads((Path(source['rotation'][arm]['light']['directory'])/'plan.json').read_text())
            for index in range(count):
                record=v.execute(worker,plan,root/f'{label}-{index}','B1',helper)
                metrics=phase_metrics(record);report[label].append({'directory':record['directory'],
                    'events_sha256':record['events_sha256'],'metrics':metrics})
                checkpoint();print('ROTATION',label,index,flush=True)
        report['comparison']=compare([x['metrics'] for x in report['R']],[x['metrics'] for x in report['C']]);report['complete']=True
    except BaseException as error:report['failure']=str(error);raise
    finally:checkpoint()
    print('REPORT',root/'report.json',flush=True)


if __name__=='__main__':
    with v.b.awake_session() as helper:main(helper)
