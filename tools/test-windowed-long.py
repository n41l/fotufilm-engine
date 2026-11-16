import unittest
from pathlib import Path
from windowed_long_driver import generate
class DriverTests(unittest.TestCase):
 def test_preserves_protocol(self):
  s=generate(Path(__file__).with_name('wavefront-benchmark.mm').read_text())
  for anchor in ('now()-firstStart < 5.0','t1 = t0+30, deadline = t1+2','sleep_for(std::chrono::seconds(5))','@autoreleasepool {\n            error = fotufilm_halide'):
   self.assertIn(anchor,s)
  self.assertEqual(s.count('wfLongStart(id,phase,limit);'),1)
  self.assertEqual(s.count('NSDictionary *sample=wfLongFinish(id);'),1)
  self.assertIn('wfLongNext=t0+.5;',s)
  self.assertIn('t+.002<limit',s)
 def test_orders_balance_positions_and_predecessors(self):
  import importlib.util,collections
  spec=importlib.util.spec_from_file_location('long',Path(__file__).with_name('run-windowed-long.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  orders=module.ORDERS;cells=set(orders[0])
  self.assertEqual(len(orders),4)
  for position in range(4):self.assertEqual({row[position] for row in orders},cells)
  pairs=collections.Counter((a,b) for row in orders for a,b in zip(row,row[1:]))
  self.assertEqual(len(pairs),12);self.assertTrue(all(v==1 for v in pairs.values()))
 def test_changed_anchors_fail(self):
  s=Path(__file__).with_name('wavefront-benchmark.mm').read_text()
  with self.assertRaises(ValueError):generate(s.replace('const double completed = now();','const double completed = 0;'))
if __name__=='__main__':unittest.main()
