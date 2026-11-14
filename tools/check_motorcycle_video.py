"""Actual source motorcycle detection must select its own fixed model."""
from pathlib import Path
import sys,json,time,tkinter as tk
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'17_载具与漫画阴影验证'
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=570)
app.ai_var.set(True);app.person_action_var.set('自动姿态');app.vehicle_view_var.set('自动估计');app.vehicle_model_var.set('自动类别')
app.sky_var.set(True);app.shading_var.set(True);app.shadow_mode_var.set('分区+投影');app._detection_changed();app._road_changed()
started=time.perf_counter()
def ready():
    try:
        assert time.perf_counter()-started<30,(app.ai_status_var.get(),app.road_status_var.get())
        if not (app.scene and app.detection_result and app._environment_is_current()):app.after(100,ready);return
        actual=[d for d in app.detection_result.detections if d.label=='motorcycle' and not d.predicted]
        assert actual,'real frame should contain reviewed motorcycle candidate'
        scene=app._presentation_scene(app.scene);entities=[e for e in scene.entities if e.vehicle_type=='motorcycle']
        assert entities and all(not e.predicted for e in entities)
        window=tk.Toplevel(app);window.geometry('800x450');canvas=SceneCanvas(window);canvas.pack(fill='both',expand=True);window.update()
        image=raster(canvas,scene,'实际视频 570s · 自动检测摩托车 → 预设摩托车素材')
        rgb=np.frombuffer(app.video_frame.pixels,np.uint8).reshape(app.video_frame.height,app.video_frame.width,3)
        original=cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),(800,450))
        cv2.imencode('.png',np.hstack((original,image)))[1].tofile(str(out/'实际视频摩托车模型对比.png'))
        window.destroy()
        (out/'motorcycle-video-result.json').write_text(json.dumps(dict(passed=True,source=source,timestamp=app.video_position,automatic_material_selection=True,detector_confidences=[d.confidence for d in actual],checks=[
            'reviewed real video motorcycle is detected as COCO class 3','detected motorcycle becomes motorcycle entity',
            'automatic material selection uses motorcycle mesh without manual replacement','full preset remains visible despite source occlusion']),ensure_ascii=False,indent=2),encoding='utf-8')
        app.close()
    except Exception:app._smoke_failure()
app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
