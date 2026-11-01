import copy,unittest
from windowed_metal_analysis import analyze_methods,REQUIRED_COMPUTE
class MetalMethodTests(unittest.TestCase):
 def fixture(self):
  cpu=[{'kind':'encode_envelope','label':'sync','begin':.1,'end':1.0},{'kind':'encode_envelope','label':'_kernel_frame_x_s0_y','begin':2.,'end':8.}]
  events=[]
  def add(kind,token,a,b,**extra):events.append({'kind':kind,'command_token':token,'begin':a,'end':b,'argument':0,'bytes':0,**extra})
  for token,a,b in [(1,.1,.2),(2,2.,5.)]:
   add('command_create',token,a,b+.05);add('command_create_native',token,a,b,queue_limit=4,callback_pending_before=4);add('command_commit',token,1.1 if token==1 else 8.1,1.15 if token==1 else 8.15)
  for kind in REQUIRED_COMPUTE:add(kind,2,5.,5.,bytes=56*1024**2 if kind=='buffer_bind' else 0)
  next(e for e in events if e['kind']=='pipeline_create')['end']=7.
  lookup=next(e for e in events if e['kind']=='function_lookup');lookup.update(begin=5.5,end=6.)
  return {'api_begin':0.,'api_end':10.,'probes':True,'method_probes':True,'cpu':cpu,'commands':[{'label':'sync','gpu_start':1.2,'gpu_end':4.},{'label':'_kernel_frame_x_s0_y','gpu_start':8.5,'gpu_end':9.5}],'metal_methods':events,'method_commands':[{'token':1,'gpu_index':0,'label':'sync'},{'token':2,'gpu_index':1,'label':'_kernel_frame_x_s0_y'}]}
 def test_native_coverage_excludes_wrapper_and_unions_nested_methods(self):
  d=analyze_methods(self.fixture());cmd=d['per_command'][1];self.assertAlmostEqual(cmd['native_methods_covered_ms'],5000);self.assertAlmostEqual(cmd['encoding_residual_ms'],1000)
 def test_factory_overlap_uses_older_gpu_work(self):
  d=analyze_methods(self.fixture());self.assertAlmostEqual(d['per_command'][1]['factory_previous_gpu_overlap_ms'],2000);self.assertEqual(d['observed_queue_limit_histogram'],{4:2})
 def test_queue_limit_is_observed_not_assumed(self):
  f=self.fixture();next(e for e in f['metal_methods'] if e['kind']=='command_create_native')['queue_limit']=64
  with self.assertRaisesRegex(ValueError,'queue limit'):analyze_methods(f)
 def test_duplicate_or_missing_links_rejected(self):
  f=self.fixture();f['method_commands']*=2
  with self.assertRaisesRegex(ValueError,'link'):analyze_methods(f)
 def test_missing_requested_method_rejected(self):
  f=self.fixture();f['metal_methods']=[e for e in f['metal_methods'] if e['kind']!='dispatch']
  with self.assertRaisesRegex(ValueError,'coverage'):analyze_methods(f)
 def test_disabled_is_unavailable_not_zero_cost(self):
  f=self.fixture();f.update(method_probes=False,metal_methods=[],method_commands=[]);self.assertEqual(analyze_methods(f),{'methods_available':False})
 def test_outside_api_interval_rejected(self):
  f=self.fixture();f['metal_methods'][0]['end']=11
  with self.assertRaisesRegex(ValueError,'interval'):analyze_methods(f)
 def test_binding_records_physical_length_without_changing_request(self):
  d=analyze_methods(self.fixture());self.assertEqual(d['bound_buffer_length_histogram'],{56*1024**2:1})
if __name__=='__main__':unittest.main()
