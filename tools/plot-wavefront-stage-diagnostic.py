#!/usr/bin/env python3
"""Plot the complete bounded three-arm diagnostic; requires matplotlib."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
r=json.loads(a.report.read_text())
if not r['complete'] or len(r['cases'])!=4:raise ValueError('complete four-case diagnostic required')
if any(not arm['scores']['valid'] for c in r['cases'] for arm in c['arms'].values()):raise ValueError('invalid round must not be plotted as a score')
a.output.mkdir(parents=True,exist_ok=True)
fig,axes=plt.subplots(1,2,figsize=(13,5.6))
labels=['Portra 1080p','Portra 4K + luma','HP5 1080p','HP5 4K']
arms=[('R-B1','R-B1: upstream windowed','#718096'),('2','E2: two stages','#3182ce'),('3','E3: three stages','#dd6b20')]
for j,(arm,label,color) in enumerate(arms):
    positions=[i+(j-1)*.25 for i in range(4)]
    for ax,key,scale in ((axes[0],'median_seconds',1000),(axes[1],'device_total_peak_bytes',1/1024**2)):
        values=[c['arms'][arm]['scores' if key=='median_seconds' else 'memory'][key]*scale for c in r['cases']]
        bars=ax.bar(positions,values,.23,label=label,color=color)
        ax.bar_label(bars,labels=[f'{v:.2f}' if scale==1000 else f'{v:.0f}' for v in values],fontsize=8,padding=3,rotation=90 if scale==1000 else 0)
for ax in axes:
    ax.set_xticks(range(4),labels,rotation=16,ha='right');ax.set_ylim(bottom=0)
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
axes[0].set_title('End-to-end warm median (lower is better)');axes[0].set_ylabel('Milliseconds');axes[0].set_ylim(0,62)
axes[1].set_title('Total device peak including cold start');axes[1].set_ylabel('MiB');axes[1].set_ylim(0,1400)
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.92),ncol=3,frameon=False)
fig.suptitle('Fotufilm: R-B1 / two-stage / three-stage diagnostic',fontsize=15,y=.99)
fig.text(.5,.025,'One round per case/arm; 5s warmup / 30s measurement; Docker running; thermal 0-1.\nR-B1 is a named control, not frozen B_ref. Single-round differences are not acceptance evidence.',ha='center',fontsize=9)
fig.subplots_adjust(top=.80,bottom=.23,wspace=.22)
for suffix in ('png','svg'):fig.savefig(a.output/f'comparison.{suffix}',dpi=180)
print(a.output/'comparison.png')
