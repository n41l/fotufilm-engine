#!/usr/bin/env python3
"""Diagnostic CPU/Metal timing of six fixed clean-R rounds; never a formal score.

Builds a separate worker, verifies exact R pixels, preserves GPU intervals and joins
all adapter records by request ID. CPU, wait and GPU times overlap; do not add them.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from wavefront_aot_driver import build


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

s=load('fixed','run-wavefront-stability.py');b=s.b
analysis=load('analysis','analyze-wavefront-stability.py')
FIELDS=('api_wall_seconds','main_thread_cpu_seconds','process_cpu_seconds','wait_wall_seconds',
        'gpu_sum_seconds','gpu_union_seconds','gpu_span_seconds')


def gpu_intervals(intervals):
    if not intervals:raise ValueError('GPU interval coverage missing')
    ordered=sorted(intervals);end=0;total=0;union=0
    for start,finish,status in ordered:
        if status!=4 or not all(math.isfinite(v) and v>0 for v in (start,finish)) or finish<start:
            raise ValueError('GPU timestamp/status invalid')
        total+=finish-start;union+=max(0,finish-max(end,start));end=max(end,finish)
    return {'gpu_sum_seconds':total,'gpu_union_seconds':union,'gpu_span_seconds':end-ordered[0][0]}


def validate_timings(requests, text):
    events=[json.loads(line[len('API_TIMING '):]) for line in text.splitlines() if line.startswith('API_TIMING ')]
    by_id={str(e['id']):e for e in events}
    if len(by_id)!=len(events):raise ValueError('duplicate timing request ID')
    expected={str(r['id']) for r in requests}
    if set(by_id)!=expected:raise ValueError('CPU/GPU timing request coverage incomplete')
    for r in requests:
        e=by_id[str(r['id'])]
        if not e['timing_complete'] or e['engine_error']!=0:raise ValueError('timing or engine completion incomplete')
        count=len(e['gpu_intervals'])
        if not count==e['committed']==e['completed']==e['timestamped'] or e['queue_count']<1 or e['wait_count']<1:
            raise ValueError('GPU/wait coverage inconsistent')
        for key in FIELDS:
            if not isinstance(e[key],(float,int)) or not math.isfinite(e[key]) or e[key]<0:
                raise ValueError('unavailable/nonfinite component time')
        if e['api_wall_seconds']<=0 or e['api_wall_seconds']>r['completed_at']-r['started_at']+1e-6:
            raise ValueError('inner API time exceeds complete observed call')
        for key,value in gpu_intervals(e['gpu_intervals']).items():
            if not math.isclose(value,e[key],rel_tol=1e-8,abs_tol=1e-8):raise ValueError('GPU interval summary disagrees')
    measured=[by_id[str(r['id'])] for r in requests if r['phase']=='measurement']
    if not measured:raise ValueError('no measured requests')
    return {'coverage_complete':True,'total_requests':len(requests),'measurement_requests':len(measured),
        'seconds':{key:analysis.distribution([e[key] for e in measured]) for key in FIELDS},
        'command_buffers_per_call':sorted({e['committed'] for e in measured}),
        'waits_per_call':sorted({e['wait_count'] for e in measured}),
        'queues_per_call':sorted({e['queue_count'] for e in measured}),
        'common_outer_mean_seconds':sum(r['completed_at']-r['started_at'] for r in requests if r['phase']=='measurement')/len(measured),
        'scope':'overlapping wall/CPU/wait/GPU envelopes; diagnostic instrumentation affects timing'}


def probe(worker, case, source_arm, root):
    run=subprocess.run([str(worker),case['pack'],case['input'],'--dump',str(root/'probe.rgba32f')],
        text=True,capture_output=True,env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1',
        'FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0'})
    (root/'probe.stdout.jsonl').write_text(run.stdout);(root/'probe.stderr.log').write_text(run.stderr)
    if run.returncode:raise RuntimeError('diagnostic probe failed; stderr preserved')
    events=[json.loads(line) for line in run.stdout.splitlines() if line.strip()]
    call=next(e for e in events if e['type']=='call_complete');call['phase']='measurement'
    output=next(e for e in events if e['type']=='verification_complete')['output_sha256']
    expected=next(e for e in source_arm[0]['phase_events'] if e['type']=='measurement_complete')['output_sha256']
    if call['status']!='success' or call['aot_calls']!=1 or output!=expected or b.sha(root/'probe.rgba32f')!=expected:
        raise ValueError('diagnostic probe differs from original R pixels/work')
    result={'passed':True,'output_sha256':output,'byte_identical_to_original_R':True,
        'timing':validate_timings([call],run.stderr),'scope':'one cold verification frame, not a warm score'}
    b.atomic_json(root/'probe.json',result)
    return result


def main(helper):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','kernels','source-report','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1];ref=a.reference.resolve();kernels=a.kernels.resolve()
    src=json.loads(a.source_report.read_text());f=src['frozen_cases']
    if not src['complete'] or not src.get('diagnostic_only') or len(f['cases'])!=1 or f['mode']!='B1':
        raise ValueError('complete fixed-B1 source diagnostic required')
    if ref==repo or subprocess.check_output(['git','-C',str(ref),'status','--porcelain'],text=True).strip():
        raise ValueError('separate clean R required')
    if subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=f['source_base']:
        raise ValueError('reference base changed')
    for name in ('wavefront-benchmark.mm','wavefront_metrics.py','run-wavefront-baseline.py'):
        if b.sha(repo/'tools'/name)!=f['tool_sources'][name]:raise ValueError('common measurement source changed')
    case=f['cases'][0]
    for key in ('input','pack'):
        if b.sha(case[key])!=case[key+'_sha256']:raise ValueError('frozen fixture changed')
    if shutil.disk_usage(a.output.parent if a.output.parent.exists() else repo).free<2*1024**3:
        raise RuntimeError('less than 2 GiB free')
    run=a.output.resolve()/uuid.uuid4().hex[:12];run.mkdir(parents=True)
    worker=build(ref,kernels,run/'worker',repo/'tools/wavefront-benchmark.mm',
        driver_definitions=('-Dfotufilm_halide_metal_process_linear_float=fotufilm_timing_process_linear_float',),
        adapter=repo/'tools/wavefront-timing-adapter.mm')
    for name in ('wavefront-timing-adapter.mm','wavefront-benchmark.mm'):
        shutil.copyfile(repo/'tools'/name,run/'worker'/name)
    original=src['cases'][case['id']]['arms']['B1'];probe_result=probe(worker,case,original,run/'worker')
    protocol={**f,'environment':b.environment_snapshot(),'worker_sha256':b.sha(worker),
        'source_report':str(a.source_report.resolve()),'source_report_sha256':b.sha(a.source_report),
        'original_R_worker_sha256':f['worker_sha256'],'timing_instrumentation':True,
        'R_aot_identity':(kernels/'.generated-from').read_text(),
        'R_shim_sha256':b.sha(ref/'Sources/FotufilmHalide/FotufilmHalideIOS.cpp'),
        'tool_sources':{name:b.sha(repo/'tools'/name) for name in ('run-wavefront-timing.py',
            'wavefront-timing-adapter.mm','wavefront-benchmark.mm','run-wavefront-baseline.py',
            'run-wavefront-stability.py','wavefront_metrics.py','wavefront_aot_driver.py')}}
    rounds=[];report={'frozen_cases':protocol,'cases':{case['id']:{'arms':{'B1':rounds}}},
        'probe':probe_result,'complete':False,'diagnostic_only':True,'B_ref_frozen':False,'performance_acceptance':False}
    def checkpoint():
        b.atomic_json(run/'report.json',report)
        b.atomic_json(a.output.resolve()/'latest.json',{'run':str(run),'report':str(run/'report.json')})
    b.atomic_json(run/'frozen-cases.json',protocol);checkpoint();print('RUN',run,flush=True)
    try:
        for index in range(6):
            b.require_awake(helper)
            if shutil.disk_usage(run).free<2*1024**3:raise RuntimeError('less than 2 GiB free')
            root=run/case['id']/f'B1-{index}';root.parent.mkdir(parents=True,exist_ok=True)
            b.atomic_json(root.with_name(root.name+'-environment.json'),b.environment_observation(run))
            result=b.run_round(worker,case['pack'],case['input'],'B1',root)
            rounds.append(b.compact(result,root/'round.json'));checkpoint()
            if not result['scores']['valid']:raise RuntimeError('invalid engine round; preserved without replacement')
            timing=validate_timings(result['requests'],(root/'stderr.log').read_text())
            b.atomic_json(root/'timing-summary.json',timing);rounds[-1]['timing']=timing;checkpoint()
            b.atomic_json(root.with_name(root.name+'-after-environment.json'),b.environment_observation(run))
            print(json.dumps({'round':index,'fps':result['scores']['throughput_fps'],
                'mean_ms':{key:value['mean']*1000 for key,value in timing['seconds'].items()}}),flush=True)
        b.require_awake(helper);report['assessment']=s.assessment(rounds);report['complete']=True
        report['timing_coverage_complete']=all(r['timing']['coverage_complete'] for r in rounds)
    except BaseException as error:
        report['failure']=str(error);raise
    finally:checkpoint()
    print('REPORT',run/'report.json',flush=True)


if __name__=='__main__':
    with b.awake_session() as helper:main(helper)
