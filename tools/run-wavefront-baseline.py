#!/usr/bin/env python3
"""Freeze real-photo B0/B1 references and independent-process B/B memory tolerance.

All worker output, unsuccessful rounds and deadline observations are retained.
No candidate runs are performed by this script. No image decoding is timed.
"""
import argparse
import contextlib
import hashlib
import json
import os
import platform
import re
from pathlib import Path
import selectors
import shutil
import statistics
import subprocess
import time
import uuid
from wavefront_metrics import summarize


def atomic_json(path, value):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


@contextlib.contextmanager
def awake_session():
    """Keep the benchmark controller awake; never override explicit user sleep."""
    helper=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        try:
            helper.wait(timeout=.1)
            raise RuntimeError('idle-sleep assertion did not stay active')
        except subprocess.TimeoutExpired:pass
        yield helper
    finally:
        if helper.poll() is None:helper.terminate()
        helper.wait(timeout=5)


def require_awake(helper):
    if helper is None or helper.poll() is not None:
        raise RuntimeError('benchmark idle-sleep assertion is not active')


def environment_snapshot():
    """Stable Mac/OS/boot identity; excludes serial numbers, host names and load."""
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        raise ValueError('this research protocol requires an ARM64 Mac')
    def read(*command):return subprocess.check_output(command,text=True,stderr=subprocess.DEVNULL,timeout=30).strip()
    cards=json.loads(read('system_profiler','SPDisplaysDataType','-json'))['SPDisplaysDataType']
    return {'architecture':platform.machine(),'model':read('sysctl','-n','hw.model'),
            'cpu':read('sysctl','-n','machdep.cpu.brand_string'),'cpu_count':int(read('sysctl','-n','hw.ncpu')),
            'memory_bytes':int(read('sysctl','-n','hw.memsize')),'boot_session':read('sysctl','-n','kern.bootsessionuuid'),
            'os_version':read('sw_vers','-productVersion'),'os_build':read('sw_vers','-buildVersion'),
            'xcode':read('xcodebuild','-version'),'sdk':read('xcrun','--sdk','macosx','--show-sdk-version'),
            'gpus':[{k:card[k] for k in ('sppci_model','spdisplays_device-id','spdisplays_vendor','spdisplays_metalfamily','sppci_cores') if k in card} for card in cards]}


def environment_observation(path):
    result={'free_disk_bytes':shutil.disk_usage(path).free,'load_average':list(os.getloadavg())}
    for name,command in (('swap_usage',['sysctl','vm.swapusage']),('memory_pressure',['memory_pressure'])):
        try:
            value=subprocess.check_output(command,text=True,stderr=subprocess.DEVNULL,timeout=15).strip()
            if name=='memory_pressure':
                match=re.search(r'System-wide memory free percentage: (\d+)%',value)
                result['system_memory_free_percent']=int(match[1]) if match else None
            else:result[name]=value
        except (OSError,subprocess.SubprocessError):result[name]=None
    return result


def validate_resume(frozen, current):
    # Controller persistence may change; the measurement worker and statistical math may not.
    old={**frozen,'tool_sources':dict(frozen['tool_sources'])}
    new={**current,'tool_sources':dict(current['tool_sources'])}
    old['tool_sources'].pop('run-wavefront-baseline.py',None)
    new['tool_sources'].pop('run-wavefront-baseline.py',None)
    if old!=new:raise ValueError('resume measurement identity changed')


def compact(result, path):
    return {k:v for k,v in result.items() if k!='requests'} | {'round_path':str(path)}


def recover_round(root, mode, image):
    path=root/'round.json'
    if not path.exists():return None
    result=json.loads(path.read_text())
    if result['requested_mode']!=mode or result['identity']['input_sha256']!=sha(image):
        raise ValueError('saved round identity changed')
    if not result['scores']['valid']:raise RuntimeError('saved invalid round requires review; refusing to replace it')
    return compact(result,path)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1048576),b''):digest.update(chunk)
    return digest.hexdigest()


def run_round(worker, pack, image, mode, root, *, expected_band=None):
    # The CLI remains clean-R only. The comparison controller explicitly admits E here.
    experimental = mode == "E" and expected_band in (64,128,256)
    if not experimental and (mode not in ("B0", "B1") or expected_band is not None):
        raise ValueError("R B0/B1 or explicit E with a supported band is required")
    root.mkdir(parents=True)
    records=[]; pending={}; events=[]; issues=[]; window=None; offset=None; deadline_missed=False
    start=time.monotonic()
    with (root/'stderr.log').open('wb') as errors, (root/'events.jsonl').open('wb') as raw:
        process=subprocess.Popen([str(worker),str(pack),str(image)],stdout=subprocess.PIPE,stderr=errors,
            env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1' if mode=='B1' else '0',
                 'FOTUFILM_METAL_POOL':'1024','FOTUFILM_TRACE_VARIANT':'0'})
        selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
        buffer=b''
        try:
            while selector.get_map():
                for key,_ in selector.select(timeout=.05):
                    block=os.read(key.fd,65536)
                    if not block:selector.unregister(key.fileobj);continue
                    raw.write(block);raw.flush();buffer+=block
                    while b'\n' in buffer:
                        line,buffer=buffer.split(b'\n',1)
                        try:event=json.loads(line)
                        except (ValueError,UnicodeError):issues.append('non-JSON worker output');continue
                        events.append(event);kind=event.get('type')
                        identity=str(event.get('id'))
                        if kind=='identity':offset=time.monotonic()-event['clock_sample']
                        elif kind=='window':window=event
                        elif kind=='call_start':pending[identity]={'id':identity,'phase':event['phase'],
                            'started_at':event['submitted_at'],'completed_at':None,'status':'pending'}
                        elif kind=='not_submitted':pending.pop(identity,None)
                        elif kind=='call_complete':
                            pending.pop(identity,None);record={**event,'id':identity};records.append(record)
                            actual=record.get('actual_variant','')
                            if record.get('status')!='success':issues.append('non-success call during warmup or measurement')
                            if experimental:
                                if '_wavefront_' not in actual or not actual.endswith('_'+str(expected_band)):
                                    issues.append('requested E variant not actually executed')
                                if record['aot_calls']<2 or record['gpu_dispatches']<record['aot_calls']:
                                    issues.append('missing actual E GPU work')
                            else:
                                if '_wavefront_' in actual or ('windowed' in actual)!=(mode=='B1'):issues.append('requested AOT mode not actually executed')
                                if record['aot_calls']!=1 or record['gpu_dispatches']<1:issues.append('missing actual GPU work')
                current=time.monotonic()
                if window and offset is not None and current>window['deadline']+offset and pending and not deadline_missed:
                    deadline_missed=True;issues.append('request not observed complete at tail deadline')
                    (root/'deadline-observation.json').write_text(json.dumps({'pending':list(pending.values()),
                        'controller_time':current,'worker_deadline':window['deadline']},indent=2)+'\n')
                if current-start>120:
                    issues.append('isolated worker did not finish within 120 seconds')
                    process.terminate();break
            process.wait(timeout=10)
        finally:
            selector.close()
            if process.poll() is None:process.kill();process.wait()
            process.stdout.close()
    if buffer:issues.append('truncated worker record')
    if process.returncode:issues.append(f'worker exit {process.returncode}')
    records+=list(pending.values())
    identity=next((e for e in events if e['type']=='identity'),None)
    if not window:
        scores={'valid':False,'reasons':['measurement window missing']}
    else:
        scores=summarize({**window,'requests':records})
    if experimental:
        stderr=(root/'stderr.log').read_text(errors='replace')
        policies=re.findall(r'WAVEFRONT_POLICY requested=(\d+) actual=(-?\d+) rows=(\d+) reason=([^\n]+)',stderr)
        counts=re.findall(r'WAVEFRONT_COUNTS rows=(\d+) source_calls=(\d+) consumer_calls=(\d+) ring_rows=(\d+)',stderr)
        height=(identity or {}).get('height',0)
        if policies!=[('1','1',str(expected_band),'admitted')]:issues.append('actual private E admission missing')
        if len(counts)!=1 or height<=0:
            issues.append('private E row accounting missing')
        else:
            rows,source,consumers,capacity=map(int,counts[0])
            if rows!=height or source<1 or consumers!=(height+expected_band-1)//expected_band or capacity!=1024:
                issues.append('invalid E row accounting')
            if any(r.get('aot_calls')!=source+consumers for r in records):issues.append('per-call E source/consumer count changed')
    retained=next((e for e in events if e['type']=='retained'),None)
    if retained is None:issues.append('retained-memory observation missing')
    hashes=[e['output_sha256'] for e in events if e['type'] in ('warmup_complete','measurement_complete')]
    if len(hashes)!=2 or hashes[0]!=hashes[1]:issues.append('fixed-input output changed or phase hash missing')
    if identity and identity['input_sha256']!=sha(image):issues.append('input hash mismatch')
    memories=[e['memory'] for e in events if 'memory' in e]
    memory_metrics={}
    reliable=memories and retained and all(m['process_footprint_bytes'] is not None
        and m['process_lifetime_peak_bytes'] is not None
        and m['process_lifetime_peak_bytes']>=m['process_footprint_bytes']>0
        and m['device_peak_bytes']>=m['device_current_bytes']>0 for m in memories)
    if reliable:
        memory_metrics={'device_total_peak_bytes':max(m['device_peak_bytes'] for m in memories),
            'process_lifetime_peak_bytes':max(m['process_lifetime_peak_bytes'] for m in memories),
            'retained_device_bytes':retained['memory']['device_current_bytes'],
            'retained_process_footprint_bytes':retained['memory']['process_footprint_bytes'],
            'max_thermal_state':max([m['thermal_state'] for m in memories]
                +[r.get('thermal_state',0) for r in records])}
    else:issues.append('memory metrics incomplete or inconsistent')
    scores['valid']=scores['valid'] and not issues
    scores['reasons']+=sorted(set(issues))
    scores['statistics_are_diagnostic_only']=not scores['valid']
    result={'requested_mode':mode,'identity':identity,'scores':scores,'memory':memory_metrics,
            'requests':records,'events_path':str(root/'events.jsonl'),
            'phase_events':[e for e in events if e['type'] not in ('call_start','call_complete')]}
    if experimental:result['experimental_band']=expected_band
    atomic_json(root/'round.json',result)
    return result


def main(*, awake_helper=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--worker',required=True,type=Path)
    parser.add_argument('--prepared',required=True,type=Path)
    parser.add_argument('--catalog',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--pilot',action='store_true',help='one round per mode on the first case; never freezes B_ref')
    parser.add_argument('--resume',type=Path,help='recover completed rounds and preserve interrupted attempts')
    args=parser.parse_args()
    require_awake(awake_helper)
    reference=args.reference.resolve();worker=args.worker.resolve()
    if subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True):raise ValueError('R must be clean')
    base=subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()
    catalog=json.loads(args.catalog.read_text()); prepared=json.loads(args.prepared.read_text())
    if base!=catalog['base_sha']:raise ValueError('stock fixtures belong to another base')
    run=args.resume.resolve() if args.resume else args.output.resolve()/uuid.uuid4().hex[:12]
    if not args.resume:run.mkdir(parents=True)
    cases=[]
    for stock in ('portra400','hp5plus400'):
        for workload in prepared['workloads']:
            size=f'{workload["width"]}x{workload["height"]}'
            pack=next(f for f in catalog['fixtures'] if f['stock']==stock and f['size']==size)
            path=(args.catalog.parent/pack['path']).resolve();image=Path(workload['path']).resolve()
            if sha(path)!=pack['sha256'] or sha(image)!=workload['sha256']:raise ValueError('frozen input changed')
            cases.append({'id':f'{stock}-coffee-{size}','stock':stock,'size':size,'pack':str(path),
                'pack_sha256':pack['sha256'],'input':str(image),'input_sha256':workload['sha256']})
    if args.pilot:cases=cases[:1]
    freeze={'idle_sleep_prevention':'controller-scoped caffeinate -i','environment':environment_snapshot(),'source_base':base,'worker_sha256':sha(worker),'prepared_sha256':sha(args.prepared),
            'corpus_primary':'coffee; SDR photograph, upscaled workload','seed':42,'idle_pool_mib':1024,
            'inflight_frames':1,'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'retained_idle_seconds':5,
            'process_isolation':'fresh process per arm; no system shader cache purge',
            'case_order':'stock then size; alternating B0/B1 order by round',
            'score_aggregation':'median of round medians; maximum round p95; median round throughput',
            'pilot':args.pilot,'cases':cases,'tool_sources':{p.name:sha(p) for p in (
                Path(__file__),Path(__file__).with_name('wavefront-benchmark.mm'),Path(__file__).with_name('wavefront_metrics.py'))}}
    if args.resume:
        frozen=json.loads((run/'frozen-cases.json').read_text());validate_resume(frozen,freeze)
        if (run/'report.json').exists():
            (run/'report.json').rename(run/f'report-before-resume-{uuid.uuid4().hex[:8]}.json')
        atomic_json(run/f'resume-{uuid.uuid4().hex[:8]}.json',{'resumed_at_unix':time.time(),
            'controller_sha256':sha(Path(__file__)),'original_controller_sha256':frozen['tool_sources']['run-wavefront-baseline.py']})
        freeze=frozen
    else:atomic_json(run/'frozen-cases.json',freeze)
    report={'frozen_cases':freeze,'cases':{},'B_ref_frozen':False,'complete':False}
    def checkpoint():
        atomic_json(run/'report.json',report)
        atomic_json(args.output/'latest.json',{'run':str(run),'report':str(run/'report.json')})
    def acquire(case,mode,index):
        require_awake(awake_helper)
        root=run/case['id']/f'{mode}-{index}'
        attempts=[root,*sorted(root.parent.glob(root.name+'-retry-*'))]
        recovered=[(p,recover_round(p,mode,case['input'])) for p in attempts if (p/'round.json').exists()]
        if len(recovered)>1:raise ValueError('multiple completed attempts; manual review required')
        if recovered:return recovered[0][1]
        if shutil.disk_usage(run).free<2*1024**3:raise RuntimeError('less than 2 GiB free; checkpoint saved before starting another worker')
        if root.exists():
            report.setdefault('interrupted_attempts',[]).append(str(root))
            root=root.with_name(root.name+'-retry-'+uuid.uuid4().hex[:8])
        root.parent.mkdir(parents=True,exist_ok=True)
        atomic_json(root.with_name(root.name+'-environment.json'),environment_observation(run))
        result=run_round(worker,case['pack'],case['input'],mode,root)
        return compact(result,root/'round.json')
    try:
        for case in cases:
            arms={'B0':[],'B1':[]};entry={'arms':arms};report['cases'][case['id']]=entry
            for index in range(1 if args.pilot else 3):
                for mode in (('B0','B1') if index%2==0 else ('B1','B0')):
                    result=acquire(case,mode,index)
                    arms[mode].append(result)
                    checkpoint()
                    print(json.dumps({'case':case['id'],'mode':mode,'round':index,'scores':result['scores'],
                                      'memory':result['memory']}),flush=True)
                    if not result['scores']['valid']:raise RuntimeError('invalid baseline round; inspect preserved data')
            if args.pilot:continue
            selected=max(arms,key=lambda m:statistics.median(r['scores']['throughput_fps'] for r in arms[m]))
            entry['B_ref']=selected;entry['selected_from_rounds']=[0,1,2]
            for index in range(3,6):
                result=acquire(case,selected,index)
                arms[selected].append(result)
                checkpoint()
                print(json.dumps({'case':case['id'],'mode':selected,'BB_round':index,'scores':result['scores'],
                                  'memory':result['memory']}),flush=True)
                if not result['scores']['valid']:raise RuntimeError('invalid B/B round')
            epsilon={}
            for metric in ('device_total_peak_bytes','process_lifetime_peak_bytes','retained_device_bytes','retained_process_footprint_bytes'):
                values=[r['memory'][metric] for r in arms[selected]]
                pairs=[abs(values[i]-values[i+1]) for i in (0,2,4)]
                cap=min(4*1024*1024,min(values)*.02)
                epsilon[metric]={'epsilon_bytes':max(pairs),'cap_bytes':cap,'stable':max(pairs)<=cap,'pairs':pairs}
            entry['memory_epsilon']=epsilon
            entry['memory_stable']=all(e['stable'] for e in epsilon.values())
            rates=[r['scores']['throughput_fps'] for r in arms[selected]]
            entry['timing_drift_ratio']=max(rates)/min(rates)-1
            entry['timing_review_required']=entry['timing_drift_ratio']>.05
            checkpoint()
        require_awake(awake_helper)
        report['complete']=True
        report['B_ref_frozen']=not args.pilot and all(e.get('memory_stable') for e in report['cases'].values())
        report['thermal_review_required']=any(r['memory']['max_thermal_state']>=2
            for e in report['cases'].values() for arm in e['arms'].values() for r in arm)
        if report['thermal_review_required']:report['B_ref_frozen']=False
        report['timing_review_required']=any(e.get('timing_review_required') for e in report['cases'].values())
        if report['timing_review_required']:report['B_ref_frozen']=False
    except BaseException as error:
        report['failure']=str(error);report['complete']=False;report['B_ref_frozen']=False
        raise
    finally:
        checkpoint()
    print('REPORT',run/'report.json',flush=True)
    return 0


if __name__=='__main__':
    with awake_session() as helper:raise SystemExit(main(awake_helper=helper))
