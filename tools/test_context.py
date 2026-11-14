from pathlib import Path
import sys,unittest
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.context import HelicopterDetector

class ContextChecks(unittest.TestCase):
    def detector(self,rows,class_name='helicopter',class_id=1):
        d=HelicopterDetector.__new__(HelicopterDetector);d.np=np;d.cv2=cv2;d.name='images';d.class_name=class_name;d.class_id=class_id
        class Session:
            def run(self,*args):return [np.asarray(rows,np.float32).T[None]]
        d.session=Session();return d
    def test_airplane_is_not_relabelled_as_helicopter(self):
        d=self.detector([[320,320,120,60,.95,.6,0,0,0]])
        self.assertFalse(d.detect(np.zeros((480,852,3),np.uint8)))
    def test_explicit_heli_box_unletterboxes_and_deduplicates(self):
        d=self.detector([[320,320,120,60,.1,.9,0,0,0],[322,320,120,60,.1,.8,0,0,0]])
        out=d.detect(np.zeros((480,852,3),np.uint8));self.assertEqual(len(out),1);self.assertEqual(out[0].label,'helicopter')
        self.assertAlmostEqual((out[0].box[0]+out[0].box[2])/2,.5,delta=.01)
        self.assertAlmostEqual((out[0].box[1]+out[0].box[3])/2,.5,delta=.01)
    def test_giant_scene_box_is_not_held_gun_evidence(self):
        d=self.detector([[320,320,635,630,.95,.05],[320,320,20,15,.4,.05]],'pistol',0)
        out=d.detect(np.zeros((480,852,3),np.uint8),.18)
        self.assertEqual(len(out),1);self.assertLess((out[0].box[2]-out[0].box[0])*(out[0].box[3]-out[0].box[1]),.01)

if __name__=='__main__':unittest.main()
