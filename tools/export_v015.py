"""Proof from actual SceneCanvas preset layers, never source actor pixels."""
from pathlib import Path
import sys,tkinter as tk,json,subprocess
from dataclasses import replace
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.combat import combat_scene
from stickfigure.rendering import SceneCanvas
from stickfigure.shading import PALETTE,contact_shadow_boxes
from stickfigure.assets import COMBAT_VIEWS
base=Path(__file__).resolve().parents[1];out=base.parent/'16_第三人称与黑灰白验证';out.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)

def raster(canvas,scene,label=''):
    canvas.draw(scene);w,h=canvas.winfo_width(),canvas.winfo_height()
    pixels=np.full((h,w,3),255,np.uint8)
    def coord(points):return np.rint(np.array(points)*[w,h]).astype(np.int32)
    if scene.shading is not None and canvas._background_cache is not None:
        photo=canvas._background_cache[1];data=photo.tk.call(str(photo),'data','-format','png')
        p=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_UNCHANGED)
        if p.shape[2]==3:p=cv2.cvtColor(p,cv2.COLOR_BGR2BGRA)
        alpha=p[:,:,3:4]/255;pixels=(p[:,:,:3]*alpha+pixels*(1-alpha)).astype(np.uint8)
    if scene.horizon:
        cv2.line(pixels,(0,round(scene.horizon.left*h)),(w-1,round(scene.horizon.right*h)),(170,152,131),1)
    if scene.buildings:
        for p in scene.buildings.outlines:cv2.polylines(pixels,[coord(p)],False,(166,150,131),1)
    if scene.road:
        for p in (scene.road.left_edge,scene.road.right_edge):
            if p:cv2.polylines(pixels,[coord(p)],False,(152,141,104),1)
    for photo,bounds in (*canvas._contact_cache.values(),*canvas._layer_cache.values()):
        if photo is None:continue
        data=photo.tk.call(str(photo),'data','-format','png');p=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_UNCHANGED)
        a,b,c,d=bounds;alpha=p[:,:,3:4]/255;pixels[b:d,a:c]=(p[:,:,:3]*alpha+pixels[b:d,a:c]*(1-alpha)).astype(np.uint8)
    if label:
        image=Image.fromarray(cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,w,38),fill='white');draw.text((12,8),label,font=font,fill='#34495e')
        pixels=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
    return pixels

def main():
    root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
    tiles=[]
    for weapon in ('pistol','rifle'):
        for label,yaw in COMBAT_VIEWS.items():
            s=combat_scene(.82,weapon,yaw=yaw);s=replace(s,entities=s.entities[:1])
            s=replace(s,entities=(replace(s.entities[0],bbox=(.38,.17,.50,.90),x=.44),))
            pixels=raster(canvas,s,('手枪' if weapon=='pistol' else '长枪')+' · '+label+' · 手动素材')
            cv2.imencode('.png',pixels)[1].tofile(str(out/f'{weapon}_{yaw}.png'));tiles.append(cv2.resize(pixels,(400,225)))
    cv2.imencode('.png',np.vstack((np.hstack(tiles[:4]),np.hstack(tiles[4:]))))[1].tofile(str(out/'第三人称持枪四视角.png'))
    process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','800x450','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-threads','2','-movflags','+faststart',str(out/'第三人称战斗素材演示.mp4')],stdin=subprocess.PIPE)
    for i in range(300):
        yaw=(35,0,90,180)[i//75];weapon='pistol' if i<150 else 'rifle'
        s=combat_scene((i%75)/30,weapon,yaw=yaw)
        process.stdin.write(raster(canvas,s,'手动预设演示 · '+list(COMBAT_VIEWS)[i//75]+' · 非视频自动识别').tobytes())
    process.stdin.close();assert process.wait()==0;root.destroy()
    (out/'material-export.json').write_text(json.dumps(dict(passed=True,manual_demo=True,views=list(COMBAT_VIEWS),weapons=2,video_seconds=10),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Exported V0.15 material proof')
if __name__=='__main__':main()
