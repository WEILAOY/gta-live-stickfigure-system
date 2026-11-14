"""Local visible-muzzle-flash candidates, not audio or general gunshot recognition.

Only event coordinates, ownership and confidence leave this analyzer. Source
pixels never become output materials. Processes each decoded video frame.
"""
from dataclasses import dataclass,replace
import threading,queue,time,math
from collections import deque
from pathlib import Path
from .tracking import map_pose

@dataclass(frozen=True)
class ShotEvent:
    generation: int
    timestamp: float
    owner: str
    x: float
    y: float
    dx: float
    dy: float
    owner_center: tuple
    confidence: float
    weapon_type: str = ''

@dataclass(frozen=True)
class HeldWeapon(ShotEvent):
    box: tuple = ()
    trusted: bool = False

@dataclass(frozen=True)
class FlashCandidate:
    generation: int
    timestamp: float
    cx: float
    cy: float
    width: int
    height: int
    weapon_boxes: tuple = ()

class ShotDetector:
    def __init__(self,weapon_model=None,hud_enabled=True):
        self._lock=threading.RLock();self.events=queue.Queue(maxsize=12)
        self.enabled=False;self.last_error='';self.frames=0;self.total_ms=0
        self.weapon_model=weapon_model if weapon_model is not None else Path(__file__).resolve().parents[1]/'models/context/pistol.onnx'
        self.gun_verifier=None
        self.hud_enabled=hud_enabled;self.hud_reader=None
        self._mailbox=threading.Condition();self._queued_frame=None;self._queued_targets=None
        self._worker=None;self._closed=False;self._work_epoch=0
        self.reset()
    def submit(self,frame):
        """Never make the decoder wait for flash analysis; keep one latest frame."""
        with self._mailbox:
            if self._closed:return
            self._queued_frame=(self._work_epoch,frame)
            if self._worker is None:
                self._worker=threading.Thread(target=self._run,name='muzzle-analysis',daemon=True);self._worker.start()
            self._mailbox.notify()
    def _run(self):
        while True:
            with self._mailbox:
                self._mailbox.wait_for(lambda:self._closed or self._queued_frame is not None)
                if self._closed:return
                epoch,frame=self._queued_frame;self._queued_frame=None
            with self._lock:
                if epoch!=self._work_epoch:continue
                self.process(frame)
                with self._mailbox:pending=self._queued_targets;self._queued_targets=None
                if pending and pending[0]==self._work_epoch:self.set_targets(*pending[1:])
    def close(self):
        with self._mailbox:
            self._closed=True;self._queued_frame=None;self._mailbox.notify_all()
    def reset(self):
        with self._lock:
            self._work_epoch+=1;self._queued_targets=None
            with self._mailbox:self._queued_frame=None
            self.previous=None;self.targets=();self.target_generation=-1;self.target_time=0
            self.cooldowns={};self.pose_memory={};self.gun_memory={};self.cut_at=float('-inf')
            self.pending=deque(maxlen=64);self.emitted={}
            self.warm_history=deque(maxlen=2)
            self.holds={};self.hold_candidates={}
            self.hud_observation=None;self.hud_time=float('-inf');self.hud_generation=-1
            self.hud_shots=deque(maxlen=12);self.foreground_id=None
            if self.hud_reader:self.hud_reader.reset()
            while True:
                try:self.events.get_nowait()
                except queue.Empty:break
    def set_enabled(self,enabled):
        with self._lock:self.enabled=bool(enabled);self.reset();self.last_error=''
    def set_targets(self,detections,generation,timestamp):
        if not self._lock.acquire(blocking=False):
            with self._mailbox:self._queued_targets=(self._work_epoch,detections,generation,timestamp)
            return
        try:
            people=[];memory={};guns={}
            for d in detections:
                if d.label!='person' or d.predicted or not d.confirmed:continue
                if d.action in ('PHONE_LOOK','PHONE','DRINK','DOWN','FALL'):
                    self.holds.pop(d.track_id,None);self.hold_candidates.pop(d.track_id,None);continue
                self._observe_hold(d,generation,timestamp)
                old=self.pose_memory.get(d.track_id)
                if d.pose and any(d.pose[i].confidence>.35 for i in (15,16)):
                    memory[d.track_id]=(d.pose,d.box,timestamp)
                elif old and 0<=timestamp-old[2]<.8:
                    d=replace(d,pose=map_pose(old[0],old[1],d.box));memory[d.track_id]=old
                old_gun=self.gun_memory.get(d.track_id)
                if d.weapon_boxes:guns[d.track_id]=(d.weapon_boxes,d.box,timestamp)
                elif old_gun and 0<=timestamp-old_gun[2]<.55:
                    from .core import Joint
                    corners=tuple(Joint(x,y) for a,b,c,e in old_gun[0] for x,y in ((a,b),(c,e)))
                    mapped=map_pose(corners,old_gun[1],d.box)
                    boxes=tuple((mapped[i].x,mapped[i].y,mapped[i+1].x,mapped[i+1].y) for i in range(0,len(mapped),2))
                    d=replace(d,weapon_boxes=boxes);guns[d.track_id]=old_gun
                people.append(d)
            self.targets=tuple(people);self.pose_memory=memory;self.gun_memory=guns
            self.target_generation=generation;self.target_time=timestamp
            active={d.track_id for d in people}
            self.holds={k:v for k,v in self.holds.items() if k in active and v.generation==generation and 0<=timestamp-v.timestamp<1.2}
            self.hold_candidates={k:v for k,v in self.hold_candidates.items() if k in active}
            for candidate in self.pending:
                if candidate.generation==generation and -.2<=candidate.timestamp-timestamp<=.35:self._associate(candidate)
            self._bind_hud()
        finally:self._lock.release()

    def get_holds(self,generation,timestamp):
        # A shallow snapshot of immutable observations does not wait for inference.
        return {k:v for k,v in self.holds.copy().items() if v.generation==generation and 0<=timestamp-v.timestamp<1.2}

    def _observe_hold(self,d,generation,timestamp):
        if not(self.hud_observation and self.hud_observation.weapon in ('rifle','pistol') and self.hud_generation==generation):return
        if not d.weapon_boxes:return
        a,b,c,e=d.box;bh=(e-b)*240
        if bh<35:return
        wrists=[d.pose[i] for i in (15,16) if d.pose and d.pose[i].confidence>.35]
        choices=[]
        for i,box in enumerate(d.weapon_boxes):
            ga,gb,gc,gd=box;gx,gy=(ga+gc)*213,(gb+gd)*120;gw,gh=(gc-ga)*426,(gd-gb)*240
            score=d.weapon_scores[i] if i<len(d.weapon_scores) else .5
            if score<.18 or gw*gh>bh*bh*.14:continue
            if not(a-(c-a)*.25<gx/426<c+(c-a)*.25 and b+.04*(e-b)<gy/240<b+.78*(e-b)):continue
            wrist=min(wrists,key=lambda p:math.hypot(gx-p.x*426,gy-p.y*240)) if wrists else None
            distance=math.hypot(gx-wrist.x*426,gy-wrist.y*240) if wrist else float('inf')
            if distance>max(12,bh*.24) and not(score>=.60 and bh>=45):continue
            old=self.hold_candidates.get(d.track_id)
            count=old[2]+1 if old and 0<timestamp-old[0]<.55 and math.hypot(gx-old[1][0],gy-old[1][1])<bh*.30 else 1
            if old and timestamp==old[0]:count=old[2]
            self.hold_candidates[d.track_id]=(timestamp,(gx,gy),count)
            if score<.60 and count<2:continue
            vx,vy=(gx-wrist.x*426,gy-wrist.y*240) if wrist else (gx-(a+c)*213,gy-(b+.50*(e-b))*240)
            length=math.hypot(vx,vy)
            if length<2:vx,vy,length=0,-1,1
            dx,dy=vx/length,vy/length
            reach=max(gw,gh)*.4
            event=HeldWeapon(generation,timestamp,d.track_id,(gx+dx*reach)/426,(gy+dy*reach)/240,dx,dy,((a+c)/2,e),score,'',box,True)
            choices.append(event)
        if choices:self.holds[d.track_id]=max(choices,key=lambda p:p.confidence)
    def process(self,frame):
        if not self.enabled and not self.hud_enabled:return
        began=time.perf_counter()
        try:
            with self._lock:
                if self.hud_enabled:self._process_hud(frame)
                if self.enabled:self._process(frame)
        except Exception as exc:
            self.last_error=str(exc);self.enabled=False
        finally:self.frames+=1;self.total_ms+=(time.perf_counter()-began)*1000

    def _process_hud(self,frame):
        import numpy as np
        if self.hud_reader is None:
            directory=Path(__file__).resolve().parents[1]/'models/hud'
            if not(directory/'gta5_hud_features.npz').exists():return
            from .hud import WeaponHud
            self.hud_reader=WeaponHud(directory)
        rgb=np.frombuffer(frame.pixels,np.uint8).reshape(frame.height,frame.width,3)
        observation,shot=self.hud_reader.update(rgb,frame.generation,frame.timestamp)
        self.hud_generation=frame.generation;self.hud_time=frame.timestamp;self.hud_observation=observation
        if shot and self.enabled:self.hud_shots.append((frame.generation,frame.timestamp,observation.weapon))
        self._bind_hud()

    def _bind_hud(self):
        observation=self.hud_observation
        if self.hud_generation!=self.target_generation or abs(self.hud_time-self.target_time)>1.2:return
        eligible=[d for d in self.targets if d.box[3]>.97 and .08<(d.box[0]+d.box[2])/2<.92 and d.box[3]-d.box[1]>.16]
        if not eligible:return
        owner=max(eligible,key=lambda d:(d.box[3]-d.box[1])*(d.box[2]-d.box[0]));self.foreground_id=owner.track_id
        if not observation or observation.weapon not in ('rifle','pistol'):
            if observation and observation.weapon=='molotov':self.holds.pop(owner.track_id,None)
            return
        a,b,c,e=owner.box;bw,bh=c-a,e-b
        direction=-1. if (a+c)/2>.5 else 1.
        if owner.pose and len(owner.pose)>16:
            shoulders=[owner.pose[i] for i in (11,12) if owner.pose[i].confidence>.45]
            wrists=[owner.pose[i] for i in (15,16) if owner.pose[i].confidence>.45 and b<=owner.pose[i].y<=b+bh*.65]
            if shoulders and len(wrists)==2:
                extension=sum(p.x for p in wrists)/2-sum(p.x for p in shoulders)/len(shoulders)
                if abs(extension)>bw*.12:direction=1. if extension>0 else -1.
        x,y=(a+bw*.08 if direction<0 else c-bw*.08),b+min(.13,bh*.50)
        dx,dy=direction,-.35;length=math.hypot(dx,dy);dx,dy=dx/length,dy/length
        previous=self.holds.get(owner.track_id)
        if previous and previous.box and self.hud_time-previous.timestamp<.4:
            x,y,dx,dy=previous.x,previous.y,previous.dx,previous.dy
        pose=HeldWeapon(self.hud_generation,self.hud_time,owner.track_id,x,y,dx,dy,((a+c)/2,e),observation.confidence,observation.weapon)
        self.holds[owner.track_id]=pose
        remaining=deque(maxlen=12)
        for generation,t,weapon in self.hud_shots:
            if generation!=self.hud_generation or self.hud_time-t>.9:continue
            if not -.25<=t-self.target_time<1.2:remaining.append((generation,t,weapon));continue
            if t-self.cooldowns.get(owner.track_id,float('-inf'))<.06:continue
            event=ShotEvent(generation,t,owner.track_id,x,y,dx,dy,pose.owner_center,observation.confidence,weapon)
            self.cooldowns[owner.track_id]=t
            try:self.events.put_nowait(event)
            except queue.Full:self.events.get_nowait();self.events.put_nowait(event)
        self.hud_shots=remaining
    def _process(self,frame):
        import cv2,numpy as np
        rgb=np.frombuffer(frame.pixels,np.uint8).reshape(frame.height,frame.width,3)
        small=cv2.resize(rgb,(426,240),interpolation=cv2.INTER_AREA)
        hsv=cv2.cvtColor(small,cv2.COLOR_RGB2HSV);value=hsv[:,:,2]
        hot_warm=(hsv[:,:,0]<42)&(hsv[:,:,1]>40)&(value>210)
        previous=self.previous;self.previous=(frame.generation,frame.timestamp,value.copy())
        if previous is None or previous[0]!=frame.generation or not 0<frame.timestamp-previous[1]<.26:
            self.warm_history.clear();self.warm_history.append(hot_warm);return
        prior_hot=tuple(self.warm_history);self.warm_history.append(hot_warm)
        before=previous[2]
        shift,response=cv2.phaseCorrelate(before.astype(np.float32),value.astype(np.float32))
        if response>.1 and abs(shift[0])<43 and abs(shift[1])<24:
            before=cv2.warpAffine(before,np.array([[1,0,shift[0]],[0,1,shift[1]]],np.float32),(426,240),borderMode=cv2.BORDER_REFLECT)
        difference=value.astype(np.int16)-before.astype(np.int16)
        if np.mean(np.abs(difference)>55)>.32:
            self.cut_at=frame.timestamp;self.pending.clear();self.emitted.clear();self.warm_history.clear();self.warm_history.append(hot_warm)
            self.holds.clear();self.hud_shots.clear()
            if self.hud_reader:self.hud_reader.reset()
            return
        warm=(hsv[:,:,0]<42)&(hsv[:,:,1]>40)
        mask=((value>210)&warm&(difference>45)).astype(np.uint8)
        mask[:22]=0;mask[-6:]=0;mask[:,:6]=0;mask[:,-6:]=0
        if mask.mean()>.025:return
        n,labels,stats,centers=cv2.connectedComponentsWithStats(mask,8)
        _,heat_labels,heat_stats,_=cv2.connectedComponentsWithStats(((value>170)&warm).astype(np.uint8),8)
        verification_budget=2
        for idx in sorted(range(1,n),key=lambda i:stats[i,4],reverse=True):
            x,y,w,h,area=stats[idx];cx,cy=centers[idx]
            if not 4<=area<=180 or w>48 or h>35 or area/(w*h)<.18:continue
            # Skin and moving warm lights can change abruptly too. Require a
            # hot warm core inside this component, not a nearby white lamp.
            if np.count_nonzero((labels==idx)&(value>=245))<2:continue
            heat_ids=np.unique(heat_labels[labels==idx])
            if any(heat and heat_stats[heat,4]>140 for heat in heat_ids):continue
            # A flame can flicker into fresh pixels while the surrounding
            # source remains hot. Require a cool recent neighborhood, not
            # just a positive one-frame luminance difference.
            ix,iy=round(cx),round(cy)
            held_here=any(v.trusted and v.generation==frame.generation and 0<=frame.timestamp-v.timestamp<.75 and
                v.box and v.box[0]*426-10<=cx<=v.box[2]*426+10 and v.box[1]*240-10<=cy<=v.box[3]*240+10 for v in self.holds.values())
            if not held_here and any(np.count_nonzero(p[max(0,iy-7):min(240,iy+8),max(0,ix-7):min(426,ix+8)])>=5 for p in prior_hot):continue
            gun_boxes=()
            # Magnify only a compact candidate neighborhood: tiny game guns
            # often vanish in full-frame detector downsampling. This remains
            # independent gun evidence, not a brightness-only fallback.
            hud_player=bool(self.hud_observation and self.hud_observation.weapon in ('rifle','pistol') and self.hud_generation==frame.generation)
            near_person=(not self.targets and not hud_player) or any(d.box[0]-(d.box[2]-d.box[0])*.7<=cx/426<=d.box[2]+(d.box[2]-d.box[0])*.7 and
                d.box[1]<=cy/240<=d.box[1]+(d.box[3]-d.box[1])*.75 for d in self.targets if not(hud_player and d.track_id==self.foreground_id))
            if verification_budget and near_person and self.weapon_model and Path(self.weapon_model).exists():
                verification_budget-=1
                if self.gun_verifier is None:
                    from .context import GunDetector
                    self.gun_verifier=GunDetector(self.weapon_model)
                nh,nw=rgb.shape[:2];rx,ry=cx/426*nw,cy/240*nh
                halfw,halfh=max(32,nw*.085),max(28,nh*.117)
                l,t=max(0,int(rx-halfw)),max(0,int(ry-halfh));r,b=min(nw,int(rx+halfw)),min(nh,int(ry+halfh))
                crop=rgb[t:b,l:r]
                if crop.size:
                    gun_boxes=tuple(((l+d.box[0]*(r-l))/nw,(t+d.box[1]*(b-t))/nh,(l+d.box[2]*(r-l))/nw,(t+d.box[3]*(b-t))/nh)
                                    for d in self.gun_verifier.detect(crop,.30))
            candidate=FlashCandidate(frame.generation,frame.timestamp,float(cx),float(cy),int(w),int(h),gun_boxes)
            self.pending.append(candidate);self._associate(candidate)
        self.pending=deque((c for c in self.pending if c.generation==frame.generation and frame.timestamp-c.timestamp<.65),maxlen=64)
        self.emitted={k:t for k,t in self.emitted.items() if frame.timestamp-t<1}

    def _associate(self,candidate):
        if candidate.generation!=self.target_generation or not -.2<=candidate.timestamp-self.target_time<.85 or self.target_time<self.cut_at-.05:return
        key=(candidate.generation,candidate.timestamp,candidate.cx,candidate.cy)
        if key in self.emitted:return
        cx,cy=candidate.cx,candidate.cy
        options=[]
        for d in self.targets:
            if self.hud_observation and self.hud_observation.weapon in ('rifle','pistol') and self.hud_generation==candidate.generation and d.track_id==self.foreground_id:continue
            if candidate.timestamp-self.cooldowns.get(d.track_id,float('-inf'))<.14:continue
            a,b,c,e=d.box;bh=(e-b)*240
            weapons=(*d.weapon_boxes,*candidate.weapon_boxes)
            if not weapons:continue
            nearby=[];matched=[]
            for ga,gb,gc,gd in weapons:
                # Match a compact observed gun, not a flame elsewhere in
                # the person's upper-body rectangle.
                gx,gy=(ga+gc)*213,(gb+gd)*120
                gw,gh=(gc-ga)*426,(gd-gb)*240
                if gw*gh>bh*bh*.14:continue
                pad=max(5,min(12,max(gw,gh)*.4))
                if ga*426-pad<=cx<=gc*426+pad and gb*240-pad<=cy<=gd*240+pad:
                    nearby.append((gx,gy,gw,gh));matched.append((ga,gb,gc,gd))
            if not nearby:continue
            if bh<35 or not (a-(c-a)*.7<=cx/426<=c+(c-a)*.7 and b+.05*(e-b)<=cy/240<=b+.70*(e-b)):continue
            wrists=[d.pose[i] for i in (15,16) if d.pose and d.pose[i].confidence>.35]
            wrist_ok=False
            if wrists:
                wrist=min(wrists,key=lambda p:math.hypot(cx-p.x*426,cy-p.y*240))
                distance=math.hypot(cx-wrist.x*426,cy-wrist.y*240)
                wrist_ok=distance<=max(12,bh*.24) and any(math.hypot(gx-wrist.x*426,gy-wrist.y*240)<max(12,bh*.22) for gx,gy,gw,gh in nearby)
            if wrist_ok:vx,vy=cx-wrist.x*426,cy-wrist.y*240;score=.85
            else:
                # Cropped game hands frequently have no reliable keypoints.
                # Only CURRENT local gun proof or a freshly verified holding
                # observation can replace wrists; brightness alone never can.
                hold=self.holds.get(d.track_id)
                if not(hold and hold.weapon_type and self.hud_generation==candidate.generation and self.foreground_id==d.track_id):continue
                vx,vy=cx-(a+c)*213,cy-(b+.5*(e-b))*240
                distance=math.hypot(vx,vy);score=.65
            length=math.hypot(vx,vy)
            if length<2:continue
            options.append((distance/max(1,bh),d,vx/length,vy/length,score,matched[0]))
        if not options:return
        _,owner,dx,dy,score,gun_box=min(options,key=lambda v:v[0])
        # Position only: estimate the source end of the bright component,
        # never copy that component's shape into the renderer.
        px=(cx-dx*min(candidate.width,candidate.height)*.25)/426;py=(cy-dy*min(candidate.width,candidate.height)*.25)/240
        a,b,c,e=owner.box
        event=ShotEvent(candidate.generation,candidate.timestamp,owner.track_id,float(px),float(py),float(dx),float(dy),((a+c)/2,e),score)
        self.cooldowns[owner.track_id]=candidate.timestamp
        self.emitted[key]=candidate.timestamp
        prior=self.holds.get(owner.track_id)
        self.holds[owner.track_id]=HeldWeapon(event.generation,event.timestamp,event.owner,event.x,event.y,event.dx,event.dy,event.owner_center,event.confidence,
                                            prior.weapon_type if prior else '',gun_box,bool(prior and prior.trusted))
        try:self.events.put_nowait(event)
        except queue.Full:self.events.get_nowait();self.events.put_nowait(event)
