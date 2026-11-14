"""Low-resolution, fixed-palette background geometry; never actor textures.

Only the coarse colour categories and simplified polygons leave this module.
No source bitmap, source actor silhouette, clustering model or full-size filter
is used by the output renderer.
"""
from functools import lru_cache
import cv2
import numpy as np
from .core import ColorRegion


DETAILS={'粗略':(80,45),'标准':(120,68),'精细':(160,90)}
FULL=((0.,0.),(1.,0.),(1.,1.),(0.,1.))
# Saturation and darkness are intentionally bounded so fixed dark line art
# remains readable. Colours describe the scene approximately, not literally.
PALETTE=(
    '#e5b4ae','#e2c0a1','#dfd2a3','#acc7ac',
    '#a8c9c2','#adc5dd','#c3b9d8','#d7b4ca',
    '#f2d8d2','#f1dfcc','#efe8c9','#d5e6d0',
    '#d1e5e0','#d4e4f1','#e4dcf0','#efdae6',
    '#bdc5cd','#d0d5da','#e2e6e9','#f3f5f6',
)
_HUE_CENTRES=np.array((0,15,30,60,90,112,140,165),np.int16)


def _quantize(rgb):
    hsv=cv2.cvtColor(np.ascontiguousarray(rgb,np.uint8),cv2.COLOR_RGB2HSV)
    hue,saturation,value=(hsv[:,:,i] for i in range(3))
    distances=np.abs(hue[:,:,None].astype(np.int16)-_HUE_CENTRES)
    distances=np.minimum(distances,180-distances)
    chromatic=distances.argmin(axis=2).astype(np.uint8)
    chromatic+=np.where(value>=192,8,0).astype(np.uint8)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    neutral=16+np.digitize(gray,(64,128,208)).astype(np.uint8)
    return np.where(saturation>=44,chromatic,neutral).astype(np.uint8)


class ColorStabilizer:
    """Smooth only small colour noise; cuts, movement and changed cells reset."""
    def __init__(self):self.reset()

    def reset(self):
        self.previous=None
        self.filtered=None
        self.key=None
        self.timestamp=None
        self.last_reset=True

    def quantize(self,coarse_rgb,timestamp,generation):
        current=np.asarray(coarse_rgb,np.float32)
        key=(current.shape,generation)
        fresh=(self.key!=key or self.timestamp is None or
               not 0<timestamp-self.timestamp<=.9)
        if not fresh:
            delta=np.max(np.abs(current-self.previous),axis=2)
            fresh=float(delta.mean())>28 or float((delta>45).mean())>.25
            if not fresh:
                old_gray=cv2.cvtColor(self.previous,cv2.COLOR_RGB2GRAY)
                new_gray=cv2.cvtColor(current,cv2.COLOR_RGB2GRAY)
                if old_gray.std()>8 and new_gray.std()>8:
                    shift,response=cv2.phaseCorrelate(old_gray,new_gray)
                    if response>.15 and max(abs(shift[0]),abs(shift[1]))>.8:
                        fresh=True
        if fresh:
            filtered=current
        else:
            stable=np.max(np.abs(current-self.previous),axis=2)<16
            # Edge/colour changes use this frame immediately. This is not an
            # optical-flow prediction or a hold of an old background region.
            filtered=np.where(stable[:,:,None],.45*current+.55*self.filtered,current)
        self.previous=current.copy()
        self.filtered=filtered
        self.key=key
        self.timestamp=timestamp
        self.last_reset=fresh
        return _quantize(np.clip(np.rint(filtered),0,255).astype(np.uint8))


def extract_colors(rgb,labels=None,exclude_boxes=(),detail='标准',
                   stabilizer=None,timestamp=0,generation=0):
    """Return at most 129 immutable flat-colour regions from a coarse sample."""
    width,height=DETAILS.get(detail,DETAILS['标准'])
    work=(max(160,width),max(90,height))
    coarse=cv2.resize(rgb,work,interpolation=cv2.INTER_AREA)
    mask=np.zeros((work[1],work[0]),np.uint8)
    if labels is not None:
        semantic=cv2.resize(np.asarray(labels,np.uint8),work,interpolation=cv2.INTER_NEAREST)
        mask[np.isin(semantic,range(11,19))]=255
    for a,b,c,d in exclude_boxes:
        x1=max(0,int(a*work[0])-2);y1=max(0,int(b*work[1])-2)
        x2=min(work[0],int(c*work[0])+3);y2=min(work[1],int(d*work[1])+3)
        if x2>x1 and y2>y1:mask[y1:y2,x1:x2]=255
    mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
    if mask.any():
        if float((mask>0).mean())>.92:
            if stabilizer is not None:stabilizer.reset()
            return ()
        coarse=cv2.inpaint(coarse,mask,5,cv2.INPAINT_TELEA)
    blur=9 if detail=='粗略' else 5
    coarse=cv2.resize(cv2.GaussianBlur(coarse,(blur,blur),0),(width,height),interpolation=cv2.INTER_AREA)
    codes=stabilizer.quantize(coarse,timestamp,generation) if stabilizer is not None else _quantize(coarse)
    dominant=int(np.bincount(codes.ravel(),minlength=len(PALETTE)).argmax())
    result=[ColorRegion(PALETTE[dominant],FULL)]
    regions=[]
    minimum={'粗略':24,'标准':18,'精细':22}.get(detail,18)
    epsilon=.65 if detail=='粗略' else .45

    def normalized(contour):
        polygon=cv2.approxPolyDP(contour,epsilon,True).reshape(-1,2)
        return tuple((float(x/(width-1)),float(y/(height-1))) for x,y in polygon)

    for code in np.unique(codes):
        if code==dominant:continue
        binary=(codes==code).astype(np.uint8)
        contours,hierarchy=cv2.findContours(binary,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        for index,contour in enumerate(contours):
            area=cv2.contourArea(contour)
            if hierarchy[0][index][3]>=0 or area<minimum:continue
            outer=normalized(contour)
            if len(outer)<3:continue
            holes=[];child=hierarchy[0][index][2]
            while child>=0:
                hole=normalized(contours[child])
                if len(hole)>=3 and cv2.contourArea(contours[child])>=minimum/3:
                    holes.append(hole)
                child=hierarchy[0][child][0]
            regions.append((area,ColorRegion(PALETTE[int(code)],outer,tuple(holes))))
    result.extend(region for _,region in sorted(regions,key=lambda item:item[0],reverse=True)[:128])
    return tuple(result)


@lru_cache(maxsize=64)
def _bgra(color):
    value=color.lstrip('#')
    if len(value)!=6:raise ValueError('Expected a six-digit RGB background colour')
    red,green,blue=(int(value[i:i+2],16) for i in (0,2,4))
    return blue,green,red,255


def color_pixels(regions,width,height):
    """Rasterize only coarse flat-colour geometry into an opaque BGRA layer."""
    width,height=max(1,int(width)),max(1,int(height))
    # Paint one-byte palette indices, then perform one colour lookup. Assigning
    # a four-byte RGB tuple through every polygon mask costs substantially more
    # CPU at 720P. No source-image pixels enter this rendering path.
    tones=np.zeros((height,width),np.uint8)
    colors={'#f7f9fc':0}
    lookup=np.zeros((256,1,3),np.uint8)
    lookup[0,0]=_bgra('#f7f9fc')[:3]

    def points(polygon):
        return np.rint(np.asarray(polygon)*[width-1,height-1]).astype(np.int32)

    for region in regions or ():
        if len(region.points)<3:continue
        code=colors.get(region.color)
        if code is None:
            code=len(colors)
            if code>255:raise ValueError('Too many flat background colours')
            colors[region.color]=code
            lookup[code,0]=_bgra(region.color)[:3]
        if region.points==FULL and not region.holes:
            tones.fill(code)
            continue
        outer=points(region.points)
        if not region.holes:
            cv2.fillPoly(tones,[outer],code)
            continue
        left,top=np.maximum(outer.min(axis=0),0)
        right,bottom=np.minimum(outer.max(axis=0)+1,(width,height))
        if right<=left or bottom<=top:continue
        mask=np.zeros((bottom-top,right-left),np.uint8)
        cv2.fillPoly(mask,[outer-[left,top]],255)
        for hole in region.holes:
            if len(hole)>=3:cv2.fillPoly(mask,[points(hole)-[left,top]],0)
        tones[top:bottom,left:right][mask>0]=code
    return cv2.cvtColor(cv2.applyColorMap(tones,lookup),cv2.COLOR_BGR2BGRA)
