#!/usr/bin/env python3
"""Plot all normal-worker stage19 rounds and repeated device peaks."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('output',type=Path);a=p.parse_args();d=json.loads(a.report.read_text());fig,ax=plt.subplots(2,2,figsize=(10,7));labels=['Original exact-bin','Bounded best-fit'];colors=['#63758c','#c67c3a']
for col,(case,arms) in enumerate(d['summary'].items()):
 rows=[arms[n] for n in ('R-B1','BestFit')];vals=[x['median_of_round_medians_ms'] for x in rows];top=ax[0,col];top.bar(range(2),vals,color=colors,width=.55,alpha=.85)
 for i,r in enumerate(rows):
  top.scatter([i-.08,i,i+.08],r['round_medians_ms'],color='#192c43',s=30,edgecolors='white',linewidths=.7,zorder=3);top.text(i,vals[i]+max(vals)*.03,f'{vals[i]:.2f}',ha='center',fontweight='bold')
 top.set_title('1080p' if '1920' in case else '4K UHD');top.set_ylabel('Frame time (ms), lower is better');top.set_ylim(0,max(max(r['round_medians_ms']) for r in rows)*1.2)
 bottom=ax[1,col];peaks=[x['max_device_peak_mib'] for x in rows];bottom.bar(range(2),peaks,color=colors,width=.55,alpha=.85)
 for i,x in enumerate(peaks):bottom.text(i,x+max(peaks)*.035,f'{x:.2f}',ha='center',fontweight='bold')
 bottom.set_ylabel('Repeated device peak (MiB)');bottom.set_ylim(0,max(peaks)*1.2)
 for pane in (top,bottom):pane.set_xticks(range(2),labels);pane.grid(axis='y',alpha=.18);pane.set_axisbelow(True);pane.spines[['top','right']].set_visible(False)
fig.suptitle('Bounded best-fit: lower 4K memory, no speed gain',fontsize=16,fontweight='bold',y=.98)
fig.text(.5,.015,f"Bars: median of 3 round medians; dots: all rounds. {d['valid_rounds']} valid rounds, {d['measurement_requests']:,} measurement calls.\n4K new buffers/frame: 4 -> 0; peak: -192 MiB (-16.2%). Interrupted campaign excluded. Experimental only.",ha='center',fontsize=10,color='#485466')
fig.tight_layout(rect=(0,.09,1,.94));a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=160);print(a.output)
