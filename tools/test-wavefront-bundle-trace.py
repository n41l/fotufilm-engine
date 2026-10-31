#!/usr/bin/env python3
"""Synthetic acceptance failures; these tests are not real GPU evidence."""
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('bundle_trace',Path(__file__).with_name('verify-wavefront-bundle-trace.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def fixture():
 lines=[]
 for band,y,n in ((0,0,872),(1,872,208)):
  lines += [f'ROW_PLAN {band} {y} {n} {y} 2048',f'PRODUCE frame_wavefront_bundle_light_v61 0 32 {y} {n} 0 3',f'PRODUCE frame_mtf_v61 0 32 {y} {n} 0 3']
  for i,(w,h,split) in enumerate(((16,540,427),(8,270,212),(8,270,206))):
   fy=0 if band==0 else split;fn=split if band==0 else h-split
   lines += [f'FIELD_PLAN {i} {band} {fy} {fn} {h}',f'PRODUCE frame_halation__v61{i}_spread 0 {w} {fy} {fn} 0 3']
  lines += [f'CONSUMER_PLAN {band} {band*512} 512',f'BAND_COMPLETE {band}']
 lines+=['CONSUMER_PLAN 2 1024 56','BAND_COMPLETE 2']
 for i,(band,phase) in enumerate(((0,1),(0,2),(1,1),(1,2),(2,2))):
  lines += [f'GPU_COMPLETION {i+1} {band+1} {phase} q {i+1} {i+2} 4',f'GPU_KERNEL {band+1} {phase} kernel']
 return lines+['BUNDLE_COUNTS light_rows=1080 producer_calls=2 consumer_calls=3 field_rows0=540 field_rows1=270 field_rows2=270 field_updates0=2 field_updates1=2 field_updates2=2']
class Tests(unittest.TestCase):
 def check(self,lines,calls=5,dispatches=5):return m.analyze(lines,32,1080,calls,dispatches)['passed']
 def test_valid_two_calls_three_outputs(self):self.assertTrue(self.check(fixture()))
 def test_mtf_recomputation_rejected(self):self.assertFalse(self.check([x.replace('frame_mtf_v61 0 32 872 208','frame_mtf_v61 0 32 871 209') for x in fixture()]))
 def test_field_overlap_rejected(self):self.assertFalse(self.check([x.replace('frame_halation__v610_spread 0 16 427 113','frame_halation__v610_spread 0 16 426 114') for x in fixture()]))
 def test_missing_field_rejected(self):self.assertFalse(self.check([x for x in fixture() if 'frame_halation__v612_spread 0 8 206' not in x]))
 def test_previous_consumer_in_flight_rejected(self):self.assertFalse(self.check([x.replace('GPU_COMPLETION 2 1 2 q 2 3 4','GPU_COMPLETION 2 1 2 q 2 3.1 4') for x in fixture()]))
 def test_extra_aot_stage_rejected(self):self.assertFalse(self.check(fixture(),calls=6))
 def test_missing_kernel_binding_rejected(self):self.assertFalse(self.check(fixture(),dispatches=6))
if __name__=='__main__':unittest.main()
