#!/usr/bin/env python3
"""Plot original general/default-windowed and revised two-stage diagnostics."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
r=json.loads(a.report.read_text())
if not r['complete'] or len(r['cases'])!=4 or any(not x['scores']['valid'] for c in r['cases'] for x in c['arms'].values()):raise ValueError('complete valid three-arm comparison required')
a.output.mkdir(parents=True,exist_ok=True);fig,axes=plt.subplots(1,2,figsize=(14,6))
arms=(('R-B0','Original: general (B0)','#a0aec0'),('R-B1','Original: default windowed (B1)','#2f855a'),('bundle','New: two-stage light + fields','#3182ce'))
for j,(arm,label,color) in enumerate(arms):
 for ax,key,scale in ((axes[0],'median_seconds',1000),(axes[1],'device_total_peak_bytes',1/1024**2)):
  values=[c['arms'][arm]['scores' if key=='median_seconds' else 'memory'][key]*scale for c in r['cases']]
  bars=ax.bar([i+(j-1)*.25 for i in range(4)],values,.23,label=label,color=color)
  ax.bar_label(bars,labels=[f'{v:.2f}' if scale==1000 else f'{v:.0f}' for v in values],fontsize=8,padding=3,rotation=90 if scale==1000 else 0)
for ax in axes:
 ax.set_xticks(range(4),['Portra 1080p','Portra 4K + luma','HP5 1080p','HP5 4K'],rotation=16,ha='right');ax.set_ylim(bottom=0,top=ax.get_ylim()[1]*1.18)
 ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
axes[0].set_title('End-to-end warm median (lower is better)');axes[0].set_ylabel('Milliseconds')
axes[1].set_title('Total device peak including cold start');axes[1].set_ylabel('MiB')
fig.suptitle('Original Fotufilm pipeline vs revised TWO-stage cut',fontsize=15,y=.99)
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.92),ncol=3,frameon=False)
thermal=sorted({x['memory']['max_thermal_state'] for c in r['cases'] for x in c['arms'].values()})
fig.text(.5,.025,'One warm round per arm/case; frozen original source; identical input/driver; thermal '+','.join(map(str,thermal))+'.\nB1 is the original enabled-window selector for these eligible cases. B_ref remains unfrozen; no causal/PR acceptance claim.',ha='center',fontsize=9)
fig.subplots_adjust(top=.80,bottom=.23,wspace=.23)
for suffix in ('png','svg'):fig.savefig(a.output/f'comparison.{suffix}',dpi=180)
print(a.output/'comparison.png')
