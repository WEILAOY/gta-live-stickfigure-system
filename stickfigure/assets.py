"""Code-native articulated figures and a continuous 3D car illustration."""
from dataclasses import dataclass, replace
from functools import lru_cache
import math
from .core import Joint

VEHICLE_VIEWS={"自动估计":None,"车尾":(0,22),"右后斜视":(45,22),"右侧":(90,22),
               "右前斜视":(135,22),"车头":(180,22),"左前斜视":(225,22),
               "左侧":(270,22),"左后斜视":(315,22),"俯视":(0,78),"高位斜前":(135,55),"自由角度":(0,22)}
ACTION_GROUPS={
    "人物·基础":("站立","行走","奔跑","抬手","下蹲","坐姿"),
    "人物·交流":("挥手","指向","交谈手势","手靠面部","看手机","打电话"),
    "人物·生活":("举杯","双臂前伸","坐姿交流","搂抱","舞动"),
    "人物·运动":("举重","划桨","攀爬","挥拳"),
    "人物·战斗":("持枪","射击","中弹","侧倒","倒地"),
}
ACTIONS={"自动姿态":None,"站立":"IDLE","行走":"WALK","奔跑":"RUN","抬手":"RAISE","下蹲":"CROUCH","坐姿":"SIT",
         "挥手":"WAVE","指向":"POINT","交谈手势":"GESTURE","手靠面部":"HAND_FACE","看手机":"PHONE_LOOK","打电话":"PHONE",
         "举杯":"DRINK","双臂前伸":"ARMS_FORWARD","坐姿交流":"SIT_GESTURE","搂抱":"HUG","舞动":"DANCE",
         "举重":"LIFT","划桨":"ROW","攀爬":"CLIMB","挥拳":"PUNCH",
         "持枪":"GUN_HOLD","射击":"GUN_FIRE","中弹":"HIT","侧倒":"FALL","倒地":"DOWN"}
ANIMATED_ACTIONS=frozenset(('WALK','RUN','WAVE','POINT','GESTURE','PHONE_LOOK','DRINK',
                           'SIT_GESTURE','HUG','DANCE','LIFT','ROW','CLIMB','PUNCH','GUN_FIRE','HIT','FALL'))
PERSON_ASPECT={'RAISE':.65,'CROUCH':.58,'SIT':.82,'WAVE':.72,'POINT':.85,
              'GESTURE':.62,'HAND_FACE':.48,'PHONE_LOOK':.48,'PHONE':.48,'DRINK':.55,
              'ARMS_FORWARD':.57,'SIT_GESTURE':.86,'HUG':.72,'DANCE':.85,
              'LIFT':.90,'ROW':1.0,'CLIMB':.70,'PUNCH':.88}
PERSON_ASPECT.update(GUN_HOLD=.38,GUN_FIRE=.38,HIT=.38,FALL=.38,DOWN=.38)
WEAPONS={'手枪':'pistol','长枪':'rifle'}
COMBAT_VIEWS={'斜后方':35,'正后方':0,'侧面':90,'正面':180}
VEHICLE_MODELS={'自动类别':None,'汽车':'car','货车':'truck','船':'boat','摩托车':'motorcycle','直升机':'helicopter'}
MODEL_GALLERIES={'车辆九视图':'car','货车九视图':'truck','船只九视图':'boat','摩托车九视图':'motorcycle','直升机九视图':'helicopter'}

def shot_phase(t):
    return t%0.45 if t>=0 else 0.45

FLASH_DURATION=.120
FLASH_STAGES=('起闪','最亮','消散')

def flash_stage(t):
    phase=shot_phase(t)
    return 0 if phase<.020 else 1 if phase<.090 else 2 if phase<FLASH_DURATION else None

def weapon_recoil(action,t):
    return .035*math.exp(-shot_phase(t)/.045) if action=='GUN_FIRE' and shot_phase(t)<.20 else 0

def weapon_muzzle(weapon,action='GUN_FIRE',t=0):
    # Exactly the center of the preset barrel's end face, including recoil.
    return (.11,.275,.50-weapon_recoil(action,t)) if weapon=='pistol' else (.11,.29,.79-weapon_recoil(action,t))

@dataclass(frozen=True)
class FlashFace:
    points: tuple[tuple[float,float,float],...]
    fill: str
    stroke: str

@lru_cache(maxsize=8)
def muzzle_flash_faces(weapon,stage):
    """Two fixed three-state materials in local muzzle coordinates (+z)."""
    if stage not in (0,1,2):return ()
    scale=(.55,1.0,.62)[stage]
    radius=(.052 if weapon=='pistol' else .065)*scale
    length=(.13 if weapon=='pistol' else .24)*scale
    outer=('#ffe7a8','#ffd36b','#fff0c9')[stage]
    # The pistol is a compact short star, the rifle an elongated pointed cone.
    profile=((0,0),(-.60,.20),(-.22,.38),(-1,.52),(-.25,.66),(0,1),(.25,.66),(1,.52),(.22,.38),(.60,.20))
    if weapon=='rifle':profile=((0,0),(-.50,.16),(-1,.28),(-.30,.48),(-.55,.63),(0,1),(.55,.63),(.30,.48),(1,.28),(.50,.16))
    faces=[]
    for core in (False,True):
        r=radius*(.38 if core else 1);l=length*(.66 if core else 1)
        fill='#ffffff' if core else outer;stroke='#fff4cf' if core else '#d58a2b'
        for plane in ('xz','yz'):
            points=tuple((q*r,0,z*l) if plane=='xz' else (0,q*r,z*l) for q,z in profile)
            faces.append(FlashFace(points,fill,stroke))
        # A small radial cap keeps the preset readable when looking along the
        # barrel; the crossed longitudinal planes alone would be edge-on.
        cap=[]
        for i in range(12):
            angle=i*math.tau/12;rr=r*1.4*(1 if i%2==0 else .43)
            cap.append((math.cos(angle)*rr,math.sin(angle)*rr,length*.38))
        faces.append(FlashFace(tuple(cap),fill,stroke))
    return tuple(faces)

def fallen_box(box,mirror=False):
    a,b,c,d=box;h=d-b;center=(a+c)/2
    left=center-(.86 if mirror else .14)*h
    return [left,b,left+h,d]

@lru_cache(maxsize=2)
def down_bounds(mirror=False):
    pose=preset_pose('DOWN',mirror=mirror)
    points=[p for p in pose if p.confidence>.25]
    head=pose[0];radius=.065
    return (min(min(p.x for p in points),head.x-radius),
            min(min(p.y for p in points),head.y-radius*1.15),
            max(max(p.x for p in points),head.x+radius),
            max(max(p.y for p in points),head.y+radius*1.15))

def down_render_box(extent,mirror=False):
    """Fit fixed lying material to a lying extent; never infer standing height."""
    a,b,c,d=extent;u,v,x,y=down_bounds(mirror)
    size=min((c-a)/max(.01,x-u),(d-b)/max(.01,y-v))
    left=(a+c)/2-(u+x)*size/2;top=d-y*size
    return [left,top,left+size,top+size]


@dataclass(frozen=True)
class Primitive:
    kind: str
    points: tuple[float,...]
    fill: str = ""
    stroke: str = "#34495e"
    width: float = 2.0
    role: str = ''


@dataclass(frozen=True)
class VehicleDrawing:
    shapes: tuple[Primitive,...]
    aspect: float


def detail_for_size(pixel_height,previous=None):
    """Choose visible detail from screen height, with optional size hysteresis.

    This changes only decoration, never the material's geometry or scale.
    A caller may keep the last level per observed target to avoid threshold flicker.
    """
    if previous=='compact':return 'standard' if pixel_height>=88 else 'compact'
    if previous=='standard':return 'compact' if pixel_height<72 else 'standard'
    return 'compact' if pixel_height<80 else 'standard'


def _material_shapes(shapes,detail):
    """Keep structural paths; omit only explicitly tagged internal decoration."""
    if detail not in ('compact','standard'):
        raise ValueError('Unknown material detail: '+str(detail))
    output=[]
    for shape in shapes:
        if detail=='compact' and shape.role=='detail':continue
        # Window divisions and small marks stay subordinate to body/wheel lines.
        limit=1.4 if shape.role=='window' else 1.25 if shape.role=='detail' else shape.width
        output.append(replace(shape,width=min(shape.width,limit)) if shape.width>limit else shape)
    return tuple(output)


DOG_ASPECT = 1.65


@lru_cache(maxsize=4)
def dog_drawing(mirror=False,detail='standard'):
    """Fixed side-view line art with separated near and far legs."""
    shapes = (
        Primitive('line', (.29,.48,.16,.42,.06,.22), width=3),
        Primitive('line', (.34,.60,.30,.80,.34,.92,.40,.92), stroke='#768697', width=1.8),
        Primitive('line', (.63,.61,.64,.89,.71,.89), stroke='#768697', width=1.8),
        Primitive('polygon', (.23,.47,.37,.36,.60,.38,.70,.34,.76,.44,.73,.61,
                              .60,.67,.36,.66,.26,.59), '#edf2f5', width=2.5),
        Primitive('line', (.40,.63,.36,.82,.39,.97,.47,.97), width=2.7),
        Primitive('line', (.70,.61,.72,.96,.80,.96), width=2.7),
        Primitive('polygon', (.68,.44,.68,.28,.75,.20,.83,.22,.87,.33,.96,.37,
                              .98,.46,.91,.52,.79,.51,.73,.58), '#edf2f5', width=2.5),
        Primitive('polygon', (.72,.29,.65,.09,.79,.20,.77,.34), '#c2ced7', width=2),
        Primitive('oval', (.81,.30,.837,.345), '#34495e', width=1, role='detail'),
        Primitive('oval', (.946,.375,.986,.433), '#34495e', width=1),
        Primitive('line', (.86,.475,.925,.475), width=1.25, role='detail'),
    )
    shapes=_material_shapes(shapes,detail)
    if not mirror:
        return shapes
    return tuple(Primitive(shape.kind,
                           tuple(1-v if i%2==0 else v for i,v in enumerate(shape.points)),
                           shape.fill,shape.stroke,shape.width,shape.role)
                 for shape in shapes)


def combat_render_box(box,mirror=False):
    a,b,c,d=box;h=d-b;center=(a+c)/2
    # Fixed projection bounds in body-height units. No per-frame fitting:
    # recoil and changing view must not change the person's scale.
    left=center-1.18*h
    return [left,b-.20*h,left+2.36*h,b+1.10*h]

def gun_line_paths(weapon):
    if weapon=='pistol':
        return (((.11,.255,.235),(.11,.255,.50),(.11,.295,.50),(.11,.295,.275),(.11,.40,.275)),
                ((.11,.295,.325),(.11,.385,.325),(.11,.40,.275)),((.09,.275,.50),(.13,.275,.50)))
    return (((.11,.29,.055),(.11,.29,.79)),((.11,.29,.235),(.11,.35,.06),(.11,.26,.06)),
            ((.11,.26,.235),(.11,.26,.51)),((.11,.30,.30),(.11,.40,.30)),
            ((.11,.30,.42),(.11,.42,.44)),((.09,.29,.79),(.13,.29,.79)))

def aimed_gun_drawing(weapon,origin,direction,size,action,t):
    """Fixed line material aimed at an analyzed screen position; no tracing."""
    dx,dy=direction;length=max(.001,math.hypot(dx,dy));dx,dy=dx/length,dy/length
    _,my,mz=weapon_muzzle(weapon,'GUN_HOLD',0)
    recoil=weapon_recoil(action,t)*size;ox,oy=origin[0]-dx*recoil,origin[1]-dy*recoil
    def point(p):
        x,y,z=p;u=(z-mz)*size;v=(y-my+x-.11)*size
        return ox+dx*u-dy*v,oy+dy*u+dx*v
    shapes=[Primitive('line',tuple(v for p in path for v in point(p)),stroke='#34495e',width=2.7,role='weapon') for path in gun_line_paths(weapon)]
    if action=='GUN_FIRE':
        for face in muzzle_flash_faces(weapon,flash_stage(t))[1::3]:
            points=[]
            for x,y,z in face.points:
                points.extend((ox+dx*z*size-dy*y*size,oy+dy*z*size+dx*y*size))
            shapes.append(Primitive('polygon',tuple(points),face.fill,face.stroke,1.2,'muzzle-flash'))
    right=point((.11,.34,.30));left=point((.075,.345,.32) if weapon=='pistol' else (.11,.335,.51))
    return tuple(shapes),(left,right)


def combat_drawing(action='GUN_HOLD',t=0,weapon='rifle',yaw=35,pitch=12,mirror=False):
    """Original slim stick figure and sparse gun lines, projected by view."""
    yaw,pitch=math.radians(yaw),math.radians(pitch)
    cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
    pieces=[]
    recoil=weapon_recoil(action,t)
    def project(p):
        x,y,z=p;xx=cy*x+sy*z;zz=-sy*x+cy*z
        perspective=1/(1+zz*.38)
        return xx*perspective,(.5+(y-.5)*cp-zz*sp)*perspective+.5*(1-perspective),zz
    def add(points,kind='line',fill='',stroke='#34495e',width=2.5,role='body'):
        p=[project(v) for v in points]
        pieces.append((sum(v[2] for v in p)/len(p),kind,[(v[0],v[1]) for v in p],fill,stroke,width,role))
    original=preset_pose('IDLE')
    def body(i):return ((original[i].x-.5)*.38,original[i].y,0)
    add(tuple(body(i) for i in (11,12,24,23,11)),width=1.7)
    for ids in ((23,25,27,31),(24,26,28,32)):add(tuple(body(i) for i in ids),width=3)
    hand_r=(.11,.34-.006*recoil,.30-recoil)
    hand_l=(.075,.345,.32-recoil) if weapon=='pistol' else (.11,.335,.51-recoil)
    add((body(11),(-.09,.43,.12-recoil*.3),hand_l),width=3)
    add((body(12),(.13,.43,.10-recoil*.3),hand_r),width=3)
    add(((0,.18,0),(0,.28,0)),width=3)
    head=project((0,.10,0));r=.065
    pieces.append((head[2],'oval',[(head[0]-r,head[1]-r*1.15),(head[0]+r,head[1]+r*1.15)],'#ffffff','#34495e',2.4))
    # Face marks only when facing the camera, not on the back of the head.
    if cy<-.3:
        for x in (-.025,.025):
            p=project((x,.10,.055));pieces.append((p[2]-.01,'oval',[(p[0]-.004,p[1]-.004),(p[0]+.004,p[1]+.004)],'#111111','#111111',1))
    shift=lambda x,y,z:(x,y,z-recoil)
    for path in gun_line_paths(weapon):add(tuple(shift(*p) for p in path),width=2.7,role='weapon')
    # Hands are preset joints attached to the grip/support positions.
    for hand in (hand_l,hand_r):
        p=project(hand);r=.017
        pieces.append((p[2]-.015,'oval',[(p[0]-r,p[1]-r),(p[0]+r,p[1]+r)],'#ffffff','#34495e',1.4))
    if action=='GUN_FIRE':
        x,y,z=weapon_muzzle(weapon,action,t)
        for face in muzzle_flash_faces(weapon,flash_stage(t)):
            add(tuple((x+u,y+v,z+w) for u,v,w in face.points),'polygon',face.fill,face.stroke,1.2,'muzzle-flash')
    shapes=[]
    for _,kind,points,fill,stroke,width,*role in sorted(pieces,key=lambda p:p[0],reverse=True):
        coords=tuple(v for x,y in points for v in ((1-(x+1.18)/2.36 if mirror else (x+1.18)/2.36),(y+.2)/1.30))
        shapes.append(Primitive(kind,coords,fill,stroke,width,role[0] if role else ''))
    return VehicleDrawing(tuple(shapes),2.36/1.30)


@lru_cache(maxsize=512)
def vehicle_drawing(yaw=0,pitch=22,vehicle_type='car',rotor_phase=0,detail='standard'):
    if vehicle_type in ('truck','boat','motorcycle','helicopter'):
        return transport_drawing(yaw,pitch,vehicle_type,rotor_phase,detail)
    yaw,pitch=math.radians(yaw),math.radians(pitch)
    cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
    pieces=[]

    def project(vertex):
        x,y,z=vertex
        xx=cy*x+sy*z
        zz=-sy*x+cy*z
        return xx,-(cp*y+sp*zz),-sp*y+cp*zz

    def add(vertices,fill="",stroke="#34495e",width=2.2,kind="polygon",role='body'):
        transformed=[project(v) for v in vertices]
        depth=sum(v[2] for v in transformed)/len(transformed)
        pieces.append((depth,[(v[0],v[1]) for v in transformed],fill,stroke,width,kind,role))

    # Bevelled body ring, rear is z<0 and front is z>0.
    ring=[(-.68,-1.75),(.68,-1.75),(.87,-1.48),(.87,1.43),(.65,1.76),(-.65,1.76),(-.87,1.43),(-.87,-1.48)]
    lower=[(x,.31,z) for x,z in ring]
    upper=[(x,.72,z) for x,z in ring]
    for i in range(8):
        j=(i+1)%8
        add([lower[i],lower[j],upper[j],upper[i]],"#f1f5f8")
    add(upper,"#f8fafc")
    roof=[(-.60,1.28,-.72),(.60,1.28,-.72),(.60,1.28,.50),(-.60,1.28,.50)]
    rearbase=[(-.75,.73,-1.14),(.75,.73,-1.14)]
    frontbase=[(-.75,.73,1.06),(.75,.73,1.06)]
    add([rearbase[0],rearbase[1],roof[1],roof[0]],"#dce8ed",role='window')
    add([frontbase[0],roof[3],roof[2],frontbase[1]],"#dce8ed",role='window')
    add([rearbase[0],roof[0],roof[3],frontbase[0]],"#e4edf1",role='window')
    add([rearbase[1],frontbase[1],roof[2],roof[1]],"#e4edf1",role='window')
    add(roof,"#f7fafb")
    for side in (-1,1):
        x=side*.78
        add([(x,.76,-1.05),(side*.61,1.23,-.67),(side*.61,1.23,-.16),(x,.76,-.16)],"#d4e2e9",role='window')
        add([(x,.76,-.10),(side*.61,1.23,-.10),(side*.61,1.23,.44),(x,.76,.94)],"#d4e2e9",role='window')
        add([(side*.88,.40,-.17),(side*.88,.70,-.17)],kind="line",width=1,role='detail')
        add([(side*.88,.63,-.47),(side*.88,.63,-.31)],kind="line",width=2,role='detail')
        add([(side*.78,.88,.70),(side*1.02,.82,.67),(side*1.02,.77,.52),(side*.78,.80,.52)],"#e5edf2",width=1)
        for axle in (-1.12,1.12):
            circle=[(side*.91,.30+math.sin(i*math.tau/28)*.29,axle+math.cos(i*math.tau/28)*.29) for i in range(28)]
            add(circle,"#dde3e8","#263b4c",2.4,role='wheel')
            hub=[(side*.919,.30+math.sin(i*math.tau/20)*.13,axle+math.cos(i*math.tau/20)*.13) for i in range(20)]
            add(hub,"#f8fafb","#627687",1,role='detail')
    for side in (-1,1):
        x=side*.48
        add([(x-.15,.51,-1.76),(x+.15,.51,-1.76),(x+.15,.63,-1.76),(x-.15,.63,-1.76)],"#e59189","#ac5f5b",1)
        add([(x-.16,.51,1.77),(x+.16,.51,1.77),(x+.16,.62,1.77),(x-.16,.62,1.77)],"#f6e5ae","#ab9760",1)
    add([(-.28,.40,1.78),(.28,.40,1.78),(.28,.49,1.78),(-.28,.49,1.78)],"#b4c1c9",width=1,role='detail')
    points=[point for _,poly,*_ in pieces for point in poly]
    minx,maxx=min(p[0] for p in points),max(p[0] for p in points)
    miny,maxy=min(p[1] for p in points),max(p[1] for p in points)
    width,height=maxx-minx,maxy-miny
    shapes=[]
    for _,poly,fill,stroke,thickness,kind,role in sorted(pieces,key=lambda piece:piece[0],reverse=True):
        coords=tuple(value for x,y in poly for value in ((x-minx)/width,(y-miny)/height))
        shapes.append(Primitive(kind,coords,fill,stroke,thickness,role))
    return VehicleDrawing(_material_shapes(shapes,detail),width/height)


def transport_drawing(yaw,pitch,vehicle_type,rotor_phase=0,detail='standard'):
    """Code-native motorcycle / helicopter meshes, shared projection and depth."""
    yaw,pitch=math.radians(yaw),math.radians(pitch)
    cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
    pieces=[]
    def project(p):
        x,y,z=p;xx=cy*x+sy*z;zz=-sy*x+cy*z
        return xx,-cp*y-sp*zz,-sp*y+cp*zz
    def add(vertices,fill='',stroke='#34495e',width=2,kind='polygon',role='body'):
        p=[project(v) for v in vertices]
        pieces.append((sum(v[2] for v in p)/len(p),kind,[(v[0],v[1]) for v in p],fill,stroke,width,role))
    def tube(points,width=3,color='#455564',role='body'):add(points,stroke=color,width=width,kind='line',role=role)
    def cuboid(a,b,tones=('#f5f7fa','#c3cbd2','#e2e7eb')):
        x,y,z=a;u,v,w=b
        p=((x,y,z),(u,y,z),(u,v,z),(x,v,z),(x,y,w),(u,y,w),(u,v,w),(x,v,w))
        for i,face in enumerate(((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(0,3,7,4),(1,5,6,2))):
            add([p[j] for j in face],tones[i%3],width=1.6)
    def ring(x,y,z,r,axis='x',n=24):
        if axis=='x':return [(x,y+math.sin(i*math.tau/n)*r,z+math.cos(i*math.tau/n)*r) for i in range(n)]
        return [(x+math.sin(i*math.tau/n)*r,y,z+math.cos(i*math.tau/n)*r) for i in range(n)]
    envelope=[]
    if vehicle_type=='truck':
        # Box cargo truck: separate cab, windshield, cargo doors and six wheels.
        cuboid((-.70,.67,-1.95),(.70,2.02,.45))
        cuboid((-.69,.50,.50),(.69,1.52,1.58))
        cuboid((-.64,1.00,1.59),(.64,1.44,1.605),('#d3e4ee',)*3)
        cuboid((-.71,.98,.64),(-.70,1.44,1.38),('#d3e4ee',)*3)
        cuboid((.70,.98,.64),(.71,1.44,1.38),('#d3e4ee',)*3)
        for x in (-.76,.76):
            for z in (-1.43,-.76,1.05):
                add(ring(x,.36,z,.34),'#7d8c98',width=2.4,role='wheel')
                add(ring(x*1.01,.36,z,.16),'#ffffff',width=1.2,role='detail')
        tube(((0,.72,-1.96),(0,2.0,-1.96)),1.4,role='detail')
        for x in (-.36,.36):tube(((x,1.10,-1.965),(x,1.49,-1.965)),2,role='detail')
        cuboid((-.57,.57,1.60),(-.28,.74,1.62),('#fff2cd',)*3)
        cuboid((.28,.57,1.60),(.57,.74,1.62),('#fff2cd',)*3)
        tube(((-.72,.48,1.63),(.72,.48,1.63)),3)
        for x in (-.52,.52):cuboid((x-.10,.68,-1.97),(x+.10,.80,-1.95),('#d39595',)*3)
    elif vehicle_type=='boat':
        # Low hull, pointed bow (+z), deck, cabin and windshield.
        deck=[(-.65,.59,-1.65),(.65,.59,-1.65),(.72,.59,.25),(.40,.59,1.35),(0,.59,1.85),(-.40,.59,1.35),(-.72,.59,.25)]
        keel=[(x*.65,.12,z*.94) for x,y,z in deck]
        for i in range(len(deck)):
            j=(i+1)%len(deck);add([deck[i],deck[j],keel[j],keel[i]],'#d6e0e7')
        add(deck,'#ffffff')
        cuboid((-.45,.61,-.78),(.45,1.14,.23))
        add([(-.45,.82,.24),(.45,.82,.24),(.39,1.14,.20),(-.39,1.14,.20)],'#d8ebf4')
        for sign in (-1,1):
            x=sign*.46
            add([(x,.84,-.65),(x,1.10,-.65),(x,1.10,.14),(x,.84,.14)],'#d8ebf4')
            tube(((sign*.59,.72,.38),(sign*.34,.72,1.30),(0,.72,1.73)),1.5,role='detail')
        cuboid((-.48,1.13,-.84),(.48,1.21,.29))
        tube(((0,1.22,-.44),(0,1.63,-.44)),2)
        cuboid((-.16,.38,-1.85),(.16,.89,-1.66),('#8798a6','#dce3e9','#a9b6c1'))
    elif vehicle_type=='motorcycle':
        # Narrow tires, two visible rims, frame triangle, engine, tank and seat.
        for z in (-.9,.95):
            for x in (-.10,.10):
                add(ring(x,.34,z,.33),'#6f7d88',width=2.2,role='wheel')
                add(ring(x*1.01,.34,z,.235),'#ffffff',width=1.3,role='detail')
                for angle in (0,math.pi/2,math.pi,math.pi*1.5):
                    tube(((x,.34,z),(x,.34+math.sin(angle)*.22,z+math.cos(angle)*.22)),1,role='detail')
        for x in (-.11,.11):
            tube(((x,.34,-.9),(x,.88,-.45),(x,.91,.36),(x,.34,-.9)))
            tube(((x,.34,-.9),(x,.44,.18),(x,.91,.36)))
            tube(((x,.34,.95),(x,1.15,.63)),3.6)
        cuboid((-.16,.43,-.34),(.16,.74,.15),('#a8b3bd','#cbd2d8','#8896a2'))
        cuboid((-.21,.81,-.14),(.21,1.06,.43))
        cuboid((-.20,.93,-.72),(.20,1.02,-.14),('#aeb9c2','#e4e8ec','#6e7b87'))
        tube(((-.41,1.22,.67),(-.2,1.18,.62),(.2,1.18,.62),(.41,1.22,.67)),3)
        cuboid((-.15,1.03,.68),(.15,1.17,.83),('#ffffff','#dfe9ee','#ffffff'))
        cuboid((-.13,.86,-.84),(.13,.97,-.73),('#d79d9d',)*3)
        tube(((.19,.45,-.72),(.23,.39,-.3)),4)
        tube(((-.12,.84,-.65),(-.12,.66,-.91)),2)
    else:
        # Faceted cabin with a clear nose/windshield and tapered tail boom.
        rings=[]
        for z,width,low,high in ((-.86,.28,.94,1.55),(-.35,.55,.77,1.87),(.65,.51,.78,1.79),(1.30,.26,1.00,1.46)):
            rings.append([(-width,low,z),(width,low,z),(width,high-.20,z),(width*.63,high,z),(-width*.63,high,z),(-width,high-.20,z)])
        add(rings[0],'#d6dfe6');add(rings[-1],'#dcecf5')
        for i in range(len(rings)-1):
            for j in range(6):
                k=(j+1)%6
                glass=i==2 and j in (1,2,3,4,5)
                add([rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]],'#d8eaf4' if glass else ('#ffffff','#d5dde4','#eef2f6')[j%3],width=1.6)
        # Tail extends opposite the cockpit, with vertical fin and tail rotor.
        for sign in (-1,1):
            add([(sign*.28,1.08,-.72),(sign*.07,1.34,-3.08),(sign*.07,1.53,-3.08),(sign*.28,1.55,-.72)],'#e3e9ee')
        add([(-.28,1.55,-.72),(.28,1.55,-.72),(.07,1.53,-3.08),(-.07,1.53,-3.08)],'#f8fafc')
        add([(0,1.40,-3.13),(0,2.03,-3.15),(0,1.91,-2.75),(0,1.42,-2.68)],'#d3dde5')
        cuboid((-.065,1.78,-.10),(.065,2.16,.03))
        # Skid landing gear is unmistakable from side, front and rear.
        for sign in (-1,1):
            x=sign*.60
            tube(((x,.38,-.93),(x,.30,-.75),(x,.30,1.17),(x,.44,1.40)),3)
            for z in (-.45,.62):tube(((sign*.34,.85,z),(x,.34,z)),2.5)
        phase=math.radians(rotor_phase)
        def blade_point(x,z):return (x*math.cos(phase)-z*math.sin(phase),2.18,x*math.sin(phase)+z*math.cos(phase))
        for angle in (0,math.pi/2,math.pi,math.pi*1.5):
            def arm(r,s):return blade_point(math.sin(angle)*r+math.cos(angle)*s,math.cos(angle)*r-math.sin(angle)*s)
            add([arm(.12,-.065),arm(2.25,-.085),arm(2.25,.085),arm(.12,.065)],'#697987',width=1.2)
        add(ring(.12,1.57,-3.06,.34),'',width=1.2,role='detail')
        for angle in (phase,phase+math.pi/2):
            tube(((.13,1.57-math.sin(angle)*.35,-3.06-math.cos(angle)*.35),(.13,1.57+math.sin(angle)*.35,-3.06+math.cos(angle)*.35)),2.6)
        # The rotor sweeps inside fixed bounds, never rescaling the whole model.
        envelope=ring(0,2.18,0,2.26,axis='y',n=48)
    projected=[p for _,_,points,*_ in pieces for p in points]+[(project(p)[0],project(p)[1]) for p in envelope]
    minx,maxx=min(p[0] for p in projected),max(p[0] for p in projected)
    miny,maxy=min(p[1] for p in projected),max(p[1] for p in projected)
    width,height=max(.01,maxx-minx),max(.01,maxy-miny)
    shapes=[]
    for _,kind,points,fill,stroke,weight,role in sorted(pieces,key=lambda p:p[0],reverse=True):
        coords=tuple(v for x,y in points for v in ((x-minx)/width,(y-miny)/height))
        shapes.append(Primitive(kind,coords,fill,stroke,weight,role))
    return VehicleDrawing(_material_shapes(shapes,detail),width/height)


def preset_pose(action,t=0,mirror=False):
    coords={0:(.5,.10),2:(.475,.085),5:(.525,.085),7:(.44,.10),8:(.56,.10),
            11:(.36,.28),12:(.64,.28),13:(.30,.43),14:(.70,.43),15:(.28,.57),16:(.72,.57),
            23:(.43,.56),24:(.57,.56),25:(.40,.76),26:(.60,.76),27:(.37,.96),28:(.63,.96),
            29:(.38,.96),30:(.62,.96),31:(.31,.985),32:(.70,.985)}
    if action in ("WALK","RUN"):
        run=action=="RUN"
        p=math.sin(t*math.tau*(2.7 if run else 1.5))
        extent=.19 if run else .12
        lean=.07 if run else .01
        for key in (0,2,5,7,8,11,12):
            x,y=coords[key];coords[key]=(x+lean,y)
        coords[15]=(.40+extent*p,.53-.05*p)
        coords[16]=(.60-extent*p,.53+.05*p)
        coords[13]=(.33+extent*.5*p,.39)
        coords[14]=(.67-extent*.5*p,.39)
        coords[25]=(.43-extent*.65*p,.75-(.16 if run else .05)*max(0,p))
        coords[26]=(.57+extent*.65*p,.75-(.16 if run else .05)*max(0,-p))
        coords[27]=(.43-extent*p,.96-(.14 if run else .04)*max(0,p))
        coords[28]=(.57+extent*p,.96-(.14 if run else .04)*max(0,-p))
        coords[31]=(coords[27][0]-.07,coords[27][1]+.02)
        coords[32]=(coords[28][0]+.07,coords[28][1]+.02)
    elif action=="RAISE":
        coords.update({13:(.21,.21),14:(.79,.21),15:(.18,.04),16:(.82,.04)})
    elif action=="CROUCH":
        for key in (0,2,5,7,8,11,12,13,14,15,16):
            x,y=coords[key];coords[key]=(x,y+.21)
        coords.update({23:(.45,.76),24:(.55,.76),25:(.27,.86),26:(.73,.86),27:(.39,.97),28:(.61,.97)})
    elif action=="SIT":
        coords.update({23:(.35,.58),24:(.49,.61),25:(.68,.60),26:(.83,.65),27:(.68,.94),28:(.83,.96),
                       13:(.29,.46),14:(.72,.45),15:(.56,.59),16:(.79,.63),29:(.68,.94),30:(.83,.96),31:(.77,.96),32:(.94,.985)})
    elif action=="WAVE":
        p=math.sin(t*math.tau*1.5)
        coords.update({14:(.80,.25),16:(.78+.10*p,.055+.02*abs(p))})
    elif action=="POINT":
        p=math.sin(t*math.tau*.5)*.012
        coords.update({14:(.80,.29+p),16:(.98,.30+p),13:(.30,.43),15:(.40,.49)})
    elif action in ("GESTURE","SIT_GESTURE"):
        p=math.sin(t*math.tau*.8);q=math.sin(t*math.tau*.8+1.1)
        coords.update({13:(.22,.43),14:(.78,.43),15:(.19-.04*p,.37-.06*p),16:(.81+.04*q,.37-.06*q)})
        if action=="SIT_GESTURE":
            coords.update({23:(.35,.58),24:(.49,.61),25:(.68,.60),26:(.83,.65),27:(.68,.94),28:(.83,.96)})
    elif action in ("HAND_FACE","PHONE"):
        coords.update({14:(.80,.36),16:(.61,.13),13:(.30,.43),15:(.30,.59)})
    elif action=="PHONE_LOOK":
        p=math.sin(t*math.tau*.7)*.012
        coords.update({0:(.52,.14),2:(.495,.125),5:(.545,.125),7:(.46,.14),8:(.58,.14),
                       13:(.31,.44),14:(.69,.44),15:(.47,.40),16:(.55+p,.40)})
    elif action=="DRINK":
        p=(1-math.cos(t*math.tau*.28))/2
        coords.update({14:(.79,.43-.08*p),16:(.72-.15*p,.46-.30*p),13:(.30,.43),15:(.30,.59)})
    elif action=="ARMS_FORWARD":
        coords.update({13:(.40,.36),14:(.80,.34),15:(.75,.28),16:(.88,.29)})
    elif action=="HUG":
        p=math.sin(t*math.tau*.35)*.015
        coords.update({13:(.68,.23),14:(.88,.39),15:(.92,.30+p),16:(.75,.49-p)})
    elif action=="DANCE":
        p=math.sin(t*math.tau*.9);q=math.cos(t*math.tau*.9)
        for i in (0,2,5,7,8,11,12,23,24):
            x,y=coords[i];coords[i]=(x+.075*p,y+.025*abs(q))
        coords.update({13:(.17,.28+.08*q),14:(.83,.28-.08*q),15:(.10,.15+.12*q),16:(.90,.15-.12*q),
                       25:(.33,.78),26:(.69,.76),27:(.22,.97-.04*max(0,p)),28:(.78,.97-.04*max(0,-p))})
    elif action=="LIFT":
        p=(1-math.cos(t*math.tau*.35))/2
        coords.update({13:(.21,.48-.20*p),14:(.79,.48-.20*p),15:(.18,.45-.35*p),16:(.82,.45-.35*p),
                       27:(.29,.96),28:(.71,.96)})
    elif action=="ROW":
        p=math.sin(t*math.tau*.65)
        coords.update({23:(.44,.61),24:(.56,.61),25:(.29,.73),26:(.72,.73),27:(.18,.84),28:(.82,.84),
                       13:(.28+.07*p,.40-.05*p),14:(.72+.07*p,.40+.05*p),
                       15:(.36+.13*p,.38-.09*p),16:(.64+.13*p,.38+.09*p)})
    elif action=="CLIMB":
        p=math.sin(t*math.tau*.65)
        coords.update({13:(.25,.20+.06*p),14:(.75,.20-.06*p),15:(.24,.04+.04*p),16:(.76,.04-.04*p),
                       25:(.25,.65-.08*p),26:(.75,.65+.08*p),27:(.30,.88-.08*p),28:(.70,.88+.08*p)})
    elif action=="PUNCH":
        p=max(0,math.sin(t*math.tau*1.0))**2
        coords.update({13:(.27,.39),15:(.42,.26),14:(.73+.08*p,.35-.04*p),16:(.65+.32*p,.24+.03*p),
                       23:(.42,.56),24:(.56,.56),27:(.24,.97),28:(.75,.97)})
    elif action in ('GUN_HOLD','GUN_FIRE'):
        recoil=.035*math.exp(-shot_phase(t)/.045) if action=='GUN_FIRE' and shot_phase(t)<.20 else 0
        coords.update({13:(.45,.41),14:(.69,.42),15:(.70-recoil,.34),16:(.74-recoil,.33)})
    elif action=='HIT':
        kick=math.sin(min(1,(t%1.0)/.30)*math.pi)*.13
        for i in (0,2,5,7,8,11,12,13,14,15,16):
            x,y=coords[i];coords[i]=(x+kick,y+.03*kick)
    elif action in ('FALL','DOWN'):
        p=1 if action=='DOWN' else min(1,max(0,t/.65))
        angle=(p*p*(3-2*p))*math.pi/2
        # Fixed bent-knee material rotates about a foot-side pivot, in
        # physical body-height units rather than a narrow detection box.
        coords[25]=(.40-.10*p,.76-.03*p);coords[26]=(.60+.10*p,.76-.05*p)
        for i,(x,y) in list(coords.items()):
            xx=.38*(x-.5);yy=y-.88
            coords[i]=(.14+xx*math.cos(angle)-yy*math.sin(angle),
                       .88+xx*math.sin(angle)+yy*math.cos(angle)+.04*math.sin(angle))
        lift=max(0,max(y for x,y in coords.values())-.99)
        if lift:coords={i:(x,y-lift) for i,(x,y) in coords.items()}
    # Heels/toes follow the fixed ankle trajectories in every added preset.
    if action not in ('IDLE','WALK','RUN','RAISE','CROUCH','SIT','UNKNOWN','FALL','DOWN'):
        for ankle,heel,toe,direction in ((27,29,31,-1),(28,30,32,1)):
            x,y=coords[ankle];coords[heel]=(x,y);coords[toe]=(x+direction*.065,min(.995,y+.02))
    if mirror:
        coords={i:(1-x,y) for i,(x,y) in coords.items()}
    return tuple(Joint(*coords[i],1) if i in coords else Joint(0,0,0) for i in range(33))


def person_props(action,t=0,mirror=False,weapon='pistol'):
    """Small fixed props; positions come only from our own preset animation."""
    joints=preset_pose(action,t)
    hand=joints[16];pieces=[]
    if action in ('GUN_HOLD','GUN_FIRE'):
        x,y=hand.x,hand.y
        if weapon=='rifle':
            pieces.extend((Primitive('line',(x-.19,y-.015,x+.18,y-.015),width=4),
                           Primitive('line',(x-.19,y-.015,x-.19,y+.04),width=3),
                           Primitive('line',(x-.07,y,x-.05,y+.085),width=3)))
            muzzle=x+.18
        else:
            pieces.append(Primitive('line',(x-.02,y-.025,x+.13,y-.025),width=4));muzzle=x+.13
        pieces.append(Primitive('line',(x,y-.015,x-.015,y+.075),width=3))
        if action=='GUN_FIRE':
            for face in muzzle_flash_faces(weapon,flash_stage(t))[::3]:
                # Compatibility projection of the SAME fixed material. The
                # production gun renderer uses the full depth-sorted mesh.
                points=tuple(v for u,vv,z in face.points for v in (muzzle+z*.30,y-.02+(u+vv)*.6))
                pieces.append(Primitive('polygon',points,face.fill,face.stroke,1.2,'muzzle-flash'))
    if action in ('PHONE','PHONE_LOOK'):
        x,y=(.625,.13) if action=='PHONE' else (.515,.39)
        pieces.append(Primitive('polygon',(x-.025,y-.045,x+.025,y-.045,x+.025,y+.045,x-.025,y+.045),'#e5edf2'))
    elif action=='DRINK':
        x,y=hand.x+.025,hand.y-.025
        pieces.append(Primitive('polygon',(x-.03,y-.04,x+.03,y-.04,x+.025,y+.03,x-.025,y+.03),'#edf2f5'))
    elif action=='LIFT':
        y=hand.y
        pieces.append(Primitive('line',(.05,y,.95,y),width=3))
        for x in (.09,.14,.86,.91):
            pieces.append(Primitive('line',(x,y-.065,x,y+.065),width=4))
    elif action=='ROW':
        p=math.sin(t*math.tau*.65)
        pieces.append(Primitive('line',(.07,.36-.18*p,.93,.36+.18*p),width=3))
        for x,y in ((.07,.36-.18*p),(.93,.36+.18*p)):
            pieces.append(Primitive('polygon',(x-.04,y-.045,x+.04,y-.045,x+.04,y+.045,x-.04,y+.045),'#e5edf2'))
    if mirror:
        pieces=[Primitive(s.kind,tuple(1-v if i%2==0 else v for i,v in enumerate(s.points)),s.fill,s.stroke,s.width,s.role) for s in pieces]
    return tuple(pieces)


BODY_LINKS=((11,12),(11,23),(12,24),(23,24),(11,13),(13,15),(12,14),(14,16),
            (23,25),(25,27),(24,26),(26,28),(27,31),(28,32))


def person_pose(action,t=0,mirror=False,seated=False,seat_mirror=False):
    """Compose only fixed materials: seated legs plus an existing upper action."""
    upper=list(preset_pose(action,t,mirror))
    if seated and action not in ('SIT','SIT_GESTURE','DOWN','FALL'):
        lower=preset_pose('SIT',0,seat_mirror)
        for i in range(23,33):upper[i]=lower[i]
    return tuple(upper)


@dataclass(frozen=True)
class BoundPose:
    """A fixed-proportion figure in the renderer's 1280 by 720 space."""
    joints: tuple[Joint,...]
    frame: tuple[float,float,float,float]
    head_radius: float
    bounds: tuple[float,float,float,float]


@lru_cache(maxsize=1)
def _rig_reference():
    # Body-height units, with the established .38 material aspect ratio.
    return tuple((p.x*.38,p.y,p.confidence) for p in preset_pose('IDLE'))


def bind_pose(pose,box,action='IDLE',mirror=False,seated=False,seat_mirror=False):
    """Retarget observed directions onto fixed bones, never source contours.

    Input landmarks use normalized full-frame coordinates; output uses the
    renderer's physical coordinate space. A reliable torso is mandatory.
    Missing limb evidence selects a complete preset segment, not a hole.
    This pure function does no inference, prediction or temporal filtering.
    """
    try:
        box=tuple(float(v) for v in box)
        if len(box)!=4 or not all(math.isfinite(v) and abs(v)<16384 for v in box):return None
        a,b,c,d=box;bw,bh=c-a,d-b
        if min(bw,bh)<3 or max(bw,bh)>8192 or len(pose)!=33:return None
    except (TypeError,ValueError,OverflowError):return None
    observed=[]
    for p in pose:
        try:
            x,y,confidence=float(p.x),float(p.y),float(p.confidence)
            good=all(math.isfinite(v) for v in (x,y,confidence)) and -4<=x<=4 and -4<=y<=4 and 0<=confidence<=1
            observed.append((x*1280,y*720,confidence) if good else None)
        except (AttributeError,TypeError,ValueError,OverflowError):observed.append(None)
    def valid(i,threshold=.55):return observed[i] is not None and observed[i][2]>=threshold
    # An unsupported hip or chest is not sufficient evidence for body scale.
    if not all(valid(i,.50) for i in (11,12,23,24)):return None
    sx,sy=((observed[11][k]+observed[12][k])/2 for k in (0,1))
    hx,hy=((observed[23][k]+observed[24][k])/2 for k in (0,1))
    dx,dy=hx-sx,hy-sy;torso=math.hypot(dx,dy);extent=max(bw,bh)
    if torso<max(3.,extent*.055) or torso>extent*.75:return None
    if not (a-extent*.4<=hx<=c+extent*.4 and b-extent*.4<=hy<=d+extent*.4):return None
    if not (a-extent*.4<=sx<=c+extent*.4 and b-extent*.4<=sy<=d+extent*.4):return None
    height=min(torso/.28,extent*1.35,2160.)
    if height<16:return None
    width=.38*height
    down=(dx/torso,dy/torso);screen_right=(down[1],-down[0])
    right=screen_right
    shoulder_delta=(observed[12][0]-observed[11][0],observed[12][1]-observed[11][1])
    side=shoulder_delta[0]*right[0]+shoulder_delta[1]*right[1]
    if abs(side)<max(1,height*.006):
        side=(observed[24][0]-observed[23][0])*right[0]+(observed[24][1]-observed[23][1])*right[1]
    if side<0:right=(-right[0],-right[1])
    frame=(hx-width/2,hy-height*.56,hx+width/2,hy+height*.44)
    reference=_rig_reference()
    fallback=person_pose(action,0,mirror,seated,seat_mirror)
    fallback_xy=tuple((p.x*.38,p.y) for p in fallback)
    fs=tuple((fallback_xy[11][k]+fallback_xy[12][k])/2 for k in (0,1))
    fh=tuple((fallback_xy[23][k]+fallback_xy[24][k])/2 for k in (0,1))
    fx,fy=fh[0]-fs[0],fh[1]-fs[1];fl=math.hypot(fx,fy)
    fallback_down=(fx/fl,fy/fl) if fl>1e-8 else (0.,1.)
    fallback_right=(fallback_down[1],-fallback_down[0])
    joints=[Joint(0.,0.,0.) for _ in range(33)]
    # Head, face, shoulders and hips remain our own fixed material.
    for i in (0,2,5,7,8,11,12,23,24):
        px,py,_=reference[i];lx,ly=(px-.19)*height,(py-.56)*height
        joints[i]=Joint(hx+right[0]*lx+down[0]*ly,hy+right[1]*lx+down[1]*ly,1.)
    def segment(parent,child):
        px,py,_=reference[parent];qx,qy,_=reference[child]
        length=math.hypot(qx-px,qy-py)*height
        direction=None
        if valid(parent) and valid(child):
            vx=observed[child][0]-observed[parent][0];vy=observed[child][1]-observed[parent][1]
            measured=math.hypot(vx,vy)
            # Reject nearly coincident and implausibly distant observations.
            if max(1.,height*.006)<=measured<=height*.75:direction=(vx/measured,vy/measured)
        if direction is None:
            vx=fallback_xy[child][0]-fallback_xy[parent][0];vy=fallback_xy[child][1]-fallback_xy[parent][1]
            forward=vx*fallback_down[0]+vy*fallback_down[1]
            sideways=vx*fallback_right[0]+vy*fallback_right[1]
            vx=screen_right[0]*sideways+down[0]*forward
            vy=screen_right[1]*sideways+down[1]*forward
            measured=math.hypot(vx,vy)
            direction=(vx/measured,vy/measured) if measured>1e-8 else down
        root=joints[parent]
        joints[child]=Joint(root.x+direction[0]*length,root.y+direction[1]*length,1.)
    for parent,child in ((11,13),(13,15),(12,14),(14,16),(23,25),(25,27),(24,26),(26,28),
                         (27,29),(28,30),(27,31),(28,32)):
        segment(parent,child)
    radius=height*.065
    visible=[p for p in joints if p.confidence>.25];head=joints[0]
    padding=max(4.,height*.014)
    bounds=(min(min(p.x for p in visible),head.x-radius)-padding,
            min(min(p.y for p in visible),head.y-radius*1.15)-padding,
            max(max(p.x for p in visible),head.x+radius)+padding,
            max(max(p.y for p in visible),head.y+radius*1.15)+padding)
    return BoundPose(tuple(joints),frame,radius,bounds)


def bound_person_props(bound,action,mirror=False,weapon='pistol'):
    """Translate existing small prop art with its matching output wrist."""
    if action not in ('PHONE','PHONE_LOOK','DRINK'):return ()
    a,b,c,d=bound.frame;width,height=c-a,d-b
    hand=preset_pose(action,0,mirror)[16]
    target=bound.joints[16]
    dx,dy=target.x-(a+hand.x*width),target.y-(b+hand.y*height)
    return tuple(replace(shape,points=tuple(a+v*width+dx if i%2==0 else b+v*height+dy
                                           for i,v in enumerate(shape.points)))
                 for shape in person_props(action,0,mirror,weapon))
