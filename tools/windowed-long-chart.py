#!/usr/bin/env python3
"""Plot independent long-window controls and overlapping sampled timings."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
p=argparse.ArgumentParser();p.add_argument('summary',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=json.loads(a.summary.read_text());g=d['groups'];rows=d['processes']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.17,'axes.axisbelow':True})
fig=plt.figure(figsize=(13,8),facecolor='#fbfcfe');gs=fig.add_gridspec(2,2,hspace=.49,wspace=.35);ax=fig.add_subplot(gs[0,:]);colors={'R':'#2563a6','BestFit':'#16876a'}
for arm in ('R','BestFit'):
 for mode in ('normal','trace'):
  rr=sorted([x for x in rows if x['cell']==arm+'-'+mode],key=lambda x:x['index']);ys=[x['api_ms'] for x in rr];xs=[x['index']+1+(-.045 if arm=='R' else .045) for x in rr]
  ax.plot(xs,ys,marker='o' if mode=='normal' else 's',linestyle='-' if mode=='normal' else '--',color=colors[arm],alpha=1 if mode=='normal' else .6,label=arm+' / '+('original driver' if mode=='normal' else '1 Hz trace'))
ax.set(xlabel='Williams-order repeat (fresh process per cell)',ylabel='API latency (ms)',xticks=[1,2,3,4]);ax.set_title('A   Process medians: original controls and sampled counterparts',loc='left',fontweight='bold');ax.legend(ncol=2,frameon=False,loc='best');ax.set_ylim(bottom=0)
bx=fig.add_subplot(gs[1,0]);labels=['Native commandBuffer','GPU interval union','Explicit frame-end wait','Main-thread CPU'];keys=['native_factory_ms','gpu_union_ms','explicit_wait_ms','main_thread_cpu_ms'];y=np.arange(len(keys));height=.34
for j,arm in enumerate(('R','BestFit')):
 vals=[g[arm+'-trace'][k] for k in keys];bars=bx.barh(y+(j-.5)*height,vals,height,color=colors[arm],label=arm)
 for bar,v in zip(bars,vals):bx.text(bar.get_width()+.3,bar.get_y()+bar.get_height()/2,f'{v:.2f}',va='center',fontsize=9)
bx.set_yticks(y,labels);bx.invert_yaxis();bx.set_xlabel('ms / sampled frame; overlapping quantities');bx.set_title('B   Sample attribution (not additive)',loc='left',fontweight='bold');bx.set_xlim(0,max(g[x+'-trace'][k] for x in ('R','BestFit') for k in keys)*1.22)
cx=fig.add_subplot(gs[1,1]);labels=['Original','BestFit'];vals=[g[x+'-normal']['device_peak_mib'] for x in ('R','BestFit')];bars=cx.bar(labels,vals,color=[colors[x] for x in ('R','BestFit')],width=.5)
for bar,v in zip(bars,vals):cx.text(bar.get_x()+bar.get_width()/2,v+18,f'{v:.2f}',ha='center',fontweight='bold')
cx.set(ylabel='Peak Metal allocated memory (MiB)',ylim=(0,max(vals)*1.2));cx.set_title('C   Original-driver device peak',loc='left',fontweight='bold')
fig.suptitle('Fotufilm 4K: long-window BestFit repeat',fontsize=19,fontweight='bold',x=.04,ha='left',y=.98)
fig.text(.04,.924,'5 s warmup + 30 s measurement | 4 repeats × 4 cells | pool 1 GiB | queue capacity 4',fontsize=11,color='#475569')
fig.text(.04,.025,'Aggregation: median of process medians; detailed timings use 30 samples/process. Trace I/O is outside API latency.\nCPU wall, GPU intervals and wait overlap. One UHD fixture on this Mac; diagnostic, not release acceptance.',fontsize=9,color='#475569')
fig.subplots_adjust(left=.18,right=.97,top=.85,bottom=.16);a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=170,facecolor=fig.get_facecolor());print(a.output)
