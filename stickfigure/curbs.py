"""Extract open left/right curb curves, not the perimeter of visible road blobs."""
import numpy as np
import cv2


def driving_view(labels):
    height,width=labels.shape
    vehicle=np.isin(labels,[13,14,15]).astype(np.uint8)
    count,_,stats,centers=cv2.connectedComponentsWithStats(vehicle,8)
    car=False
    for i in range(1,count):
        x,y,w,h,area=stats[i]
        cx,cy=centers[i]
        if area>width*height*.012 and .18*width<cx<.82*width and cy>.4*height and y+h>.60*height:
            car=True
    count,_,stats,centers=cv2.connectedComponentsWithStats((labels==11).astype(np.uint8),8)
    walking=False
    for i in range(1,count):
        x,y,w,h,area=stats[i]
        cx,cy=centers[i]
        if area>width*height*.018 and h>height*.28 and y+h>height*.87 and .18*width<cx<.82*width:
            walking=True
    return car and not walking


def _fit(observations,width,height):
    if len(observations)<5:
        return ()
    data=np.asarray(observations,dtype=np.float64)
    x,y,weights=data[:,0]/(width-1),data[:,1]/(height-1),data[:,2]
    degree=2 if len(data)>=9 else 1
    original=weights.copy()
    for _ in range(5):
        coefficients=np.polyfit(y,x,degree,w=weights)
        residual=np.abs(np.polyval(coefficients,y)-x)
        limit=max(.012,float(np.median(residual))*2.5)
        weights=original*np.minimum(1,limit/np.maximum(residual,1e-6))
    if float(np.median(residual))>.065:
        return ()
    low=max(.20,float(y.min())-.025)
    high=min(.99,float(y.max())+.09)
    if degree==2:
        slopes=np.polyval(np.polyder(coefficients),[low,high])
        if slopes[0]*slopes[1]<0:
            # A curb must not turn back into a U around a vehicle or HUD patch.
            coefficients=np.polyfit(y,x,1,w=weights)
    values=np.linspace(low,high,22)
    curve=np.polyval(coefficients,values)
    result=[]
    for xx,yy in zip(curve,values):
        if -.03<=xx<=1.03:
            result.append((float(np.clip(xx,0,1)),float(yy)))
    return tuple(result) if len(result)>=6 else ()


def extract_curbs(labels,road_probability,rgb):
    height,width=labels.shape
    road=((labels==0)&(road_probability>.33)).astype(np.uint8)
    # Vehicles join road components for connectivity only; vehicle silhouettes
    # never become boundary observations.
    support=(road|np.isin(labels,[13,14,15]).astype(np.uint8))
    support=cv2.morphologyEx(support,cv2.MORPH_CLOSE,np.ones((3,7),np.uint8))
    count,components,stats,centers=cv2.connectedComponentsWithStats(support,8)
    scored=[]
    for label in range(1,count):
        x,y,w,h,area=stats[label]
        lower=np.count_nonzero(components[int(height*.55):,:]==label)
        if area>width*height*.035 and lower>width*height*.015:
            score=lower+area*.25-abs(centers[label,0]-width/2)*2
            scored.append((score,label))
    if not scored:
        return (),()
    main=max(scored)[1]
    visible=road&(components==main)
    gray=cv2.cvtColor(cv2.resize(rgb,(width,height)),cv2.COLOR_RGB2GRAY)
    gradient=np.abs(cv2.Sobel(gray,cv2.CV_32F,1,0,ksize=3))
    left,right=[],[]
    permitted={1,2,3,4,8,9}  # sidewalk, solid curb surroundings; not cars/people
    for row in range(int(height*.36),int(height*.88),2):
        xs=np.flatnonzero(visible[row])
        if len(xs)<max(5,width*.045):
            continue
        a,b=int(xs[0]),int(xs[-1])
        if b-a<width*.08:
            continue
        for side,position,target in ((-1,a,left),(1,b,right)):
            if not 3<position<width-4:
                continue  # image border is not a curb
            if row>height*.72 and position<width*.29:
                continue  # minimap/HUD is not curb evidence
            sample=labels[max(0,row-1):row+2,max(0,position+side*3-1):min(width,position+side*3+2)]
            if sample.size==0:
                continue
            outside=int(np.bincount(sample.ravel(),minlength=19).argmax())
            if outside not in permitted:
                continue
            # Follow a nearby visual edge, constrained by the semantic boundary.
            candidates=np.arange(max(1,position-2),min(width-1,position+3))
            strength=gradient[max(0,row-1):row+2,candidates].mean(axis=0)-np.abs(candidates-position)*5
            refined=int(candidates[int(strength.argmax())])
            weight=1.5 if outside==1 else .8
            target.append((refined,row,weight))
    return _fit(left,width,height),_fit(right,width,height)
