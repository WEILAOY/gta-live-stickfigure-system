"""Actual material renderer: two new vehicles and comic-screen-tone scene."""
from pathlib import Path
import sys,tkinter as tk,json,subprocess
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.core import Scene,Entity,Horizon,ShadeRegion
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'17_载具与漫画阴影验证';out.mkdir(exist_ok=True)

def fixture(t=0,vehicle_type='motorcycle',yaw=45):
    actor=Entity('预设载具','car',.5,.83,bbox=(.18,.22,.82,.83),yaw=yaw,pitch=22,vehicle_type=vehicle_type)
    return Scene(0,0,1,t,(actor,),True,frame_clipping=True)

def main():
    root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
    tiles=[]
    for material,label in (('motorcycle','摩托车'),('helicopter','直升机')):
        row=[]
        for yaw in (0,45,90,135,180,225,270,315,0):
            s=fixture(vehicle_type=material,yaw=yaw)
            if len(row)==8:
                from dataclasses import replace
                s=replace(s,entities=(replace(s.entities[0],pitch=78),))
            image=raster(canvas,s,label+' · '+('俯视' if len(row)==8 else str(yaw)+'°')+' · 预设素材')
            row.append(cv2.resize(image,(400,225)))
        sheet=np.vstack([np.hstack(row[i:i+3]) for i in (0,3,6)])
        cv2.imencode('.png',sheet)[1].tofile(str(out/(label+'九视图.png')));tiles.append(sheet)
    cv2.imencode('.png',np.vstack(tiles))[1].tofile(str(out/'新增载具多视角.png'))
    shades=(ShadeRegion(3,((0,0),(1,0),(1,.45),(0,.45))),
            ShadeRegion(0,((0,.35),(.20,.35),(.20,.55),(.45,.55),(.45,1),(0,1))),
            ShadeRegion(1,((.45,.56),(1,.56),(1,1),(.45,1))))
    actors=(Entity('motorcycle','car',.30,.87,bbox=(.13,.51,.47,.87),yaw=90,vehicle_type='motorcycle'),
            Entity('helicopter','car',.69,.45,bbox=(.46,.07,.95,.45),yaw=135,vehicle_type='helicopter'))
    sample=Scene(0,0,2,0,actors,True,frame_clipping=True,shading=shades,contact_shadows=True)
    cv2.imencode('.png',raster(canvas,sample,'漫画阴影 + 淡蓝天空 · 人工几何与预设素材演示'))[1].tofile(str(out/'漫画阴影素材示例.png'))
    process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','800x450','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-threads','2','-movflags','+faststart',str(out/'载具预设旋转演示.mp4')],stdin=subprocess.PIPE)
    for i in range(240):
        material='motorcycle' if i<120 else 'helicopter'
        s=fixture(i/30,material,(i%120)*3)
        process.stdin.write(raster(canvas,s,('摩托车' if material=='motorcycle' else '直升机')+' · 手动素材旋转演示').tobytes())
    process.stdin.close();assert process.wait()==0;root.destroy()
    (out/'material-export.json').write_text(json.dumps(dict(passed=True,manual_demo=True,models=['motorcycle','helicopter'],views_each=9,video_seconds=8),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Exported actual V0.16 preset models and comic screen tone.')
if __name__=='__main__':main()
