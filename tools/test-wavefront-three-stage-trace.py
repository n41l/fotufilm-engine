#!/usr/bin/env python3
"""Trace acceptance rejection tests; synthetic data is not GPU evidence."""
import importlib.util
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('three_trace',Path(__file__).with_name('verify-wavefront-three-stage-trace.py'))
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def fixture():
    lines=['ROW_PLAN 0 0 1025 0 2048','PRODUCE frame_wavefront_light_output_v58 0 32 0 1025 0 3']
    for band,n in ((0,512),(1,512),(2,1)):
        y=band*512
        lines += [f'LOG_PLAN {band} {y} {n} {y%1024} 1024',f'PRODUCE frame_wavefront_log_output_v61 0 32 {y} {n} 0 3',
            f'CONSUMER_PLAN {band} {y} {n}',f'BAND_COMPLETE {band}']
    for i,(band,phase) in enumerate(((0,1),(0,3),(0,2),(1,3),(1,2),(2,3),(2,2))):
        lines += [f'GPU_COMPLETION {i+1} {band+1} {phase} q {i+1} {i+2} 4',f'GPU_KERNEL {band+1} {phase} kernel']
    return lines+['THREE_STAGE_COUNTS light_rows=1025 log_rows=1025 light_calls=1 log_calls=3 output_calls=3 log_ring_rows=1024 log_reach=0 halo_reach=0']


class TraceTests(unittest.TestCase):
    def check(self,lines,dispatches=7):return m.analyze(lines,32,1025,7,dispatches)['passed']
    def test_complete_wrap(self):self.assertTrue(self.check(fixture()))
    def test_missing_actual_log_production(self):
        lines=fixture();lines.remove('PRODUCE frame_wavefront_log_output_v61 0 32 1024 1 0 3')
        self.assertFalse(self.check(lines))
    def test_log_reads_before_light_ready(self):
        lines=fixture();lines=lines[2:4]+lines[:2]+lines[4:]
        self.assertFalse(self.check(lines))
    def test_wrap_before_old_output_finishes(self):
        lines=fixture();lines=lines[:4]+lines[6:8]+lines[10:12]+lines[4:6]+lines[8:10]+lines[12:]
        self.assertFalse(self.check(lines))
    def test_gpu_previous_band_still_running(self):
        lines=[x.replace('GPU_COMPLETION 3 1 2 q 3 4 4','GPU_COMPLETION 3 1 2 q 3 4.5 4') for x in fixture()]
        self.assertFalse(self.check(lines))
    def test_missing_actual_dispatch(self):self.assertFalse(self.check(fixture(),8))
    def test_cross_queue(self):self.assertFalse(self.check([x.replace(' 2 q ',' 2 other ') for x in fixture()]))


if __name__=='__main__':unittest.main()
