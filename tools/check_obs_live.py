"""Measure the normal OBS input and preset rendering path with saved settings."""
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base))
from stickfigure.app import Application, SOURCES
from stickfigure.core import RunState
from export_v015 import raster


class LiveCheck(Application):
    def __init__(self):
        super().__init__(base)
        self.received = 0
        self.observed = {name: set() for name in ('preview', 'objects', 'environment', 'ocr')}
        self.video.frame_observer = self.receive

    def receive(self, frame):
        self.received += 1
        self.fire_detector.submit(frame)

    def _tick(self):
        super()._tick()
        for name, value in (
            ('preview', self.video_frame),
            ('objects', self.detection_result),
            ('environment', self.road_result),
            ('ocr', self.text_result),
        ):
            if value is not None and value.generation == self.video.generation:
                self.observed[name].add(value.timestamp)


app = LiveCheck()
app.source_var.set(SOURCES[1])
app._source_changed()
app.start()
deadline = time.perf_counter() + 25
measurement = None
report = None
reconnected = False
vehicle_sample = False


def poll():
    global measurement, report, reconnected, deadline, vehicle_sample
    try:
        now = time.perf_counter()
        assert now < deadline and app.state_value != RunState.ERROR, app.video_info_text.get()
        if measurement is not None and not vehicle_sample and app.video_frame:
            scene = app._presentation_scene(app.scene)
            if scene and any(actor.kind == 'car' for actor in scene.entities):
                output = raster(app.output_canvas, scene)
                frame = app.video_frame
                source = np.frombuffer(frame.pixels, np.uint8).reshape(frame.height, frame.width, 3)
                source = cv2.resize(cv2.cvtColor(source, cv2.COLOR_RGB2BGR), output.shape[1::-1])
                proof = np.hstack((source, output))
                cv2.imencode('.png', proof)[1].tofile(str(app.runtime / 'obs-gta5-output.png'))
                vehicle_sample = True
        if reconnected:
            if app.video_frame is not None and app.video_frame.timestamp >= .5:
                report['stop_and_reconnect'] = True
                (app.runtime / 'obs-live-test.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(report, ensure_ascii=False), flush=True)
                app.close()
                return
        elif measurement is None:
            if app.video_frame is not None and app.video_frame.timestamp >= 3:
                measurement = (now, app.received, app.output_canvas._frame_serial,
                               {key: len(values) for key, values in app.observed.items()})
        elif now - measurement[0] >= 12:
            began, received, draws, counts = measurement
            seconds = now - began
            report = {
                'seconds': round(seconds, 2),
                'input_fps': round((app.received - received) / seconds, 1),
                'canvas_fps': round((app.output_canvas._frame_serial - draws) / seconds, 1),
                'updates_hz': {key: round((len(values) - counts[key]) / seconds, 1)
                               for key, values in app.observed.items()},
                'profile': app.model_profile_var.get(),
                'down_recovery': app.down_recovery_var.get(),
                'ocr_roi': app.text_roi,
                'object_status': app.ai_status_var.get(),
                'vehicle_sample': vehicle_sample,
            }
            print(json.dumps(report, ensure_ascii=False), flush=True)
            assert vehicle_sample, 'No vehicle preset during measurement'
            assert report['input_fps'] > 20 and report['updates_hz']['objects'] > 0, report
            generation = app.video.generation
            app.stop()
            assert app.video_frame is None and app.scene is None
            app.start()
            assert app.video.generation != generation
            deadline = now + 10
            reconnected = True
        app.after(100, poll)
    except Exception:
        app._smoke_failure()


app.after(100, poll)
app.mainloop()
sys.exit(int(app.test_failed))
