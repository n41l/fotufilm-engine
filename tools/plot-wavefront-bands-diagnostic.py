#!/usr/bin/env python3
"""Plot the complete12-round original1080/bundle512/bundle1080 diagnostic."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
d=json.loads(a.report.read_text())
if not d['complete'] or len(d['cases'])!=4 or any(set(x['arms'])!={'R-B1','E512','E1080'} or not all(v['scores']['valid'] for v in x['arms'].values()) for x in d['cases']):raise ValueError('complete valid three-arm report required')
a.output.mkdir(parents=True,exist_ok=True)
fig,axes=plt.subplots(1,2,figsize=(14,6));xs=np.arange(4);colors=['#29845c','#86a9cc','#226dc2'];labels=['Original: windowed 1080','Wavefront: band 512','Wavefront: band 1080']
for i,key in enumerate(('R-B1','E512','E1080')):
 for ax,metric in zip(axes,('latency','memory')):
  vals=[row['arms'][key]['scores']['median_seconds']*1000 if metric=='latency' else row['arms'][key]['memory']['device_total_peak_bytes']/2**20 for row in d['cases']]
  bars=ax.bar(xs+(i-1)*.25,vals,.25,color=colors[i],label=labels[i]);ax.bar_label(bars,labels=[f'{v:.2f}' if metric=='latency' else f'{v:.0f}' for v in vals],padding=3,fontsize=9,rotation=90 if metric=='latency' else 0)
for ax,title,ylabel in zip(axes,('End-to-end warm median (lower is better)','Total device peak including cold start'),('Milliseconds','MiB')):
 ax.set_xticks(xs,['Portra 1080p','Portra 4K + luma','HP5 1080p','HP5 4K'],rotation=13);ax.set_title(title);ax.set_ylabel(ylabel);ax.set_ylim(0,ax.get_ylim()[1]*1.20);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
fig.suptitle('Does a 1080-row band help the two-stage wavefront?',fontsize=17,y=.98)
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',ncol=3,bbox_to_anchor=(.5,.91),frameon=False)
fig.text(.5,.035,'One round per arm/case; same current-source wavefront worker, A2048 / lead360 / per-band sync.\nFresh original B1 controls; thermal/background drift remains. No frozen B_ref or performance acceptance.',ha='center',fontsize=10)
fig.subplots_adjust(top=.77,bottom=.22,wspace=.25)
for suffix in ('png','svg'):fig.savefig(a.output/('comparison.'+suffix),dpi=180,facecolor='white')
print(a.output/'comparison.png')
