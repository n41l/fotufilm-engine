#!/usr/bin/env python3
"""One pre/post pair per frozen case, 512 rows. Diagnostic, never a PR gate.

No image dumps are written. Keep a 1-GiB disk reserve and a 128-MiB evidence
budget for this bounded campaign; the full baseline campaign is unchanged.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import uuid


def load_module(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m


def main():
    c=Path(__file__).resolve().parents[1]
    b=load_module('baseline',c/'tools/run-wavefront-baseline.py')
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pre-worker','pre-identity','pre-proof','post-proof','fixtures','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    a=parser.parse_args()
    frozen=json.loads(a.fixtures.read_text());pre=json.loads(a.pre_proof.read_text())
    post=json.loads(a.post_proof.read_text());identity=json.loads(a.pre_identity.read_text())
    if not pre['complete'] or not post['complete'] or any(not x['comparison']['passed'] for d in (pre,post) for x in d['results']):
        raise ValueError('complete independent normal pixel proofs required')
    if not all(identity['fresh_archive_equal_to_frozen'].values()) or len(identity['fresh_archive_sha256'])!=6:
        raise ValueError('active pre-cut kernels must match their independently verified frozen archives')
    if b.sha(c/'tools/wavefront-benchmark.mm')!=frozen['tool_sources']['wavefront-benchmark.mm']:
        raise ValueError('common timed driver changed')
    workers={'pre':a.pre_worker.resolve(),'post':Path(post['C_worker_paths']['E_512'])}
    if b.sha(workers['post'])!=post['C_worker_sha256']['E_512']:raise ValueError('post worker changed')
    for row in frozen['cases']:
        for name in ('input','pack'):
            if b.sha(row[name])!=row[name+'_sha256']:raise ValueError('frozen fixture changed')
    root=a.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    os.environ['FOTUFILM_WAVEFRONT_BENCH_ROWS']='512'
    report={'scope':__doc__,'complete':False,'performance_acceptance':False,'B_ref_frozen':False,
        'protocol':{'band_rows':512,'ring_rows':2048,'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,
            'idle_seconds':5,'inflight_frames':1,'pool_mib':1024,'pairs_per_case':1,
            'minimum_free_bytes':1024**3,'evidence_budget_before_next_round_bytes':128*1024**2,'image_dumps':False},
        'workers':{k:{'path':str(v),'sha256':b.sha(v)} for k,v in workers.items()},
        'source_reports':{str(p.resolve()):b.sha(p) for p in (a.pre_identity,a.pre_proof,a.post_proof,a.fixtures)},
        'controller_sha256':b.sha(Path(__file__)),'cases':[]}
    def save():
        b.atomic_json(root/'report.json',report)
        b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
    save();print('RUN',root,flush=True)
    try:
        with b.awake_session() as helper:
            for index,case in enumerate(frozen['cases']):
                row={'case':case['id'],'order':['pre','post'] if index%2==0 else ['post','pre'],'arms':{}}
                report['cases'].append(row)
                for arm in row['order']:
                    b.require_awake(helper)
                    if shutil.disk_usage(root).free<1024**3:raise RuntimeError('less than 1 GiB free; bounded diagnostic stopped before another worker')
                    if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>128*1024**2:raise RuntimeError('diagnostic evidence budget reached')
                    out=root/(case['id']+'-'+arm)
                    b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
                    result=b.run_round(workers[arm],Path(case['pack']),Path(case['input']),'E',out,
                        expected_band=512,expected_ring_rows=2048)
                    proof=pre if arm=='pre' else post
                    expected=next(x['C_output_sha256'] for x in proof['results'] if x['case']==case['id'] and x['candidate']=='E_512')
                    phases=[e for e in result['phase_events'] if e['type'] in ('warmup_complete','measurement_complete')]
                    if len(phases)!=2 or any(e['output_sha256']!=expected for e in phases):raise RuntimeError('own-arm verified pixel hash mismatch')
                    row['arms'][arm]=b.compact(result,out/'round.json');save()
                    print(json.dumps({'case':case['id'],'arm':arm,'scores':result['scores'],'memory':result['memory']}),flush=True)
                    if not result['scores']['valid']:raise RuntimeError('invalid diagnostic round retained')
                before=row['arms']['pre']['scores']['median_seconds'];after=row['arms']['post']['scores']['median_seconds']
                row['observed_median_reduction_ratio']=1-after/before
                save()
        report['complete']=True
    except BaseException as error:
        report['failure']=str(error);raise
    finally:
        save()
    print('REPORT',root/'report.json',flush=True)


if __name__=='__main__':main()
