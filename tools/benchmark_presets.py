"""Predefined material rendering; source frames only drive detection parameters."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,time,tkinter as tk
import cv2,numpy as np
from stickfigure.video import VideoFrame
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.road import RoadSegmenter
from stickfigure.core import Scene,Entity
from stickfigure.rendering import SceneCanvas


def main():
    base=Path(__file__).resolve().parents[1]
    output=base.parent/'09_预设素材与画面裁剪验证';output.mkdir(exist_ok=True)
    detector=YoloXDetector(base/'models/yolox_nano.onnx')
    analyzer=SceneAnalyzer(base/'models')
    segmenter=RoadSegmenter(base/'models/segformer_b0_cityscapes.onnx')
    cap=cv2.VideoCapture(str(base.parent/'03_测试素材/gta5_test_01.mp4'))
    root=tk.Tk();root.geometry('560x315');canvas=SceneCanvas(root,width=560,height=315);canvas.pack(fill='both',expand=True);root.update()
    records=[]
    for name,second,crop,occlude in (
            ('full_car',90,None,False),('left_edge_crop',90,(.50,0,1,1),False),
            ('bottom_edge_crop',90,(0,0,1,.70),False),('occluder_test',90,None,True),
            ('real_people',30,None,False),('real_close_vehicle',35,None,False),('real_partial_vehicle',60,None,False)):
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,image=cap.read();assert ok
        if crop:
            x1,y1,x2,y2=crop;h,w=image.shape[:2]
            image=image[round(y1*h):round(y2*h),round(x1*w):round(x2*w)]
        image=cv2.resize(image,(560,315))
        if occlude:
            # Artificial opaque block tests hiding; this is labelled, not claimed
            # to be a naturally occurring obstruction in the downloaded video.
            cv2.rectangle(image,(280,190),(330,314),(140,140,140),-1)
        rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        frame=VideoFrame(1,second,560,315,rgb.tobytes())
        analyzer.reset();segmenter.reset()
        detections,_,_=detector.detect_rgb(frame.pixels,560,315)
        detections,horizon=analyzer.analyze(frame,detections)
        geometry,elapsed=segmenter.segment(frame)
        entities=tuple(Entity(d.track_id,'person' if d.label=='person' else 'car',
                              (d.box[0]+d.box[2])/2,d.box[3],bbox=d.box,pose=d.pose,
                              render_bbox=d.render_box,yaw=d.yaw,action=d.action)
                       for d in detections if not d.predicted)
        scene=Scene(0,time.perf_counter(),records.__len__(),second,entities,False,
                    horizon=horizon,road=geometry if geometry.driving_view else None,
                    frame_clipping=True)
        canvas.draw(scene,simulated=False)
        rendered=np.full((315,560,3),(252,249,247),np.uint8)
        cv2.line(rendered,(0,round(horizon.left*315)),(559,round(horizon.right*315)),(170,152,131),1)
        if scene.road:
            for edge in (geometry.left_edge,geometry.right_edge):
                if edge:
                    cv2.polylines(rendered,[np.array([(round(x*560),round(y*315)) for x,y in edge])],False,(152,141,104),1,cv2.LINE_AA)
        for photo,bounds in canvas._layer_cache.values():
            if photo is None:
                continue
            data=photo.tk.call(str(photo),'data','-format','png')
            pixels=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_UNCHANGED)
            x1,y1,x2,y2=bounds
            alpha=pixels[:,:,3:4]/255
            rendered[y1:y2,x1:x2]=(pixels[:,:,:3]*alpha+rendered[y1:y2,x1:x2]*(1-alpha)).astype(np.uint8)
        combined=np.hstack((image,rendered))
        combined=cv2.copyMakeBorder(combined,32,0,0,0,cv2.BORDER_CONSTANT,value=(35,35,35))
        cv2.putText(combined,name+' | SOURCE / PRESET MATERIAL',(12,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(240,240,240),1,cv2.LINE_AA)
        cv2.imencode('.png',combined)[1].tofile(str(output/f'{name}.png'))
        records.append(dict(name=name,second=second,artificial_crop=crop,artificial_occluder=occlude,
                            detections=len(entities),rendered=len(canvas._images),segmentation_ms=elapsed,
                            edge_boxes=[e.bbox for e in entities if min(e.bbox[:2])<.015 or max(e.bbox[2:])>.985]))
    root.destroy();cap.release()
    (output/'preset-report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False))


if __name__=='__main__':
    main()
