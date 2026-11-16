"""Fail-closed isolated archive admission; rejected inputs never reach native compilation."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from wavefront_aot_driver import build
from windowed_mtf_helper import NAME
class Tests(unittest.TestCase):
 def attempt(self,mutate=lambda identity,folder:None,**options):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);control=root/'control';kernels=control/'kernels';kernels.mkdir(parents=True);(kernels/'.generated-from').write_text('frozen')
   (control/'control.json').write_text(json.dumps({'source':{},'artifacts':{}}));arm=root/'arm';arm.mkdir();archive=arm/(NAME+'.a');archive.write_bytes(b'fake archive')
   (arm/'source-key.txt').write_text('key');identity={'kind':'windowed-mtf','fusion':True,'windowed':True,'wavefront':False,'source_key':'key','archives':{archive.name:hashlib.sha256(archive.read_bytes()).hexdigest()}};mutate(identity,arm);(arm/'identity.json').write_text(json.dumps(identity))
   with patch('wavefront_aot_driver.subprocess.check_output',return_value='key'),patch('wavefront_aot_driver.subprocess.run') as native:
    with self.assertRaises(ValueError):build(root,kernels,root/'out',root/'driver.mm',diagnostic_control=control,diagnostic_kernels=arm,windowed_mtf_research=True,**options)
    native.assert_not_called()
 def test_integer_is_not_boolean(self):self.attempt(lambda i,p:i.update(fusion=1))
 def test_wrong_archive_rejected(self):self.attempt(lambda i,p:(p/'extra.a').write_bytes(b'wrong'))
 def test_hash_change_rejected(self):self.attempt(lambda i,p:(p/(NAME+'.a')).write_bytes(b'changed'))
 def test_wavefront_identity_rejected(self):self.attempt(lambda i,p:i.update(wavefront=True))
 def test_disabled_windowed_rejected(self):self.attempt(lambda i,p:i.update(windowed=False))
 def test_wavefront_host_rejected(self):self.attempt(definitions=('-DFOTUFILM_AOT_WAVEFRONT_HOST=1',))
 def test_mixed_research_rejected(self):self.attempt(general_research=True)
class ProofTests(unittest.TestCase):
 def setUp(self):
  import importlib.util
  s=importlib.util.spec_from_file_location('mtf_timing',Path(__file__).with_name('run-windowed-mtf-diagnostic.py'));self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)
 def rows(self):return {'results':[{'case':'4k','arm':a,'passed':True,'active':True,'actual':NAME,'output_sha256':a} for a in ('R-B1','W0','Fused')]}
 def test_own_arm_hash(self):self.assertEqual(self.m.expected_row(self.rows(),'4k','Fused')['output_sha256'],'Fused')
 def test_duplicate_rejected(self):
  p=self.rows();p['results'].append(p['results'][-1])
  with self.assertRaises(ValueError):self.m.expected_row(p,'4k','Fused')
 def test_inactive_rejected(self):
  p=self.rows();p['results'][-1]['active']=False
  with self.assertRaises(ValueError):self.m.expected_row(p,'4k','Fused')
 def test_failed_rejected(self):
  p=self.rows();p['results'][-1]['passed']=False
  with self.assertRaises(ValueError):self.m.expected_row(p,'4k','Fused')
if __name__=='__main__':unittest.main()
