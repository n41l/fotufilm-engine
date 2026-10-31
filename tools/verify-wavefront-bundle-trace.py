#!/usr/bin/env python3
"""Check bundled two-stage A/F production and preceding-band GPU completion.

Command-buffer phase tags are commit scopes, not exclusive kernel times. Actual
film pixels and host demand guards are separate prerequisites. This checker
does not assert that internal U/horizontal scratch is never recomputed.
"""
import argparse,json,re,hashlib
from pathlib import Path

def analyze(lines,width,height,aot_calls,dispatches,band_rows=512):
    a=[];ap=[];fp=[[],[],[]];fa=[[],[],[]];mtf={};buffers=[];kernels=[];cons=[];done=[];counts=None
    for line in lines:
        p=line.split()
        if not p:continue
        if p[0]=='ROW_PLAN':ap.append(tuple(map(int,p[1:])))
        elif p[0]=='FIELD_PLAN':
            i,b,y,n,h=map(int,p[1:]);fp[i].append((b,y,n,h))
        elif p[0]=='CONSUMER_PLAN':cons.append(tuple(map(int,p[1:])))
        elif p[0]=='BAND_COMPLETE':done.append(int(p[1]))
        elif p[0]=='PRODUCE' and len(p)==8:
            region=tuple(map(int,p[2:]));name=p[1]
            if re.fullmatch(r'frame_wavefront_bundle_light_v\d+',name):a.append(region)
            elif re.fullmatch(r'frame_mtf(?:_mixed|_separated)?_v\d+',name):mtf.setdefault(name,[]).append(region)
            else:
                match=re.fullmatch(r'frame_halation__v\d+([012])_spread',name)
                if match:fa[int(match[1])].append(region)
        elif p[0]=='GPU_COMPLETION':buffers.append({'id':int(p[1]),'band':int(p[2])-1,'phase':int(p[3]),'queue':p[4],'start':float(p[5]),'end':float(p[6]),'status':int(p[7])})
        elif p[0]=='GPU_KERNEL':kernels.append((int(p[1])-1,int(p[2]),p[3]))
        elif p[0]=='BUNDLE_COUNTS':counts={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
    if not counts:return {'passed':False,'failure':'missing bundle accounting'}
    bands=(height+band_rows-1)//band_rows;regions=len(a)==len(ap)>0;head=0
    for (band,y,n,slot,cap),actual in zip(ap,a):
        regions=regions and y==head and n>0 and cap==2048 and slot==y%cap and slot+n<=cap and actual==(0,width,y,n,0,3)
        head=y+n
    regions=regions and head==height
    fields=[]
    for i in range(3):
        valid=len(fp[i])==len(ap);pos=[(b,y,n,h) for b,y,n,h in fp[i] if n>0];actual=[x for x in fa[i] if x[3]>0]
        valid=valid and len(pos)==len(actual);fh=0;fw=None
        for (b,y,n,h),(x,w,ay,an,c,ch) in zip(pos,actual):
            if fw is None:fw=w
            valid=valid and y==fh and n>0 and h==counts['field_rows'+str(i)] and (x,ay,an,c,ch)==(0,y,n,0,3) and w==fw
            fh=y+n
        valid=valid and fh==counts['field_rows'+str(i)] and len(pos)==counts['field_updates'+str(i)]
        fields.append({'scale':i,'passed':bool(valid),'width':fw,'height':fh,'plans':fp[i],'actual':fa[i]})
    mtf_valid=bool(mtf)
    for name,rs in mtf.items():
        mtf_valid=mtf_valid and len(rs)==len(ap) and all((r[0],r[1],r[2],r[3])==(0,width,p[1],p[2]) for p,r in zip(ap,rs))
    accounting=(counts['light_rows']==height and counts['producer_calls']==len(ap) and counts['consumer_calls']==bands
        and aot_calls==len(ap)+bands and cons==[(b,b*band_rows,min(band_rows,height-b*band_rows)) for b in range(bands)] and done==list(range(bands)))
    timing=bool(buffers) and len({b['id'] for b in buffers})==len(buffers) and len({b['queue'] for b in buffers})==1
    timing=timing and all(b['status']==4 and b['end']>=b['start']>0 and b['phase'] in (1,2) for b in buffers)
    checks=[]
    for band in range(bands):
        writers=[b for b in buffers if b['band']==band and b['phase']==1];readers=[b for b in buffers if b['band']==band and b['phase']==2]
        prior=[b for b in buffers if b['band']<band and b['phase']==2]
        has=any(p[0]==band for p in ap);first=min((b['start'] for b in writers),default=None);last=max((b['end'] for b in prior),default=None)
        valid=bool(readers) and bool(writers)==has and (not has or band==0 or (last is not None and first is not None and last<=first))
        checks.append({'band':band,'previous_output_gpu_end':last,'producer_gpu_start':first,'passed':valid})
    bindings=len(kernels)==dispatches
    return {'passed':bool(regions and all(f['passed'] for f in fields) and mtf_valid and accounting and timing and bindings and all(x['passed'] for x in checks)),
        'light_regions_passed':bool(regions),'final_mtf_regions_match_new_light_only':bool(mtf_valid),'mtf_regions':mtf,'light_plans':ap,
        'fields':fields,'counts':counts,'accounting_passed':accounting,'actual_kernel_bindings':len(kernels),'bindings_match_dispatches':bindings,
        'gpu_scopes_valid':bool(timing),'previous_band_completion_checks':checks,'scope':__doc__}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verification',required=True,type=Path);p.add_argument('--band',type=int,choices=(512,1080),default=512);a=p.parse_args();root=a.verification
    proof=json.loads((root/'report.json').read_text());results=[]
    for row in proof['results']:
        if row['worker']!='bundletrace':continue
        w,h=map(int,row['case'].split('-')[-1].split('x'));path=root/row['case']/'bundletrace.stderr'
        results.append({'case':row['case'],'trace_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**analyze(path.read_text().splitlines(),w,h,row['aot_calls'],row['dispatches'],a.band)})
    report={'complete':len(results)==4,'passed':len(results)==4 and all(x['passed'] for x in results),'results':results}
    (root/'bundle-trace.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([{k:x[k] for k in ('case','passed','light_regions_passed','final_mtf_regions_match_new_light_only','accounting_passed','bindings_match_dispatches','gpu_scopes_valid')} for x in results]))
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
