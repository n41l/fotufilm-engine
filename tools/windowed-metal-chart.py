#!/usr/bin/env python3
"""Show the acquisition wait location, native method scales and three-mode controls."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from windowed_speed_analysis import merge
p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('output',type=Path);a=p.parse_args();d=json.loads(a.report.read_text());case='portra400-coffee-3840x2160';cells=d['summary'][case];v=lambda x:x['median_of_process_medians'];colors=['#617c96','#c47c38'];fig,ax=plt.subplots(2,2,figsize=(13,8.8))
methods=['command_create_native','pipeline_create','encoder_create','command_commit','dispatch','buffer_bind','end_encoding'];labels=['Native commandBuffer','Pipeline creation','Encoder creation','Commit','Dispatch','Buffer binding','End encoding']
for j,cell in enumerate(('R-detail','BestFit-detail')):
 values=[v(cells[cell]['method_ms'][k]) for k in methods];ys=[i+(j-.5)*.32 for i in range(len(methods))];ax[0,0].barh(ys,values,height=.3,color=colors[j],label='Original' if j==0 else 'Best-fit')
 for y,x in zip(ys,values):ax[0,0].text(x*1.10,y,f'{x:.3f}',va='center',fontsize=8)
ax[0,0].set_yticks(range(len(methods)),labels,fontsize=9);ax[0,0].invert_yaxis();ax[0,0].set_xscale('log');ax[0,0].set_xlim(.004,55);ax[0,0].set_xlabel('CPU-side elapsed ms/frame (log scale)');ax[0,0].set_title('The large interval is native acquisition');ax[0,0].legend(frameon=False,loc='lower right')
profile=json.loads(Path(d['profile_report']).read_text());choices=[]
for row in profile['runs']:
 if row['case']==case and row['cell']=='R-detail':
  data=json.loads(Path(row['analysis']).read_text())
  for frame in data['frames']:
   if frame['phase']=='measurement':choices.append((abs(frame['api_ms']-v(cells['R-detail']['api_ms'])),Path(data['path'])/(str(frame['frame'])+'.json')))
chosen=min(choices,key=lambda x:x[0])[1];raw=json.loads(chosen.read_text());begin=raw['api_begin'];groups=[[(e['begin'],e['end']) for e in raw['metal_methods'] if e['kind']=='command_create_native'],merge([(e['gpu_start'],e['gpu_end']) for e in raw['commands'] if e['gpu_start']>0]),[(e['begin'],e['end']) for e in raw['cpu'] if e['kind']=='wait_until_completed']]
for i,(intervals,color) in enumerate(zip(groups,['#417ca1','#e49b46','#60936f'])):ax[0,1].broken_barh([((x-begin)*1000,(y-x)*1000) for x,y in intervals],(i-.22,.44),facecolors=color)
ax[0,1].set_yticks(range(3),['CPU acquisition wall','GPU interval union','Explicit wait wall'],fontsize=9);ax[0,1].invert_yaxis();ax[0,1].set_xlim(0,(raw['api_end']-begin)*1000);ax[0,1].set_xlabel('Milliseconds from API entry');ax[0,1].set_title('Representative R frame: intervals overlap')
for j,cell in enumerate(('R-detail','BestFit-detail')):
 h=cells[cell]['callback_pending_histogram'];total=sum(h.values());values=[100*h.get(str(i),0)/total for i in range(5)];ax[1,0].bar([i+(j-.5)*.32 for i in range(5)],values,width=.3,color=colors[j])
ax[1,0].set_xticks(range(5));ax[1,0].set_xlabel('Pending probe callbacks before acquisition');ax[1,0].set_ylabel('Share of acquisitions (%)');ax[1,0].set_title('Observed queue capacity stays 4')
for j,arm in enumerate(('R','BestFit')):
 values=[v(cells[arm+'-'+mode]['api_ms']) for mode in ('off','basic','detail')];xs=[i+(j-.5)*.32 for i in range(3)];ax[1,1].bar(xs,values,width=.3,color=colors[j],alpha=.85)
 for x,val,mode in zip(xs,values,('off','basic','detail')):
  points=cells[arm+'-'+mode]['api_ms']['process_medians'];ax[1,1].scatter([x-.09+k*.036 for k in range(6)],points,s=15,color='#193449',edgecolors='white',linewidths=.4,zorder=3);ax[1,1].text(x,max([val,*points])+.65,f'{val:.2f}',ha='center',fontweight='bold',fontsize=9)
ax[1,1].set_xticks(range(3),['Off','Basic probes','Detailed probes']);ax[1,1].set_ylabel('API wall ms/frame');ax[1,1].set_ylim(0,max(max(cells[k]['api_ms']['process_medians']) for k in cells)*1.18);ax[1,1].set_title('Short cohort: Best-fit is faster in all modes')
for pane in ax.flat:pane.spines[['top','right']].set_visible(False);pane.set_axisbelow(True);pane.grid(axis='x' if pane is ax[0,0] or pane is ax[0,1] else 'y',alpha=.16)
fig.suptitle('4K Metal method probes: depth-4 backpressure appears in commandBuffer acquisition',fontsize=14,fontweight='bold',y=.985)
fig.text(.5,.012,'72 fresh processes; 10 warm + 12 measured frames each. Queue depth and allocation policy unchanged.\nPending callbacks include delivery lag; GPU intervals are not utilization. Overlapping times do not add. Earlier latency direction is not reproduced here.',ha='center',fontsize=9.5,color='#475565')
fig.tight_layout(rect=(0,.08,1,.945));a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=160);print(a.output);print('representative trace',chosen)
