"""Image-derived horizon, body landmarks and conservative appearance heuristics.

Horizon and vehicle orientation are estimates, not recovered game geometry.
Pose model: OpenCV Zoo's MediaPipe Pose ONNX conversion (Apache-2.0).
"""
from dataclasses import replace
from pathlib import Path
import math
import numpy as np
import cv2
from .core import Horizon,Joint
from .tracking import TrackManager
from .actions import classify_action,action_mirror,ActionStabilizer,upright_posture,seated_evidence,seated_mirror,seat_context_evidence


class CameraMotion:
    def __init__(self):
        self.gray=None
        self.boxes=()

    def estimate(self,rgb,boxes):
        gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        previous=self.gray
        old_boxes=self.boxes
        self.gray,self.boxes=gray,boxes
        if previous is None or previous.shape!=gray.shape:
            return None
        height,width=gray.shape
        mask=np.full_like(gray,255)
        for box in old_boxes:
            a,b,c,d=box
            mask[max(0,int(b*height)-4):min(height,int(d*height)+4),max(0,int(a*width)-4):min(width,int(c*width)+4)]=0
        mask[int(height*.87):,:]=0
        mask[:18,:]=0
        corners=cv2.goodFeaturesToTrack(previous,120,.02,8,mask=mask,blockSize=7)
        if corners is None or len(corners)<12:
            return None
        corners=corners.reshape(-1,1,2)
        moved,status,error=cv2.calcOpticalFlowPyrLK(previous,gray,corners,None,winSize=(21,21),maxLevel=2)
        if moved is None:
            return None
        returned,back_status,_=cv2.calcOpticalFlowPyrLK(gray,previous,moved,None,winSize=(21,21),maxLevel=2)
        if returned is None:
            return None
        valid=(status.ravel()>0)&(back_status.ravel()>0)&(np.linalg.norm(returned.reshape(-1,2)-corners.reshape(-1,2),axis=1)<1.5)
        if valid.sum()<10:
            return None
        affine,inliers=cv2.estimateAffinePartial2D(corners.reshape(-1,2)[valid],moved.reshape(-1,2)[valid],method=cv2.RANSAC,ransacReprojThreshold=2.5)
        if affine is None or float(inliers.mean())<.55:
            return None
        scale=math.hypot(affine[0,0],affine[0,1])
        if not .8<scale<1.25 or abs(affine[0,2])>width*.25 or abs(affine[1,2])>height*.25:
            return None
        return ((float(affine[0,0]),float(affine[0,1]*height/width),float(affine[0,2]/width)),
                (float(affine[1,0]*width/height),float(affine[1,1]),float(affine[1,2]/height)))


def iou(a,b):
    x1,y1,x2,y2=max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])
    intersection=max(0,x2-x1)*max(0,y2-y1)
    return intersection/max(1e-8,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


class HorizonEstimator:
    def __init__(self):
        self.previous=None

    def estimate(self,rgb,boxes=()):
        h,w=rgb.shape[:2]
        if h<20 or w<20:
            return self.previous or Horizon()
        image=cv2.resize(rgb,(320,180))
        gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
        edges=cv2.Canny(gray,65,145)
        # Exclude objects and common HUD/subtitle regions from geometric evidence.
        for box in boxes:
            x1,y1,x2,y2=box
            edges[max(0,int(y1*180)-2):min(180,int(y2*180)+2),max(0,int(x1*320)-2):min(320,int(x2*320)+2)]=0
        edges[155:,:]=0
        edges[135:,:80]=0
        edges[:12,:]=0
        segments=cv2.HoughLinesP(edges,1,np.pi/180,22,minLineLength=24,maxLineGap=7)
        positive,negative,horizontal=[],[],[]
        if segments is not None:
            for x1,y1,x2,y2 in np.asarray(segments).reshape(-1,4):
                dx,dy=float(x2-x1),float(y2-y1)
                length=math.hypot(dx,dy)
                if abs(dx)<4:
                    continue
                slope=dy/dx
                intercept=y1-slope*x1
                if abs(slope)<.16 and min(y1,y2)<125:
                    horizontal.append((math.atan(slope),length))
                if .18<abs(slope)<3 and (y1+y2)/2>65:
                    (positive if slope>0 else negative).append((slope,intercept,length))
        candidates=[]
        for m1,b1,l1 in positive[:30]:
            for m2,b2,l2 in negative[:30]:
                x=(b2-b1)/(m1-m2)
                y=m1*x+b1
                if 25<x<295 and 22<y<125:
                    candidates.append((x,y,min(l1,l2)))
        measurement=None
        if len(candidates)>=3:
            points=np.array(candidates)
            distances=np.sum((points[:,None,:2]-points[None,:,:2])**2,axis=2)
            support=distances<18**2
            votes=(support*points[None,:,2]).sum(axis=1)
            group=points[support[int(votes.argmax())]]
            if len(group)>=3:
                y=float(np.average(group[:,1],weights=group[:,2]))/180
                confidence=min(.88,.36+len(group)*.025)
                measurement=(y,confidence,"消失点估计")
        if measurement is None:
            hsv=cv2.cvtColor(image,cv2.COLOR_RGB2HSV)
            sky=(((hsv[:,:,0]>85)&(hsv[:,:,0]<125)&(hsv[:,:,1]<155)&(hsv[:,:,2]>115))|
                 ((hsv[:,:,1]<40)&(hsv[:,:,2]>175))).astype(np.uint8)
            count,labels,stats,_=cv2.connectedComponentsWithStats(sky,8)
            eligible=[]
            for label in range(1,count):
                x,y,bw,bh,area=stats[label]
                if y<4 and bw>100 and area>2000 and area<320*180*.8:
                    eligible.append(label)
            if eligible:
                label=max(eligible,key=lambda item:stats[item,cv2.CC_STAT_AREA])
                boundaries=[]
                for x in range(15,305,4):
                    ys=np.flatnonzero(labels[:,x]==label)
                    if len(ys)>6:
                        boundaries.append(int(ys[-1]))
                if len(boundaries)>18:
                    y=float(np.percentile(boundaries,75))/180
                    if .10<y<.75:
                        measurement=(y,.34,"天空边界估计")
        if measurement is None:
            if self.previous:
                self.previous=replace(self.previous,confidence=self.previous.confidence*.88,method="保持上次估计")
            return self.previous or Horizon()
        y,confidence,method=measurement
        roll=0.0
        if len(horizontal)>=3:
            angles=np.array([a for a,_ in horizontal])
            lengths=np.array([v for _,v in horizontal])
            order=np.argsort(angles)
            roll=float(angles[order][np.searchsorted(np.cumsum(lengths[order]),lengths.sum()/2)])
        delta=math.tan(roll)*(w/h)/2
        left,right=np.clip([y-delta,y+delta],.03,.94)
        if self.previous:
            # Bounded corrections avoid snapping onto a passing roof edge.
            alpha=.32 if confidence>.5 else .18
            left=self.previous.left+alpha*np.clip(left-self.previous.left,-.16,.16)
            right=self.previous.right+alpha*np.clip(right-self.previous.right,-.16,.16)
        self.previous=Horizon(float(left),float(right),confidence,method)
        return self.previous


class PoseEstimator:
    def __init__(self,path):
        import onnxruntime as ort
        options=ort.SessionOptions()
        options.intra_op_num_threads=2
        options.inter_op_num_threads=1
        options.add_session_config_entry('session.intra_op.allow_spinning','0')
        options.add_session_config_entry('session.inter_op.allow_spinning','0')
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=["CPUExecutionProvider"])
        self.input_name=self.session.get_inputs()[0].name

    def estimate(self,rgb,box):
        pose=self._estimate_roi(rgb,box)
        h,w=rgb.shape[:2];a,b,c,d=box
        bw,bh=(c-a)*w,(d-b)*h
        feet=bool(pose and all(pose[i].confidence>.6 and pose[i].y>d-(d-b)*.18 for i in (27,28)))
        if d>.975 and bw>bh*.75 and not feet:
            # A broad, bottom-clipped portrait is often upper-body footage.
            # Analyze a padded full-body ROI, then keep only visible landmarks.
            factor=min(2.5,max(1.35,bw/max(1,bh)/.55))
            extended=self._estimate_roi(rgb,(a,b,c,b+(d-b)*factor))
            if extended:return extended
        return pose

    def _estimate_roi(self,rgb,box):
        h,w=rgb.shape[:2]
        x1,y1,x2,y2=box
        bw,bh=(x2-x1)*w,(y2-y1)*h
        side=max(bw,bh)*1.20
        if bh<38 or side<10:
            return ()
        cx,cy=(x1+x2)*w/2,(y1+y2)*h/2
        left,top=cx-side/2,cy-side/2
        transform=np.array([[256/side,0,-left*256/side],[0,256/side,-top*256/side]],dtype=np.float32)
        crop=cv2.warpAffine(rgb,transform,(256,256),borderMode=cv2.BORDER_CONSTANT)
        tensor=np.asarray(crop,dtype=np.float32)[None]/255
        outputs=self.session.run(None,{self.input_name:tensor})
        landmark=next(o for o in outputs if o.shape==(1,195)).reshape(39,5)
        confidence=float(next(o for o in outputs if o.size==1).ravel()[0])
        if confidence<.5:
            return ()
        probability=1/(1+np.exp(-np.clip(landmark[:,3:5],-30,30)))
        points=[]
        for i,row in enumerate(landmark[:33]):
            x,y=(left+row[0]/256*side)/w,(top+row[1]/256*side)/h
            score=float(min(probability[i]))*confidence
            if not (0<=x<=1 and 0<=y<=1):
                score=0
            points.append(Joint(float(x),float(y),score))
        torso=sum(points[i].confidence>.45 for i in (11,12,23,24))
        upper=all(points[i].confidence>.45 for i in (11,12)) and any(points[i].confidence>.45 for i in (0,7,8))
        return tuple(points) if torso>=3 or upper else ()


def estimate_vehicle_view(rgb,box,previous_yaw=0,vehicle_type='car',relative_velocity=(0,0)):
    h,w=rgb.shape[:2]
    x1,y1,x2,y2=box
    crop=rgb[int(y1*h):max(int(y1*h)+1,int(y2*h)),int(x1*w):max(int(x1*w)+1,int(x2*w))]
    if crop.size==0:
        return previous_yaw,.1
    aspect=crop.shape[1]/max(1,crop.shape[0])
    hsv=cv2.cvtColor(crop,cv2.COLOR_RGB2HSV)
    red=((hsv[:,:,0]<10)|(hsv[:,:,0]>170))&(hsv[:,:,1]>120)&(hsv[:,:,2]>90)
    # Frame truncation makes aspect unreliable; do not turn a clipped nose
    # into a side view. Image position alone says nothing about heading.
    if min(x1,y1)<.012 or max(x2,y2)>.988:return previous_yaw,.10
    # Camera elevation and vehicle shape can make a straight car tail wider
    # than 1.15. Treat the observed end-on range as a single view.
    front,side={'truck':(.90,2.3),'bus':(.90,2.3),'motorcycle':(.60,1.8),'boat':(.85,2.9)}.get(vehicle_type,(1.45,2.4))
    oblique=math.degrees(math.asin(float(np.clip((aspect-front)/max(.1,side-front),0,1))))
    options=(oblique,180-oblique,180+oblique,360-oblique)
    # Require a compact left/right pair of lower red lamps. Red paint or a
    # red background must not decide the car is showing its rear.
    rh,rw=red.shape;mask=red.astype(np.uint8);mask[:int(rh*.45)]=0
    n,_,stats,centroids=cv2.connectedComponentsWithStats(mask,8)
    lamps=[]
    for (x,y,ww,hh,area),(cx,cy) in zip(stats[1:],centroids[1:]):
        if .0006<area/(rh*rw)<.025 and ww<rw*.24 and hh<rh*.28:lamps.append((cx/rw,cy/rh))
    rear_cue=any(a[0]<.42 and b[0]>.58 and abs(a[1]-b[1])<.14 for a in lamps for b in lamps)
    if vehicle_type=='car' and rw>=45 and aspect<1.65:
        aligned_pair=any(
            a[0]<.32 and b[0]>.68 and abs((a[0]+b[0])/2-.5)<.08 and abs(a[1]-b[1])<.06
            for a in lamps for b in lamps
        )
        if aligned_pair:
            return 0.,.60
    if rear_cue:options=(oblique,360-oblique)
    vx=relative_velocity[0]
    if abs(vx)>.025 and oblique>25:
        directed=tuple(v for v in options if math.sin(math.radians(v))*vx>=0)
        if directed:options=directed
    candidate=min(options,key=lambda v:abs((v-previous_yaw+180)%360-180))%360
    return float(candidate),(.45 if rear_cue else .32)


def stabilize_vehicle_yaw(previous,candidate,confidence,dt):
    """Suppress weak view jitter without adding a frame-count waiting period.

    The angles remain appearance estimates. Missing/edge-clipped evidence does
    not rotate an observed vehicle; reliable evidence corrects it promptly.
    """
    if confidence<.2 or dt<=0:
        return previous
    if dt>.75:
        return candidate
    difference=(candidate-previous+180)%360-180
    reliable=confidence>=.55
    deadband=.5 if reliable else (1.5 if confidence>=.4 else 3.0)
    if abs(difference)<=deadband:
        return candidate if reliable else previous
    tau=.045 if reliable else (.10 if confidence>=.4 else .18)
    step=difference*(1-math.exp(-dt/tau))
    if not reliable:
        speed=360 if confidence>=.4 else 180
        step=max(-speed*dt,min(speed*dt,step))
    return (previous+step)%360


class SceneAnalyzer:
    def __init__(self,model_dir):
        self.model_dir=Path(model_dir)
        self.pose_model=None
        self.reset()

    def reset(self):
        self.horizon=HorizonEstimator()
        if not hasattr(self,'tracker'):
            self.tracker=TrackManager()
        self.tracker.clear()
        self.enriched={}
        self.action_states={};self.seated_states={}
        self.revision=getattr(self,'revision',0)+1
        self.camera_motion=CameraMotion()
        self.last_time=None
        self.histogram=None

    def analyze(self,frame,detections):
        rgb=np.frombuffer(frame.pixels,dtype=np.uint8).reshape(frame.height,frame.width,3)
        # Camera flow describes the background, not object detail. Keep its
        # working size bounded while the detector and pose use native pixels.
        motion_rgb=cv2.resize(rgb,(480,round(480*frame.height/frame.width))) if frame.width>480 else rgb
        histogram=cv2.calcHist([motion_rgb],[0],None,[32],[0,256])
        cv2.normalize(histogram,histogram)
        cut=self.histogram is not None and cv2.compareHist(self.histogram,histogram,cv2.HISTCMP_BHATTACHARYYA)>.65
        if cut or (self.last_time is not None and (frame.timestamp-self.last_time>1 or frame.timestamp<self.last_time-.02)):
            self.reset()
        self.histogram=histogram
        self.last_time=frame.timestamp
        horizon=self.horizon.estimate(rgb,[d.box for d in detections])
        camera=self.camera_motion.estimate(motion_rgb,[d.box for d in detections])
        appearances=[]
        for detection in detections:
            x1,y1,x2,y2=detection.box
            crop=rgb[int(y1*frame.height):max(int(y1*frame.height)+1,int(y2*frame.height)),
                     int(x1*frame.width):max(int(x1*frame.width)+1,int(x2*frame.width))]
            if crop.size:
                hsv=cv2.cvtColor(crop,cv2.COLOR_RGB2HSV)
                histogram=cv2.calcHist([hsv],[0,1],None,[12,4],[0,180,0,256]).ravel()
                histogram/=max(1e-6,float(np.linalg.norm(histogram)))
                appearances.append(tuple(float(x) for x in histogram))
            else:
                appearances.append(())
        tracked=self.tracker.update(detections,frame.timestamp,camera,appearances)
        old_enriched=self.enriched
        state={}
        enriched=[]
        pose_budget=3
        # Reserve one of the existing three pose slots for a broad, compact
        # person. Sorting only by height starved seated people behind walkers.
        people=sorted((d for d in tracked if d.label=='person' and not d.predicted),key=lambda d:-(d.box[3]-d.box[1]))
        chosen={d.track_id for d in people[:2]}
        compact=[d for d in people[2:] if (d.box[2]-d.box[0])*frame.width/max(1,(d.box[3]-d.box[1])*frame.height)>.65
                 and (d.box[3]-d.box[1])*frame.height>55]
        supported=[d for d in people[2:] if seat_context_evidence(d,frame.width/frame.height)]
        if supported:compact=supported
        third=max(compact,key=lambda d:(d.box[2]-d.box[0])*(d.box[3]-d.box[1]),default=people[2] if len(people)>2 else None)
        if third:chosen.add(third.track_id)
        for detection in sorted(tracked,key=lambda d:(d.predicted,-(d.box[3]-d.box[1]))):
            ident=detection.track_id
            old=old_enriched.get(ident)
            if detection.predicted:
                enriched.append(detection)
                if old:
                    state[ident]=old
                continue
            pose=();sitting=None;seat_left=False
            action='DOWN' if detection.posture_hint=='DOWN' else 'UNKNOWN'
            mirrored=detection.action_mirror if action=='DOWN' else False
            yaw=old['yaw'] if old else 0
            view_confidence=0.0
            if detection.label=="person" and ident in chosen and pose_budget>0 and (detection.box[3]-detection.box[1])*frame.height>=38:
                if self.pose_model is None:
                    self.pose_model=PoseEstimator(self.model_dir/'pose_estimation_mediapipe_2023mar.onnx')
                pose=self.pose_model.estimate(rgb,detection.box)
                pose_budget-=1
                if pose:
                    sitting=seated_evidence(pose,frame.width/frame.height);seat_left=seated_mirror(pose)
                    classified=classify_action(pose,old['pose'] if old else None,frame.timestamp-old['time'] if old else .2,frame.width/frame.height,detection.object_hints)
                    # A visible upright head/torso overrides a rotated box
                    # proposal, e.g. a broad upper-body portrait or bending.
                    if action!='DOWN' or upright_posture(pose,frame.width/frame.height):
                        action=classified;mirrored=action_mirror(pose,action)
                    if old and old['pose']:
                        pose=tuple(Joint(.55*p.x+.45*q.x,.55*p.y+.45*q.y,p.confidence)
                                   if p.confidence>.45 and q.confidence>.45 else p for p,q in zip(pose,old['pose']))
                    sitting=seated_evidence(pose,frame.width/frame.height);seat_left=seated_mirror(pose)
            elif detection.label=='dog':
                mirrored=old['mirror'] if old else False
                track=self.tracker.tracks.get(ident)
                if track:
                    vx,vy=track.relative_velocity
                    if abs(vx)>max(.025,abs(vy)):
                        mirrored=vx<0
            elif detection.label!="person":
                relative=self.tracker.tracks[ident].relative_velocity if ident in self.tracker.tracks else (0,0)
                candidate,view_confidence=estimate_vehicle_view(rgb,detection.box,yaw,detection.label,relative)
                if old:
                    yaw=stabilize_vehicle_yaw(yaw,candidate,view_confidence,frame.timestamp-old['time'])
                else:
                    yaw=candidate
            if detection.label=='person':
                box=detection.box
                horizontal=(box[2]-box[0])*frame.width/max(1,(box[3]-box[1])*frame.height)>1.25
                if action=='UNKNOWN' and old and old.get('action')=='DOWN' and horizontal:
                    # Requires a CURRENT person detection. Never draw a held
                    # prediction when the person has disappeared.
                    action='DOWN';mirrored=old.get('mirror',False)
                stabilizer=self.action_states.setdefault(ident,ActionStabilizer())
                action,mirrored=stabilizer.update(action,mirrored,frame.timestamp)
            seated=False
            if detection.label=='person':
                if sitting is None and seat_context_evidence(detection,frame.width/frame.height):
                    sitting=True
                    if action=='UNKNOWN':action='SIT'
                state_filter=self.seated_states.setdefault(ident,ActionStabilizer())
                if sitting is True and pose and all(pose[i].confidence>.6 for i in (11,12,23,24,25,26)):
                    # Two agreeing visible knee chains can establish posture
                    # in one observation, like paused first-frame pose labels.
                    state_filter.current=('SIT',seat_left)
                posture,_=state_filter.update('SIT' if sitting is True else 'IDLE' if sitting is False else 'UNKNOWN',seat_left,frame.timestamp)
                seated=posture=='SIT' and action not in ('DOWN','FALL')
                seat_left=state_filter.current[1]
            payload=replace(detection,seated=seated,seat_mirror=seat_left,pose=pose,action=action,action_mirror=mirrored,yaw=yaw,view_confidence=view_confidence)
            enriched.append(payload)
            self.tracker.enrich(ident,payload)
            state[ident]=dict(time=frame.timestamp,pose=pose,yaw=yaw,action=action,mirror=mirrored)
        self.enriched=state
        self.seated_states={k:v for k,v in self.seated_states.items() if k in state}
        self.action_states={ident:value for ident,value in self.action_states.items() if ident in state}
        return tuple(enriched),horizon
