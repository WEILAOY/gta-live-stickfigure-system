"""Game-HUD context, with no video timestamps or output image materials."""
from dataclasses import dataclass
from pathlib import Path
import json,math

@dataclass(frozen=True)
class HudObservation:
    weapon: str
    ammo: int|None
    confidence: float

class WeaponHud:
    def __init__(self,directory):
        import cv2,numpy as np
        self.cv2,self.np=cv2,np
        directory=Path(directory)
        with np.load(directory/'gta5_hud_features.npz',allow_pickle=False) as packed:
            self.data={key:packed[key] for key in packed.files}
        self.info=json.loads((directory/'reference-info.json').read_text(encoding='utf-8'))['weapons']
        self.last=None;self.ammo_candidate=None;self.confirmed=None;self.weapon='';self.count=0
    def reset(self):
        self.last=None;self.ammo_candidate=None;self.confirmed=None;self.weapon='';self.count=0
    def _digit(self,p):
        np,cv2=self.np,self.cv2;h,w=p.shape
        res=cv2.resize(p.astype(np.float32),(max(1,min(14,round(w*16/h))),16),interpolation=cv2.INTER_NEAREST)
        result=np.zeros((16,16),np.float32);left=(16-res.shape[1])//2;result[:,left:left+res.shape[1]]=res
        templates=self.data['digits'];scores=(2*(templates*result).sum(axis=(1,2))+1)/(templates.sum(axis=(1,2))+result.sum()+1)
        index=int(scores.argmax());return int(self.data['digit_labels'][index]),float(scores[index])
    def inspect(self,rgb):
        cv2,np=self.cv2,self.np
        gray=cv2.cvtColor(cv2.resize(rgb,(852,480)),cv2.COLOR_RGB2GRAY)
        choices=[]
        for name,info in self.info.items():
            a,b,c,d=info['box'];feature=self.data[name+'_feature'];mask=self.data[name+'_mask'][:,:,None]
            for shift in (-34,0,34):
                if b+shift<0 or d+shift>100:continue
                patch=gray[b+shift:d+shift,a:c]
                v=np.stack((cv2.Sobel(patch,cv2.CV_32F,1,0,ksize=3),cv2.Sobel(patch,cv2.CV_32F,0,1,ksize=3)),axis=-1)
                norm=float(np.sqrt((feature*feature*mask).sum()*(v*v*mask).sum()))
                score=float((feature*v*mask).sum()/max(1,norm));choices.append((score,name,shift))
        score,name,shift=max(choices)
        if score<.78:return None
        if name.startswith('pistol'):name='pistol'
        base=48 if name!='pistol' else 14
        top=base+shift;ammo=None
        if 0<=top<80:
            patch=gray[max(0,top-2):top+11,780:821];binary=(patch>190).astype(np.uint8)
            n,_,stats,_=cv2.connectedComponentsWithStats(binary,8)
            boxes=sorted((x,y,w,h) for x,y,w,h,area in stats[1:] if 2<=w<=9 and 6<=h<=10 and area>=8)
            numbers=[]
            for x,y,w,h in boxes:
                value,quality=self._digit(binary[y:y+h,x:x+w])
                if quality>.70:numbers.append((x,value))
            if 1<=len(numbers)<=3 and all(b[0]-a[0]<=10 for a,b in zip(numbers,numbers[1:])):
                ammo=int(''.join(str(v) for _,v in numbers))
        return HudObservation(name,ammo,score)
    def update(self,rgb,generation,timestamp):
        observation=self.inspect(rgb);shot=False
        if self.last is None or self.last[0]!=generation or not 0<timestamp-self.last[1]<.26:self.reset()
        self.last=(generation,timestamp)
        if observation is None:
            self.weapon='';self.count=0;self.confirmed=None;self.ammo_candidate=None;return None,False
        if observation.weapon!=self.weapon:
            self.weapon=observation.weapon;self.count=1;self.confirmed=None;self.ammo_candidate=None
        else:self.count+=1
        if observation.ammo is None:return observation,False
        if self.ammo_candidate and self.ammo_candidate[0]==observation.ammo:
            self.ammo_candidate=(observation.ammo,self.ammo_candidate[1]+1)
        else:self.ammo_candidate=(observation.ammo,1)
        if self.ammo_candidate[1]>=2:
            previous=self.confirmed
            if previous and previous[0]!=observation.ammo:
                delta=previous[0]-observation.ammo;gap=timestamp-previous[1]
                shot=(self.count>=3 and observation.weapon in ('rifle','pistol') and 0<gap<.75 and 0<delta<=max(2,math.ceil(gap*18)))
            self.confirmed=(observation.ammo,timestamp)
        return observation,shot
