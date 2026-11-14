"""Material-only preview. Never label this as automatic video recognition."""
from pathlib import Path
import sys,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from stickfigure.assets import ACTIONS,preset_pose,person_props,BODY_LINKS
base=Path(__file__).resolve().parents[1];out=base.parent/'13_GTA6动作验证'
actions=[a for a in ACTIONS.values() if a]
W,H=1400,95+275*((len(actions)+6)//7)
def frame(t):
    image=np.full((H,W,3),249,np.uint8)
    cv2.putText(image,f'{len(actions)} FIXED ACTION PRESETS / MATERIAL DEMO, NOT AUTO RECOGNITION',(30,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(65,80,95),2,cv2.LINE_AA)
    for index,action in enumerate(actions):
        col,row=index%7,index//7;left=col*200+32;top=75+row*275;pw,ph=136,215
        pose=preset_pose(action,t);points={i:(round(left+p.x*pw),round(top+p.y*ph)) for i,p in enumerate(pose) if p.confidence>.5}
        color=(85,70,55)
        cv2.fillPoly(image,[np.array([points[i] for i in (11,12,24,23)])],(239,236,227),cv2.LINE_AA)
        for a,b in BODY_LINKS:cv2.line(image,points[a],points[b],color,2,cv2.LINE_AA)
        for i in (13,14,15,16,25,26,27,28):cv2.circle(image,points[i],2,color,1,cv2.LINE_AA)
        neck=((points[11][0]+points[12][0])//2,(points[11][1]+points[12][1])//2)
        radius=round(ph*.065)
        cv2.line(image,(points[0][0],points[0][1]+radius),neck,color,2,cv2.LINE_AA)
        cv2.ellipse(image,points[0],(radius,round(radius*1.15)),0,0,360,color,2,cv2.LINE_AA)
        for prop in person_props(action,t):
            p=np.array([(round(left+prop.points[i]*pw),round(top+prop.points[i+1]*ph)) for i in range(0,len(prop.points),2)],np.int32)
            if prop.kind=='polygon':
                cv2.fillPoly(image,[p],(235,229,222),cv2.LINE_AA);cv2.polylines(image,[p],True,color,2,cv2.LINE_AA)
            else:cv2.polylines(image,[p],False,color,max(1,round(prop.width)),cv2.LINE_AA)
        cv2.putText(image,action,(col*200+25,top+250),cv2.FONT_HERSHEY_SIMPLEX,.45,(85,95,105),1,cv2.LINE_AA)
    return image
cv2.imencode('.png',frame(.35))[1].tofile(str(out/'人物动作素材.png'))
target=out/'预设人物动作演示.mp4'
process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}',
                          '-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-threads','2','-movflags','+faststart',str(target)],stdin=subprocess.PIPE)
for i in range(240):process.stdin.write(frame(i/30).tobytes())
process.stdin.close();assert process.wait()==0
print(f'Exported {len(actions)} fixed presets and 8-second animation.')
