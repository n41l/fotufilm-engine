#!/usr/bin/env python3
"""Stage22 UHD long-window controls plus one detailed frame per second; four Williams orders."""
import argparse,gzip,hashlib,importlib.util,json,os,shutil,subprocess,time
from pathlib import Path
from windowed_speed_analysis import analyze
from windowed_metal_analysis import analyze_methods
s=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('run-wavefront-baseline.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ORDERS=[['R-normal','BestFit-normal','BestFit-trace','R-trace'],['BestFit-normal','R-trace','R-normal','BestFit-trace'],['R-trace','BestFit-trace','BestFit-normal','R-normal'],['BestFit-trace','R-normal','R-trace','BestFit-normal']]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
 return h.hexdigest()
def save(p,v):b.atomic_json(p,v)
def guard(root):
 if shutil.disk_usage(root).free<1024**3:raise RuntimeError('1 GiB reserve')
 if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('256 MiB evidence budget')
def metrics(event):
 path=Path(event['probe_sample']['trace_path']);raw=json.loads(path.read_text());v=analyze(raw,event['gpu_dispatches'],event['new_buffer_allocations']);v.update(analyze_methods(raw))
 noncommand=[e for e in raw.get('metal_methods',[]) if e['kind']=='queue_create_with_limit' and e['command_token']==0 and e['bytes']==4]
 if not v['methods_available'] or v['unlinked_method_events']!=len(noncommand) or v['unlinked_native_commits']:raise ValueError('incomplete method links')
 v['noncommand_queue_events']=len(noncommand)
 return {**v,'id':event['id'],'phase':event['phase'],'main_thread_cpu_ms':event['probe_sample']['main_thread_cpu_ms'],'trace_write_ms':event['probe_sample']['trace_write_ms'],'api_protocol_ms':1000*(event['completed_at']-event['started_at']),'new_buffers':event['new_buffer_allocations'],'trace_path':str(path),'trace_sha256':sha(path)}
def main():
 c=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
 for n in ('workers','proof','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--preflight',action='store_true');p.add_argument('--preflight-proof',type=Path);a=p.parse_args();root=a.output.resolve();root.mkdir();w=json.loads(a.workers.read_text());proof=json.loads(a.proof.read_text());r=a.reference.resolve()
 if not w['complete'] or w['reference_base']!=proof['reference_base'] or subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True) or subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()!=proof['reference_base']:raise ValueError('frozen reference identity')
 for n,h in w['tools'].items():
  if sha(c/'tools'/n)!=h:raise ValueError('changed build source '+n)
 if sha(a.workers.parent/'long-driver.mm')!=w['generated_driver_sha256']:raise ValueError('generated driver changed')
 for x in w['workers'].values():
  if sha(x['path'])!=x['sha256']:raise ValueError('trace worker changed')
 normal={'R':proof['workers']['R-B1'],'BestFit':json.loads((c/'build/windowed-pool-stage19-performance/worker.json').read_text())}
 for x in normal.values():
  path=Path(x['path'])
  if not path.exists():raise ValueError('restore original normal binary before cohort')
  if sha(path)!=x['sha256']:raise ValueError('normal worker changed')
 normal_proof_path=c/'build/windowed-pool-stage19-performance/normal-proof.json';normal_proof=json.loads(normal_proof_path.read_text())
 if not normal_proof['complete'] or normal_proof['worker']['sha256']!=normal['BestFit']['sha256'] or len(normal_proof['results'])!=6 or any(not x['passed'] or not x['bitwise_equal_R'] for x in normal_proof['results']):raise ValueError('normal BestFit six-case proof required')
 cases=proof['cases'] if a.preflight else [x for x in proof['cases'] if x['id']=='portra400-coffee-3840x2160']
 for case in cases:
  for n in ('pack','input'):
   if sha(case[n])!=case[n+'_sha256']:raise ValueError('fixture changed')
 if not a.preflight:
  if not a.preflight_proof:raise ValueError('preflight required')
  pre=json.loads(a.preflight_proof.read_text())
  if not pre['complete'] or len(pre['runs'])!=12 or pre['workers_sha256']!=sha(a.workers) or pre['normal_workers']!=normal:raise ValueError('12 matching preflight rows required')
 report={'complete':False,'stage':22,'performance_acceptance':False,'reference_base':w['reference_base'],'workers_sha256':sha(a.workers),'normal_workers':normal,'sources':{str(x.resolve()):sha(x) for x in [a.workers,a.proof,normal_proof_path,*([a.preflight_proof] if a.preflight_proof else [])]},'controllers':{n:sha(c/'tools'/n) for n in ('run-windowed-long.py','run-wavefront-baseline.py','wavefront_metrics.py','windowed_metal_analysis.py','windowed_speed_analysis.py')},'protocol':{'preflight':a.preflight,'cases':[x['id'] for x in cases],'orders':ORDERS,'warmup_seconds':5,'window_seconds':30,'tail_seconds':2,'retained_idle_seconds':5,'pool_mib':1024,'queue_capacity':4,'inflight_frames':1,'sample_period_seconds':1,'measurement_sample_offset_seconds':.5,'minimum_free_bytes':1024**3,'evidence_budget_bytes':256*1024**2,'scope':'UHD primary long-window diagnostic; no HD inference; no GPU-frequency/external-GPU measurement','sample_write':'outside API timer, included in throughput window; inactive hooks remain installed on unsampled trace calls'},'runs':[]}
 save(root/'report.json',report)
 env={**os.environ,'FOTUFILM_AOT_WINDOWED':'1','FOTUFILM_METAL_POOL':'1024','FOTUFILM_METAL_METHOD_PROBES':'1','FOTUFILM_TRACE_VARIANT':'0'};env.pop('DYLD_INSERT_LIBRARIES',None)
 try:
  with b.awake_session() as awake:
   for case in cases:
    own=next(x for x in proof['results'] if x['case']==case['id'] and x['arm']=='R-B1')
    for index,order in enumerate([['R-trace','BestFit-trace']] if a.preflight else ORDERS):
     for cell in order:
      b.require_awake(awake);guard(root);arm,mode=cell.split('-');out=root/(case['id']+'-'+str(index)+'-'+cell);trace=out/'traces';trace.mkdir(parents=True);worker=w['workers'][arm] if mode=='trace' else normal[arm]
      if sha(worker['path'])!=worker['sha256']:raise ValueError('worker changed between rounds')
      run={'case':case['id'],'index':index,'cell':cell,'worker':worker,'environment_before':b.environment_observation(root)}
      if a.preflight:
       dump=out/'output.rgba32f'
       with (out/'events.jsonl').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run([worker['path'],case['pack'],case['input'],'--dump',str(dump)],env={**env,'FOTUFILM_LONG_TRACE_DIRECTORY':str(trace)},stdout=log,stderr=err,check=True,timeout=120)
       events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()];calls=[e for e in events if e['type']=='call_complete'];complete=events[-1]
       if len(calls)!=1 or calls[0]['status']!='success' or complete['type']!='verification_complete' or complete['output_sha256']!=own['output_sha256'] or sha(dump)!=own['output_sha256']:raise ValueError('full pixel hash verification')
       event=calls[0]
       if event['actual_variant']!=own['actual'] or event['aot_calls']!=1 or event['gpu_dispatches']!=own['dispatches']:raise ValueError('actual pipeline changed')
       save(out/'analysis.json',metrics(event));dump.unlink();run['output_sha256']=complete['output_sha256'];run['analysis']=str(out/'analysis.json')
      else:
       old=dict(os.environ)
       try:
        os.environ.clear();os.environ.update(env);os.environ['FOTUFILM_LONG_TRACE_DIRECTORY']=str(trace)
        # run_round creates the round directory; retain the precreated trace subdirectory separately.
        result=b.run_round(worker['path'],case['pack'],case['input'],'B1',out/'round')
       finally:os.environ.clear();os.environ.update(old)
       run.update({'round_path':str(out/'round/round.json'),'scores':result['scores'],'memory':result['memory']})
       if not result['scores']['valid']:raise ValueError('invalid round '+str(result['scores']['reasons']))
       for event in result['phase_events']:
        if event['type'] in ('warmup_complete','measurement_complete') and event['output_sha256']!=own['output_sha256']:raise ValueError('phase output hash mismatch')
       if any(e['actual_variant']!=own['actual'] or e['gpu_dispatches']!=own['dispatches'] for e in result['requests']):raise ValueError('actual pipeline changed')
      run['environment_after']=b.environment_observation(root);report['runs'].append(run);save(root/'report.json',report);guard(root);print('PASS',case['id'],index,cell,run.get('scores',{}),flush=True)
  # Analyze only once the entire timed cohort has stopped.
  if not a.preflight:
   for run in report['runs']:
    rr=json.loads(Path(run['round_path']).read_text());samples=[metrics(e) for e in rr['requests'] if e.get('probe_sample',{}).get('sampled')];measured=[x for x in samples if x['phase']=='measurement']
    if run['cell'].endswith('trace') and len(measured)!=30:raise ValueError('expected exactly 30 measurement samples')
    if run['cell'].endswith('normal') and samples:raise ValueError('normal binary emitted detailed samples')
    dest=Path(run['round_path']).parents[1]/'samples.json';save(dest,{'samples':samples});run['samples_path']=str(dest);run['samples_sha256']=sha(dest)
  guard(root);report['complete']=True
 except BaseException as e:report['failure']=str(e);raise
 finally:save(root/'report.json',report)
 print('REPORT',root/'report.json',flush=True)
if __name__=='__main__':main()
