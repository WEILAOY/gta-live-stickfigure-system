"""Simplified outer building outlines plus unchanged predefined actors."""
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
    output=base.parent/'12_城市群与识别对照';output.mkdir(exist_ok=True)
    detector=YoloXDetector(base/'models/yolox_s.onnx')
    analyzer=SceneAnalyzer(base/'models')
    segmenter=RoadSegmenter(base/'models/segformer_b0_cityscapes.onnx')
    cap=cv2.VideoCapture(str(base.parent/'03_测试素材/gta5_test_01.mp4'))
    root=tk.Tk();root.geometry('560x315');canvas=SceneCanvas(root,width=560,height=315);canvas.pack(fill='both',expand=True);root.update()
    records=[]
    for name,second,crop,occlude in (('street_000',0,None,False),('street_015',15,None,False),('street_030',30,None,False),('street_035',35,None,False),('street_064',64,None,False),('street_090',90,None,False),('street_105',105,None,False)):
        analyzer.reset();segmenter.reset()
        # Confirm low-score targets using an actual preceding frame, matching
        # production tracking rather than artificially repeating one image.
        if second>.2:
            cap.set(cv2.CAP_PROP_POS_MSEC,(second-.2)*1000);ok,previous=cap.read();assert ok
            ph,pw=previous.shape[:2]
            previous=VideoFrame(1,second-.2,pw,ph,cv2.cvtColor(previous,cv2.COLOR_BGR2RGB).tobytes())
            observed,_,_=detector.detect_rgb(previous.pixels,pw,ph)
            analyzer.analyze(previous,observed)
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,image=cap.read();assert ok
        if crop:
            x1,y1,x2,y2=crop;h,w=image.shape[:2]
            image=image[round(y1*h):round(y2*h),round(x1*w):round(x2*w)]
        height,width=image.shape[:2]
        if occlude:
            # Artificial opaque block tests hiding; this is labelled, not claimed
            # to be a naturally occurring obstruction in the downloaded video.
            cv2.rectangle(image,(280,190),(330,314),(140,140,140),-1)
        rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        frame=VideoFrame(1,second,width,height,rgb.tobytes())
        detections,_,_=detector.detect_rgb(frame.pixels,width,height)
        detections,horizon=analyzer.analyze(frame,detections)
        geometry,elapsed=segmenter.segment(frame)
        entities=tuple(Entity(d.track_id,'person' if d.label=='person' else 'car',
                              (d.box[0]+d.box[2])/2,d.box[3],bbox=d.box,pose=d.pose,
                              render_bbox=d.render_box,yaw=d.yaw,action=d.action)
                       for d in detections if not d.predicted and d.confirmed)
        scene=Scene(0,time.perf_counter(),records.__len__(),second,entities,False,
                    horizon=horizon,road=geometry if geometry.driving_view else None,
                    frame_clipping=True,buildings=segmenter.buildings)
        canvas.draw(scene,simulated=False)
        rendered=np.full((315,560,3),(252,249,247),np.uint8)
        for outline in scene.buildings.outlines:
            points=np.array([(round(x*560),round(y*315)) for x,y in outline],np.int32)
            cv2.polylines(rendered,[points],False,(166,150,131),1,cv2.LINE_AA)
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
        source=cv2.resize(image,(560,315))
        before_path=base.parent/'11_建筑外轮廓验证'/f'{name}.png'
        before=cv2.imdecode(np.fromfile(str(before_path),np.uint8),cv2.IMREAD_COLOR)
        assert before is not None
        combined=np.hstack((source,before[32:,560:1120],rendered))
        combined=cv2.copyMakeBorder(combined,32,0,0,0,cv2.BORDER_CONSTANT,value=(35,35,35))
        cv2.putText(combined,name+' | SOURCE / V0.10 / V0.11 CITY OUTLINES + PRESETS',(12,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(240,240,240),1,cv2.LINE_AA)
        cv2.imencode('.png',combined)[1].tofile(str(output/f'{name}.png'))
        records.append(dict(name=name,second=second,artificial_crop=crop,artificial_occluder=occlude,
                            detections=len(entities),rendered=len(canvas._images),segmentation_ms=elapsed,building_outlines=scene.buildings.outlines,
                            edge_boxes=[e.bbox for e in entities if min(e.bbox[:2])<.015 or max(e.bbox[2:])>.985]))
    root.destroy();cap.release()
    (output/'building-report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False))


if __name__=='__main__':
    main()
