"""Attribute successful allocations and observed pool eviction; no latency attribution."""
from collections import Counter

def analyze(trace,attempts):
 if trace['errors']:raise ValueError('resource observer errors')
 physical={p['id']:p for p in trace['physical']}
 if any(physical[l['physical']]['length']<l['requested'] for l in trace['leases']):raise ValueError('undersized lease')
 if any(not f['delivered'] or f['status']!=4 or f['complete']<=f['commit'] for f in trace['fences']):raise ValueError('incomplete GPU completion proof')
 rows=[]
 for m in trace['markers']:
  if m['name']!='frame_begin':continue
  end=next(x['event'] for x in trace['markers'] if x['name']=='frame_end' and x['frame']==m['frame']);fresh=[];evictions=[];count=0
  for a in attempts['attempts']:
   if not m['event']<a['begin']<a['end']<end:continue
   count+=1;after={x['physical'] for x in a['after']}
   drops=[x for x in a['before'] if x['physical'] not in after and x['state']==2 and a['begin']<physical[x['physical']]['freed']<a['end']]
   if drops:evictions.append({'request':a['requested'],'idle_before':sum(x['length'] for x in a['before'] if x['state']==1),'returned_before':sum(x['length'] for x in a['before'] if x['state']==2),'capacity':a['capacity'],'evicted':[{'physical':x['physical'],'length':x['length'],'pre_fence_status':x['fence_status']} for x in drops]})
   if a['fresh']:
    before=a['before'];fresh.append({'physical':a['physical'],'requested':a['requested'],'rounded':a['rounded'],'pooled':a['capacity']>0 and a['frame_depth']>0,'idle_before':sum(x['length'] for x in before if x['state']==1),'idle_exact':sum(x['state']==1 and x['length']==a['rounded'] for x in before),'idle_larger_eligible':sum(x['state']==1 and a['rounded']<=x['length']<=a['rounded']*1.5 for x in before),'returned_exact_pending':sum(x['state']==2 and x['length']==a['rounded'] and x['fence_status']<4 for x in before),'returned_exact_ready':sum(x['state']==2 and x['length']==a['rounded'] and x['fence_status']>=4 for x in before)})
  rows.append({'frame':m['frame'],'allocation_attempts':count,'fresh_count':len(fresh),'fresh_rounded_histogram':dict(Counter(x['rounded'] for x in fresh)),'fresh':fresh,'reclaim_evictions':evictions})
 return {'frames':rows,'scope':'Snapshots may perturb scheduling and fence status may progress. Removal during original allocator reclamation is distinguished from ordinary logical release. No field-name or time attribution.'}
