from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,threading,queue
from unittest.mock import patch
from stickfigure.road import RoadWorker
from stickfigure.core import RoadGeometry
from stickfigure.video import VideoFrame


class RoadWorkerChecks(unittest.TestCase):
    def test_cancel_discards_old_road_and_uses_latest_frame(self):
        entered,release=threading.Event(),threading.Event()
        calls=[]
        class SlowSegmenter:
            def __init__(self,path):
                pass
            def segment(self,frame):
                calls.append(frame.timestamp)
                if len(calls)==1:
                    entered.set()
                    assert release.wait(3)
                return RoadGeometry((((0,.5),(1,.5),(1,1),(0,1)),),.5,.9),1
        with patch('stickfigure.road.RoadSegmenter',SlowSegmenter):
            worker=RoadWorker('unused')
            try:
                worker.submit(VideoFrame(1,0,1,1,b'\0\0\0'))
                self.assertTrue(entered.wait(2))
                worker.reset()
                for i in range(1,7):
                    worker.submit(VideoFrame(2,i,1,1,b'\0\0\0'))
                release.set()
                result=worker.results.get(timeout=3)
                self.assertEqual((result.epoch,result.generation,result.timestamp),(worker.epoch,2,6))
                self.assertEqual(calls,[0,6])
                with self.assertRaises(queue.Empty):
                    worker.results.get(timeout=.1)
            finally:
                release.set();worker.close();worker._thread.join(3)
                self.assertFalse(worker._thread.is_alive())

    def test_missing_road_model_reports_error(self):
        worker=RoadWorker(Path(__file__).parent/'missing-road.onnx')
        try:
            worker.submit(VideoFrame(1,0,1,1,b'\0\0\0'))
            epoch,message=worker.events.get(timeout=5)
            self.assertEqual(epoch,worker.epoch)
            self.assertTrue(message)
            self.assertTrue(worker.results.empty())
        finally:
            worker.close();worker._thread.join(3)
            self.assertFalse(worker._thread.is_alive())


if __name__=='__main__':
    unittest.main()
