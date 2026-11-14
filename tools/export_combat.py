"""Export the actual preset renderer, explicitly labelled as a manual demo."""
from pathlib import Path
import sys,tkinter as tk,subprocess,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from stickfigure.combat import combat_scene
from stickfigure.rendering import SceneCanvas
base=Path(__file__).resolve().parents[1];out=base.parent/'15_极简战斗素材验证';out.mkdir(exist_ok=True)
root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root,width=800,height=450);canvas.pack(fill='both',expand=True);root.update()
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
def frame(t,weapon='pistol',mirror=False):
    scene=combat_scene(t,weapon,mirror);canvas.draw(scene,simulated=True)
    pixels=np.full((450,800,3),(252,249,247),np.uint8)
    cv2.line(pixels,(0,round(.85*450)),(799,round(.85*450)),(170,152,131),1)
    for photo,bounds in canvas._layer_cache.values():
        if photo is None:continue
        data=photo.tk.call(str(photo),'data','-format','png');p=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_UNCHANGED)
        a,b,c,d=bounds;alpha=p[:,:,3:4]/255;pixels[b:d,a:c]=(p[:,:,:3]*alpha+pixels[b:d,a:c]*(1-alpha)).astype(np.uint8)
    image=Image.fromarray(cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(image)
    draw.text((14,10),'手动预设素材演示 · 非视频自动识别',font=font,fill='#34495e')
    draw.text((14,40),('手枪' if weapon=='pistol' else '长枪')+(' · 左右镜像' if mirror else '')+f' · {t:.2f}s',font=font,fill='#62758a')
    return cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
records=[];tiles=[]
for t,label in ((.4,'持枪'),(.82,'开火'),(1.1,'中弹'),(1.55,'侧倒'),(2.4,'倒地保持')):
    image=frame(t);cv2.imencode('.png',image)[1].tofile(str(out/f'{label}.png'));tiles.append(cv2.resize(image,(480,270)))
    records.append(dict(t=t,actions=[e.action for e in combat_scene(t).entities]))
cv2.imencode('.png',np.vstack((np.hstack(tiles[:2]),np.hstack(tiles[2:4]),np.hstack((tiles[4],cv2.resize(frame(2.4,'rifle',True),(480,270)))))))[1].tofile(str(out/'战斗素材流程.png'))
process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','800x450',
    '-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-threads','2','-movflags','+faststart',str(out/'极简战斗预设演示.mp4')],stdin=subprocess.PIPE)
for i in range(300):process.stdin.write(frame((i%150)/30,'pistol' if i<150 else 'rifle',i>=150).tobytes())
process.stdin.close();assert process.wait()==0;root.destroy()
(out/'material-export.json').write_text(json.dumps(dict(passed=True,manual_demo=True,records=records,video_seconds=10),ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported actual-renderer manual combat materials.')
