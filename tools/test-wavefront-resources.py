#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wavefront_resource_analysis as a
import wavefront_aot_driver as builder
spec=importlib.util.spec_from_file_location('resource',Path(__file__).with_name('verify-wavefront-resources.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class ResourceTests(unittest.TestCase):
    def test_interval_peaks_are_coincident(self):
        self.assertEqual(a.peak([(1,3,100),(3,5,200)],0,6),200)
        self.assertEqual(a.peak([(1,4,100),(3,5,200)],0,6),300)
    def test_peak_clips_frame_boundaries(self):
        self.assertEqual(a.peak([(0,10,100),(5,7,200)],2,4),100)
    def test_alias_is_one_category(self):
        self.assertEqual(a.category({'roles':2|4|32,'aot':'source'}),'frontier_and_configuration')
        self.assertEqual(a.category({'roles':1|2,'aot':'source'}),'external_io_alias')
    def test_aot_internal_is_not_claimed_spatial_local(self):
        self.assertEqual(a.category({'roles':0,'aot':'kernel'}),'AOT_intermediate')
        self.assertEqual(a.category({'roles':0,'aot':''}),'unclassified_halide')
    def trace(self):
        return {'errors':[],'physical':[{'id':1,'length':100,'allocated':100,'born':1,'freed':9}],
            'leases':[{'id':1,'physical':1,'requested':90,'born':3,'logical_end':5,'fence':1,'reuse_proof':0,'references':0,'roles':0,'aot':'kernel'}],
            'fences':[{'id':1,'commit':4,'complete':6,'delivered':True,'status':4}],
            'markers':[{'frame':0,'name':'frame_begin','event':2,'pool':[]},
                {'frame':0,'name':'frame_end','event':7,'pool':[{'physical':1,'length':100,'references':0,'state':2,'fence_status':4}]},
                {'frame':1,'name':'final','event':10,'pool':[]}]}
    def test_gpu_safe_interval_and_returned_complete_pool(self):
        d=a.analyze(self.trace())
        self.assertTrue(d['frame_intermediates_released'])
        self.assertEqual(d['snapshots'][1]['pool_allocated_bytes']['returned_GPU_complete'],100)
        self.assertEqual(d['frames'][0]['logical']['working_combined']['requested'],90)
    def test_premature_return_or_observer_errors_fail(self):
        t=self.trace();t['fences'][0]['complete']=8
        with self.assertRaisesRegex(ValueError,'still active'):a.analyze(t)
        t=self.trace();t['errors']=['bad reuse']
        with self.assertRaises(ValueError):a.analyze(t)
    def test_pool_aliases_cannot_double_count(self):
        t=self.trace();t['markers'][1]['pool']*=2
        with self.assertRaisesRegex(ValueError,'double counted'):a.analyze(t)
    def test_incomplete_gpu_coverage_rejected(self):
        t=self.trace();t['fences'][0]['delivered']=False
        with self.assertRaisesRegex(ValueError,'coverage'):a.analyze(t)
    def test_calibration_keeps_original_caps(self):
        rows=[{'metrics':{k:100_000_000 for k in v.METRICS}} for _ in range(6)]
        self.assertTrue(all(x['stable'] for x in v.calibrate(rows).values()))
        rows[1]['metrics'][v.METRICS[0]]+=2_000_001
        self.assertFalse(v.calibrate(rows)[v.METRICS[0]]['stable'])
    def test_warm_device_metric_keeps_cold_process_peak(self):
        frames=[{'type':'resource_frame','status':'success','memory':{'device_peak_bytes':1000 if i==0 else 100,
            'process_lifetime_peak_bytes':500}} for i in range(6)]
        events=frames+[{'type':'idle','memory':{'process_lifetime_peak_bytes':500,
            'device_current_bytes':80,'process_footprint_bytes':200}}]
        m=v.metrics(events)
        self.assertEqual(m['device_total_peak_bytes'],100)
        self.assertEqual(m['process_lifetime_peak_bytes'],500)
        self.assertEqual(m['retained_device_bytes'],80)
        with self.assertRaises(ValueError):v.metrics(events[1:])
    def test_rotation_calibration_cap_is_not_a_free_allowance(self):
        spec=importlib.util.spec_from_file_location('rotation',Path(__file__).with_name('calibrate-wavefront-resource-rotation.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        R=[{'bytes':100_000_000} for _ in range(6)];E=[{'bytes':101_000_000} for _ in range(3)]
        x=m.compare(R,E)['bytes']
        self.assertTrue(x['R_stable']);self.assertEqual(x['epsilon_bytes'],0)
        self.assertFalse(x['all_observed_within_R_plus_epsilon'])
        R[1]['bytes']+=5_000_000
        x=m.compare(R,[{'bytes':80_000_000} for _ in range(3)])['bytes']
        self.assertFalse(x['R_stable']);self.assertFalse(x['all_observed_within_R_plus_epsilon'])
    def builder(self,hooks):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';source=repo/'Sources/FotufilmHalide';source.mkdir(parents=True)
            (source/'FotufilmHalideIOS.cpp').write_text('// original shim\n')
            kernels=root/'kernels';kernels.mkdir();(kernels/'.generated-from').write_text('fixed key')
            header='fotufilm_halide_ios_color_test';(kernels/(header+'.h')).write_text('int '+header+'(struct halide_buffer_t *input, int width);')
            suffix=root/'suffix';suffix.write_text('// observer only\n')
            with patch.object(builder.subprocess,'check_output',return_value='fixed'),patch.object(builder.subprocess,'run') as run:
                builder.build(repo,kernels,root/'out',root/'driver.cpp',resource_hooks=hooks,
                    shim_definitions=('-Dnew_buffer=renamed',) if hooks else (),shim_suffix=suffix if hooks else None)
            wrappers=(root/'out/wrappers.cpp').read_text()
            if hooks:
                self.assertIn('wf_resource_bind',wrappers)
                self.assertEqual((root/'out/diagnostic-shim.cpp').read_text(),'// original shim\n\n// observer only\n')
                self.assertIn('-Dnew_buffer=renamed',run.call_args_list[0].args[0])
                self.assertNotIn('-Dnew_buffer=renamed',run.call_args_list[1].args[0])
            return wrappers
    def test_default_builder_preserves_original_wrapper(self):
        wrappers=self.builder(False)
        self.assertNotIn('wf_resource_',wrappers)
        self.assertIn('  return fotufilm_halide_ios_color_test(input, width);',wrappers)
    def test_diagnostic_only_flags_and_shim_copy(self):self.builder(True)

if __name__=='__main__':unittest.main()
