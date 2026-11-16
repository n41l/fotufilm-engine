#!/usr/bin/env python3
"""Plot separate, nonadditive 4K probe observations and observer-effect controls."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=json.loads(a.report.read_text());case='portra400-coffee-3840x2160';d=r['summary'][case];v=lambda x:x['median_of_process_medians'];fig,ax=plt.subplots(2,2,figsize=(13,9));colors=['#61788e','#c27b3c'];policies=['R-on','BestFit-on']
keys=['allocator_inclusive','metal_new_buffer','pool_reclaim','pool_eviction_release'];labels=['Allocator\ninclusive','Metal creation\nsubset','Reclaim\nsubset','Eviction release\nsubset']
for j,cell in enumerate(policies):
 vals=[v(d[cell]['cpu_scope_ms'][k]) for k in keys];x=[i+(j-.5)*.32 for i in range(len(keys))];ax[0,0].bar(x,vals,width=.3,color=colors[j],label='Original' if j==0 else 'Best-fit')
 for pos,val in zip(x,vals):ax[0,0].text(pos,val+.004,f'{val:.3f}',ha='center',fontsize=9)
ax[0,0].set_xticks(range(4),labels,fontsize=9);ax[0,0].set_ylabel('CPU-side elapsed time (ms)');ax[0,0].set_ylim(0,.29);ax[0,0].set_title('Allocation is a small direct CPU-side cost');ax[0,0].legend(frameon=False)
for j,cell in enumerate(policies):
 vals=[v(d[cell]['gpu_metrics_ms']['gpu_compute_union_ms']),v(d[cell]['cpu_scope_ms']['wait_until_completed']),v(d[cell]['main_thread_cpu_ms'])];x=[i+(j-.5)*.32 for i in range(3)];ax[0,1].bar(x,vals,width=.3,color=colors[j])
 for pos,val in zip(x,vals):ax[0,1].text(pos,val+.4,f'{val:.2f}',ha='center',fontsize=10)
ax[0,1].set_xticks(range(3),['GPU interval\nunion','Explicit wait\nwall time','Main-thread\nCPU time']);ax[0,1].set_ylabel('Milliseconds');ax[0,1].set_ylim(0,38);ax[0,1].set_title('Overlapping observations: do not add')
families=r['kernel_command_families'][case];names=[x['family'] for x in families['R-on'][:6]];maps={k:{x['family']:x['median_per_command_ms'] for x in families[k]} for k in policies}
for j,cell in enumerate(policies):ax[1,0].barh([i+(j-.5)*.32 for i in range(len(names))],[maps[cell].get(n,0) for n in names],height=.3,color=colors[j])
ax[1,0].set_yticks(range(len(names)),[n.replace('frame_','',1).replace('_v40','') for n in names],fontsize=9);ax[1,0].invert_yaxis();ax[1,0].set_xlabel('Median GPU command interval per call (ms)');ax[1,0].set_title('Longer kernel command envelopes')
cells=['R-off','R-on','BestFit-off','BestFit-on'];vals=[v(d[x]['api_ms']) for x in cells];ax[1,1].bar(range(4),vals,color=[colors[0],colors[0],colors[1],colors[1]],alpha=.8,width=.6)
for i,cell in enumerate(cells):
 points=d[cell]['api_ms']['process_medians'];ax[1,1].scatter([i-.12,i-.04,i+.04,i+.12],points,color='#183040',edgecolors='white',linewidths=.5,s=25,zorder=3);ax[1,1].text(i,vals[i]+.6,f'{vals[i]:.2f}',ha='center',fontweight='bold')
ax[1,1].set_xticks(range(4),['R off','R on','Best-fit off','Best-fit on']);ax[1,1].set_ylabel('API wall time (ms)');ax[1,1].set_ylim(0,max(max(d[x]['api_ms']['process_medians']) for x in cells)*1.2);ax[1,1].set_title('Probe controls vary: no exact correction')
for pane in ax.flat:pane.spines[['top','right']].set_visible(False);pane.grid(axis='x' if pane is ax[1,0] else 'y',alpha=.16);pane.set_axisbelow(True)
fig.suptitle('4K timing probes: allocation CPU time does not explain the whole frame',fontsize=15,fontweight='bold',y=.985)
fig.text(.5,.015,'32 fresh processes; 10 warm + 40 measured frames each. CPU/GPU/wait intervals overlap.\nGPU timestamps describe command envelopes, not hardware utilization. Scope-correct final cohort only; defaults unchanged.',ha='center',fontsize=10,color='#465363')
fig.tight_layout(rect=(0,.075,1,.95));a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=160);print(a.output)
