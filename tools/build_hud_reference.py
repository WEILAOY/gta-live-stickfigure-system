"""Compile tiny analysis-only HUD references from the supplied test footage.

Reference timestamps are build annotations, never runtime event schedules.
No reference image is used as output art.
"""
from pathlib import Path
import sys,json,hashlib
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
base=Path(__file__).resolve().parents[1];out=base/'models/hud';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source'];cap=cv2.VideoCapture(source)
def frame(t):
    cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,bgr=cap.read();assert ok
    return cv2.cvtColor(cv2.resize(bgr,(852,480)),cv2.COLOR_BGR2GRAY)
def gradient(p):
    return np.stack((cv2.Sobel(p,cv2.CV_32F,1,0,ksize=3),cv2.Sobel(p,cv2.CV_32F,0,1,ksize=3)),axis=-1)
definitions={'rifle':((760,62,840,90),(842,844,845,848,850)),
             'pistol':((790,28,840,56),(1404,1405,1406,1407,1408)),
             'pistol_dark':((790,28,840,56),(1403.6,1403.8,1404,1404.2)),
             'molotov':((798,62,840,92),(959,960,961,963,965,967))}
arrays={};meta={}
for name,(box,times) in definitions.items():
    a,b,c,d=box;patches=np.asarray([gradient(frame(t)[b:d,a:c]) for t in times])
    feature=np.median(patches,axis=0);deviation=np.median(np.abs(patches-feature),axis=0).mean(axis=-1)
    mask=((np.linalg.norm(feature,axis=-1)>75)&(deviation<65)).astype(np.float32)
    arrays[name+'_feature']=feature;arrays[name+'_mask']=mask
    meta[name]={'box':box,'count':int(mask.sum()),'reference_times':times}
def digit_image(p):
    h,w=p.shape;res=cv2.resize(p.astype(np.float32),(max(1,min(14,round(w*16/h))),16),interpolation=cv2.INTER_NEAREST)
    result=np.zeros((16,16),np.float32);left=(16-res.shape[1])//2;result[:,left:left+res.shape[1]]=res
    return result
samples=((842,'39'),(842.3,'36'),(842.6,'33'),(843,'28'),(843.3,'26'),(843.6,'23'),(844,'19'),
         (844.3,'17'),(844.6,'14'),(845,'10'),(845.3,'8'),(847,'40'),(847.6,'37'),(848.3,'35'),(848.6,'32'))
glyphs=[];labels=[]
for t,text in samples:
    p=frame(t)[46:57,785:814];mask=(p>190).astype(np.uint8)
    n,_,stats,_=cv2.connectedComponentsWithStats(mask,8)
    boxes=sorted((x,y,w,h) for x,y,w,h,area in stats[1:] if 2<=w<=8 and 6<=h<=10 and area>=8)
    if len(boxes)!=len(text):raise ValueError((t,text,boxes))
    for digit,(x,y,w,h) in zip(text,boxes):glyphs.append(digit_image(mask[y:y+h,x:x+w]));labels.append(int(digit))
for t,text in ((1404,'17'),(1406.133,'15')):
    mask=(frame(t)[12:24,795:817]>190).astype(np.uint8)
    n,_,stats,_=cv2.connectedComponentsWithStats(mask,8)
    boxes=sorted((x,y,w,h) for x,y,w,h,area in stats[1:] if 2<=w<=8 and 6<=h<=10 and area>=8)
    assert len(boxes)==len(text),(t,boxes)
    for digit,(x,y,w,h) in zip(text,boxes):glyphs.append(digit_image(mask[y:y+h,x:x+w]));labels.append(int(digit))
assert set(labels)==set(range(10))
arrays['digits']=np.asarray(glyphs);arrays['digit_labels']=np.asarray(labels,np.int32)
np.savez_compressed(out/'gta5_hud_features.npz',**arrays)
(out/'reference-info.json').write_text(json.dumps(dict(description='Analysis-only normalized HUD icon/digit features; never output art.',weapons=meta,
    sha256=hashlib.sha256((out/'gta5_hud_features.npz').read_bytes()).hexdigest()),ensure_ascii=False,indent=2),encoding='utf-8')
print('Compiled HUD reference',meta,'digits',len(labels))
