"""Rasterize predefined primitives into a transparent viewport-clipped layer.

No video pixels, semantic masks, contours or image edges enter this module.
"""
import math
import cv2
import numpy as np


def render_extent(box,visible_box,aspect):
    """Keep full model size at a truncated frame edge; do not fit it inside."""
    x1,y1,x2,y2=box
    a,b,c,d=visible_box
    if a<=15 and c<1265:
        width=max(x2-x1,(y2-y1)*aspect,(c-a)*1.35 if x1>=0 else 0)
        x1=x2-width
    elif c>=1265 and a>15:
        width=max(x2-x1,(y2-y1)*aspect,(c-a)*1.35 if x2<=1280 else 0)
        x2=x1+width
    if b<=9 and d<711:
        height=max(y2-y1,(x2-x1)/max(.1,aspect),(d-b)*1.35 if y1>=0 else 0)
        y1=y2-height
    elif d>=711 and b>9:
        height=max(y2-y1,(x2-x1)/max(.1,aspect),(d-b)*1.35 if y2<=720 else 0)
        y2=y1+height
    return x1,y1,x2,y2


def clipped_bounds(art_bounds,viewport):
    """Return the padded, viewport-clipped pixel rectangle without allocating."""
    # Multiplication of normalized coordinates may produce e.g. 368.00000000006.
    # Do not let that arithmetic noise change the crop by one whole pixel.
    a,b,c,d=(round(v,8) for v in art_bounds)
    x,y,width,height=(round(v,8) for v in viewport)
    left,top=max(math.floor(a)-5,math.ceil(x)),max(math.floor(b)-5,math.ceil(y))
    right,bottom=min(math.ceil(c)+5,math.floor(x+width)),min(math.ceil(d)+5,math.floor(y+height))
    return left,top,max(left,right),max(top,bottom)


class FrameLayer:
    """Only rectangular frame clipping; no object or occlusion mask."""
    # OpenCV's fixed-point coordinates keep small movements visible without
    # allocating a supersampled layer. Stroke widths remain output pixels.
    COORD_SHIFT = 8
    COORD_SCALE = 1 << COORD_SHIFT

    def __init__(self,art_bounds,viewport,opaque_light=False,halo=False):
        self.opaque_light,self.halo=opaque_light,halo
        self.bounds=clipped_bounds(art_bounds,viewport)
        left,top,right,bottom=self.bounds
        self.pixels=np.zeros((bottom-top,right-left,4),np.uint8)

    @staticmethod
    def color(value):
        value=value.lstrip('#')
        if len(value)==3:
            value=''.join(v*2 for v in value)
        r,g,b=(int(value[i:i+2],16) for i in (0,2,4))
        return b,g,r,255

    def points(self,coords):
        points=np.asarray(coords,np.float64).reshape(-1,2)-self.bounds[:2]
        return np.rint(np.clip(points,-100000,100000)*self.COORD_SCALE).astype(np.int32)

    def paint(self,kind,coords,**options):
        if not self.pixels.size:
            return
        points=self.points(coords)
        width=max(1,round(options.get('width',1)))
        fill=options.get('fill','')
        outline=options.get('outline','')
        if kind=='line':
            cv2.polylines(self.pixels,[points],False,self.color(fill),width,cv2.LINE_AA,self.COORD_SHIFT)
        elif kind=='polygon':
            if fill:
                cv2.fillPoly(self.pixels,[points],self.color(fill),cv2.LINE_AA,self.COORD_SHIFT)
            if outline:
                cv2.polylines(self.pixels,[points],True,self.color(outline),width,cv2.LINE_AA,self.COORD_SHIFT)
        elif kind=='oval':
            a,b=points
            center=tuple(np.rint((a+b)/2).astype(int))
            axes=tuple(np.maximum(self.COORD_SCALE,np.rint(np.abs(b-a)/2)).astype(int))
            if fill:
                cv2.ellipse(self.pixels,center,axes,0,0,360,self.color(fill),-1,cv2.LINE_AA,self.COORD_SHIFT)
            if outline:
                cv2.ellipse(self.pixels,center,axes,0,0,360,self.color(outline),width,cv2.LINE_AA,self.COORD_SHIFT)

    def png(self):
        if not self.pixels.size or not self.pixels[:,:,3].any():
            return None
        # Preset material is line art: light interior paint only handles the
        # model's own face ordering, then becomes transparent for compositing.
        # Thus another object's complete lines remain visible behind it.
        if not self.opaque_light:self.pixels[:,:,3][np.all(self.pixels[:,:,:3]>=175,axis=2)]=0
        if self.halo:
            alpha=self.pixels[:,:,3].copy()
            edge=cv2.dilate(alpha,np.ones((3,3),np.uint8))
            outside=(edge>0)&(alpha==0)
            self.pixels[outside,:3]=255;self.pixels[outside,3]=edge[outside]
        return cv2.imencode('.png',self.pixels)[1].tobytes()
