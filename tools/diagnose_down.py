"""Inspect upright versus rotated person proposals on actual source frames."""
from pathlib import Path
import sys,json
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.detection import YoloXDetector
base=Path(__file__).resolve().parents[1];out=base.parent/'18_倒地人物验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
capture=cv2.VideoCapture(source);assert capture.isOpened();detector=YoloXDetector(base/'models/yolox_s.onnx')
records=[]
for second in (565,569,570,571,572,575,580):
    capture.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,frame=capture.read()
    if not ok:continue
    original=frame.copy();h,w=frame.shape[:2];rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    record={'second':second,'views':[]}
    for turns in (0,1,3):
        image=np.ascontiguousarray(np.rot90(rgb,turns));ih,iw=image.shape[:2]
        found,*_=detector.detect_rgb(image.tobytes(),iw,ih,threshold=.15)
        people=[]
        for d in found:
            if d.label!='person':continue
            a,b,c,e=d.box
            box=d.box if turns==0 else (1-e,a,1-b,c) if turns==1 else (b,1-c,e,1-a)
            people.append(dict(confidence=d.confidence,box=box,pixel_aspect=(box[2]-box[0])*w/max(1,(box[3]-box[1])*h)))
            a,b,c,e=box;color=(0,170,255) if turns==0 else (255,180,0) if turns==1 else (60,255,80)
            cv2.rectangle(frame,(round(a*w),round(b*h)),(round(c*w),round(e*h)),color,1)
            cv2.putText(frame,f'{turns*90}:{d.confidence:.2f}',(round(a*w),max(15,round(b*h))),cv2.FONT_HERSHEY_SIMPLEX,.42,color,1)
        record['views'].append(dict(turns=turns,people=people))
    cv2.imencode('.jpg',frame)[1].tofile(str(out/f'诊断_{second}s.jpg'))
    cv2.imencode('.jpg',original)[1].tofile(str(out/f'原帧_{second}s.jpg'))
    records.append(record);print(second,[(r['turns'],[(round(d['confidence'],2),round(d['pixel_aspect'],2)) for d in r['people']]) for r in record['views']],flush=True)
capture.release();(out/'diagnosis.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
