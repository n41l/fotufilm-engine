#!/usr/bin/env python3
"""Plot completed isolated Coupler fusion results, with all round medians visible."""
import argparse,json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=json.loads(a.report.read_text())
 if not r['complete'] or r['protocol']['rounds_per_arm_case']!=3:raise ValueError('completed three-repeat cohort required')
 a.output.mkdir(parents=True,exist_ok=True);names=['R-B1','W0','Fused'];labels=['Original windowed','Same-source control','Coupler fused'];colors=['#4D7595','#8D969F','#32836F'];cases=list(r['summary'])
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.5,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#9BA6AE','text.color':'#263846','axes.labelcolor':'#263846','xtick.color':'#263846','ytick.color':'#536371'})
 fig,axes=plt.subplots(2,2,figsize=(12,8));fig.patch.set_facecolor('#FAFCFD')
 for col,case in enumerate(cases):
  s=r['summary'][case];size=case.rsplit('-',1)[-1]
  for row,key,unit,title in [(0,'median_of_round_medians_ms','Milliseconds / frame','Warm latency'),(1,'max_device_peak_mib','MiB','Repeated total device peak')]:
   ax=axes[row,col];values=[s[n][key] for n in names];roundkey='round_medians_ms' if row==0 else 'device_peaks_mib';top=max(max(s[n][roundkey]) for n in names);limit=math.ceil(top*1.23/(2 if row==0 else 100))*(2 if row==0 else 100)
   ax.set_facecolor('#FAFCFD');ax.set_axisbelow(True);ax.grid(axis='y',alpha=.18);ax.bar(range(3),values,color=colors,width=.58,zorder=2);ax.set_xticks(range(3),labels);ax.tick_params(axis='x',length=0,pad=7);ax.set_ylim(0,limit);ax.set_ylabel(unit);ax.set_title(f'{size}  ·  {title}',loc='left',fontsize=11.5,pad=13)
   for i,n in enumerate(names):
    dots=s[n][roundkey];ax.scatter([i-.07,i,i+.07],dots,color='#142B36',s=18,zorder=4,edgecolor='white',linewidth=.45);ax.text(i,max(values[i],max(dots))+limit*.035,f'{values[i]:.2f}' if row==0 else f'{values[i]:,.1f}',ha='center',va='bottom',weight='bold',fontsize=10.5)
 fig.suptitle('Coupler release → downsample fusion  |  Portra 400',x=.065,y=.98,ha='left',fontsize=16,weight='bold')
 fig.text(.065,.93,'Original windowed and matched current-source control. MTF fusion off. Lower is better.',fontsize=10.5,color='#536371')
 fig.text(.065,.09,'Latency bars: median of 3 round medians. Memory bars: maximum peak. Dots: individual rounds.',fontsize=9,color='#536371')
 fig.text(.065,.055,'Each panel has its own scale. Two upscaled Coffee SDR workloads. Device totals include pools. Defaults off.',fontsize=9,color='#536371')
 fig.subplots_adjust(left=.075,right=.98,top=.84,bottom=.18,wspace=.26,hspace=.53)
 for ext in ('png','svg'):fig.savefig(a.output/('comparison.'+ext),dpi=180,facecolor=fig.get_facecolor())
 plt.close(fig)
if __name__=='__main__':main()
