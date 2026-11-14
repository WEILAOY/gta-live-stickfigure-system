"""Simplified external building silhouettes, without internal facade lines."""
import cv2
import numpy as np
from .core import BuildingGeometry


def extract_building_outlines(labels,probability=None):
    height,width=labels.shape
    mask=(labels==2).astype(np.uint8)
    if probability is not None:
        mask[probability<.38]=0
    # Keep distant buildings and roof steps. A large opening kernel erased both.
    # Median filtering removes single-pixel noise without drawing facade holes.
    mask=cv2.medianBlur(mask,3)
    # Close short notches from facade occlusion; keep the large roof changes.
    # This operates on building semantics only, never image edges or actors.
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    # External retrieval discards windows, doors and other internal holes.
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    accepted=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        area=cv2.contourArea(contour)
        if area>=max(18,width*height*.0009) and h>=max(5,height*.028) and w>=max(4,width*.012):
            accepted.append((area,contour))
    outlines=[]
    for _,contour in sorted(accepted,key=lambda item:item[0],reverse=True)[:12]:
        perimeter=cv2.arcLength(contour,True)
        epsilon=max(1.3,min(width,height)*.014)
        simplified=cv2.approxPolyDP(contour,epsilon,True).reshape(-1,2)
        while len(simplified)>28:
            epsilon*=1.25
            simplified=cv2.approxPolyDP(contour,epsilon,True).reshape(-1,2)
        if len(simplified)<3:
            continue
        edges=[]
        for a,b in zip(simplified,np.roll(simplified,-1,axis=0)):
            frame_edge=any((a[axis]<=max(1,limit*.008) and b[axis]<=max(1,limit*.008)) or
                           (a[axis]>=limit-1-max(1,limit*.008) and b[axis]>=limit-1-max(1,limit*.008))
                           for axis,limit in ((0,width),(1,height)))
            edges.append(None if frame_edge else (a,b))
        if all(edge is not None for edge in edges):
            chain=[*simplified,simplified[0]]
            outlines.append(tuple((float(x/(width-1)),float(y/(height-1))) for x,y in chain))
            continue
        # Start after a removed frame edge, avoiding many detached strokes.
        split=next(i for i,edge in enumerate(edges) if edge is None)
        edges=edges[split+1:]+edges[:split+1]
        chain=[]
        for edge in edges:
            if edge is None:
                if len(chain)>=2:
                    outlines.append(tuple((float(x/(width-1)),float(y/(height-1))) for x,y in chain))
                chain=[]
            else:
                if not chain:
                    chain.append(edge[0])
                chain.append(edge[1])
    return BuildingGeometry(tuple(outlines))
