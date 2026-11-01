"""Validate probe coverage and compute overlapping CPU/GPU intervals without double counting."""
from collections import Counter,defaultdict
import math,re,statistics

def merge(intervals):
 out=[]
 for a,b in sorted(intervals):
  if not math.isfinite(a+b) or b<a:raise ValueError('invalid interval')
  if a==b:continue
  if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(out[-1][1],b))
  else:out.append((a,b))
 return out

def duration(intervals):return sum(b-a for a,b in merge(intervals))
def overlap(a,b):return duration([(max(x,u),min(y,v)) for x,y in merge(a) for u,v in merge(b) if max(x,u)<min(y,v)])
def kernel_family(label):
 m=re.match(r'_kernel_(.*?)_s\d+_',label)
 return m.group(1) if m else label

def analyze(frame,expected_dispatches,expected_new_buffers):
 begin,end=frame['api_begin'],frame['api_end']
 if not math.isfinite(begin+end) or end<=begin:raise ValueError('invalid API duration')
 result={'api_ms':(end-begin)*1000,'probe_flush_ms':frame['flush_seconds']*1000,'gpu_available':frame['probes']}
 if not frame['probes']:
  if frame['cpu'] or frame['commands']:raise ValueError('disabled probe collected events')
  return result
 cpu=defaultdict(float);counts=Counter();waits=[]
 for e in frame['cpu']:
  a,b=e['begin'],e['end']
  if not math.isfinite(a+b) or a<begin-1e-6 or b>end+1e-6 or b<a:raise ValueError('CPU interval outside API')
  cpu[e['kind']]+=(b-a)*1000;counts[e['kind']]+=1
  if e['kind']=='wait_until_completed':waits.append((a,b))
 if counts['metal_new_buffer']!=expected_new_buffers:raise ValueError('allocation probe coverage')
 gpu=[];kernels=[];lags=[];families=defaultdict(lambda:{'calls':0,'gpu_ms':0})
 for e in frame['commands']:
  if not e['done'] or e['status']!=4:raise ValueError('GPU completion missing')
  a,b=e['gpu_start'],e['gpu_end'];commit=e['submit_begin']
  if not all(math.isfinite(x) for x in (a,b,commit,e['submit_end'])) or e['submit_end']<commit:raise ValueError('invalid GPU timestamp')
  is_kernel=e['label'].startswith('_kernel_')
  if is_kernel and (a<=0 or b<=a):raise ValueError('kernel timestamp missing')
  if a>0 and b>=a:
   if a<commit-1e-4 or b>end+1e-4:raise ValueError('Metal/host clock or frame coverage mismatch')
   gpu.append((a,b));lags.append((a-commit)*1000)
  elif a!=0 or b!=0:raise ValueError('partial GPU timestamp')
  if is_kernel:
   kernels.append((a,b));family=families[kernel_family(e['label'])];family['calls']+=1;family['gpu_ms']+=(b-a)*1000
 if len(kernels)!=expected_dispatches:raise ValueError('kernel/dispatch coverage mismatch')
 if counts['wait_until_completed']<1:raise ValueError('wait probe coverage missing')
 if counts['encode_envelope']!=len(frame['commands']):raise ValueError('encoding probe coverage missing')
 result.update({'cpu_ms':dict(cpu),'cpu_calls':dict(counts),'gpu_kernel_interval_sum_ms':sum(b-a for a,b in kernels)*1000,'gpu_compute_union_ms':duration(kernels)*1000,'gpu_all_commands_union_ms':duration(gpu)*1000,'gpu_span_ms':(max(b for a,b in gpu)-min(a for a,b in gpu))*1000 if gpu else 0,'wait_gpu_overlap_ms':overlap(waits,gpu)*1000,'submit_to_gpu_start_median_ms':statistics.median(lags),'command_count':len(frame['commands']),'kernel_count':len(kernels),'families':dict(families)})
 return result
