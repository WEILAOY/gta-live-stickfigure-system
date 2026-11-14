"""Find review candidates in the user's existing video; not an accuracy score."""
from pathlib import Path
import sys,json
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.detection import YoloXDetector
base=Path(__file__).resolve().parents[1];out=base.parent/'17_载具与漫画阴影验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
capture=cv2.VideoCapture(source);assert capture.isOpened()
detector=YoloXDetector(base/'models/yolox_s.onnx');records=[]
for second in range(30,1590,15):
    capture.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,bgr=capture.read()
    if not ok:continue
    rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2]
    found,*_=detector.detect_rgb(rgb.tobytes(),w,h)
    motors=[d for d in found if d.label=='motorcycle' and d.confidence>=.50]
    if motors:
        for d in motors:
            a,b,c,e=d.box;cv2.rectangle(bgr,(round(a*w),round(b*h)),(round(c*w),round(e*h)),(0,150,255),2)
        cv2.imencode('.jpg',bgr)[1].tofile(str(out/f'摩托车候选_{second}s.jpg'))
        records.append(dict(second=second,detections=[dict(label=d.label,box=d.box,confidence=d.confidence) for d in motors]))
        print(second,[(d.label,round(d.confidence,3)) for d in motors],flush=True)
        if len(records)>=4:break
capture.release()
(out/'motorcycle-candidates.json').write_text(json.dumps(dict(source=source,candidates=records,note='Candidates for human visual review; detector confidence is not calibrated accuracy.'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Candidates:',len(records))
