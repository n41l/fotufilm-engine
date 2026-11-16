#!/usr/bin/env python3
"""Render all stage18 round medians and repeated device peaks."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('output',type=Path);a=p.parse_args();d=json.loads(a.report.read_text());fig,ax=plt.subplots(2,2,figsize=(11,7.4));colors=['#65758b','#327ca8','#c67736'];labels=['Original','Generic fusion','Stride-1 specialization']
for col,(case,arms) in enumerate(d['summary'].items()):
 rows=[arms[n] for n in ('R-B1','Generic','Unit')];values=[r['median_of_round_medians_ms'] for r in rows];top=ax[0,col];top.bar(range(3),values,color=colors,alpha=.8,width=.62)
 for i,r in enumerate(rows):
  top.scatter([i-.11,i,i+.11],r['round_medians_ms'],s=32,color='#1b2534',edgecolors='white',linewidths=.7,zorder=3)
  top.text(i,values[i]+max(values)*.025,f'{values[i]:.2f}',ha='center',fontsize=11,fontweight='bold')
 top.set_title('1080p' if '1920' in case else '4K UHD',fontsize=13);top.set_ylabel('Frame time (ms), lower is better');top.set_ylim(0,max(max(r['round_medians_ms']) for r in rows)*1.18);top.set_xticks(range(3),labels,fontsize=9);top.grid(axis='y',alpha=.18);top.set_axisbelow(True)
 bottom=ax[1,col];peaks=[r['max_device_peak_mib'] for r in rows];bottom.bar(range(3),peaks,color=colors,alpha=.8,width=.62)
 for i,x in enumerate(peaks):bottom.text(i,x+max(peaks)*.025,f'{x:.2f}',ha='center',fontsize=11,fontweight='bold')
 bottom.set_ylabel('Repeated device peak (MiB)');bottom.set_ylim(0,max(peaks)*1.2);bottom.set_xticks(range(3),labels,fontsize=9);bottom.grid(axis='y',alpha=.18);bottom.set_axisbelow(True)
 for pane in (top,bottom):
  pane.spines[['top','right']].set_visible(False)
fig.suptitle('Coupler stride-1 specialization: no consistent end-to-end gain',fontsize=16,fontweight='bold',y=.98)
fig.text(.5,.015,f"Bars: median of 3 round medians; dots: every round. {d['valid_rounds']} valid rounds, {d['measurement_requests']:,} measurement calls.\nHD has strong time drift; UHD specialization is 1.56% slower than generic fusion. Defaults remain off.",ha='center',fontsize=10,color='#4a5260')
fig.tight_layout(rect=(0,.08,1,.94));a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=160);print(a.output)
