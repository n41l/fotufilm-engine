#!/usr/bin/env python3
"""Check diagnostic comparison validity and units, without executing GPU work."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('diagnostic',Path(__file__).with_name('run-wavefront-latency-diagnostic.py'))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def score(t, valid=True):
    return {'valid':valid,'median_seconds':t,'p95_seconds':t*1.5,
        'throughput_fps':1/t,'request_count':100}

class LatencyDiagnosticTests(unittest.TestCase):
    def pairs(self):
        return [{'band':b,'R':{'scores':score(.01)},'E':{'scores':score(.02)}} for b in (64,128,256)]
    def test_milliseconds_and_adjacent_reference_ratio(self):
        p=self.pairs();p[1]['R']['scores']=score(.02)
        r=m.summarize_pairs(p)
        self.assertEqual(r['pairs'][0]['R_median_ms'],10)
        self.assertEqual(r['pairs'][0]['E_p95_ms'],30)
        self.assertEqual([x['E_over_adjacent_R_median_ratio'] for x in r['pairs']],[2,1,2])
    def test_invalid_round_does_not_supply_accepted_ratio(self):
        p=self.pairs();p[0]['E']['scores']['valid']=False
        r=m.summarize_pairs(p)
        self.assertFalse(r['all_rounds_valid'])
        self.assertIsNone(r['pairs'][0]['E_over_adjacent_R_median_ratio'])
        self.assertEqual(r['pairs'][0]['E_median_ms'],20)
    def test_reference_variation_requires_review(self):
        p=self.pairs();p[1]['R']['scores']=score(.012)
        r=m.summarize_pairs(p)
        self.assertTrue(r['R_timing_review_required'])
        self.assertAlmostEqual(r['R_median_range_ratio'],.2)
    def test_incomplete_controls_cannot_be_stable(self):
        r=m.summarize_pairs(self.pairs()[:2])
        self.assertFalse(r['all_rounds_valid'])
        self.assertIsNone(r['R_median_range_ratio'])
        self.assertTrue(r['R_timing_review_required'])
    def test_complete_valid_diagnostic_never_freezes_reference(self):
        r=m.summarize_pairs(self.pairs())
        self.assertTrue(r['all_rounds_valid'])
        self.assertFalse(r['B_ref_frozen'])
        self.assertFalse(r['performance_acceptance'])

if __name__=='__main__':unittest.main()
