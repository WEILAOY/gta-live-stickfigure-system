"""GPU selection and fallback must not break plain CPU operation."""
from pathlib import Path
import sys,unittest,os,threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import onnxruntime as ort
from stickfigure.inference import create_session,GpuSession

class InferenceChecks(unittest.TestCase):
    def test_separate_gpu_sessions_do_not_run_concurrently(self):
        first_entered,second_attempt,second_entered,release= (threading.Event() for _ in range(4))
        class First:
            def run(self):first_entered.set();assert release.wait(2)
        class Second:
            def run(self):second_entered.set()
        a,b=GpuSession(First()),GpuSession(Second())
        def call_second():second_attempt.set();b.run()
        ta=threading.Thread(target=a.run);tb=threading.Thread(target=call_second)
        try:
            ta.start();self.assertTrue(first_entered.wait(1))
            tb.start();self.assertTrue(second_attempt.wait(1))
            self.assertFalse(second_entered.wait(.05))
        finally:
            release.set();ta.join(2);tb.join(2)
        self.assertTrue(second_entered.is_set())
    def test_nvidia_adapter_selected_and_directml_options_are_valid(self):
        class Session:
            def get_providers(self):return ['DmlExecutionProvider','CPUExecutionProvider']
        adapters=({'index':0,'name':'Intel','vendor':32902},{'index':1,'name':'NVIDIA','vendor':0x10de})
        with patch.dict(os.environ,{'STICKFIGURE_CPU':'0'}), \
             patch('stickfigure.inference.windows_adapters',return_value=adapters), \
             patch.object(ort,'get_available_providers',return_value=['DmlExecutionProvider','CPUExecutionProvider']), \
             patch.object(ort,'InferenceSession',return_value=Session()) as factory:
            session,backend=create_session('model')
            args=factory.call_args.kwargs
            self.assertEqual(args['providers'][0],('DmlExecutionProvider',{'device_id':'1'}))
            self.assertFalse(args['sess_options'].enable_mem_pattern)
            self.assertEqual(args['sess_options'].execution_mode,ort.ExecutionMode.ORT_SEQUENTIAL)
            self.assertIn('NVIDIA',backend)

    def test_gpu_initialization_failure_falls_back_to_cpu(self):
        with patch.dict(os.environ,{'STICKFIGURE_CPU':'0'}), \
             patch('stickfigure.inference.windows_adapters',return_value=()), \
             patch.object(ort,'get_available_providers',return_value=['DmlExecutionProvider','CPUExecutionProvider']), \
             patch.object(ort,'InferenceSession',side_effect=[RuntimeError('device unavailable'),object()]) as factory:
            session,backend=create_session('model')
            self.assertEqual(factory.call_args.kwargs['providers'],['CPUExecutionProvider'])
            self.assertTrue(backend.startswith('CPU'))

    def test_explicit_cpu_mode_does_not_initialize_gpu(self):
        with patch.dict(os.environ,{'STICKFIGURE_CPU':'1'}), \
             patch.object(ort,'InferenceSession',return_value=object()) as factory:
            session,backend=create_session('model')
            self.assertEqual(factory.call_count,1)
            self.assertEqual(factory.call_args.kwargs['providers'],['CPUExecutionProvider'])

if __name__=='__main__':unittest.main()
