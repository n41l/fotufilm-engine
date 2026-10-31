#!/usr/bin/env python3
"""Synthetic worker events test controller rejection paths; these prove no GPU coverage."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('controller',Path(__file__).with_name('run-wavefront-baseline.py'))
controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)


class ControllerTests(unittest.TestCase):
    def test_resume_allows_only_controller_persistence_changes(self):
        freeze={'worker_sha256':'fixed','tool_sources':{'run-wavefront-baseline.py':'old','wavefront_metrics.py':'math'}}
        current={**freeze,'tool_sources':{**freeze['tool_sources'],'run-wavefront-baseline.py':'new'}}
        controller.validate_resume(freeze,current)
        current['tool_sources']['wavefront_metrics.py']='changed'
        with self.assertRaises(ValueError):controller.validate_resume(freeze,current)

    def test_recovery_preserves_invalid_round(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);image=root/'image';image.write_bytes(b'input')
            saved={'requested_mode':'B0','identity':{'input_sha256':controller.sha(image)},'scores':{'valid':False}}
            controller.atomic_json(root/'round.json',saved)
            with self.assertRaises(RuntimeError):controller.recover_round(root,'B0',image)
            self.assertEqual(json.loads((root/'round.json').read_text()),saved)

    def test_compact_checkpoint_does_not_duplicate_requests(self):
        result={'requests':[{'id':1}],'scores':{'valid':True}}
        self.assertEqual(controller.compact(result,Path('/round.json')),
                         {'scores':{'valid':True},'round_path':'/round.json'})

    def check(self,change=None,*,experimental=False,stderr=None):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);image=root/'input';image.write_bytes(bytes(16));pack=root/'pack';pack.write_bytes(b'fixture')
            memory={'device_current_bytes':100,'device_peak_bytes':120,'process_footprint_bytes':200,
                    'process_lifetime_peak_bytes':250,'buffer_allocations':1,'thermal_state':0}
            events=[{'type':'identity','clock_sample':0,'input_sha256':hashlib.sha256(image.read_bytes()).hexdigest()},
                    {'type':'call_complete','id':0,'phase':'warmup','started_at':0,'completed_at':5,'status':'success',
                     'actual_variant':'general','aot_calls':1,'gpu_dispatches':1},
                    {'type':'warmup_complete','output_sha256':'constant','memory':memory},
                    {'type':'window','t0':5,'t1':35,'deadline':37}]
            events += [{'type':'call_complete','id':i+1,'phase':'measurement','started_at':5+i*.5,
                        'completed_at':5.1+i*.5,'status':'success','actual_variant':'general',
                        'aot_calls':1,'gpu_dispatches':1} for i in range(40)]
            events += [{'type':'measurement_complete','output_sha256':'constant','memory':memory},
                       {'type':'retained','memory':memory}]
            if experimental:
                events[0]['height']=1080
                for event in events:
                    if event['type']=='call_complete':event.update(actual_variant='color_wavefront_negative_256',aot_calls=9,gpu_dispatches=9)
                if stderr is None:stderr='WAVEFRONT_POLICY requested=1 actual=1 rows=256 reason=admitted\nWAVEFRONT_COUNTS rows=1080 source_calls=4 consumer_calls=5 ring_rows=1024\n'
            if change:change(events)
            worker=root/'worker.py';worker.write_text('#!/usr/bin/env python3\nimport json\n'
                +'events=json.loads('+repr(json.dumps(events))+')\nfor e in events:print(json.dumps(e),flush=True)\n')
            if stderr:
                worker.write_text(worker.read_text()+'import sys\nsys.stderr.write('+repr(stderr)+')\n')
            worker.chmod(0o755)
            return controller.run_round(worker,pack,image,'E' if experimental else 'B0',root/'round',expected_band=256 if experimental else None)

    def test_consistent_synthetic_round(self):self.assertTrue(self.check()['scores']['valid'])
    def test_warmup_cancellation_rejected(self):self.assertFalse(self.check(lambda e:e[1].update(status='cancelled'))['scores']['valid'])
    def test_warmup_failure_rejected(self):self.assertFalse(self.check(lambda e:e[1].update(status='failure'))['scores']['valid'])
    def test_explicit_E_round(self):self.assertTrue(self.check(experimental=True)['scores']['valid'])
    def test_E_fallback_rejected(self):self.assertFalse(self.check(lambda e:e[5].update(actual_variant='general'),experimental=True)['scores']['valid'])
    def test_E_wrong_band_rejected(self):self.assertFalse(self.check(lambda e:e[5].update(actual_variant='color_wavefront_negative_64'),experimental=True)['scores']['valid'])
    def test_E_changed_call_count_rejected(self):self.assertFalse(self.check(lambda e:e[5].update(aot_calls=8),experimental=True)['scores']['valid'])
    def test_E_missing_dispatch_rejected(self):self.assertFalse(self.check(lambda e:e[5].update(gpu_dispatches=1),experimental=True)['scores']['valid'])
    def test_E_missing_admission_rejected(self):self.assertFalse(self.check(experimental=True,stderr='none')['scores']['valid'])
    def test_E_wrong_admission_rejected(self):self.assertFalse(self.check(experimental=True,stderr='WAVEFRONT_POLICY requested=1 actual=0 rows=256 reason=fallback\nWAVEFRONT_COUNTS rows=1080 source_calls=4 consumer_calls=5 ring_rows=1024\n')['scores']['valid'])
    def test_E_wrong_row_count_rejected(self):self.assertFalse(self.check(experimental=True,stderr='WAVEFRONT_POLICY requested=1 actual=1 rows=256 reason=admitted\nWAVEFRONT_COUNTS rows=1079 source_calls=4 consumer_calls=5 ring_rows=1024\n')['scores']['valid'])
    def test_E_warmup_cancellation_rejected(self):self.assertFalse(self.check(lambda e:e[1].update(status='cancelled'),experimental=True)['scores']['valid'])
    def test_changed_output_rejected(self):
        self.assertFalse(self.check(lambda e:e[-2].update(output_sha256='different'))['scores']['valid'])
    def test_missing_retained_rejected(self):self.assertFalse(self.check(lambda e:e.pop())['scores']['valid'])
    def test_unavailable_footprint_rejected_without_losing_record(self):
        self.assertFalse(self.check(lambda e:e[-1]['memory'].update(process_lifetime_peak_bytes=None))['scores']['valid'])
    def test_cancelled_request_rejected(self):
        self.assertFalse(self.check(lambda e:e[5].update(status='cancelled'))['scores']['valid'])
    def test_missing_aot_rejected(self):self.assertFalse(self.check(lambda e:e[5].update(aot_calls=0))['scores']['valid'])
    def test_R_multiple_aot_rejected(self):self.assertFalse(self.check(lambda e:e[5].update(aot_calls=2))['scores']['valid'])
    def test_missing_gpu_dispatch_rejected(self):
        self.assertFalse(self.check(lambda e:e[5].update(gpu_dispatches=0))['scores']['valid'])
    def test_experiment_cannot_be_B0(self):
        self.assertFalse(self.check(lambda e:e[5].update(actual_variant='color_wavefront_negative_256'))['scores']['valid'])
    def test_fallback_cannot_be_B0(self):
        self.assertFalse(self.check(lambda e:e[5].update(actual_variant='color_windowed'))['scores']['valid'])


if __name__=='__main__':unittest.main()
