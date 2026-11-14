"""New fixed models, local angle invariants, bound-only correction and proof."""
from pathlib import Path
import sys,json,tkinter as tk,unittest
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.assets import vehicle_drawing,MODEL_GALLERIES
from stickfigure.core import Scene,Entity
from stickfigure.rendering import SceneCanvas
from stickfigure.vision import estimate_vehicle_view
from stickfigure.detection import YoloXDetector
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'19_货车船与方向验证';out.mkdir(exist_ok=True)
root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
tiles=[]
for kind,label in (('truck','货车'),('boat','船')):
    row=[]
    for i,yaw in enumerate((0,45,90,135,180,225,270,315,0)):
        pitch=78 if i==8 else 22
        art=vehicle_drawing(yaw,pitch,kind)
        assert all(-1e-8<=v<=1+1e-8 for s in art.shapes for v in s.points)
        e=Entity('material','car',.5,.85,bbox=(.15,.15,.85,.85),yaw=yaw,pitch=pitch,vehicle_type=kind)
        scene=Scene(0,0,1,0,(e,),frame_clipping=True)
        row.append(cv2.resize(raster(canvas,scene,label+' · '+('俯视' if i==8 else str(yaw)+'°')+' · 预设素材'),(400,225)))
        for box in ((-.2,.3,.3,.8),(.7,.3,1.2,.8),(.3,-.2,.7,.3),(.3,.8,.7,1.2)):
            canvas.draw(replace(scene,entities=(replace(e,bbox=box),)))
            assert canvas.find_withtag('vehicle')
            assert all(0<=b[0]<b[2]<=800 and 0<=b[1]<b[3]<=450 for p,b in canvas._layer_cache.values() if p)
    sheet=np.vstack([np.hstack(row[i:i+3]) for i in (0,3,6)])
    cv2.imencode('.png',sheet)[1].tofile(str(out/(label+'九视图.png')));tiles.append(sheet)
root.destroy();cv2.imencode('.png',np.vstack(tiles))[1].tofile(str(out/'货车与船多视角.png'))
# The same crop's image position and red body paint cannot flip its heading.
image=np.full((400,800,3),120,np.uint8)
left=estimate_vehicle_view(image,(.1,.3,.4,.6),0)[0]
right=estimate_vehicle_view(image,(.6,.3,.9,.6),0)[0];assert abs(left-right)<1e-6
red=image.copy();red[:]=(220,20,20)
assert estimate_vehicle_view(red,(.1,.3,.4,.6),180)[0]>90
assert estimate_vehicle_view(image,(0,.3,.4,.6),42)==(42,.1)
side=estimate_vehicle_view(image,(.1,.4,.5,.6),0)[0]
front=estimate_vehicle_view(image,(.1,.3,.2,.7),0)[0];assert side>70 and front<10
# Raw boat class is wired without obtaining another model or cloud call.
detector=YoloXDetector.__new__(YoloXDetector);detector.np=np;detector.cv2=cv2
detector.width=detector.height=32;detector.grid=np.zeros((1,2),np.float32);detector.strides=np.ones((1,1),np.float32);detector.input_name='input'
output=np.zeros((1,1,85),np.float32);output[0,0,:5]=(16,16,np.log(24),np.log(12),1);output[0,0,13]=.9
class Session:
    def run(self,*args):return [output]
detector.session=Session();assert detector.detect_rgb(bytes(32*32*3),32,32)[0][0].label=='boat'
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True);app._restore_automatic()
one=Entity('one','car',.3,.8,bbox=(.1,.4,.5,.8),yaw=90)
two=Entity('two','car',.7,.8,bbox=(.6,.5,.8,.8),yaw=0)
raw=Scene(0,0,1,0,(one,two));app.scene=raw;app.primary_id='one'
app._correct_vehicle(90);presented=app._presentation_scene(raw)
assert [e.yaw for e in presented.entities]==[180,0]
app.clear_primary(False);assert not app._vehicle_corrections
assert [e.yaw for e in app._presentation_scene(raw).entities]==[90,0]
app.tabs.select(app.appearance_tab);app.update_idletasks()
for group in ('货车九视图','船只九视图'):
    app.gallery_mode_var.set(group);app._draw_asset_gallery();assert len(app.gallery_canvas.hitboxes)==9
    app._gallery_clicked('右侧');assert app._presentation_scene(raw).entities[0].vehicle_type==MODEL_GALLERIES[group]
app._restore_automatic();app.close()
(out/'transport-view-result.json').write_text(json.dumps(dict(passed=True,model_calls=0,checks=[
    'truck and boat fixed meshes render nine views','new materials clip at all frame edges','boat detector class 8 enabled',
    'same crop at left and right has same yaw','red paint alone does not reverse heading','truncated view keeps previous yaw',
    'wide and narrow examples select side and end views','bound-only rotation preserves other vehicles','unbind clears per-track correction',
    'two new galleries select correct material','all direction calculations remain local']),ensure_ascii=False,indent=2),encoding='utf-8')
print('Transport and local view checks passed.')
