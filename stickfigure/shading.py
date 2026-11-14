"""Coarse background luminance regions, not actor silhouettes or tracing."""
import cv2,numpy as np
from functools import lru_cache
from .core import ShadeRegion

PALETTE={0:'#a1adb7',1:'#b0bbc5',2:'#ffffff',3:'#dceefa'}
TONE_ORDER=(6,5,0,1,4,2)  # dark -> paper; 3 remains semantic sky
TONE_NAMES=('深阴影·交叉排线','次深·密排线','中阴影·疏排线','次浅·网点','浅阴影·疏点','亮部·留白')
DENSITIES={'疏':.78,'中等':1.0,'密':1.25}
DETAILS={'粗略':(80,45),'标准':(120,68),'精细':(160,90)}

@lru_cache(maxsize=6)
def _tone_patterns(width,height,density='中等'):
    yy,xx=np.indices((height,width),dtype=np.float32)
    scale=max(width/1280,.01);factor=DENSITIES.get(density,1)
    x,y=xx/scale,yy/scale
    def dots(step,radius):
        step/=factor;row=np.floor(y/step)
        dx=(x+(row%2)*step/2+step/2)%step-step/2
        dy=(y+step/2)%step-step/2
        return dx*dx+dy*dy<=max(radius,.72/scale)**2
    def lines(step):return ((x+y)%(step/factor))<max(1.5,.85/scale)
    patterns={4:dots(22,1.6),1:dots(15,2),0:lines(14),5:lines(8),
              6:lines(8)|(((x-y)%(10/factor))<max(1.5,.85/scale))}
    for p in patterns.values():p.setflags(write=False)
    return patterns

@lru_cache(maxsize=4)
def _patterns(width,height):
    yy,xx=np.indices((height,width),dtype=np.float32)
    scale=max(width/1280,.01);x,y=xx/scale,yy/scale
    hatch=((x+y)%14)<max(1.5,1/scale)
    row=np.floor(y/16)
    dx=((x+(row%2)*8+8)%16)-8;dy=((y+8)%16)-8
    dots=dx*dx+dy*dy<=max(2,.8/scale)**2
    dense=((x%10-5)**2+(y%10-5)**2)<=max(1.5,.85/scale)**2
    for p in (hatch,dots,dense):p.setflags(write=False)
    return hatch,dots,dense

def contact_layer(box,width,height,density='中等'):
    """Tiny cropped, preset dotted ellipse, independent of background cache."""
    a,b,c,d=box
    left,top=max(0,int(a*width)-1),max(0,int(b*height)-1)
    right,bottom=min(width,int(np.ceil(c*width))+1),min(height,int(np.ceil(d*height))+1)
    if right<=left or bottom<=top:return np.zeros((0,0,4),np.uint8),(left,top,right,bottom)
    yy,xx=np.indices((bottom-top,right-left),dtype=np.float32)
    cx=(a+c)*width/2-left;cy=(b+d)*height/2-top
    radius=((xx-cx)/max(1,(c-a)*width/2))**2+((yy-cy)/max(1,(d-b)*height/2))**2
    outer=_tone_patterns(width,height,density)[1][top:bottom,left:right]
    inner=_patterns(width,height)[2][top:bottom,left:right]
    pixels=np.zeros((*radius.shape,4),np.uint8)
    pixels[(radius<=1)&outer]=(200,190,180,255)
    pixels[(radius<=.42)&inner]=(163,149,133,255)
    return pixels,(left,top,right,bottom)


def comic_pixels(regions,width,height,shadow_boxes=(),density='中等'):
    """Rasterize preset screen-tone marks into geometry; no source pixels.

    Screen coordinates anchor the pattern so it does not slide with contours.
    None gives a transparent contact-shadow layer; () gives white paper.
    """
    width,height=max(1,int(width)),max(1,int(height))
    tones=np.full((height,width),2,np.uint8)
    def points(p):return np.rint(np.asarray(p)*[width-1,height-1]).astype(np.int32)
    for region in regions or ():
        outer=points(region.points)
        l,t=np.maximum(outer.min(axis=0),0);r,b=np.minimum(outer.max(axis=0)+1,(width,height))
        if r<=l or b<=t:continue
        mask=np.zeros((b-t,r-l),np.uint8)
        cv2.fillPoly(mask,[outer-[l,t]],255)
        for hole in region.holes:
            cv2.fillPoly(mask,[points(hole)-[l,t]],0)
        tones[t:b,l:r][mask>0]=region.tone
    pixels=np.full((height,width,4),255,np.uint8)
    if regions is None:pixels[:,:,3]=0
    patterns=_tone_patterns(width,height,density)
    for tone,color in ((4,(216,207,198)),(1,(197,187,176)),(0,(174,160,144)),(5,(161,147,131)),(6,(143,130,116))):
        pixels[(tones==tone)&patterns[tone],:3]=color
    pixels[tones==3,:3]=(250,238,220)
    if shadow_boxes:
        for a,b,c,d in shadow_boxes:
            layer,(l,t,r,bottom)=contact_layer((a,b,c,d),width,height,density)
            if layer.size:
                view=pixels[t:bottom,l:r];view[layer[:,:,3]>0]=layer[layer[:,:,3]>0]
    return pixels

def contact_shadow_boxes(entities,bound_poses=None):
    """Fixed material ellipses, clipped to the viewport; no video contours."""
    result=[]
    for e in entities:
        if e.predicted or e.vehicle_type in ('helicopter','boat'):continue
        bound=bound_poses.get(e.track_id) if bound_poses and e.kind=='person' else None
        if bound is not None:
            # The caller supplies this frame's deterministic retargeting.
            # Position the same dotted material under the output figure;
            # neither a previous frame's joints nor source shadow pixels
            # participate in this geometry.
            joints=bound.joints;height=bound.frame[3]-bound.frame[1]
            sx,sy=((getattr(joints[11],k)+getattr(joints[12],k))/2 for k in ('x','y'))
            hx,hy=((getattr(joints[23],k)+getattr(joints[24],k))/2 for k in ('x','y'))
            horizontal=abs(hx-sx)>abs(hy-sy)*1.4
            if horizontal:
                visible=[p for p in joints if p.confidence>.25]
                head=joints[0]
                left=min(min(p.x for p in visible),head.x-bound.head_radius)
                right=max(max(p.x for p in visible),head.x+bound.head_radius)
                ground=max(max(p.y for p in visible),head.y+bound.head_radius*1.15)
                center=(left+right)/2/1280
                radius=max(height*.14,(right-left)*.48)/1280
            else:
                feet=[joints[i] for i in (27,28,31,32)]
                center=(min(p.x for p in feet)+max(p.x for p in feet))/2/1280
                ground=max(p.y for p in feet)
                # Same fixed body proportions as the previous upright
                # ellipse; extending an arm cannot enlarge this shadow.
                width=(bound.frame[2]-bound.frame[0])/1280
                radius=max(width*.40,height/720*.12)
            box=(max(0,center-radius),max(0,(ground-height*.025)/720),
                 min(1,center+radius),min(1,(ground+height*.015)/720))
            if box[2]>box[0] and box[3]>box[1]:result.append(box)
            continue
        if e.bbox:a,b,c,d=e.render_bbox or e.bbox
        else:
            width,height=(.05,.167) if e.kind=='person' else (.127,.125)
            a,b,c,d=e.x-width*e.scale/2,e.y-height*e.scale,e.x+width*e.scale/2,e.y
        center=(a+c)/2;width=c-a;height=d-b
        radius=max(width*.40,height*.12) if e.kind=='person' else width*.48
        if e.action=='DOWN' and e.posture_fit:
            radius=width*.48
        elif e.action in ('FALL','DOWN'):
            center+=(-1 if e.action_mirror else 1)*height*.22*720/1280
            radius=height*.45*720/1280
        box=(max(0,center-radius),max(0,d-height*.025),min(1,center+radius),min(1,d+height*.015))
        if box[2]>box[0] and box[3]>box[1]:result.append(box)
    return tuple(result)

def tone_spec(levels):
    if levels==3:return np.array((85,170)),np.array((0,1,2),np.uint8)
    if levels==4:return np.array((65,135,205)),np.array((6,0,1,2),np.uint8)
    return np.array((50,90,130,175,215)),np.array(TONE_ORDER,np.uint8)


class ShadingStabilizer:
    """Bounded brightness history; large changes/motion adopt the new frame."""
    def __init__(self):self.reset()
    def reset(self):
        self.previous=None;self.filtered=None;self.indices=None;self.key=None
        self.timestamp=None;self.last_reset=True
    def quantize(self,coarse,levels,timestamp,generation):
        edges,order=tone_spec(levels);key=(coarse.shape,levels,generation)
        fresh=(self.key!=key or self.timestamp is None or
               not 0<timestamp-self.timestamp<=.9)
        current=coarse.astype(np.float32)
        if not fresh:
            delta=np.abs(current-self.previous)
            fresh=float(delta.mean())>28 or float((delta>45).mean())>.25
            # A translating camera must not drag old shadow edges behind it.
            if not fresh and current.std()>8 and self.previous.std()>8:
                shift,response=cv2.phaseCorrelate(self.previous,current)
                if response>.15 and max(abs(shift[0]),abs(shift[1]))>.8:fresh=True
        if fresh:
            filtered=current;indices=np.digitize(current,edges)
        else:
            stable=np.abs(current-self.previous)<18
            filtered=np.where(stable,.35*current+.65*self.filtered,current)
            indices=np.digitize(filtered,edges)
            old=self.indices
            brighter=indices>old;darker=indices<old
            up=edges[np.minimum(old,len(edges)-1)]+6
            down=edges[np.maximum(old-1,0)]-6
            keep=stable&((brighter&(filtered<up))|(darker&(filtered>=down)))
            indices=np.where(keep,old,indices)
        self.previous=current.copy();self.filtered=filtered;self.indices=indices
        self.key=key;self.timestamp=timestamp;self.last_reset=fresh
        return order[indices]


def extract_shading(rgb,labels=None,exclude_boxes=(),levels=6,detail='标准',
                    stabilizer=None,timestamp=0,generation=0):
    """Low-resolution background geometry plus fixed tone IDs, no actor art."""
    width,height=DETAILS.get(detail,DETAILS['标准'])
    work=(max(160,width),max(90,height))
    gray=cv2.cvtColor(cv2.resize(rgb,work),cv2.COLOR_RGB2GRAY)
    mask=np.zeros_like(gray)
    semantic=None
    if labels is not None:
        semantic=cv2.resize(labels.astype(np.uint8),work,interpolation=cv2.INTER_NEAREST)
        mask[np.isin(semantic,range(11,19))]=255
    for a,b,c,d in exclude_boxes:
        x1=max(0,int(a*work[0])-2);y1=max(0,int(b*work[1])-2)
        x2=min(work[0],int(c*work[0])+3);y2=min(work[1],int(d*work[1])+3)
        if x2>x1 and y2>y1:mask[y1:y2,x1:x2]=255
    mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
    if mask.any():
        if (mask>0).mean()>.92:
            if stabilizer:stabilizer.reset()
            return ()
        gray=cv2.inpaint(gray,mask,5,cv2.INPAINT_TELEA)
    # Still a coarse brightness map: no source textures or traced actor edges.
    blur=9 if detail=='粗略' else 5
    coarse=cv2.resize(cv2.GaussianBlur(gray,(blur,blur),0),(width,height),interpolation=cv2.INTER_AREA)
    if stabilizer is not None:tones=stabilizer.quantize(coarse,levels,timestamp,generation)
    else:
        edges,order=tone_spec(levels);tones=order[np.digitize(coarse,edges)]
    _,order=tone_spec(levels)
    ordinal=np.zeros(7,np.uint8);ordinal[order]=np.arange(len(order),dtype=np.uint8)
    tones=order[cv2.medianBlur(ordinal[tones],3)]
    # Dominant paper/tone underneath all smaller components prevents white seams
    # and fills discarded tiny islands without borrowing actor silhouettes.
    dominant=int(np.bincount(tones.ravel(),minlength=7).argmax())
    full=((0.,0.),(1.,0.),(1.,1.),(0.,1.))
    result=[ShadeRegion(dominant,full)];regions=[]
    minimum={'粗略':24,'标准':18,'精细':22}.get(detail,18)
    epsilon=.45 if detail!='粗略' else .65
    def normalized(contour):
        poly=cv2.approxPolyDP(contour,epsilon,True).reshape(-1,2)
        return tuple((float(x/(width-1)),float(y/(height-1))) for x,y in poly)
    for tone in np.unique(tones):
        if tone==dominant:continue
        binary=(tones==tone).astype(np.uint8)
        contours,hierarchy=cv2.findContours(binary,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        for i,contour in enumerate(contours):
            area=cv2.contourArea(contour)
            if hierarchy[0][i][3]>=0 or area<minimum:continue
            outer=normalized(contour)
            if len(outer)<3:continue
            holes=[];child=hierarchy[0][i][2]
            while child>=0:
                hole=normalized(contours[child])
                if len(hole)>=3 and cv2.contourArea(contours[child])>=minimum/3:holes.append(hole)
                child=hierarchy[0][child][0]
            regions.append((area,ShadeRegion(int(tone),outer,tuple(holes))))
    result.extend(r for _,r in sorted(regions,key=lambda p:p[0],reverse=True)[:128])
    if semantic is not None:
        sky=(semantic==10).astype(np.uint8)*255
        if mask.any():sky=cv2.inpaint(sky,mask,5,cv2.INPAINT_TELEA)
        sky=cv2.resize(sky,(width,height),interpolation=cv2.INTER_AREA)
        sky=cv2.medianBlur((sky>180).astype(np.uint8),3)
        contours,hierarchy=cv2.findContours(sky,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is not None:
            for i,c in enumerate(contours):
                if hierarchy[0][i][3]>=0 or cv2.contourArea(c)<minimum:continue
                outer=normalized(c)
                if len(outer)<3:continue
                holes=[];child=hierarchy[0][i][2]
                while child>=0:
                    hole=normalized(contours[child])
                    if cv2.contourArea(contours[child])>=6 and len(hole)>=3:holes.append(hole)
                    child=hierarchy[0][child][0]
                result.append(ShadeRegion(3,outer,tuple(holes)))
                if sum(r.tone==3 for r in result)>=16:break
    return tuple(result)
