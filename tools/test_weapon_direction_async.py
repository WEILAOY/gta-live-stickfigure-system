from pathlib import Path
import sys, unittest, threading, time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.shooting import ShotDetector
from stickfigure.hud import HudObservation
from stickfigure.detection import Detection
from stickfigure.video import VideoFrame
from stickfigure.core import Joint

class DirectionAndScheduling(unittest.TestCase):
    def test_both_camera_sides_attach_gun_and_flash_to_same_owner(self):
        for box, sign in (((.2,.5,.4,1),1),((.6,.5,.8,1),-1)):
            d=ShotDetector(weapon_model=False,hud_enabled=False)
            d.hud_observation=HudObservation('rifle',30,.95);d.hud_generation=1;d.hud_time=.1
            d.set_targets((Detection('person',.9,box,'player'),),1,0)
            hold=d.get_holds(1,.1)['player']
            self.assertGreater(hold.dx*sign,0)
            self.assertLess(hold.x,(box[0]+box[2])/2) if sign<0 else self.assertGreater(hold.x,(box[0]+box[2])/2)
            d.hud_shots.append((1,.1,'rifle'));d._bind_hud()
            flash=d.events.get_nowait()
            self.assertEqual((flash.x,flash.dx,flash.owner),(hold.x,hold.dx,'player'))
        # Screen side is only a fallback: reliable arms can point the other way.
        pose=[Joint(0,0,0)]*33
        for i in (11,12):pose[i]=Joint(.65,.6,1)
        for i in (15,16):pose[i]=Joint(.76,.65,1)
        d.set_targets((Detection('person',.9,(.6,.5,.8,1),'player',pose=tuple(pose)),),1,.1)
        self.assertGreater(d.get_holds(1,.1)['player'].dx,0)

    def test_slow_analysis_never_blocks_decoder_or_ui_and_drops_backlog(self):
        d=ShotDetector(weapon_model=False,hud_enabled=False)
        entered=threading.Event();release=threading.Event();seen=[]
        def slow(frame):
            seen.append(frame.timestamp)
            if len(seen)==1:entered.set();release.wait(3)
        d.process=slow
        try:
            d.submit(VideoFrame(1,0,1,1,b''));self.assertTrue(entered.wait(1))
            began=time.perf_counter()
            for i in range(1,101):d.submit(VideoFrame(1,i,1,1,b''))
            d.set_targets((),1,100);d.get_holds(1,100)
            self.assertLess(time.perf_counter()-began,.15)
            release.set()
            until=time.perf_counter()+1
            while len(seen)<2 and time.perf_counter()<until:time.sleep(.005)
            self.assertEqual(seen,[0,100])
        finally:release.set();d.close()

    def test_reset_discards_queued_frames_and_close_stops_worker(self):
        d=ShotDetector(weapon_model=False,hud_enabled=False)
        d.submit(VideoFrame(1,0,1,1,b''));d.reset();d.close();d._worker.join(1)
        self.assertFalse(d._worker.is_alive())

if __name__=='__main__':unittest.main()
