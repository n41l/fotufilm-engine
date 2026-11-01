"""Attribute elapsed Metal methods to commands; preserve nesting and queue backpressure evidence."""
from collections import Counter,defaultdict
import math
from windowed_speed_analysis import duration,overlap,kernel_family
NATIVE_ENCODING={'command_create_native','encoder_create','function_lookup','pipeline_create','pipeline_bind','buffer_bind','bytes_bind','threadgroup_memory','dispatch','end_encoding'}
REQUIRED_COMPUTE={'encoder_create','function_lookup','pipeline_create','pipeline_bind','buffer_bind','threadgroup_memory','dispatch','end_encoding'}
def clip(intervals,a,b):return [(max(x,a),min(y,b)) for x,y in intervals if max(x,a)<min(y,b)]
def analyze_methods(frame,queue_limit=4):
 events=frame.get('metal_methods',[]);links=frame.get('method_commands',[])
 if not frame.get('method_probes',False):
  if events or links:raise ValueError('disabled method probe collected events')
  return {'methods_available':False}
 if not frame['probes']:raise ValueError('method probe requires base probes')
 commands=frame['commands'];by_token={};indices=set()
 for link in links:
  token,index=link['token'],link['gpu_index']
  if not token or token in by_token or index in indices or index<0 or index>=len(commands) or commands[index]['label']!=link['label']:raise ValueError('invalid method command link')
  by_token[token]=link;indices.add(index)
 if indices!=set(range(len(commands))):raise ValueError('method command coverage missing')
 envelopes=[e for e in frame['cpu'] if e['kind']=='encode_envelope']
 if len(envelopes)!=len(commands):raise ValueError('encoding envelope coverage')
 groups=defaultdict(list);times=defaultdict(float);counts=Counter();unknown=0
 for e in events:
  a,b=e['begin'],e['end']
  if not math.isfinite(a+b) or b<a or a<frame['api_begin']-1e-6 or b>frame['api_end']+1e-6:raise ValueError('invalid method interval')
  groups[e['command_token']].append(e);times[e['kind']]+=(b-a)*1000;counts[e['kind']]+=1
  if e['command_token'] not in by_token:unknown+=1
 covered=residual=encoding=previous_gpu_overlap=0;rows=[];pending=Counter();limits=Counter();sizes=Counter()
 for token,link in by_token.items():
  index=link['gpu_index'];command=commands[index];env=envelopes[index];items=groups[token];calls=Counter(e['kind'] for e in items)
  if env['label']!=command['label']:raise ValueError('encoding order mismatch')
  if calls['command_create']!=1 or calls['command_create_native']!=1 or calls['command_commit']!=1:raise ValueError('factory/commit coverage')
  if command['label'].startswith('_kernel_') and any(calls[k]<1 for k in REQUIRED_COMPUTE):raise ValueError('compute method coverage')
  if command['label'].startswith('_kernel_') and (calls['dispatch']!=1 or calls['end_encoding']!=1):raise ValueError('dispatch/end method coverage')
  native=next(e for e in items if e['kind']=='command_create_native')
  if native.get('queue_limit')!=queue_limit:raise ValueError('actual queue limit differs')
  pending[native['callback_pending_before']]+=1;limits[native['queue_limit']]+=1
  for e in items:
   if e['kind']=='buffer_bind':sizes[e['bytes']]+=1
  intervals=[(e['begin'],e['end']) for e in items if e['kind'] in NATIVE_ENCODING]
  a,b=env['begin'],env['end'];covered_ms=duration(clip(intervals,a,b))*1000;envelope_ms=(b-a)*1000;residual_ms=envelope_ms-covered_ms
  if residual_ms< -1e-5:raise ValueError('covered time exceeds encoding envelope')
  previous=[(e['gpu_start'],e['gpu_end']) for e in commands[:index] if e['gpu_start']>0 and e['gpu_end']>=e['gpu_start']]
  older_overlap=overlap([(native['begin'],native['end'])],previous)*1000;previous_gpu_overlap+=older_overlap;covered+=covered_ms;residual+=max(residual_ms,0);encoding+=envelope_ms
  method_ms=defaultdict(float)
  for e in items:method_ms[e['kind']]+=(e['end']-e['begin'])*1000
  rows.append({'token':token,'gpu_index':index,'family':kernel_family(command['label']),'label':command['label'],'methods_ms':dict(method_ms),'method_calls':dict(calls),'encoding_ms':envelope_ms,'native_methods_covered_ms':covered_ms,'encoding_residual_ms':max(residual_ms,0),'factory_previous_gpu_overlap_ms':older_overlap,'callback_pending_before_factory':native['callback_pending_before']})
 return {'methods_available':True,'method_ms':dict(times),'method_calls':dict(counts),'method_union_ms':duration([(e['begin'],e['end']) for e in events])*1000,'encoding_native_covered_ms':covered,'encoding_residual_ms':residual,'encoding_ms':encoding,'native_factory_previous_gpu_overlap_ms':previous_gpu_overlap,'factory_callback_pending_histogram':dict(pending),'observed_queue_limit_histogram':dict(limits),'bound_buffer_length_histogram':dict(sizes),'unlinked_method_events':unknown,'unlinked_native_commits':frame.get('unlinked_native_commits',0),'per_command':rows}
