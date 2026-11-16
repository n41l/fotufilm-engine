#!/usr/bin/env python3
"""Plot completed stage16 round medians and repeated-run total device peaks."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=json.loads(a.report.read_text())
 if not r['complete'] or r['protocol']['rounds_per_arm']!=3:raise ValueError('completed three-repeat report required')
 names=['R-B1','W0','Fused'];labels=['Original windowed','Same-source control','MTF fused'];colors=['#4D7595','#8D969F','#32836F'];s=r['summary'];a.output.mkdir(parents=True,exist_ok=True)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#9BA6AE','text.color':'#263846','axes.labelcolor':'#263846','xtick.color':'#263846','ytick.color':'#536371'})
 fig,axes=plt.subplots(1,2,figsize=(11.8,5.6));fig.patch.set_facecolor('#FAFCFD')
 for ax,key,unit,title,limit in [(axes[0],'median_of_round_medians_ms','Milliseconds / frame','Warm latency',48),(axes[1],'max_device_peak_mib','MiB','Repeated-run total device peak',1400)]:
  values=[s[n][key] for n in names];ax.set_facecolor('#FAFCFD');ax.set_axisbelow(True);ax.grid(axis='y',alpha=.18);bars=ax.bar(range(3),values,color=colors,width=.58,zorder=2);ax.set_xticks(range(3),labels);ax.tick_params(axis='x',length=0,pad=9);ax.set_ylim(0,limit);ax.set_ylabel(unit);ax.set_title(title,loc='left',fontsize=12,pad=18)
  for i,n in enumerate(names):
   dots=s[n]['round_medians_ms'] if key.startswith('median') else s[n]['device_peaks_mib'];ax.scatter([i-.075,i,i+.075],dots,color='#142B36',s=20,zorder=4,edgecolor='white',linewidth=.45)
   ax.text(i,values[i]+limit*.045,f'{values[i]:.2f}' if key.startswith('median') else f'{values[i]:,.1f}',ha='center',va='bottom',weight='bold',fontsize=11)
 fig.suptitle('MTF pointwise fusion  |  Portra 400  |  3840 × 2160',x=.065,y=.98,ha='left',fontsize=16,weight='bold')
 effect=r['effect_vs']['R-B1']
 fig.text(.065,.905,f"Compared with original windowed: {effect['observed_latency_reduction_percent']:.1f}% less median time · {effect['device_peak_reduction_mib']:.0f} MiB lower device peak",fontsize=11,color='#226650')
 fig.text(.065,.105,'Latency bars: median of 3 round medians. Memory bars: maximum peak. Dots: individual rounds.',fontsize=9,color='#536371')
 fig.text(.065,.065,'One upscaled Coffee SDR fixture. Device totals include I/O, tables, pool and scratch. Defaults remain off.',fontsize=9,color='#536371')
 fig.subplots_adjust(left=.075,right=.98,top=.79,bottom=.22,wspace=.28)
 for extension in ('png','svg'):fig.savefig(a.output/('comparison.'+extension),dpi=180,facecolor=fig.get_facecolor())
 plt.close(fig)
if __name__=='__main__':main()
