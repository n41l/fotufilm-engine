import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('general',Path(__file__).with_name('run-general-optimizations-diagnostic.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def proof(self):return {'results':[{'case':'4k','arm':a,'output_sha256':a,'actual':a,'passed':True} for a in m.ORDER]}
 def test_own_arm_hash_used(self):
  p=self.proof()
  self.assertEqual(m.expected_row(p,'4k','normalized')['output_sha256'],'normalized')
  self.assertEqual(m.expected_row(p,'4k','G0')['output_sha256'],'G0')
 def test_missing_arm_rejected(self):
  with self.assertRaises(ValueError):m.expected_row(self.proof(),'4k','missing')
 def test_failed_proof_rejected(self):
  p=self.proof();p['results'][0]['passed']=False
  with self.assertRaises(ValueError):m.expected_row(p,'4k','R-B0')
 def test_duplicate_proof_rejected(self):
  p=self.proof();p['results'].append(p['results'][0])
  with self.assertRaises(ValueError):m.expected_row(p,'4k','R-B0')
if __name__=='__main__':unittest.main()
