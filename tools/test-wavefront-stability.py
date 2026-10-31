#!/usr/bin/env python3
"""Synthetic accounting tests; these provide no GPU performance evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

analysis=module('analysis','analyze-wavefront-stability.py')
controller=module('stability','run-wavefront-stability.py')


class StabilityTests(unittest.TestCase):
    def test_partition_clips_tail_and_leading_interval(self):
        r=[{'started_at':-1,'completed_at':2},{'started_at':9,'completed_at':12}]
        d=analysis.partition(r,0,10)
        self.assertEqual(d['api_envelope_seconds'],3)
        self.assertEqual(d['outside_api_seconds'],7)

    def test_partition_rejects_overlapping_calls(self):
        with self.assertRaises(ValueError):analysis.partition([
            {'started_at':0,'completed_at':2},{'started_at':1,'completed_at':3}],0,10)

    def test_partition_rejects_negative_duration(self):
        with self.assertRaises(ValueError):analysis.partition([{'started_at':2,'completed_at':1}],0,10)

    def test_partition_boundary_is_not_double_counted(self):
        r=[{'started_at':0,'completed_at':10}]
        self.assertEqual(analysis.partition(r,0,5)['api_envelope_seconds']+analysis.partition(r,5,10)['api_envelope_seconds'],10)

    def test_distribution_keeps_long_tail(self):
        d=analysis.distribution([1]*29+[100])
        self.assertEqual(d['median'],1);self.assertEqual(d['max'],100)
        self.assertEqual(d['mean'],129/30)

    def test_pearson_constant_is_unavailable(self):
        self.assertIsNone(analysis.pearson([1,1,1],[1,2,3]))
        self.assertAlmostEqual(analysis.pearson([1,2,3],[3,2,1]),-1)

    def rounds(self):
        return [{'scores':{'valid':True,'throughput_fps':100},
                 'memory':{**{m:100_000_000 for m in controller.METRICS},'max_thermal_state':0}}
                for _ in range(6)]

    def test_stable_diagnostic_never_freezes_baseline(self):
        d=controller.assessment(self.rounds())
        self.assertTrue(d['stable_under_diagnostic_protocol'])
        self.assertFalse(d['B_ref_frozen']);self.assertFalse(d['performance_acceptance'])

    def test_timing_failure_keeps_slow_round(self):
        r=self.rounds();r[-1]['scores']['throughput_fps']=90
        d=controller.assessment(r)
        self.assertTrue(d['timing_review_required']);self.assertFalse(d['stable_under_diagnostic_protocol'])

    def test_original_memory_cap_is_enforced(self):
        r=self.rounds();r[1]['memory'][controller.METRICS[0]]+=2_000_001
        self.assertFalse(controller.assessment(r)['memory_stable'])

    def test_serious_thermal_requires_review(self):
        r=self.rounds();r[-1]['memory']['max_thermal_state']=2
        self.assertTrue(controller.assessment(r)['thermal_review_required'])
        self.assertFalse(controller.assessment(r)['stable_under_diagnostic_protocol'])

    def test_incomplete_or_invalid_cohort_cannot_be_assessed(self):
        r=self.rounds()
        with self.assertRaises(ValueError):controller.assessment(r[:5])
        r[-1]['scores']['valid']=False
        with self.assertRaises(ValueError):controller.assessment(r)

    def test_saved_score_mismatch_is_rejected(self):
        q=[{'id':0,'phase':'warmup','started_at':0,'completed_at':5,'status':'success'}]
        q += [{'id':i+1,'phase':'measurement','started_at':5+i*.5,'completed_at':5.1+i*.5,'status':'success'} for i in range(40)]
        w={'type':'window','t0':5,'t1':35,'deadline':37}
        scores=analysis.summarize({**w,'requests':q});scores['throughput_fps']+=1
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'round.json';p.write_text(json.dumps({'scores':scores,'requests':q,'phase_events':[w]}))
            with self.assertRaisesRegex(ValueError,'saved score'):analysis.analyze_round(p)


timing=module('timing','run-wavefront-timing.py')


class TimingTests(unittest.TestCase):
    def event(self):
        return {'id':0,'timing_complete':True,'engine_error':0,
            'committed':2,'completed':2,'timestamped':2,'queue_count':1,'wait_count':2,
            'gpu_intervals':[[1,3,4],[2,4,4]],'api_wall_seconds':3,
            'main_thread_cpu_seconds':1,'process_cpu_seconds':1.5,'wait_wall_seconds':2,
            'gpu_sum_seconds':4,'gpu_union_seconds':3,'gpu_span_seconds':3}

    def validate(self,event):
        requests=[{'id':'0','phase':'measurement','started_at':0,'completed_at':4}]
        return timing.validate_timings(requests,'API_TIMING '+json.dumps(event))

    def test_overlapping_gpu_intervals_are_not_added_as_busy_time(self):
        d=timing.gpu_intervals([[1,3,4],[2,4,4]])
        self.assertEqual(d,{'gpu_sum_seconds':4,'gpu_union_seconds':3,'gpu_span_seconds':3})
        self.assertTrue(self.validate(self.event())['coverage_complete'])

    def test_gpu_gaps_are_preserved(self):
        self.assertEqual(timing.gpu_intervals([[1,2,4],[3,4,4]])['gpu_union_seconds'],2)

    def test_invalid_gpu_timestamp_or_status_is_rejected(self):
        for interval in ([0,1,4],[2,1,4],[1,2,5]):
            with self.assertRaises(ValueError):timing.gpu_intervals([interval])

    def test_missing_and_duplicate_timing_requests_are_rejected(self):
        r=[{'id':'0','phase':'measurement','started_at':0,'completed_at':4}]
        text='API_TIMING '+json.dumps(self.event())
        for value in ('',text+'\n'+text):
            with self.assertRaises(ValueError):timing.validate_timings(r,value)

    def test_reported_gpu_union_must_match_raw_intervals(self):
        e=self.event();e['gpu_union_seconds']=2
        with self.assertRaisesRegex(ValueError,'summary disagrees'):self.validate(e)

    def test_incomplete_completion_cannot_claim_coverage(self):
        for key,value in (('timing_complete',False),('completed',1),('wait_count',0)):
            e=self.event();e[key]=value
            with self.assertRaises(ValueError):self.validate(e)

    def test_unavailable_cpu_time_is_rejected(self):
        e=self.event();e['main_thread_cpu_seconds']=-1
        with self.assertRaises(ValueError):self.validate(e)

    def test_inner_api_time_cannot_exceed_whole_call(self):
        e=self.event();e['api_wall_seconds']=5
        with self.assertRaises(ValueError):self.validate(e)


if __name__=='__main__':unittest.main()
