#!/usr/bin/env python3
"""Check two ring histories and actual GPU scopes. Never a timing score.

GPU phase tags describe commit scopes, not per-kernel dependency fences. This
checks the conservative preceding-band completion rule; it does not infer
within-band GPU costs from CPU submissions or realization events.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def analyze(lines,width,height,aot_calls,dispatches):
    plans={'ROW_PLAN':[],'LOG_PLAN':[]};actual={'ROW_PLAN':[],'LOG_PLAN':[]}
    order=[];consumers=[];done=[];gpu=[];kernels=[];counts=None
    for line in lines:
        p=line.split()
        if p and p[0] in plans:
            event=tuple(map(int,p[1:]));plans[p[0]].append(event);order.append((p[0],event))
        elif p and p[0]=='CONSUMER_PLAN':
            event=tuple(map(int,p[1:]));consumers.append(event);order.append(('CONSUMER_PLAN',event))
        elif p and p[0]=='BAND_COMPLETE':done.append(int(p[1]));order.append(('BAND_COMPLETE',(int(p[1]),)))
        elif len(p)==8 and p[0]=='PRODUCE':
            key='ROW_PLAN' if p[1].startswith('frame_wavefront_light_output') else 'LOG_PLAN' if p[1].startswith('frame_wavefront_log_output') else None
            if key:actual[key].append(tuple(map(int,p[2:])))
        elif len(p)==8 and p[0]=='GPU_COMPLETION':
            gpu.append({'id':int(p[1]),'band':int(p[2])-1,'phase':int(p[3]),'queue':p[4],
                'start':float(p[5]),'end':float(p[6]),'status':int(p[7])})
        elif len(p)==4 and p[0]=='GPU_KERNEL':kernels.append((int(p[1])-1,int(p[2]),p[3]))
        elif line.startswith('THREE_STAGE_COUNTS '):counts={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
    if not counts:return {'passed':False,'failure':'missing stage accounting'}
    bands=(height+511)//512;region_checks={}
    for key,capacity in (('ROW_PLAN',2048),('LOG_PLAN',1024)):
        head=0;valid=bool(plans[key]) and len(plans[key])==len(actual[key])
        for (band,y,n,slot,cap),(x,w,ay,an,c,channels) in zip(plans[key],actual[key]):
            valid=valid and y==head and n>0 and cap==capacity and slot==y%cap and slot+n<=cap
            valid=valid and (x,w,ay,an,c,channels)==(0,width,y,n,0,3)
            head=y+n
        region_checks[key]={'passed':bool(valid and head==height),'produced_rows':head,'calls':len(plans[key]),'plans':plans[key]}
    expected=[(i,i*512,min(512,height-i*512)) for i in range(bands)]
    accounting=(consumers==expected and done==list(range(bands)) and aot_calls==len(plans['ROW_PLAN'])+len(plans['LOG_PLAN'])+bands
        and counts['light_rows']==counts['log_rows']==height and counts['light_calls']==len(plans['ROW_PLAN'])
        and counts['log_calls']==len(plans['LOG_PLAN']) and counts['output_calls']==bands and counts['log_ring_rows']==1024)
    labels={'ROW_PLAN':[-1]*2048,'LOG_PLAN':[-1]*1024};completed=-1;logical=True
    for key,event in order:
        if key=='BAND_COMPLETE':completed=event[0];continue
        if key in plans:
            band,y,n,slot,capacity=event
            support=counts['log_reach']+(counts['halo_reach'] if key=='ROW_PLAN' else 0)
            for r in range(y,y+n):
                old=labels[key][r%capacity]
                logical=logical and (old<0 or min(bands-1,(old+support)//512)<=completed)
                labels[key][r%capacity]=r
            if key=='LOG_PLAN':
                logical=logical and all(labels['ROW_PLAN'][r%2048]==r for r in range(max(0,y-counts['halo_reach']),min(height,y+n+counts['halo_reach'])))
        else:
            band,y,n=event
            logical=logical and all(labels['LOG_PLAN'][r%1024]==r for r in range(max(0,y-counts['log_reach']),min(height,y+n+counts['log_reach'])))
    timing=bool(gpu) and len({g['id'] for g in gpu})==len(gpu) and len({g['queue'] for g in gpu})==1
    timing=timing and all(g['status']==4 and g['end']>=g['start']>0 and g['phase'] in (1,2,3) for g in gpu)
    checks=[]
    for band in range(bands):
        writes=[g for g in gpu if g['band']==band and g['phase'] in (1,3)]
        prior=[g for g in gpu if g['band']<band and g['phase']==2]
        readers=[g for g in gpu if g['band']==band and g['phase']==2]
        last=max((g['end'] for g in prior),default=None);first=min((g['start'] for g in writes),default=None)
        valid=bool(readers and writes) and (band==0 or (last is not None and first is not None and last<=first))
        checks.append({'band':band,'previous_output_gpu_end':last,'next_write_gpu_start':first,'passed':valid})
    binding=len(kernels)==dispatches and all(any(k[0]==i and k[1]==phase for k in kernels) for i in range(bands) for phase in (2,3))
    return {'passed':bool(all(r['passed'] for r in region_checks.values()) and accounting and logical and timing and binding and all(r['passed'] for r in checks)),
        'regions':region_checks,'accounting_passed':accounting,'logical_readiness_and_overwrite_passed':logical,
        'gpu_completion_scopes_valid':bool(timing),'previous_band_completion_checks':checks,'actual_kernel_bindings':len(kernels),
        'binding_count_matches_dispatches':binding,'counts':counts,'gpu_buffers':gpu,
        'scope':__doc__}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verification',type=Path,required=True);a=p.parse_args()
    root=a.verification.resolve();source=root/'report.json';proof=json.loads(source.read_text());results=[]
    for row in proof['results']:
        if row['worker']!='3trace':continue
        path=root/row['case']/'3trace.stderr';width,height=map(int,row['case'].split('-')[-1].split('x'))
        report=analyze(path.read_text().splitlines(),width,height,row['aot_calls'],row['dispatches'])
        results.append({'case':row['case'],'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**report})
    output=root/'three-stage-trace.json';output.write_text(json.dumps({'complete':len(results)==4,'passed':len(results)==4 and all(r['passed'] for r in results),
        'source_proof_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results},indent=2)+'\n')
    print(json.dumps({'report':str(output),'cases':[{k:r[k] for k in ('case','passed','accounting_passed','logical_readiness_and_overwrite_passed','gpu_completion_scopes_valid','binding_count_matches_dispatches')} for r in results]}))
    if len(results)!=4 or not all(r['passed'] for r in results):raise SystemExit(1)


if __name__=='__main__':main()
