import unittest
from windowed_pool_analysis import analyze
class PoolAnalysisTests(unittest.TestCase):
 def fixture(self):
  t={'errors':[],'physical':[{'id':1,'length':48,'freed':15},{'id':2,'length':48,'freed':0}],'leases':[{'physical':2,'requested':47}],'fences':[{'delivered':True,'status':4,'commit':1,'complete':2}],'markers':[{'name':'frame_begin','frame':0,'event':10},{'name':'frame_end','frame':0,'event':20}]}
  a={'attempts':[{'begin':11,'end':16,'physical':2,'fresh':True,'requested':47,'rounded':48,'frame_depth':1,'capacity':100,'before':[{'physical':1,'length':48,'state':2,'fence_status':4}],'after':[{'physical':2,'length':48,'state':0,'fence_status':0}]}]};return t,a
 def test_reclaim_removal_has_physical_free_inside_call(self):
  t,a=self.fixture();r=analyze(t,a)['frames'][0];self.assertEqual(r['fresh_count'],1);self.assertEqual(r['reclaim_evictions'][0]['evicted'][0]['length'],48)
  t['physical'][0]['freed']=19;self.assertFalse(analyze(t,a)['frames'][0]['reclaim_evictions'])
 def test_undersized_physical_allocation_rejected(self):
  t,a=self.fixture();t['leases'][0]['requested']=49
  with self.assertRaisesRegex(ValueError,'undersized'):analyze(t,a)
 def test_missing_gpu_completion_cannot_validate_reuse(self):
  t,a=self.fixture();t['fences'][0]['delivered']=False
  with self.assertRaisesRegex(ValueError,'completion'):analyze(t,a)
 def test_snapshot_pending_and_idle_are_distinct(self):
  t,a=self.fixture();x=a['attempts'][0];x['before']=[{'physical':1,'length':48,'state':2,'fence_status':3},{'physical':2,'length':56,'state':1,'fence_status':0}];r=analyze(t,a)['frames'][0]['fresh'][0];self.assertEqual(r['idle_exact'],0);self.assertEqual(r['returned_exact_pending'],1);self.assertEqual(r['idle_larger_eligible'],1)
if __name__=='__main__':unittest.main()
