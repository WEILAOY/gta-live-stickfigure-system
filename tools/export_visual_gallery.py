"""Export a reviewable PNG from the same code-native meshes and joint presets."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from stickfigure.assets import vehicle_drawing,preset_pose,BODY_LINKS


def bgr(color):
    color=color.lstrip('#')
    return tuple(int(color[i:i+2],16) for i in (4,2,0))


def main():
    image=np.full((1240,1440,3),250,dtype=np.uint8)
    cv2.putText(image,'VEHICLE VIEWS / 360-DEGREE LINE ART',(50,55),cv2.FONT_HERSHEY_SIMPLEX,.9,(65,80,95),2,cv2.LINE_AA)
    names=['REAR','REAR RIGHT','RIGHT','FRONT RIGHT','FRONT','FRONT LEFT','LEFT','REAR LEFT','TOP']
    for i,name in enumerate(names):
        drawing=vehicle_drawing(i*45 if i<8 else 0,22 if i<8 else 78)
        col,row=i%3,i//3
        width,height=350,175
        scale=min(width,height*drawing.aspect)
        dw,dh=scale,scale/drawing.aspect
        left,top=col*470+(470-dw)/2,100+row*240+(175-dh)/2
        for primitive in drawing.shapes:
            coords=np.array([(left+primitive.points[j]*dw,top+primitive.points[j+1]*dh) for j in range(0,len(primitive.points),2)],dtype=np.int32)
            if primitive.kind=='polygon':
                if primitive.fill:
                    cv2.fillPoly(image,[coords],bgr(primitive.fill),cv2.LINE_AA)
                cv2.polylines(image,[coords],True,bgr(primitive.stroke),2,cv2.LINE_AA)
            else:
                cv2.polylines(image,[coords],False,bgr(primitive.stroke),2,cv2.LINE_AA)
        cv2.putText(image,name,(col*470+150,310+row*240),cv2.FONT_HERSHEY_SIMPLEX,.55,(90,105,120),1,cv2.LINE_AA)
    cv2.putText(image,'ARTICULATED FIGURES / SIX BASIC ACTIONS',(50,880),cv2.FONT_HERSHEY_SIMPLEX,.8,(65,80,95),2,cv2.LINE_AA)
    for i,action in enumerate(('IDLE','WALK','RUN','RAISE','CROUCH','SIT')):
        pose=preset_pose(action,.12)
        left,top=i*235+30,930
        pts={j:(round(left+p.x*170),round(top+p.y*210)) for j,p in enumerate(pose) if p.confidence>.5}
        torso=np.array([pts[j] for j in (11,12,24,23)],np.int32)
        cv2.fillPoly(image,[torso],(235,240,242),cv2.LINE_AA)
        for a,b in BODY_LINKS:
            cv2.line(image,pts[a],pts[b],(70,85,100),3,cv2.LINE_AA)
        for j in (13,14,15,16,25,26,27,28):
            cv2.circle(image,pts[j],3,(70,85,100),1,cv2.LINE_AA)
        neck=(round((pts[11][0]+pts[12][0])/2),round((pts[11][1]+pts[12][1])/2))
        cv2.line(image,(pts[0][0],pts[0][1]+15),neck,(70,85,100),2,cv2.LINE_AA)
        cv2.ellipse(image,pts[0],(12,15),0,0,360,(70,85,100),2,cv2.LINE_AA)
        cv2.putText(image,action,(i*235+85,1190),cv2.FONT_HERSHEY_SIMPLEX,.5,(90,105,120),1,cv2.LINE_AA)
    output=Path(__file__).resolve().parents[2]/'05_视觉升级验证'
    output.mkdir(exist_ok=True)
    cv2.imencode('.png',image)[1].tofile(str(output/'车辆与人物素材预览.png'))
    print('Exported visual gallery.')


if __name__=='__main__':
    main()
