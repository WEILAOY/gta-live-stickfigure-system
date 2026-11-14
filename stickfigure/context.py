"""Small local context models. They return evidence, never drawing pixels."""
import ast

class HelicopterDetector:
    def __init__(self,path,class_name='helicopter'):
        import cv2,numpy as np
        from .inference import create_session
        self.cv2,self.np=cv2,np
        self.session,self.backend=create_session(path,prefer_gpu=False)
        names=ast.literal_eval(self.session.get_modelmeta().custom_metadata_map['names'])
        self.class_id=next(k for k,v in names.items() if v.lower()==class_name)
        self.class_name=class_name
        self.name=self.session.get_inputs()[0].name
    def detect(self,rgb,threshold=.45):
        from .detection import Detection
        cv2,np=self.cv2,self.np;h,w=rgb.shape[:2];ratio=640/max(h,w)
        res=cv2.resize(rgb,(round(w*ratio),round(h*ratio)));dw=(640-res.shape[1])//2;dh=(640-res.shape[0])//2
        image=np.full((640,640,3),114,np.uint8);image[dh:dh+res.shape[0],dw:dw+res.shape[1]]=res
        raw=self.session.run(None,{self.name:np.ascontiguousarray(image.transpose(2,0,1)[None],dtype=np.float32)/255})[0][0].T
        winners=raw[:,4:].argmax(axis=1);scores=raw[:,4+self.class_id]
        selected=np.flatnonzero((winners==self.class_id)&(scores>=threshold))
        if self.class_name=='pistol':
            selected=np.array([i for i in selected if raw[i,2]*raw[i,3]/(res.shape[0]*res.shape[1])<.16],dtype=int)
        if not len(selected):return ()
        rows=raw[selected];xywh=np.column_stack((rows[:,:2]-rows[:,2:4]/2,rows[:,2:4]));keep=cv2.dnn.NMSBoxes(xywh.tolist(),scores[selected].tolist(),threshold,.45)
        result=[]
        for index in np.asarray(keep,dtype=int).ravel():
            x,y,bw,bh=xywh[index];box=((x-dw)/ratio/w,(y-dh)/ratio/h,(x+bw-dw)/ratio/w,(y+bh-dh)/ratio/h)
            box=tuple(float(v) for v in np.clip(box,0,1))
            minimum=3 if self.class_name=='pistol' else 9
            if (box[2]-box[0])*w<minimum or (box[3]-box[1])*h<minimum*.65:continue
            result.append(Detection(self.class_name,float(scores[selected[index]]),box,render_box=box))
        return tuple(sorted(result,key=lambda d:d.confidence,reverse=True)[:(8 if self.class_name=='pistol' else 2)])

class GunDetector(HelicopterDetector):
    def __init__(self,path):super().__init__(path,'pistol')
    def for_person(self,rgb,box):
        from .detection import ObjectHint
        h,w=rgb.shape[:2];a,b,c,d=box;bw,bh=c-a,d-b
        x1=max(0,int((a-bw*.2)*w));x2=min(w,int((c+bw*.2)*w))
        y1=max(0,int(b*h));y2=min(h,int((b+bh*.78)*h))
        crop=rgb[y1:y2,x1:x2]
        if not crop.size:return ()
        result=[]
        for found in self.detect(crop,.18):
            u,v,s,t=found.box
            # This model can incorrectly box nearly the entire scene as a
            # pistol. A held gun must occupy a small part of the person crop.
            if (s-u)*(t-v)>.16 or (s-u)>.7 or (t-v)>.65:continue
            mapped=(float((x1+u*(x2-x1))/w),float((y1+v*(y2-y1))/h),float((x1+s*(x2-x1))/w),float((y1+t*(y2-y1))/h))
            result.append(ObjectHint('pistol',found.confidence,mapped))
        return tuple(result)
