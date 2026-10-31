#!/usr/bin/env python3
"""Synthetic protocol/threshold tests; these establish no GPU or performance coverage."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('comparison',Path(__file__).with_name('run-wavefront-comparison.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def round_result(rate=12):
    return {'scores':{'valid':True,'median_seconds':.1,'p95_seconds':.2,'throughput_fps':rate},
            'memory':dict.fromkeys(c.METRICS,16*1024*1024)|{'max_thermal_state':0}}


def protocol():
    cases=[{'id':str(i),'stock':'stock','size':'1920x1080','pack':'pack','pack_sha256':'p','input':'input','input_sha256':'i'} for i in range(4)]
    epsilon={m:{'stable':True,'epsilon_bytes':0,'cap_bytes':16*1024*1024*.02} for m in c.METRICS}
    entry={'B_ref':'B1','memory_stable':True,'timing_review_required':False,'memory_epsilon':epsilon,
           'arms':{'B0':[round_result(10) for _ in range(3)],'B1':[round_result() for _ in range(6)]}}
    baseline={'complete':True,'B_ref_frozen':True,'frozen_cases':{'pilot':False,'source_base':'base',
        'idle_sleep_prevention':'controller-scoped caffeinate -i','worker_sha256':'r','cases':cases,'environment':{'boot':'one'},'warmup_seconds':5,'window_seconds':30,
        'tail_seconds':2,'retained_idle_seconds':5,'idle_pool_mib':1024,'inflight_frames':1,
        'tool_sources':{'wavefront-benchmark.mm':'common','wavefront_metrics.py':'math'}},
        'cases':{str(i):copy.deepcopy(entry) for i in range(4)}}
    verification={'complete':True,'normal_experimental_kernel_coverage':True,'frozen_cases_sha256':'fixtures',
        'reference_base':'base','R_worker_sha256':'r','C_worker_sha256':{'E_256':'e'},'common_driver_sha256':'common',
        'results':[{'case':str(i),'candidate':'E_256','comparison':{'passed':True}} for i in range(4)]}
    fixtures={'source_base':'base','worker_sha256':'r','cases':copy.deepcopy(cases)}
    kwargs={'band':256,'R_sha':'r','E_sha':'e','fixture_sha':'fixtures','common_sha':'common','stats_sha':'math','environment':{'boot':'one'}}
    return baseline,verification,fixtures,kwargs


class ProtocolTests(unittest.TestCase):
    def check(self,change=None):
        B,V,F,K=protocol()
        if change:change(B,V,F,K)
        return c.validate_protocol(B,V,F,**K)
    def rejects(self,change):
        with self.assertRaises(ValueError):self.check(change)
    def test_valid_frozen_protocol(self):self.check()
    def test_unfrozen_baseline(self):self.rejects(lambda B,V,F,K:B.update(B_ref_frozen=False))
    def test_pilot_baseline(self):self.rejects(lambda B,V,F,K:B['frozen_cases'].update(pilot=True))
    def test_sleep_uncontrolled_baseline(self):self.rejects(lambda B,V,F,K:B['frozen_cases'].pop('idle_sleep_prevention'))
    def test_new_boot(self):self.rejects(lambda B,V,F,K:K.update(environment={'boot':'two'}))
    def test_changed_worker(self):self.rejects(lambda B,V,F,K:K.update(E_sha='different'))
    def test_traced_verifier(self):self.rejects(lambda B,V,F,K:V.update(normal_experimental_kernel_coverage=False))
    def test_changed_input(self):self.rejects(lambda B,V,F,K:F['cases'][0].update(input_sha256='changed'))
    def test_missing_normal_case(self):self.rejects(lambda B,V,F,K:V['results'].pop())
    def test_changed_math(self):self.rejects(lambda B,V,F,K:K.update(stats_sha='changed'))
    def test_changed_window(self):self.rejects(lambda B,V,F,K:B['frozen_cases'].update(window_seconds=31))
    def test_invalid_baseline_round(self):self.rejects(lambda B,V,F,K:B['cases']['0']['arms']['B1'][0]['scores'].update(valid=False))
    def test_changed_epsilon(self):self.rejects(lambda B,V,F,K:B['cases']['0']['memory_epsilon'][c.METRICS[0]].update(epsilon_bytes=1))
    def test_relaxed_epsilon_cap(self):self.rejects(lambda B,V,F,K:B['cases']['0']['memory_epsilon'][c.METRICS[0]].update(cap_bytes=4*1024*1024))
    def test_incomplete_baseline_arm(self):self.rejects(lambda B,V,F,K:B['cases']['0']['arms'].update(B0=[]))
    def test_missing_preselected_band(self):self.rejects(lambda B,V,F,K:K.update(band=64))


class AssessmentTests(unittest.TestCase):
    def setup(self):
        arms={a:[round_result() for _ in range(3)] for a in ('B','E')}
        for r in arms['E']:r['scores'].update(median_seconds=.09,p95_seconds=.18,throughput_fps=13)
        return arms,{m:{'epsilon_bytes':0} for m in c.METRICS}
    def check(self,change=None):
        arms,epsilon=self.setup()
        if change:change(arms)
        return c.assess(arms,epsilon)
    def test_passing_primary_only(self):
        r=self.check();self.assertTrue(r['primary_nonregression']);self.assertTrue(r['median_improvement_at_least_10pct'])
        self.assertIsNone(r['local_intermediate_peak_reduction'])
    def test_median_regression(self):self.assertFalse(self.check(lambda a:[r['scores'].update(median_seconds=.106) for r in a['E']])['primary_nonregression'])
    def test_p95_regression(self):self.assertFalse(self.check(lambda a:[r['scores'].update(p95_seconds=.221) for r in a['E']])['primary_nonregression'])
    def test_throughput_regression(self):self.assertFalse(self.check(lambda a:[r['scores'].update(throughput_fps=11.3) for r in a['E']])['primary_nonregression'])
    def test_memory_growth(self):self.assertFalse(self.check(lambda a:a['E'][0]['memory'].update(device_total_peak_bytes=16*1024*1024+1))['primary_nonregression'])
    def test_R_memory_noise(self):self.assertTrue(self.check(lambda a:a['B'][0]['memory'].update(device_total_peak_bytes=16*1024*1024+1))['environment_review_required'])
    def test_R_timing_drift(self):self.assertTrue(self.check(lambda a:a['B'][0]['scores'].update(throughput_fps=8))['environment_review_required'])
    def test_thermal_review(self):self.assertTrue(self.check(lambda a:a['E'][0]['memory'].update(max_thermal_state=2))['environment_review_required'])
    def test_spec_boundary_values(self):
        r=self.check(lambda a:[r['scores'].update(median_seconds=.105,p95_seconds=.22,throughput_fps=11.4) for r in a['E']])
        self.assertTrue(r['primary_nonregression']);self.assertFalse(r['median_improvement_at_least_10pct'])
    def test_missing_pair(self):
        with self.assertRaises(ValueError):self.check(lambda a:a['E'].pop())
    def test_invalid_pair(self):
        with self.assertRaises(ValueError):self.check(lambda a:a['E'][0]['scores'].update(valid=False))


if __name__=='__main__':unittest.main()
