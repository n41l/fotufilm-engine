#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
p=argparse.ArgumentParser();p.add_argument('summary',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=json.loads(a.summary.read_text());arms=['R','BestFit','Recent'];labels=['Original','Best-fit','Recent frequency'];colors=['#2563a6','#16876a','#d97706']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'axes.axisbelow':True})
fig,axes=plt.subplots(2,2,figsize=(12,8),facecolor='#fbfcfe')
for i,(case,g) in enumerate(d['groups'].items()):
 for j,(key,title,unit) in enumerate([('api_ms','API latency','ms / frame'),('device_peak_mib','Metal allocation peak','MiB')]):
  ax=axes[j,i];v=[g[x][key] for x in arms];bars=ax.bar(labels,v,color=colors,width=.58)
  for b,y in zip(bars,v):ax.text(b.get_x()+b.get_width()/2,y+max(v)*.035,f'{y:.2f}',ha='center',fontweight='bold')
  if key=='api_ms':
   for k,arm in enumerate(arms):
    ys=[x[key] for x in d['processes'] if x['case']==case and x['arm']==arm];ax.scatter([k-.4,k-.36,k-.32],ys,color='#334155',s=18,zorder=3)
  ax.set_ylim(0,max([x[key] for x in d['processes'] if x['case']==case])*1.25);ax.set_ylabel(unit);ax.set_title(('1080p' if '1920' in case else '4K')+' — '+title,loc='left',fontweight='bold')
fig.suptitle('Fotufilm: recent-frequency eviction vs best-fit',x=.065,y=.98,ha='left',fontsize=18,fontweight='bold');fig.text(.065,.925,'Original normal driver | 5 s warmup + 30 s measurement | 3 repeats / arm / size',fontsize=11,color='#475569');fig.text(.065,.035,'Bars: median of three independent process medians. Dots: each process. Queue 4; idle pool cap 1 GiB.\nRecent frequency keeps exact-size reuse. One HD/UHD fixture; background varies; diagnostic, not acceptance.',fontsize=10,color='#475569');fig.subplots_adjust(top=.84,bottom=.17,left=.09,right=.97,hspace=.4,wspace=.3);a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=170,facecolor=fig.get_facecolor());print(a.output)
