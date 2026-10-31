#!/usr/bin/env python3
"""Plot the complete seven-arm general optimization pilot, with original controls."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare_general_helper import ARMS
ORDER=('R-B0','G0','registers','normalized','counted','radius1','R-B1')
LABELS=('R general','C0','Registers','Norm','Count','Radius=1','R window')
COLORS=('#8f99a7','#424c59','#db8d42','#468a63','#448cbe','#9572ad','#29a38d')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=json.loads(a.report.read_text())
if not d['complete'] or len(d['cases'])!=4 or any(set(x['arms'])!=set(ORDER) or not all(y['scores']['valid'] for y in x['arms'].values()) for x in d['cases']):raise ValueError('complete28-round report required')
a.output.mkdir(parents=True,exist_ok=True)
for memory in (False,True):
 fig,axes=plt.subplots(2,2,figsize=(14,9));fig.suptitle('Whole-frame general: isolated kernel optimizations' + (' — device peak' if memory else ' — warm median'),fontsize=17,y=.98)
 for ax,row,title in zip(axes.flat,d['cases'],('Portra 1080p','Portra 4K + luma','HP5 1080p','HP5 4K')):
  vals=[row['arms'][k]['memory']['device_total_peak_bytes']/2**20 if memory else row['arms'][k]['scores']['median_seconds']*1000 for k in ORDER]
  bars=ax.bar(range(7),vals,color=COLORS,width=.73);ax.bar_label(bars,labels=[f'{v:.0f}' if memory else f'{v:.2f}' for v in vals],padding=3,fontsize=10)
  ax.set_xticks(range(7),LABELS,rotation=18);ax.set_title(title);ax.set_ylabel('MiB' if memory else 'Milliseconds');ax.set_ylim(0,max(vals)*1.21);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
 fig.text(.5,.025,'One round per arm/case; full-frame single AOT call; same-source C0 and four individual switches.\nFresh original general/windowed controls. Thermal/background drift remains; no frozen B_ref or release acceptance.',ha='center',fontsize=10)
 fig.subplots_adjust(top=.90,bottom=.13,hspace=.43,wspace=.20)
 name='memory' if memory else 'latency'
 for ext in ('png','svg'):fig.savefig(a.output/(name+'.'+ext),dpi=180,facecolor='white')
 print(a.output/(name+'.png'))
