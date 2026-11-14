"""Actual OCR on the same subtitle frame, comparing full image and cropped ROI."""
from pathlib import Path
import sys,json,subprocess,time
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.ocr import TextRecognizer
from stickfigure.video import VideoFrame
base=Path(__file__).resolve().parents[1];out=base.parent/'27_OCR范围与性能验证';out.mkdir(exist_ok=True)
cv2.setNumThreads(2)
path=base.parent/'03_测试素材/gta6_actions_test.mp4'
cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_POS_MSEC,95000);ok,bgr=cap.read();cap.release();assert ok
rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2];frame=VideoFrame(1,95,w,h,rgb.tobytes())
engine=TextRecognizer(base/'models/ocr');records=[]
for name,roi,scale in [('full_fine',None,1.5),('subtitle_native',(0,.72,1,1),1.),('subtitle_fine',(0,.72,1,1),1.5)]:
    times=[]
    for _ in range(3):
        regions,elapsed=engine.recognize(frame,roi,scale);times.append(elapsed)
    records.append(dict(name=name,roi=roi,scale=scale,median_ms=sorted(times)[1],times_ms=times,regions=[dict(text=r.text,box=r.box) for r in regions]))
    if roi:assert regions and all(r.box[1]>=.71 for r in regions),records[-1]
    print(records[-1],flush=True)
assert records[1]['median_ms']<records[0]['median_ms'],records
report=dict(passed=True,records=records,note='Same real subtitle frame, 3 calls per mode, median timings; native crop may miss small text; this is OCR latency, not end-to-end FPS.')
(out/'ocr-region-source-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
