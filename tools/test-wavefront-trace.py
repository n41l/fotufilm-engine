#!/usr/bin/env python3
"""Synthetic trace validator rejection tests; these do not establish real GPU coverage."""
import unittest
from wavefront_trace import analyze,analyze_explicit


def fixture():
    return ['FRONTIER_EVENT 2 frame_through_gate_v48 1 0 6 0',
            'FRONTIER_EVENT 4 frame_through_gate_v48 2 1 6 1',
            'PRODUCE frame_through_gate_v48 0 32 -1 129 0 3',
            'FRONTIER_EVENT 5 frame_through_gate_v48 3 2 6 1',
            'FRONTIER_EVENT 6 frame_through_gate_v48 4 1 6 1',
            'FRONTIER_EVENT 7 frame_through_gate_v48 5 4 6 1',
            'FRONTIER_EVENT 4 frame_through_gate_v48 6 1 6 2',
            'PRODUCE frame_through_gate_v48 0 32 128 128 0 3',
            'GPU_COMPLETION 1 1 1 queue1 1 2 4',
            'GPU_COMPLETION 2 1 2 queue1 2 3 4',
            'GPU_COMPLETION 3 2 1 queue1 3 4 4',
            'GPU_COMPLETION 4 2 2 queue1 4 5 4']


class TraceTests(unittest.TestCase):
    def test_valid_regions_and_completed_consumers(self):self.assertTrue(analyze(fixture())['passed'])
    def test_recomputed_rows_rejected(self):
        lines=fixture();lines[7]=lines[7].replace('128 128','127 129')
        self.assertFalse(analyze(lines)['passed'])
    def test_overwrite_before_previous_consumers_finish_rejected(self):
        lines=fixture();lines[9]=lines[9].replace('2 3 4','2 3.1 4')
        self.assertFalse(analyze(lines)['passed'])
    def test_different_queues_rejected(self):
        lines=fixture();lines[-1]=lines[-1].replace('queue1','queue2')
        self.assertFalse(analyze(lines)['passed'])
    def test_missing_gpu_timestamps_rejected(self):self.assertFalse(analyze(fixture()[:-4])['passed'])
    def test_failed_command_rejected(self):
        lines=fixture();lines[-1]=lines[-1][:-1]+'5';self.assertFalse(analyze(lines)['passed'])
    def test_wrong_parent_rejected(self):
        lines=fixture();lines[3]=lines[3].replace('3 2 6','3 999 6');self.assertFalse(analyze(lines)['passed'])


class ExplicitTraceTests(unittest.TestCase):
    def lines(self):
        return ['ROW_PLAN 0 0 100 0 1024','PRODUCE frame_wavefront_light_output_v55 0 32 0 100 0 3',
                'CONSUMER_PLAN 0 0 64','BAND_COMPLETE 0','CONSUMER_PLAN 1 64 36','BAND_COMPLETE 1',
                'GPU_COMPLETION 1 1 1 q 1 2 4','GPU_COMPLETION 2 1 2 q 2 3 4',
                'GPU_COMPLETION 3 2 2 q 3 4 4',
                'WAVEFRONT_COUNTS rows=100 source_calls=1 consumer_calls=2 ring_rows=1024']
    def test_actual_regions_counts_and_completions(self):self.assertTrue(analyze_explicit(self.lines(),32,100,64,3)['passed'])
    def test_wrong_slot_rejected(self):
        lines=self.lines();lines[0]='ROW_PLAN 0 0 100 1 1024';self.assertFalse(analyze_explicit(lines,32,100,64,3)['passed'])
    def test_wrong_actual_producer_extent_rejected(self):
        lines=self.lines();lines[1]=lines[1].replace('0 100 0 3','0 99 0 3');self.assertFalse(analyze_explicit(lines,32,100,64,3)['passed'])
    def test_missing_gpu_completion_rejected(self):
        lines=self.lines();lines.pop(8);self.assertFalse(analyze_explicit(lines,32,100,64,3)['passed'])
    def test_extra_aot_call_rejected(self):self.assertFalse(analyze_explicit(self.lines(),32,100,64,4)['passed'])
    def test_uncompleted_consumer_rejected(self):
        lines=self.lines();lines.remove('BAND_COMPLETE 1');self.assertFalse(analyze_explicit(lines,32,100,64,3)['passed'])


if __name__=='__main__':unittest.main()
