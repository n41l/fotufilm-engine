#!/usr/bin/env python3
"""Count-based resource diagnostics. No E latency/FPS scores and no frozen B_ref.

Light workers measure total resources. Detailed workers attribute logical leases;
their CPU footprint is not used for memory nonregression. Docker is left running.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import uuid
from wavefront_aot_driver import build
from wavefront_resource_analysis import analyze
spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
TOOLS=('wavefront-resource-driver.mm','wavefront-resource-observer.mm','wavefront-resource-observer.h',
       'wavefront-resource-shim.inc','wavefront_aot_driver.py')
METRICS=('device_total_peak_bytes','process_lifetime_peak_bytes','retained_device_bytes','retained_process_footprint_bytes')


def build_workers(c,r,rkernels,ckernels,root):
    workers={};saved=os.environ.get('FOTUFILM_AOT_WAVEFRONT')
    try:
        for label,repo,kernels in (('R',r,rkernels),('C',c,ckernels)):
            if label=='C':os.environ['FOTUFILM_AOT_WAVEFRONT']='1'
            else:os.environ.pop('FOTUFILM_AOT_WAVEFRONT',None)
            for detail in (False,True):
                key=label+('_detail' if detail else '_light')
                workers[key]=str(build(repo,kernels,root/key,c/'tools/wavefront-resource-driver.mm',
                    definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1',) if label=='C' else (),
                    driver_definitions=(f'-DWF_RESOURCE_CANDIDATE={int(label=="C")}',f'-DWF_RESOURCE_OBSERVER={int(detail)}'),
                    shim_definitions=tuple('-D'+n+'=wf_original_'+n for n in ('new_buffer','commit_command_buffer','retain_ns_object','release_ns_object')) if detail else (),
                    resource_hooks=detail,adapter=c/'tools/wavefront-resource-observer.mm' if detail else None,
                    shim_suffix=c/'tools/wavefront-resource-shim.inc' if detail else None))
    finally:
        if saved is None:os.environ.pop('FOTUFILM_AOT_WAVEFRONT',None)
        else:os.environ['FOTUFILM_AOT_WAVEFRONT']=saved
    identity={'tools':{n:b.sha(c/'tools'/n) for n in TOOLS},'workers':{k:b.sha(v) for k,v in workers.items()},
        'shim':{label:b.sha(repo/'Sources/FotufilmHalide/FotufilmHalideIOS.cpp') for label,repo in (('R',r),('C',c))},
        'aot_identity':{'R':b.sha(rkernels/'.generated-from'),'C':b.sha(ckernels/'.generated-from')}}
    b.atomic_json(root/'workers.json',workers);b.atomic_json(root/'identity.json',identity)
    return workers,identity


def calibrate(rows):
    if len(rows)!=6:raise ValueError('six R processes required for three B/B pairs')
    result={}
    for key in METRICS:
        values=[r['metrics'][key] for r in rows];pairs=[abs(values[i]-values[i+1]) for i in (0,2,4)]
        cap=min(4*1024**2,min(values)*.02)
        result[key]={'epsilon_bytes':max(pairs),'cap_bytes':cap,'stable':max(pairs)<=cap,'pairs':pairs}
    return result


def frame(case,mode,band=256,expected=None):
    actual=int(mode=='E' and band in (64,128,256))
    d={'type':'frame','id':case['id'],'pack':case['pack'],'input':case['input'],
       'mode':mode,'band':band,'expected_mode':actual}
    if expected:d['expected_sha256']=expected
    return d


def metrics(events):
    frames=[e for e in events if e['type']=='resource_frame'];idle=[e for e in events if e['type']=='idle'][-1]
    if len(frames)!=6 or any(e['status']!='success' for e in frames):raise ValueError('six valid count-based frames required')
    warm=frames[3:]
    return {'device_total_peak_bytes':max(e['memory']['device_peak_bytes'] for e in warm),
        'process_lifetime_peak_bytes':max(e['memory']['process_lifetime_peak_bytes'] for e in [*frames,idle]),
        'retained_device_bytes':idle['memory']['device_current_bytes'],
        'retained_process_footprint_bytes':idle['memory']['process_footprint_bytes']}


def execute(worker,plan,out,mode,helper):
    b.require_awake(helper)
    if shutil.disk_usage(out.parent).free<2*1024**3:raise RuntimeError('less than 2 GiB free')
    out.mkdir();b.atomic_json(out/'plan.json',plan)
    b.atomic_json(out/'environment.json',b.environment_observation(out))
    with (out/'events.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
        p=subprocess.run([str(worker),str(out/'plan.json'),str(out)],stdout=stdout,stderr=stderr,
            env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1' if mode=='B1' else '0','FOTUFILM_METAL_POOL':'1024'},timeout=600)
    if p.returncode:raise RuntimeError('resource worker failed: '+str(out))
    events=[json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
    if not events or events[-1]['type']!='resource_complete':raise ValueError('incomplete resource process')
    wanted=[a for a in plan['actions'] if a['type']=='frame'];actual=[e for e in events if e['type']=='resource_frame']
    if len(wanted)!=len(actual):raise ValueError('resource frame coverage changed')
    for a,e in zip(wanted,actual):
        isE=e['actual_mode']==1
        if e['id']!=a['id'] or e['status']!='success' or isE!=bool(a['expected_mode']):raise ValueError('actual resource mode changed')
        if isE!=('_wavefront_' in e['actual_variant']):raise ValueError('fallback counted as E')
        if isE and not e['actual_variant'].endswith('_'+str(a['band'])):raise ValueError('actual band changed')
    record={'directory':str(out),'events_sha256':b.sha(out/'events.jsonl'),'frames':actual}
    if (out/'resource-trace.json').exists():
        data=analyze(json.loads((out/'resource-trace.json').read_text()));b.atomic_json(out/'analysis.json',data)
        record['attribution']=data;record['trace_sha256']=b.sha(out/'resource-trace.json')
    return record


def oracle(cworker,reference_worker,requests,root,compare,helper):
    root.mkdir();plan={'dump':True,'actions':requests+[{'type':'cleanup','seconds':0}]};b.atomic_json(root/'plan.json',plan)
    env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'}
    frames=[];references=[]
    with (root/'stderr.log').open('wb') as err,(root/'events.jsonl').open('wb') as raw:
        process=subprocess.Popen([str(cworker),str(root/'plan.json'),str(root),'--step'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0,env=env)
        buffer=b''
        try:
            for index,request in enumerate(requests):
                b.require_awake(helper)
                while True:
                    # One complete JSON event is flushed per line. No GPU work overlaps reference.
                    while b'\n' not in buffer:
                        ready=selectors.DefaultSelector();ready.register(process.stdout,selectors.EVENT_READ)
                        result=ready.select(timeout=120);ready.close()
                        if not result:raise RuntimeError('oracle C worker stalled')
                        block=os.read(process.stdout.fileno(),65536)
                        if not block:raise RuntimeError('oracle C worker ended early')
                        buffer+=block
                    line,buffer=buffer.split(b'\n',1)
                    raw.write(line+b'\n');raw.flush();event=json.loads(line)
                    if event['type']=='resource_frame':break
                if event['status']!='success':raise ValueError('oracle C frame failed')
                rfile=root/'R.rgba32f';cfile=root/f'{index}.rgba32f'
                if shutil.disk_usage(root).free<2*1024**3+cfile.stat().st_size:raise RuntimeError('oracle disk pressure')
                ref=subprocess.run([str(reference_worker),request['pack'],request['input'],'--dump',str(rfile)],
                    capture_output=True,text=True,env={**env,'FOTUFILM_AOT_WINDOWED':'0'},timeout=120)
                (root/f'R-{index}.jsonl').write_text(ref.stdout);(root/f'R-{index}.stderr').write_text(ref.stderr)
                if ref.returncode:raise RuntimeError('clean R oracle failed')
                checked=subprocess.run([str(compare),str(rfile),str(cfile),'linear'],capture_output=True,text=True)
                comparison=json.loads(checked.stdout)
                if checked.returncode or not comparison['passed'] or comparison['samples']!=Path(request['input']).stat().st_size//4:raise ValueError('resource oracle pixel disagreement; dumps preserved')
                references.append({'frame':index,'R_output_sha256':b.sha(rfile),'C_output_sha256':b.sha(cfile),'comparison':comparison})
                frames.append(event);rfile.unlink();cfile.unlink();process.stdin.write(b'\n');process.stdin.flush()
            process.wait(timeout=30);tail=process.stdout.read();raw.write(buffer+tail)
            if process.returncode:raise RuntimeError('oracle C cleanup failed')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
            process.stdin.close();process.stdout.close()
    b.atomic_json(root/'comparison.json',references)
    return frames,references


def main(helper):
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('reference','reference-kernels','kernels','frozen-cases','normal-verification','baseline-report','prepared','converter','output'):
        p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--reuse-workers',type=Path);args=p.parse_args();c=Path(__file__).resolve().parents[1];r=args.reference.resolve()
    frozen=json.loads(args.frozen_cases.read_text());normal=json.loads(args.normal_verification.read_text());baseline=json.loads(args.baseline_report.read_text());prepared=json.loads(args.prepared.read_text())
    if r==c or subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True).strip():raise ValueError('separate clean R required')
    if subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=frozen['source_base']:raise ValueError('R base changed')
    if normal['frozen_cases_sha256']!=b.sha(args.frozen_cases) or not normal['complete'] or not normal['normal_experimental_kernel_coverage']:raise ValueError('normal E proof required')
    if any(not x['comparison']['passed'] for x in normal['results']):raise ValueError('nonpassing normal verification')
    cases=frozen['cases'];assert len(cases)==4
    for case in cases:
        for key in ('pack','input'):
            if b.sha(case[key])!=case[key+'_sha256']:raise ValueError('fixture changed')
    root=args.output.resolve()/uuid.uuid4().hex[:12];root.mkdir(parents=True)
    if args.reuse_workers:
        workers=json.loads(args.reuse_workers.read_text());identity=json.loads(args.reuse_workers.with_name('identity.json').read_text())
        for n,value in identity['tools'].items():
            if b.sha(c/'tools'/n)!=value:raise ValueError('diagnostic worker source changed: '+n)
        for name,path in workers.items():
            if b.sha(path)!=identity['workers'][name]:raise ValueError('diagnostic worker changed')
        for label,repo in (('R',r),('C',c)):
            if b.sha(repo/'Sources/FotufilmHalide/FotufilmHalideIOS.cpp')!=identity['shim'][label]:raise ValueError('shim source changed')
        for label,k in (('R',args.reference_kernels),('C',args.kernels)):
            if b.sha(k/'.generated-from')!=identity['aot_identity'][label]:raise ValueError('kernel identity changed')
    else:workers,identity=build_workers(c,r,args.reference_kernels.resolve(),args.kernels.resolve(),root/'workers')
    if b.sha(args.converter)!=prepared['converter_sha256']:raise ValueError('converter changed')
    grass=next(x for x in prepared['images'] if x['id']=='grass');assert grass['split']=='tuning'
    if b.sha(grass['canonical'])!=grass['canonical_sha256']:raise ValueError('grass canonical changed')
    grass_inputs={}
    for w,h in ((1920,1080),(3840,2160)):
        path=root/f'grass-{w}x{h}.rgba32f';subprocess.run([str(args.converter.resolve()),grass['canonical'],str(w),str(h),str(path)],check=True)
        grass_inputs[f'{w}x{h}']={'path':str(path),'sha256':b.sha(path)}
    compare=root/'compare';subprocess.run(['xcrun','clang++','-std=c++17','-O2',str(c/'tools/wavefront-compare.cpp'),'-o',str(compare)],check=True)
    report={'scope':'count-based memory and lifecycle diagnostics; no E speed score or formal acceptance',
        'source_base':frozen['source_base'],'worker_identity':identity,'grass_inputs':grass_inputs,
        'sources':{n:b.sha(c/'tools'/n) for n in (*TOOLS,'verify-wavefront-resources.py','wavefront_resource_analysis.py')},
        'source_reports':{str(x.resolve()):b.sha(x) for x in (args.frozen_cases,args.normal_verification,args.baseline_report)},
        'baseline_source_usage':'pixel hashes only; no old timing score or epsilon reused',
        'complete':False,'B_ref_frozen':False,'performance_acceptance':False,'primary':{},'detailed':{},'rotation':{}}
    def checkpoint():
        b.atomic_json(root/'report.json',report);b.atomic_json(args.output.resolve()/'latest.json',{'root':str(root),'report':str(root/'report.json')})
    checkpoint();print('RUN',root,flush=True)
    expected={}
    for case in cases:
        for mode in ('B0','B1'):
            arm=baseline['cases'][case['id']]['arms'][mode][0]
            expected[case['id'],mode]=next(e for e in arm['phase_events'] if e['type']=='measurement_complete')['output_sha256']
        for band in (64,128,256):expected[case['id'],f'E{band}']=next(x['C_output_sha256'] for x in normal['results'] if x['case']==case['id'] and x['candidate']==f'E_{band}')
    try:
        for case in cases:
            entry={};report['primary'][case['id']]=entry
            for mode in ('B0','B1','E64','E128','E256'):
                rows=[];entry[mode]={'processes':rows};isE=mode.startswith('E');band=int(mode[1:]) if isE else 256
                request=frame(case,'E' if isE else 'legacy',band,expected[case['id'],mode])
                for index in range(3 if isE else 6):
                    out=root/f'primary-{case["id"]}-{mode}-{index}'
                    result=execute(workers['C_light' if isE else 'R_light'],{'actions':[request]*6+[{'type':'idle','seconds':5},{'type':'cleanup','seconds':0}]},out,'B1' if isE else mode,helper)
                    result['metrics']=metrics([json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]);rows.append(result);checkpoint()
                if not isE:entry[mode]['epsilon']=calibrate(rows)
                detail=execute(workers['C_detail' if isE else 'R_detail'],{'actions':[request]*3+[{'type':'idle','seconds':5},{'type':'cleanup','seconds':0}]},root/f'detailed-{case["id"]}-{mode}','B1' if isE else mode,helper)
                report['detailed'][case['id']+'-'+mode]=detail;checkpoint();print('RESOURCE',case['id'],mode,flush=True)
        # Predeclared rotation: image/stock/geometry/channel/band/fallback changes, then A again.
        by={(x['stock'],x['size']):x for x in cases}
        A=by['portra400','1920x1080'];B=copy.deepcopy(by['hp5plus400','3840x2160']);B['input']=grass_inputs['3840x2160']['path'];B['id']='hp5plus400-grass-3840x2160'
        G=copy.deepcopy(A);G['input']=grass_inputs['1920x1080']['path'];G['id']='portra400-grass-1920x1080'
        rotation=[frame(A,'E',256),frame(B,'E',128),frame(by['portra400','3840x2160'],'E',64),frame(by['hp5plus400','1920x1080'],'legacy'),frame(A,'E',256),frame(G,'legacy'),frame(A,'E',17),frame(A,'E',256)]
        original_worker=Path(frozen['reference_worker']) if 'reference_worker' in frozen else r/'build/wavefront-benchmark-v2/instrumented/runner'
        if b.sha(original_worker)!=frozen['worker_sha256']:raise ValueError('original pixel oracle worker changed')
        control,pixels=oracle(workers['C_light'],original_worker,rotation,root/'rotation-oracle',compare,helper)
        report['rotation_oracle']=pixels;checkpoint()
        for arm in ('R_B0','R_B1','C_mix'):
            sequence=[]
            for index,request in enumerate(rotation):
                q=copy.deepcopy(request)
                if arm!='C_mix':q['mode']='legacy';q['expected_mode']=0
                if arm=='R_B0':q['expected_sha256']=pixels[index]['R_output_sha256']
                elif arm=='C_mix':q['expected_sha256']=pixels[index]['C_output_sha256']
                # R_B1 is independently checked below against R_B0 for each image before rotation.
                else:q['expected_sha256']=None
                sequence.append(q)
            if arm=='R_B1':
                for index,q in enumerate(sequence):
                    out=root/f'R1-oracle-{index}';out.mkdir();dump=out/'out.rgba32f'
                    result=subprocess.run([str(original_worker),q['pack'],q['input'],'--dump',str(dump)],capture_output=True,text=True,
                        env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024'},timeout=120)
                    if result.returncode:raise RuntimeError('R1 control failed')
                    q['expected_sha256']=b.sha(dump);dump.unlink();(out/'events.jsonl').write_text(result.stdout);(out/'stderr.log').write_text(result.stderr)
            actions=[]
            for session in range(2):
                for cycle in range(2):actions+=sequence+[{'type':'idle','seconds':5}]
                actions+=[{'type':'cleanup','seconds':5}]
            entry={};report['rotation'][arm]=entry
            for detail in (False,True):
                worker=workers[('C' if arm=='C_mix' else 'R')+('_detail' if detail else '_light')]
                entry['detail' if detail else 'light']=execute(worker,{'actions':actions},root/f'rotation-{arm}-{detail}', 'B0' if arm=='R_B0' else 'B1',helper)
                checkpoint()
            print('ROTATION',arm,flush=True)
        report['complete']=True
    except BaseException as error:report['failure']=str(error);raise
    finally:checkpoint()
    print('REPORT',root/'report.json',flush=True)


if __name__=='__main__':
    with b.awake_session() as helper:main(helper)
