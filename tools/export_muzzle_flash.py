"""Actual preset renderer proof: three states, four views and 15/30fps."""
from pathlib import Path
import sys,json,subprocess,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.assets import combat_drawing,COMBAT_VIEWS,FLASH_STAGES,flash_stage
from stickfigure.frame_clipping import FrameLayer
from stickfigure.combat import combat_scene
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'21_枪口火光素材验证';out.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
phases=(.010,.050,.105)

def static_material(weapon,phase):
    shapes=[s for s in combat_drawing('GUN_FIRE',phase,weapon,90).shapes if s.role=='muzzle-flash']
    layer=FrameLayer((0,0,944,520),(0,0,944,520),opaque_light=True)
    for s in shapes:
        coords=[v*(944 if i%2==0 else 520) for i,v in enumerate(s.points)]
        layer.paint(s.kind,coords,fill=s.fill,outline=s.stroke,width=s.width)
    p=layer.pixels;alpha=p[:,:,3:4]/255
    # Identical crop and scale for all six panels, retaining their size ratios.
    image=(p[:,:,:3]*alpha+255*(1-alpha)).astype(np.uint8)[115:245,640:930]
    return cv2.resize(image,(580,260),interpolation=cv2.INTER_NEAREST)

def labelled(pixels,label):
    im=Image.fromarray(cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB));d=ImageDraw.Draw(im)
    d.rectangle((0,0,im.width,35),fill='white');d.text((10,7),label,font=font,fill='#34495e')
    return cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2BGR)

def main():
    tiles=[]
    for weapon,name in (('pistol','手枪'),('rifle','长枪')):
        for phase,stage in zip(phases,FLASH_STAGES):
            pixels=labelled(static_material(weapon,phase),name+' · '+stage+' · 固定素材')
            cv2.imencode('.png',pixels)[1].tofile(str(out/(name+'_'+stage+'.png')));tiles.append(pixels)
    cv2.imencode('.png',np.vstack((np.hstack(tiles[:3]),np.hstack(tiles[3:]))))[1].tofile(str(out/'两套火光三态素材.png'))
    root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
    def scene_frame(t,weapon='pistol',yaw=35,label=''):
        s=combat_scene(t,weapon,mode='fire',yaw=yaw)
        shooter=replace(s.entities[0],bbox=(.35,.14,.48,.89),x=.415)
        return raster(canvas,replace(s,entities=(shooter,)),label)
    tiles=[]
    for weapon,name in (('pistol','手枪'),('rifle','长枪')):
        for label,yaw in COMBAT_VIEWS.items():
            p=scene_frame(.85,weapon,yaw,name+' · '+label+' · 最亮态 / 手动预设')
            tiles.append(cv2.resize(p,(400,225)))
    cv2.imencode('.png',np.vstack((np.hstack(tiles[:4]),np.hstack(tiles[4:]))))[1].tofile(str(out/'枪口连接四视角.png'))
    records=[]
    for fps in (15,30):
        process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','800x450',
            '-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-movflags','+faststart',str(out/f'枪口火光演示_{fps}fps.mp4')],stdin=subprocess.PIPE)
        active=[]
        for i in range(4*fps):
            local=(i%(2*fps))/fps;weapon='pistol' if i<2*fps else 'rifle'
            s=combat_scene(local,weapon,mode='fire');shooter=s.entities[0]
            stage=flash_stage(shooter.action_time) if shooter.action=='GUN_FIRE' else None
            if stage is not None:active.append(dict(frame=i,t=i/fps,weapon=weapon,stage=FLASH_STAGES[stage]))
            p=scene_frame(local,weapon,35 if weapon=='pistol' else 90,f'{fps} FPS · 手动预设演示 · 非视频自动识别')
            process.stdin.write(p.tobytes())
        process.stdin.close();assert process.wait()==0
        assert all(any(a['weapon']==weapon and a['stage']=='最亮' for a in active) for weapon in ('pistol','rifle'))
        records.append(dict(fps=fps,seconds=4,active_frames=active))
    root.destroy()
    (out/'muzzle-export-result.json').write_text(json.dumps(dict(passed=True,manual_demo=True,materials=2,states=3,views=4,records=records),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Exported three-state materials, attached views and two frame-rate demos.')
if __name__=='__main__':main()
