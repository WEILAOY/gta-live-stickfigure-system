"""Conservative pose categories select fixed assets; they never generate art.

Phone/drink labels require a nearby detected prop. Hug, dance, climb, punch,
lifting and rowing remain explicit manual presets: a single 2-D skeleton
cannot establish these scene meanings reliably.
"""
import math
from dataclasses import dataclass

def seated_evidence(pose,aspect=1.):
    """Screen-space sitting evidence; None means insufficient visible joints."""
    if len(pose or ())<33 or not all(pose[i].confidence>.55 for i in (11,12,23,24)):return None
    sx,sy=(pose[11].x+pose[12].x)*aspect/2,(pose[11].y+pose[12].y)/2
    hx,hy=(pose[23].x+pose[24].x)*aspect/2,(pose[23].y+pose[24].y)/2
    torso=math.hypot(hx-sx,hy-sy)
    if torso<.025 or hy-sy<torso*.55:return False
    votes=[]
    for hip,knee,ankle in ((23,25,27),(24,26,28)):
        if not (pose[hip].confidence>.7 and pose[knee].confidence>.55 and pose[ankle].confidence>.28):continue
        a,b,c=pose[hip],pose[knee],pose[ankle]
        u=((a.x-b.x)*aspect,a.y-b.y);v=((c.x-b.x)*aspect,c.y-b.y)
        length=math.hypot(*u)*math.hypot(*v)
        angle=math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/max(1e-8,length)))))
        match=(55<angle<125 and -.20*torso<b.y-a.y<.42*torso
               and c.y-b.y>torso*.55 and c.y-a.y>torso*.65)
        # Reclined seats project knees above hips. Accept weak ankles only
        # with two agreeing legs and strong hip/knee observations below.
        reclined=(55<angle<130 and -.60*torso<b.y-a.y<-.12*torso
                  and c.y-b.y>torso*.25 and abs(u[0])>torso*.15
                  and min(pose[hip].confidence,pose[knee].confidence)>.6)
        match=match or reclined
        votes.append((match,min(pose[i].confidence for i in (hip,knee,ankle)),abs(u[0]),u[0]))
    if not votes:return None
    if len(votes)==2:
        aligned=votes[0][3]*votes[1][3]>=0 or max(v[2] for v in votes)<torso*.20
        return aligned and all(v[0] for v in votes)
    # One clear side-view leg can support sitting; ambiguous occlusion cannot.
    return True if votes[0][0] and votes[0][1]>.75 and votes[0][2]>torso*.45 else None

def seated_posture(pose,aspect=1.):return seated_evidence(pose,aspect) is True

def seated_mirror(pose):
    if len(pose or ())<33:return False
    legs=[(h,k) for h,k in ((23,25),(24,26)) if min(pose[h].confidence,pose[k].confidence)>.55]
    return bool(legs and sum(pose[k].x-pose[h].x for h,k in legs)<0)

def seat_context_evidence(detection,aspect=1.):
    """Independent detected seat plus lower-body overlap; never width alone."""
    a,b,c,d=detection.box;w,h=c-a,d-b
    if detection.confidence<.6 or h<.12 or d>.97 or not .50<w*aspect/h<1.5:return False
    for hint in detection.object_hints:
        if hint.label not in ('chair','couch') or hint.confidence<.60:continue
        x,y,z,v=hint.box;mid=(x+z)/2
        overlap=max(0,min(c,z)-max(a,x))
        if a-w*.15<=mid<=c+w*.15 and overlap>min(w,z-x)*.35 and b+h*.45<(y+v)/2<d+h*.1 and v>b+h*.65:
            return True
    return False

def horizontal_posture(pose,aspect=1):
    """Observed horizontal torso AND head-to-leg alignment; no hit/death claim."""
    if len(pose or ())<33:return False
    if not all(pose[i].confidence>.5 for i in (0,11,12,23,24)):return False
    feet=[pose[i] for i in (27,28) if pose[i].confidence>.45]
    if not feet:return False
    sx,sy=(pose[11].x+pose[12].x)/2,(pose[11].y+pose[12].y)/2
    hx,hy=(pose[23].x+pose[24].x)/2,(pose[23].y+pose[24].y)/2
    dx,dy=abs(hx-sx)*aspect,abs(hy-sy)
    fx,fy=sum(p.x for p in feet)/len(feet),sum(p.y for p in feet)/len(feet)
    length=abs(fx-pose[0].x)*aspect;rise=abs(fy-pose[0].y)
    return dx>.025 and dx>dy*1.4 and length>max(rise*1.35,dx*1.3)

def upright_posture(pose,aspect=1):
    if len(pose or ())<33 or not all(pose[i].confidence>.5 for i in (0,11,12)):return False
    sx,sy=(pose[11].x+pose[12].x)/2,(pose[11].y+pose[12].y)/2
    return sy-pose[0].y>max(.012,abs(sx-pose[0].x)*aspect*1.2)


def classify_action(pose,previous=None,dt=.2,aspect=1.0,object_hints=()):
    if len(pose or ())<33:return 'UNKNOWN'
    if horizontal_posture(pose,aspect):return 'DOWN'
    def valid(*ids):return all(pose[i].confidence>.45 for i in ids)
    if not valid(11,12):return 'UNKNOWN'
    def point(i):return pose[i].x*aspect,pose[i].y
    def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
    def angle(a,b,c):
        a,b,c=point(a),point(b),point(c)
        u=(a[0]-b[0],a[1]-b[1]);v=(c[0]-b[0],c[1]-b[1])
        den=max(1e-8,math.hypot(*u)*math.hypot(*v))
        return math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/den))))
    shoulder=(pose[11].y+pose[12].y)/2
    cx=(pose[11].x+pose[12].x)/2
    if valid(23,24):
        hip=(pose[23].y+pose[24].y)/2
        body=max(.04,distance((cx*aspect,shoulder),((pose[23].x+pose[24].x)*aspect/2,hip)))
    else:
        if not valid(0):return 'UNKNOWN'
        body=max(.04,abs(pose[11].x-pose[12].x)*aspect*.8,abs(shoulder-pose[0].y)*1.7)
        hip=shoulder+body
    wrists=[i for i in (15,16) if valid(i)]
    heads=[point(i) for i in (0,7,8) if valid(i)]
    near_face=[i for i in wrists if heads and min(distance(point(i),h) for h in heads)<body*.58
               and pose[i].y<shoulder+body*.08]
    # Semantic names require both the object detector and hand proximity.
    for hint in object_hints:
        if hint.confidence<.40:continue
        center=((hint.box[0]+hint.box[2])*aspect/2,(hint.box[1]+hint.box[3])/2)
        close=[i for i in wrists if distance(point(i),center)<body*.60]
        if hint.label=='phone' and close:
            return 'PHONE' if any(i in near_face for i in close) else 'PHONE_LOOK'
        if hint.label in ('cup','glass','bottle') and any(i in near_face for i in close):return 'DRINK'
    if seated_posture(pose,aspect):
        return 'SIT_GESTURE' if any(pose[i].y<hip-body*.15 for i in wrists) else 'SIT'
    raised=[i for i in wrists if pose[i].y<shoulder-body*.25]
    if len(raised)==2:return 'RAISE'
    if near_face:return 'HAND_FACE'
    if raised:return 'WAVE'
    hand_high=any(pose[i].y<hip-body*.15 for i in wrists)
    legs=valid(23,24,25,26,27,28)
    if legs:
        bend=(angle(23,25,27)+angle(24,26,28))/2
        if bend<118:
            knee=(pose[25].y+pose[26].y)/2
            knee_span=abs(pose[25].x-pose[26].x)
            ankle_span=abs(pose[27].x-pose[28].x)
            if ankle_span<knee_span*.72 and knee>hip:return 'CROUCH'
    for s,e,w in ((11,13,15),(12,14,16)):
        if valid(s,e,w) and abs(pose[w].x-cx)*aspect>body*1.05 and \
           shoulder-body*.25<pose[w].y<hip-body*.15 and angle(s,e,w)>145:return 'POINT'
    if len(wrists)==2 and all(shoulder-body*.20<pose[i].y<hip-body*.15 for i in wrists):
        if distance(point(15),point(16))<body*.95:return 'ARMS_FORWARD'
        return 'GESTURE'
    if legs:
        movement=0.0
        if previous and len(previous)>=33 and .04<dt<.6 and all(previous[i].confidence>.45 for i in (23,24,27,28)):
            oldhip=(previous[23].x+previous[24].x)/2
            newhip=(pose[23].x+pose[24].x)/2
            movement=max(abs((pose[i].x-newhip)-(previous[i].x-oldhip)) for i in (27,28))*aspect/body/dt
        separation=abs(pose[27].x-pose[28].x)*aspect/body
        lean=abs((pose[11].x+pose[12].x-pose[23].x-pose[24].x)/2)*aspect/body
        if movement>2.2 and (bend<135 or lean>.2):return 'RUN'
        if movement>.18 or separation>1.2:return 'WALK'
        return 'IDLE'
    return 'GESTURE' if hand_high else 'UNKNOWN'


def action_mirror(pose,action):
    if action in ('SIT','SIT_GESTURE'):return seated_mirror(pose)
    if action=='DOWN' and len(pose or ())>=33:
        return pose[0].x<(pose[23].x+pose[24].x)/2
    if len(pose or ())<33 or action not in ('WAVE','POINT','HAND_FACE','PHONE','DRINK'):return False
    wrists=[i for i in (15,16) if pose[i].confidence>.45]
    if not wrists:return False
    center=(pose[11].x+pose[12].x)/2
    chosen=(max(wrists,key=lambda i:abs(pose[i].x-center)) if action=='POINT'
            else min(wrists,key=lambda i:pose[i].y))
    return pose[chosen].x<center


@dataclass
class ActionStabilizer:
    current: tuple = ('UNKNOWN',False)
    candidate: tuple = ('UNKNOWN',False)
    since: float = 0
    count: int = 0
    last_known: float = float('-inf')
    last_time: float | None = None

    def update(self,action,mirror,timestamp):
        if self.last_time is not None and (timestamp<self.last_time or timestamp-self.last_time>1):
            self.current=('UNKNOWN',False);self.candidate=('UNKNOWN',False);self.count=0
            self.last_known=float('-inf')
        self.last_time=timestamp
        if action=='UNKNOWN':
            self.candidate=('UNKNOWN',False);self.count=0
            if timestamp-self.last_known>.35:self.current=('IDLE',False)
            return self.current
        self.last_known=timestamp
        value=(action,mirror)
        if self.current[0]=='UNKNOWN':self.current=value
        if value!=self.candidate:
            self.candidate=value;self.since=timestamp;self.count=1
        else:self.count+=1
        if self.count>=2 and timestamp-self.since>=.12:self.current=value
        return self.current
