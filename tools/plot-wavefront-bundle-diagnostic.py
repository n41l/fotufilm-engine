#!/usr/bin/env python3
"""Plot a complete bundled two-stage pilot; requires matplotlib."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
r=json.loads(a.report.read_text())
if not r['complete'] or len(r['cases'])!=4 or any(not x['scores']['valid'] for c in r['cases'] for x in c['arms'].values()):raise ValueError('complete valid pilot required')
a.output.mkdir(parents=True,exist_ok=True);fig,axes=plt.subplots(1,2,figsize=(13,5.6))
for j,(arm,label,color) in enumerate((('2','Original E2: MTF cut','#718096'),('bundle','New E2: light + fields','#3182ce'))):
 for ax,key,scale in ((axes[0],'median_seconds',1000),(axes[1],'device_total_peak_bytes',1/1024**2)):
  values=[c['arms'][arm]['scores' if key=='median_seconds' else 'memory'][key]*scale for c in r['cases']]
  bars=ax.bar([i+(j-.5)*.32 for i in range(4)],values,.29,label=label,color=color)
  ax.bar_label(bars,labels=[f'{v:.2f}' if scale==1000 else f'{v:.0f}' for v in values],fontsize=8,padding=3,rotation=90 if scale==1000 else 0)
for ax in axes:
 ax.set_xticks(range(4),['Portra 1080p','Portra 4K + luma','HP5 1080p','HP5 4K'],rotation=16,ha='right');ax.set_ylim(bottom=0)
 ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
axes[0].set_title('End-to-end warm median');axes[0].set_ylabel('Milliseconds');axes[0].set_ylim(0,70)
axes[1].set_title('Total device peak including cold start');axes[1].set_ylabel('MiB');axes[1].set_ylim(0,1300)
fig.suptitle('Fotufilm: original versus revised TWO-stage cut',fontsize=15,y=.99)
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.92),ncol=2,frameon=False)
fig.text(.5,.025,'One paired pilot per case; Docker running; thermal 0-1 (arms differ on Portra 4K).\nC/C diagnostic only: observed differences are not stable causal speedups or upstream acceptance.',ha='center',fontsize=9)
fig.subplots_adjust(top=.80,bottom=.23,wspace=.22)
for suffix in ('png','svg'):fig.savefig(a.output/f'comparison.{suffix}',dpi=180)
print(a.output/'comparison.png')
