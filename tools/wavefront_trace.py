"""Validate diagnostic frontier regions and actual GPU completion ordering."""
import re


def analyze(lines):
    regions=[];events=[];buffers=[];generation=0;begins={};ancestry=True
    for line in lines:
        fields=line.split()
        if len(fields)==7 and fields[0]=='FRONTIER_EVENT':
            kind=int(fields[1]);identity=int(fields[3]);parent=int(fields[4]);generation=int(fields[6])
            events.append({'kind':kind,'function':fields[2],'id':identity,'parent':parent,'generation':generation})
            if kind in (2,4,6):
                ancestry=ancestry and identity not in begins;begins[identity]=kind
            elif kind in (3,5,7):ancestry=ancestry and begins.get(parent)=={3:2,5:4,7:6}[kind]
        elif len(fields)==8 and fields[0]=='PRODUCE' and re.fullmatch(r'frame_(through_gate|light_gate)_v[0-9]+',fields[1]):
            x,columns,y,rows,c,channels=map(int,fields[2:])
            regions.append({'producer':fields[1],'generation':generation,'x':x,'columns':columns,
                            'start':y,'end':y+rows,'channels':channels})
        elif len(fields)==8 and fields[0]=='GPU_COMPLETION':
            buffers.append({'id':int(fields[1]),'generation':int(fields[2]),'phase':int(fields[3]),
                            'queue':fields[4],'start':float(fields[5]),'end':float(fields[6]),'status':int(fields[7])})
    positive=[r for r in regions if r['end']>r['start']]
    no_overlap=all(a['end']<=b['start'] for a,b in zip(positive,positive[1:]))
    timing_valid=bool(buffers) and len({b['id'] for b in buffers})==len(buffers) and all(
        b['end']>=b['start']>0 and b['status']==4 and b['phase'] in (1,2) for b in buffers)
    one_queue=bool(buffers) and len({b['queue'] for b in buffers})==1
    order=[]
    for region in positive:
        g=region['generation'];writes=[b for b in buffers if b['generation']==g and b['phase']==1]
        prior=[b for b in buffers if b['generation']<g and b['phase']==2]
        current=[b for b in buffers if b['generation']==g and b['phase']==2]
        passed=bool(writes and current) and (g==positive[0]['generation'] or bool(prior))
        last=max((b['end'] for b in prior),default=None)
        first=min((b['start'] for b in writes),default=None)
        if last is not None and first is not None:passed=passed and last<=first
        order.append({'generation':g,'previous_consumers_completed_at':last,
                      'next_producer_started_at':first,'passed':passed})
    passed=bool(len(positive)>1 and len({r['producer'] for r in positive})==1 and ancestry
                and events and no_overlap and timing_valid and one_queue and all(o['passed'] for o in order))
    return {'passed':passed,'intervals':regions,'producer_rows':sum(r['end']-r['start'] for r in positive),
            'positive_regions_do_not_overlap':no_overlap,'trace_ancestry_valid':ancestry,
            'gpu_timestamps_valid':timing_valid,'single_command_queue':one_queue,
            'conservative_consumer_completion_checks':order,'gpu_buffers':buffers,'frontier_events':events,
            'scope':'diagnostic traced kernels only; requires all earlier consumer-scope GPU buffers complete before each next producer; no performance claim'}


def analyze_explicit(lines, width, height, band_rows, aot_calls, *, expected_ring_rows=1024):
    plans=[];actual=[];consumers=[];done=[];buffers=[];counts=None
    for line in lines:
        p=line.split()
        if len(p)==6 and p[0]=='ROW_PLAN':plans.append(tuple(map(int,p[1:])))
        elif len(p)==4 and p[0]=='CONSUMER_PLAN':consumers.append(tuple(map(int,p[1:])))
        elif len(p)==2 and p[0]=='BAND_COMPLETE':done.append(int(p[1]))
        elif len(p)==8 and p[0]=='PRODUCE' and p[1].startswith('frame_wavefront_light_output'):
            x,w,y,n,c,channels=map(int,p[2:]);actual.append((y,n,x,w,c,channels))
        elif len(p)==8 and p[0]=='GPU_COMPLETION':
            buffers.append({'id':int(p[1]),'band':int(p[2])-1,'phase':int(p[3]),'queue':p[4],
                            'start':float(p[5]),'end':float(p[6]),'status':int(p[7])})
        elif line.startswith('WAVEFRONT_COUNTS '):counts={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
    bands=(height+band_rows-1)//band_rows
    expected=[(b,b*band_rows,min(band_rows,height-b*band_rows)) for b in range(bands)]
    regions=bool(plans) and len(actual)==len(plans)
    head=0
    for (band,y,n,slot,capacity),observed in zip(plans,actual):
        regions=regions and y==head and n>0 and capacity==expected_ring_rows and slot==y%capacity and slot+n<=capacity
        regions=regions and observed[:2]==(y,n) and observed[2:5]==(0,width,0) and observed[5] in (3,4)
        head=y+n
    regions=regions and head==height
    complete=consumers==expected and done==list(range(bands))
    complete=complete and counts=={'rows':height,'source_calls':len(plans),'consumer_calls':bands,'ring_rows':expected_ring_rows}
    complete=complete and aot_calls==len(plans)+bands
    timing=bool(buffers) and len({b['id'] for b in buffers})==len(buffers) and len({b['queue'] for b in buffers})==1
    timing=timing and all(b['status']==4 and b['end']>=b['start']>0 for b in buffers)
    checks=[]
    for band in range(bands):
        producers=[b for b in buffers if b['band']==band and b['phase']==1]
        readers=[b for b in buffers if b['band']==band and b['phase']==2]
        prior=[b for b in buffers if b['band']<band and b['phase']==2]
        has_production=any(p[0]==band for p in plans)
        passed=bool(readers) and (bool(producers)==has_production)
        last=max((b['end'] for b in prior),default=None);first=min((b['start'] for b in producers),default=None)
        if has_production and band:passed=passed and last is not None and last<=first
        checks.append({'band':band,'previous_consumers_gpu_end':last,'producer_gpu_start':first,'passed':passed})
    return {'passed':bool(regions and complete and timing and all(c['passed'] for c in checks)),
            'producer_intervals_match_actual_gpu_function':bool(regions),'producer_rows':head,
            'source_calls':len(plans),'consumer_bands':bands,'plan_and_counts_complete':bool(complete),
            'gpu_timestamps_valid':bool(timing),'completion_checks':checks,'plans':plans,'actual_source_regions':actual,
            'gpu_buffers':buffers,'scope':'call-scoped labels, explicit incremental producer, per-band device sync; traced diagnostic only'}
