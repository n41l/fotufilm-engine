"""Fail-closed isolated archive admission; rejected inputs never reach native compilation."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from wavefront_aot_driver import build
from windowed_unit_helper import NAMES
NAME=NAMES[0]
class Tests(unittest.TestCase):
 def attempt(self,mutate=lambda identity,folder:None,**options):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);control=root/'control';kernels=control/'kernels';kernels.mkdir(parents=True);(kernels/'.generated-from').write_text('frozen')
   (control/'control.json').write_text(json.dumps({'source':{},'artifacts':{}}));arm=root/'arm';arm.mkdir();archive=arm/(NAME+'.a');archive.write_bytes(b'fake archive')
   (arm/(NAMES[1]+'.a')).write_bytes(b'fake archive');(arm/'source-key.txt').write_text('key');identity={'kind':'windowed-coupler','fusion':True,'unit_stride':True,'windowed':True,'wavefront':False,'mtf_fusion':False,'source_key':'key','archives':{n+'.a':hashlib.sha256(b'fake archive').hexdigest() for n in NAMES}};mutate(identity,arm);(arm/'identity.json').write_text(json.dumps(identity))
   with patch('wavefront_aot_driver.subprocess.check_output',return_value='key'),patch('wavefront_aot_driver.subprocess.run') as native:
    with self.assertRaises(ValueError):build(root,kernels,root/'out',root/'driver.mm',diagnostic_control=control,diagnostic_kernels=arm,windowed_coupler_research=True,**options)
    native.assert_not_called()
 def test_integer_is_not_boolean(self):self.attempt(lambda i,p:i.update(fusion=1))
 def test_wrong_archive_rejected(self):self.attempt(lambda i,p:(p/'extra.a').write_bytes(b'wrong'))
 def test_hash_change_rejected(self):self.attempt(lambda i,p:(p/(NAME+'.a')).write_bytes(b'changed'))
 def test_wavefront_identity_rejected(self):self.attempt(lambda i,p:i.update(wavefront=True))
 def test_disabled_windowed_rejected(self):self.attempt(lambda i,p:i.update(windowed=False))
 def test_wavefront_host_rejected(self):self.attempt(definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1',))
 def test_mixed_research_rejected(self):self.attempt(general_research=True)
 def test_mtf_research_rejected(self):self.attempt(windowed_mtf_research=True)
 def test_mtf_combination_rejected(self):self.attempt(lambda i,p:i.update(mtf_fusion=True))
 def test_unit_requires_fusion(self):self.attempt(lambda i,p:i.update(fusion=False))
 def test_unit_requires_boolean(self):self.attempt(lambda i,p:i.update(unit_stride=1))
class ProofTests(unittest.TestCase):
 def setUp(self):
  import importlib.util
  s=importlib.util.spec_from_file_location('mtf_timing',Path(__file__).with_name('run-windowed-unit-diagnostic.py'));self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)
 def rows(self):return {'results':[{'case':'4k','arm':a,'passed':True,'active':True,'actual':NAME,'output_sha256':a} for a in ('R-B1','Generic','Unit')]}
 def test_own_arm_hash(self):self.assertEqual(self.m.expected_row(self.rows(),'4k','Unit')['output_sha256'],'Unit')
 def test_duplicate_rejected(self):
  p=self.rows();p['results'].append(p['results'][-1])
  with self.assertRaises(ValueError):self.m.expected_row(p,'4k','Unit')
 def test_inactive_rejected(self):
  p=self.rows();p['results'][-1]['active']=False
  with self.assertRaises(ValueError):self.m.expected_row(p,'4k','Unit')
 def test_failed_rejected(self):
  p=self.rows();p['results'][-1]['passed']=False
  with self.assertRaises(ValueError):self.m.expected_row(p,'4k','Unit')
if __name__=='__main__':unittest.main()
