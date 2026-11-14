"""Timestamp-based box association, brief occlusion retention and render smoothing."""
from dataclasses import dataclass,replace
import math
from .core import Joint


def overlap(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return intersection/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def center(box):
    return (box[0]+box[2])/2,(box[1]+box[3])/2


def family(label):
    return 'vehicle' if label in ('car','bus','truck') else label


def shift(box,dx,dy):
    width,height=box[2]-box[0],box[3]-box[1]
    cx,cy=center(box)
    cx,cy=max(0,min(1,cx+dx)),max(0,min(1,cy+dy))
    return max(0,cx-width/2),max(0,cy-height/2),min(1,cx+width/2),min(1,cy+height/2)


def warp_box(box,matrix):
    if matrix is None:
        return box
    coords=[(matrix[0][0]*x+matrix[0][1]*y+matrix[0][2],matrix[1][0]*x+matrix[1][1]*y+matrix[1][2])
            for x,y in ((box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3]))]
    return (max(0,min(x for x,y in coords)),max(0,min(y for x,y in coords)),
            min(1,max(x for x,y in coords)),min(1,max(y for x,y in coords)))


def map_pose(pose,old_box,new_box,decay=1):
    if not pose:
        return ()
    ow,oh=max(1e-6,old_box[2]-old_box[0]),max(1e-6,old_box[3]-old_box[1])
    nw,nh=new_box[2]-new_box[0],new_box[3]-new_box[1]
    return tuple(Joint(new_box[0]+(p.x-old_box[0])/ow*nw,new_box[1]+(p.y-old_box[1])/oh*nh,p.confidence*decay) for p in pose)


def stable_material_size(raw,prior,dt):
    """Smooth only small complete-observation size noise, at the current feet.

    Larger scale/posture changes are adopted immediately. This does not change
    the observed box, pose analysis, tracking position or visibility decision.
    """
    if not 0<dt<=.4:
        return raw
    width,height=raw[2]-raw[0],raw[3]-raw[1]
    old_width,old_height=prior[2]-prior[0],prior[3]-prior[1]
    if min(width,height,old_width,old_height)<=0:
        return raw
    if max(abs(width/old_width-1),abs(height/old_height-1))>.06:
        return raw
    alpha=1-math.exp(-dt/.18)
    width=old_width+(width-old_width)*alpha
    height=old_height+(height-old_height)*alpha
    cx=(raw[0]+raw[2])/2
    return cx-width/2,raw[3]-height,cx+width/2,raw[3]


@dataclass
class Track:
    ident: str
    label: str
    box: tuple
    last_seen: float
    updated: float
    payload: object
    relative_velocity: tuple = (0.,0.)
    screen_velocity: tuple = (0.,0.)
    appearance: tuple = ()
    hits: int = 1


class TrackManager:
    def __init__(self,retention=1.0):
        self.retention=retention
        self.tracks={}
        self.next_id=1

    def clear(self):
        self.tracks.clear()

    def enrich(self,ident,payload):
        if ident in self.tracks:
            self.tracks[ident].payload=payload

    def update(self,detections,timestamp,camera=None,appearances=()):
        self.tracks={ident:t for ident,t in self.tracks.items() if -.02<=timestamp-t.last_seen<=self.retention}
        predicted={}
        camera_boxes={}
        for ident,track in self.tracks.items():
            dt=max(0,min(.5,timestamp-track.updated))
            camera_boxes[ident]=warp_box(track.box,camera)
            predicted[ident]=shift(camera_boxes[ident],track.relative_velocity[0]*dt,track.relative_velocity[1]*dt)
        pairs=[]
        for i,detection in enumerate(detections):
            for ident,track in self.tracks.items():
                if family(track.label)!=family(detection.label):
                    continue
                box=predicted[ident]
                a,b=center(box),center(detection.box)
                distance=math.hypot(a[0]-b[0],a[1]-b[1])
                diagonal=math.hypot(box[2]-box[0],box[3]-box[1])
                iou=overlap(box,detection.box)
                if iou<.03 and distance>min(.20,max(.045,diagonal*.8)):
                    continue
                size=(detection.box[2]-detection.box[0])*(detection.box[3]-detection.box[1])/max(1e-6,(box[2]-box[0])*(box[3]-box[1]))
                if not .25<size<4:
                    continue
                similarity=1.0
                if appearances and appearances[i] and track.appearance:
                    similarity=sum(a*b for a,b in zip(appearances[i],track.appearance))
                    if similarity<.30 and iou<.45:
                        continue
                cost=.65*(1-iou)+.22*min(1,distance/.15)+.13*(1-similarity)
                pairs.append((cost,i,ident))
        assignments={}
        used=set()
        for cost,i,ident in sorted(pairs):
            if i not in assignments and ident not in used:
                assignments[i]=ident
                used.add(ident)
        output=[]
        for i,detection in enumerate(detections):
            appearance=tuple(appearances[i]) if appearances else ()
            if i in assignments:
                ident=assignments[i]
                track=self.tracks[ident]
                dt=timestamp-track.updated
                old_box=track.box
                # Correct most of the measurement while suppressing detector jitter.
                box=tuple(.78*a+.22*b for a,b in zip(detection.box,predicted[ident]))
                if dt>.04:
                    observed,camera_center=center(detection.box),center(camera_boxes[ident])
                    previous,current=center(old_box),center(box)
                    track.relative_velocity=tuple(max(-.8,min(.8,.45*old+.55*(a-b)/dt))
                                                  for old,a,b in zip(track.relative_velocity,observed,camera_center))
                    track.screen_velocity=tuple(max(-.8,min(.8,.5*old+.5*(a-b)/dt))
                                                for old,a,b in zip(track.screen_velocity,current,previous))
                track.hits+=1
                payload=replace(detection,track_id=ident,box=box,velocity=track.screen_velocity,
                                confirmed=track.hits>=2 or detection.confidence>=.60 or detection.corroborated)
                # At the frame edge, keep the last observed full extent rather
                # than fitting a whole model into a shrinking visible fragment.
                raw=detection.render_box or detection.box
                prior=track.payload.render_box or old_box
                x1,y1,x2,y2=raw
                nw,nh=detection.box[2]-detection.box[0],detection.box[3]-detection.box[1]
                ow,oh=prior[2]-prior[0],prior[3]-prior[1]
                interior=min(detection.box[:2])>.015 and max(detection.box[2:])<.985
                if (interior and detection.label=='person' and detection.posture_hint!='DOWN'
                        and not track.payload.predicted and not track.payload.seated and not detection.seated
                        and detection.action not in ('SIT','SIT_GESTURE','CROUCH','DOWN','FALL')
                        and track.payload.action not in ('SIT','SIT_GESTURE','CROUCH','DOWN','FALL')):
                    x1,y1,x2,y2=stable_material_size(raw,prior,dt)
                if interior and ((nw<ow*.75 and .7<nh/max(oh,1e-6)<1.3) or
                                 (nh<oh*.75 and .7<nw/max(ow,1e-6)<1.3)):
                    # Sudden one-axis shrink is partial occlusion evidence.
                    # Retain the known material extent instead of shrinking it.
                    pc,oc=center(camera_boxes[ident]),center(old_box)
                    px,py=center(prior);px+=pc[0]-oc[0];py+=pc[1]-oc[1]
                    pw,ph=prior[2]-prior[0],prior[3]-prior[1]
                    x1,y1,x2,y2=px-pw/2,py-ph/2,px+pw/2,py+ph/2
                if detection.box[0]<.012:
                    x1=min(x1,x2-(prior[2]-prior[0]))
                if detection.box[2]>.988:
                    x2=max(x2,x1+(prior[2]-prior[0]))
                if detection.box[1]<.012:
                    y1=min(y1,y2-(prior[3]-prior[1]))
                if detection.box[3]>.988:
                    y2=max(y2,y1+(prior[3]-prior[1]))
                payload=replace(payload,render_box=(x1,y1,x2,y2))
                track.box,track.last_seen,track.updated,track.payload=box,timestamp,timestamp,payload
                track.appearance=appearance or track.appearance
            else:
                ident=f"目标{self.next_id}"
                self.next_id+=1
                payload=replace(detection,track_id=ident,confirmed=detection.confidence>=.60 or detection.corroborated)
                track=Track(ident,detection.label,detection.box,timestamp,timestamp,payload,appearance=appearance)
                self.tracks[ident]=track
            output.append(payload)
        for ident,track in self.tracks.items():
            if ident in used or any(d.track_id==ident for d in output):
                continue
            age=max(0,timestamp-track.last_seen)
            box=predicted[ident]
            payload=track.payload
            held=replace(payload,box=box,predicted=True,missing_age=age,action="UNKNOWN",
                         confidence=payload.confidence*math.exp(-age*2),velocity=track.screen_velocity,
                         pose=map_pose(payload.pose,track.box,box,.65))
            if payload.render_box:
                dx,dy=center(box)[0]-center(track.box)[0],center(box)[1]-center(track.box)[1]
                a,b,c,d=payload.render_box
                held=replace(held,render_box=(a+dx,b+dy,c+dx,d+dy))
            track.box,track.updated,track.payload=box,timestamp,held
            output.append(held)
        return tuple(output)


class SceneSmoother:
    def __init__(self):
        self.states={}
        self.epoch=None
        self.last_clock=None

    def reset(self):
        self.states.clear()
        self.last_clock=None
        self.epoch=None

    def update(self,scene,media_time,clock,running=True):
        if scene is None:
            self.reset()
            return None
        if scene.scene_epoch!=self.epoch:
            self.reset()
            self.epoch=scene.scene_epoch
        dt=max(0,min(.1,clock-self.last_clock)) if self.last_clock is not None else .1
        self.last_clock=clock
        alpha=1-math.exp(-dt/.065) if running else 1.0
        entities=[]
        states={}
        for entity in scene.entities:
            if scene.frame_clipping and entity.predicted:
                # Retain its identity in the tracker, not an extra grey object
                # on screen. Partially occluded observations still use the
                # complete preset material.
                continue
            if entity.bbox is None:
                entities.append(entity)
                continue
            lead=min(.18,max(0,media_time-entity.sample_time)) if running else 0
            if entity.predicted and entity.missing_age+lead>(1.0 if scene.frame_clipping else .35):
                continue
            target=shift(entity.bbox,entity.velocity[0]*lead,entity.velocity[1]*lead)
            old=self.states.get(entity.track_id,target)
            box=tuple(a+(b-a)*alpha for a,b in zip(old,target))
            states[entity.track_id]=box
            pose=map_pose(entity.pose,entity.bbox,box)
            cx,cy=center(box)
            raw=entity.render_bbox
            if raw:
                dx,dy=cx-entity.x,box[3]-entity.y
                raw=(raw[0]+dx,raw[1]+dy,raw[2]+dx,raw[3]+dy)
            entities.append(replace(entity,bbox=box,x=cx,y=box[3],pose=pose,render_bbox=raw))
        self.states=states
        return replace(scene,entities=tuple(entities))
