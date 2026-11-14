from pathlib import Path
import sys,json,cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.vision import PoseEstimator
from stickfigure.actions import classify_action
base=Path(__file__).resolve().parents[1];out=base.parent/'18_倒地人物验证'
pose=PoseEstimator(base/'models/pose_estimation_mediapipe_2023mar.onnx')
for record in json.loads((out/'diagnosis.json').read_text(encoding='utf-8')):
    if record['second'] not in (565,570,575):continue
    bgr=cv2.imdecode(np.fromfile(out/f"原帧_{record['second']}s.jpg",np.uint8),cv2.IMREAD_COLOR);rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
    for view in record['views']:
        k=view['turns'];image=np.ascontiguousarray(np.rot90(rgb,k))
        for person in view['people']:
            a,b,c,d=person['box'];box=(a,b,c,d) if k==0 else (b,1-c,d,1-a) if k==1 else (1-d,a,1-b,c)
            points=pose.estimate(image,box)
            if k:
                from dataclasses import replace
                points=tuple(replace(p,x=1-p.y,y=p.x) if k==1 else replace(p,x=p.y,y=1-p.x) for p in points)
            vals={i:tuple(round(v,3) for v in (points[i].x,points[i].y,points[i].confidence)) for i in (0,11,12,23,24,25,26,27,28)} if points else {}
            print(record['second'],k,round(person['confidence'],2),round(person['pixel_aspect'],2),classify_action(points,aspect=852/480),vals,flush=True)
