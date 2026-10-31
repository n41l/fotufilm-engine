"""Analyze diagnostic allocator events. No latency scores or spatial-locality claim."""
from collections import defaultdict


def category(lease):
    r=lease['roles']
    if r&32:return 'frontier_and_configuration'
    if r&3==3:return 'external_io_alias'
    if r&1:return 'input'
    if r&2:return 'output'
    if r&8:return 'LUT'
    if r&4:return 'configuration'
    if r&16:return 'film_tiles'
    return 'AOT_intermediate' if lease['aot'] else 'unclassified_halide'


def peak(intervals,lo,hi):
    changes=defaultdict(int)
    for begin,end,size in intervals:
        begin=max(begin,lo);end=min(end,hi)
        if begin<end:changes[begin]+=size;changes[end]-=size
    live=maximum=0
    for event in sorted(changes):
        live+=changes[event];maximum=max(maximum,live)
        if live<0:raise ValueError('negative live allocation count')
    return maximum


def analyze(trace):
    if trace['errors']:raise ValueError('observer ledger errors: '+str(trace['errors'][:4]))
    physical={p['id']:p for p in trace['physical']};fences={f['id']:f for f in trace['fences']}
    if any(not f['delivered'] or f['status']!=4 or f['complete']<=f['commit'] for f in fences.values()):
        raise ValueError('GPU completion coverage incomplete')
    tail=max([m['event'] for m in trace['markers']]+[p['born'] for p in physical.values()])+1
    intervals=[];by_physical=defaultdict(list)
    for l in trace['leases']:
        p=physical[l['physical']];end=l['logical_end'] or tail
        if not p['born']<=l['born']<end or l['references']<0:raise ValueError('invalid lease lifetime')
        if p['freed'] and (p['freed']<end or not l['logical_end']):raise ValueError('physical buffer freed while logically live')
        gpu_end=end
        if l['logical_end'] and l['fence']:
            complete=fences[l['fence']]['complete']
            if l['reuse_proof']:complete=min(complete,l['reuse_proof'])
            gpu_end=max(end,complete)
        intervals.append({'id':l['id'],'physical':p['id'],'category':category(l),'begin':l['born'],
            'logical_end':end,'gpu_safe_end':gpu_end,'requested':l['requested'],'allocated':p['allocated']})
        by_physical[p['id']].append((l['born'],end))
    for runs in by_physical.values():
        runs.sort()
        if any(b[0]<a[1] for a,b in zip(runs,runs[1:])):raise ValueError('one physical buffer has overlapping logical leases')
    categories=sorted({i['category'] for i in intervals});frames=[]
    begins={m['frame']:m['event'] for m in trace['markers'] if m['name']=='frame_begin'}
    for m in trace['markers']:
        if m['name']!='frame_end':continue
        lo=begins[m['frame']];hi=m['event']+1;row={'frame':m['frame']}
        for endkey,label in (('logical_end','logical'),('gpu_safe_end','gpu_safe_upper_bound')):
            row[label]={cat:{size:peak([(i['begin'],i[endkey],i[size]) for i in intervals if i['category']==cat],lo,hi)
                for size in ('requested','allocated')} for cat in categories}
            row[label]['working_combined']={size:peak([(i['begin'],i[endkey],i[size]) for i in intervals
                if i['category'] in ('AOT_intermediate','frontier_and_configuration')],lo,hi) for size in ('requested','allocated')}
        row['tracked_physical_object_peak']=peak([(p['born'],p['freed'] or tail,p['allocated']) for p in physical.values()],lo,hi)
        active=[i for i in intervals if i['category'] in ('AOT_intermediate','frontier_and_configuration') and i['begin']<=m['event']<i['gpu_safe_end']]
        if active:raise ValueError('frame intermediates still active after API/drain')
        frames.append(row)
    snapshots=[]
    for m in trace['markers']:
        if 'pool' not in m:raise ValueError('exact pool snapshots missing')
        seen=set();parts=defaultdict(int);lengths=defaultdict(int)
        for entry in m['pool']:
            pid=entry['physical']
            if pid in seen:raise ValueError('pool aliases double counted')
            seen.add(pid);p=physical[pid]
            if not p['born']<=m['event'] or p['freed'] and p['freed']<m['event']:raise ValueError('pool owns a freed buffer')
            if entry['state']==0:
                if entry['references']<=0:raise ValueError('invalid active pool references')
                state='in_use'
            elif entry['state']==1:state='idle'
            elif entry['state']==2:state='returned_GPU_complete' if entry['fence_status']>=4 else 'returned_in_flight'
            else:raise ValueError('invalid pool state')
            parts[state]+=p['allocated'];lengths[state]+=entry['length']
        if lengths['idle']>1024*1024*1024:raise ValueError('original idle pool cap exceeded')
        snapshots.append({'event':m['event'],'name':m['name'],'frame':m['frame'],
            'pool_allocated_bytes':dict(parts),'pool_length_bytes':dict(lengths),
            'tracked_live_physical_bytes':sum(p['allocated'] for p in physical.values() if p['born']<=m['event'] and (not p['freed'] or p['freed']>m['event']))})
    return {'frames':frames,'snapshots':snapshots,'physical_buffers':len(physical),'leases':len(intervals),
        'fully_classified_halide_leases':all(i['category']!='unclassified_halide' for i in intervals),
        'frame_intermediates_released':True,'pool_idle_within_original_cap':True,
        'scope':'AOT_intermediate includes per-call downsampled/spatial intermediates; it is not a named-edge spatial-local decomposition.',
        'limitations':['GPU-safe intervals end at CPU observations of completed fences and are conservative bounds.',
            'Detailed observer CPU footprint and GPU allocation peaks are not substituted for light-worker totals.',
            'Category peak values can occur at different events; they must not be added as a simultaneous total.']}
