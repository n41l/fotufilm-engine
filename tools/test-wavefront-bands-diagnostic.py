import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('bands',Path(__file__).with_name('run-wavefront-bands-diagnostic.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def proof(self):return {'results':[{'case':'4k','worker':worker,'band':band,'C_output_sha256':worker+str(band),'R_B1_output_sha256':'original'} for worker in ('bundle','bundletrace') for band in (512,1080)]}
 def test_512_uses_normal_proof_even_if_trace_differs(self):self.assertEqual(m.expected_output(self.proof(),'4k',512),'bundle512')
 def test_1080_uses_own_normal_proof(self):self.assertEqual(m.expected_output(self.proof(),'4k',1080),'bundle1080')
 def test_original_uses_original_proof(self):self.assertEqual(m.expected_output(self.proof(),'4k',None),'original')
 def test_missing_normal_proof_rejected(self):
  p=self.proof();p['results']=[x for x in p['results'] if x['worker']=='bundletrace']
  with self.assertRaises(ValueError):m.expected_output(p,'4k',1080)
if __name__=='__main__':unittest.main()
