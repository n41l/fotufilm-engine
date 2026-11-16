import unittest
from windowed_speed_analysis import merge,duration,overlap,analyze
class SpeedTests(unittest.TestCase):
 def fixture(self):return {'api_begin':10,'api_end':11,'flush_seconds':.001,'probes':True,'cpu':[{'kind':'encode_envelope','begin':10.1,'end':10.2},{'kind':'wait_until_completed','begin':10.4,'end':10.9},{'kind':'allocator_inclusive','begin':10.1,'end':10.3},{'kind':'pool_reclaim','begin':10.15,'end':10.2}],'commands':[{'label':'_kernel_frame_mtf_v40_s0_x','done':True,'status':4,'submit_begin':10.2,'submit_end':10.21,'gpu_start':10.3,'gpu_end':10.8}]}
 def test_gpu_and_wait_are_overlapping_not_additive(self):
  d=analyze(self.fixture(),1,0);self.assertAlmostEqual(d['wait_gpu_overlap_ms'],400);self.assertAlmostEqual(d['gpu_kernel_interval_sum_ms'],500);self.assertAlmostEqual(d['cpu_ms']['allocator_inclusive'],200);self.assertAlmostEqual(d['cpu_ms']['pool_reclaim'],50)
 def test_merge_union_handles_overlapping_commands(self):
  self.assertAlmostEqual(duration([(1,3),(2,4)]),3);self.assertAlmostEqual(overlap([(1,3),(2,4)],[(2.5,5)]),1.5)
 def test_missing_gpu_timestamp_rejects_zero_as_measurement(self):
  f=self.fixture();f['commands'][0]['gpu_start']=0;f['commands'][0]['gpu_end']=0
  with self.assertRaisesRegex(ValueError,'timestamp missing'):analyze(f,1,0)
 def test_wrong_clock_origin_rejected(self):
  f=self.fixture();f['commands'][0]['gpu_start']=1;f['commands'][0]['gpu_end']=2
  with self.assertRaisesRegex(ValueError,'clock'):analyze(f,1,0)
 def test_dispatch_and_allocation_coverage_required(self):
  with self.assertRaisesRegex(ValueError,'dispatch'):analyze(self.fixture(),2,0)
  with self.assertRaisesRegex(ValueError,'allocation'):analyze(self.fixture(),1,4)
 def test_disabled_is_unavailable_not_zero_gpu_time(self):
  f=self.fixture();f.update(probes=False,cpu=[],commands=[]);d=analyze(f,1,0);self.assertFalse(d['gpu_available']);self.assertNotIn('gpu_compute_ms',d)
 def test_failed_command_not_timed_as_success(self):
  f=self.fixture();f['commands'][0]['status']=5
  with self.assertRaisesRegex(ValueError,'completion'):analyze(f,1,0)
 def test_overlapping_kernel_sum_is_not_frame_gpu_time(self):
  f=self.fixture();f['commands'].append({**f['commands'][0],'gpu_start':10.4,'gpu_end':10.9});f['cpu'].append({'kind':'encode_envelope','begin':10.21,'end':10.22});d=analyze(f,2,0);self.assertAlmostEqual(d['gpu_kernel_interval_sum_ms'],1000);self.assertAlmostEqual(d['gpu_compute_union_ms'],600)
 def test_generated_transform_preserves_frozen_source_and_requires_exact_match(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import patch
  import wavefront_aot_driver as b
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'repo';src=repo/'Sources/FotufilmHalide';src.mkdir(parents=True);source=src/'FotufilmHalideIOS.cpp';source.write_text('void reclaim_returned() {}\n');kernels=root/'kernels';kernels.mkdir();(kernels/'.generated-from').write_text('fixed key');(kernels/'fotufilm_halide_ios_color_test.h').write_text('int fotufilm_halide_ios_color_test(int width);');prefix=root/'prefix';prefix.write_text('// prefix');suffix=root/'suffix';suffix.write_text('// suffix')
   with patch.object(b.subprocess,'check_output',return_value='fixed'),patch.object(b.subprocess,'run'):
    b.build(repo,kernels,root/'out',root/'driver',shim_prefix=prefix,shim_suffix=suffix,shim_replacements=[('void reclaim_returned() {','void reclaim_returned() { int timer;',1)])
    self.assertEqual(source.read_text(),'void reclaim_returned() {}\n');self.assertTrue((root/'out/diagnostic-shim.cpp').read_text().startswith('// prefix\n'));self.assertIn('int timer;',(root/'out/diagnostic-shim.cpp').read_text())
    with self.assertRaisesRegex(ValueError,'count mismatch'):b.build(repo,kernels,root/'bad',root/'driver',shim_replacements=[('missing','changed',1)])
if __name__=='__main__':unittest.main()
