"""Race and degradation checks for asynchronous detection."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import queue
import threading
import unittest
from unittest.mock import patch
from stickfigure.detection import DetectionWorker, Detection,person_fragment
from stickfigure.video import VideoFrame


class WorkerChecks(unittest.TestCase):
    def test_model_switch_discards_old_inflight_result_and_loads_new_model(self):
        entered,release=threading.Event(),threading.Event()
        loaded=[]
        class FakeDetector:
            backend='test'
            def __init__(self,path):
                self.path=Path(path).name;loaded.append(self.path)
            def detect_rgb(self,*args):
                if self.path=='old':
                    entered.set();assert release.wait(3)
                return (Detection('person',.9,(.1,.2,.3,.9)),),1,1
        with patch('stickfigure.detection.YoloXDetector',FakeDetector):
            worker=DetectionWorker('old',analysis_enabled=False)
            try:
                worker.submit(VideoFrame(1,0,1,1,b'\0\0\0'))
                self.assertTrue(entered.wait(2))
                worker.set_model('new')
                worker.submit(VideoFrame(1,1,1,1,b'\0\0\0'));release.set()
                result=worker.results.get(timeout=3)
                self.assertEqual(result.epoch,worker.epoch)
                self.assertEqual(result.timestamp,1)
                self.assertEqual(loaded,['old','new'])
                with self.assertRaises(queue.Empty):worker.results.get(timeout=.1)
            finally:
                release.set();worker.close();worker._thread.join(3)

    def test_person_fragment_filter_preserves_adjacent_people(self):
        person=Detection('person',.8,(.3,.2,.5,.9))
        fragment=Detection('person',.35,(.31,.205,.49,.4))
        neighbor=Detection('person',.4,(.46,.23,.58,.5))
        self.assertTrue(person_fragment(fragment,person))
        self.assertFalse(person_fragment(neighbor,person))
        self.assertFalse(person_fragment(Detection('person',.7,fragment.box),person))

    def test_reset_discards_inflight_and_only_runs_latest_pending_frame(self):
        entered,release = threading.Event(),threading.Event()
        timestamps = []

        class SlowDetector:
            backend="test"
            def __init__(self,path):
                pass
            def detect_rgb(self,pixels,width,height):
                timestamps.append(pixels[0])
                if len(timestamps)==1:
                    entered.set()
                    if not release.wait(3):
                        raise RuntimeError("test gate timed out")
                return (Detection("person",.9,(.1,.2,.3,.9)),),1,1

        with patch("stickfigure.detection.YoloXDetector",SlowDetector):
            worker=DetectionWorker("unused",analysis_enabled=False)
            try:
                worker.submit(VideoFrame(1,0,1,1,b"\x01\x00\x00"))
                self.assertTrue(entered.wait(2))
                worker.reset()
                for i in range(2,10):
                    worker.submit(VideoFrame(2,i,1,1,bytes((i,0,0))))
                release.set()
                result=worker.results.get(timeout=3)
                self.assertEqual(result.epoch,worker.epoch)
                self.assertEqual(result.timestamp,9)
                self.assertEqual(result.generation,2)
                self.assertEqual(timestamps,[1,9])
                with self.assertRaises(queue.Empty):
                    worker.results.get(timeout=.1)
            finally:
                release.set()
                worker.close()
                worker._thread.join(timeout=3)
                self.assertFalse(worker._thread.is_alive())

    def test_missing_model_reports_error_without_fabricated_detections(self):
        worker=DetectionWorker(Path(__file__).parent/"missing-model.onnx")
        try:
            worker.submit(VideoFrame(1,0,1,1,b"\x00\x00\x00"))
            while True:
                epoch,kind,payload=worker.events.get(timeout=5)
                if kind=="error":
                    break
            self.assertTrue(payload)
            self.assertEqual(epoch,worker.epoch)
            self.assertTrue(worker.results.empty())
        finally:
            worker.close()
            worker._thread.join(timeout=3)
            self.assertFalse(worker._thread.is_alive())


if __name__=="__main__":
    unittest.main()
