"""Local OCR returns Unicode strings and positions, never source-image art."""
from pathlib import Path
from dataclasses import dataclass
import threading,queue,time,math,unicodedata
from dataclasses import replace
import hashlib
from .core import TextRegion

def normalize_roi(roi):
    if roi is None:return None
    if not isinstance(roi,(list,tuple)) or len(roi)!=4:raise ValueError('请选择有效识别范围')
    a,b,c,d=map(float,roi)
    if not all(math.isfinite(v) for v in (a,b,c,d)) or not 0<=a<c<=1 or not 0<=b<d<=1:
        raise ValueError('识别范围必须在画面内且有有效面积')
    return a,b,c,d

def crop_frame(frame,roi):
    import numpy as np
    rgb=np.frombuffer(frame.pixels,np.uint8).reshape(frame.height,frame.width,3)
    a,b,c,d=normalize_roi(roi) or (0,0,1,1)
    left,top=int(a*frame.width),int(b*frame.height)
    right,bottom=min(frame.width,math.ceil(c*frame.width)),min(frame.height,math.ceil(d*frame.height))
    return rgb[top:bottom,left:right],(left,top,right,bottom)

def text_free_outlines(outlines,texts):
    """Reject small semantic building fragments around recognized lettering."""
    kept=[]
    for outline in outlines:
        xs=[p[0] for p in outline];ys=[p[1] for p in outline]
        a,b,c,d=min(xs),min(ys),max(xs),max(ys);area=(c-a)*(d-b)
        is_letter=False
        for r in texts:
            x,y,z,v=r.box;h=v-y;text_area=(z-x)*h
            left,top,right,bottom=x-.02,y-h*.6,z+.02,v+h*.6
            intersection=max(0,min(c,right)-max(a,left))*max(0,min(d,bottom)-max(b,top))
            if area>0 and area<text_area*8 and intersection/area>.2:is_letter=True;break
        if not is_letter:kept.append(outline)
    return tuple(kept)

def clean_regions(boxes,texts,scores,width,height):
    output=[]
    for quad,value,score in zip(boxes,texts,scores):
        value=''.join(c for c in str(value) if not unicodedata.category(c).startswith('C')).strip()[:180]
        if not value or not math.isfinite(float(score)) or score<.60:continue
        xs=[float(p[0])/width for p in quad];ys=[float(p[1])/height for p in quad]
        if not all(math.isfinite(v) for v in xs+ys):continue
        a,b,c,d=max(0,min(xs)),max(0,min(ys)),min(1,max(xs)),min(1,max(ys))
        if c<=a or d<=b:continue
        from .tracking import overlap
        if any(r.text==value and overlap(r.box,(a,b,c,d))>.45 for r in output):continue
        output.append(TextRegion(value,float(score),(a,b,c,d)))
        if len(output)>=48:break
    return tuple(sorted(output,key=lambda r:(r.box[1],r.box[0])))

class TextRecognizer:
    def __init__(self,model_dir):
        from rapidocr import RapidOCR
        paths={name:Path(model_dir)/file for name,file in (
            ('Det','PP-OCRv6_det_small.onnx'),('Rec','PP-OCRv6_rec_small.onnx'),('Cls','ch_ppocr_mobile_v2.0_cls_mobile.onnx'))}
        for path in paths.values():
            if not path.is_file():raise FileNotFoundError(f'OCR 模型缺失：{path.name}')
        params={f'{name}.model_path':str(path) for name,path in paths.items()}
        params.update({'Global.text_score':.60,'Global.use_cls':False,'Global.log_level':'error',
                       'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':1,
                       'EngineConfig.onnxruntime.use_dml':False,'Det.limit_side_len':1280,'Det.limit_type':'max'})
        self.engine=RapidOCR(params=params)

    def recognize(self,frame,roi=None,scale=1.5):
        import numpy as np,cv2
        started=time.perf_counter()
        rgb,(left,top,right,bottom)=crop_frame(frame,roi)
        h,w=rgb.shape[:2]
        width=max(1,min(1280,round(w*scale)));height=max(1,round(width*h/w))
        bgr=cv2.cvtColor(cv2.resize(rgb,(width,height)),cv2.COLOR_RGB2BGR)
        result=self.engine(bgr)
        regions=clean_regions(result.boxes,result.txts,result.scores,width,height) if result.boxes is not None else ()
        regions=tuple(replace(r,box=((left+r.box[0]*w)/frame.width,(top+r.box[1]*h)/frame.height,
                                    (left+r.box[2]*w)/frame.width,(top+r.box[3]*h)/frame.height)) for r in regions)
        return regions,(time.perf_counter()-started)*1000

@dataclass(frozen=True)
class TextResult:
    epoch:int
    generation:int
    timestamp:float
    regions:tuple[TextRegion,...]
    total_ms:float
    reused:bool=False

class TextWorker:
    def __init__(self,model_dir):
        self.model_dir=model_dir;self.results=queue.Queue(maxsize=2);self.events=queue.Queue(maxsize=4)
        self._condition=threading.Condition();self._pending=None;self._closed=False;self._epoch=0
        self.options=(None,1.5)
        self._thread=threading.Thread(target=self._run,name='text-recognition',daemon=True);self._thread.start()
    @property
    def epoch(self):
        with self._condition:return self._epoch
    def reset(self):
        with self._condition:self._epoch+=1;self._pending=None;self._condition.notify_all()
    def submit(self,frame):
        with self._condition:self._pending=(self._epoch,frame,self.options);self._condition.notify_all()
    def configure(self,roi=None,scale=1.5):
        roi=normalize_roi(roi)
        if scale not in (1.,1.5):raise ValueError('不支持的OCR缩放')
        with self._condition:
            self.options=(roi,scale);self._epoch+=1;self._pending=None;self._condition.notify_all()
    def close(self):
        with self._condition:self._closed=True;self._epoch+=1;self._condition.notify_all()
    @staticmethod
    def _latest(target,value):
        try:target.put_nowait(value)
        except queue.Full:
            try:target.get_nowait()
            except queue.Empty:pass
            target.put_nowait(value)
    def _run(self):
        recognizer=None
        cached_key=cached_regions=None
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._closed or self._pending is not None)
                if self._closed:return
                epoch,frame,options=self._pending;self._pending=None
            try:
                if recognizer is None:recognizer=TextRecognizer(self.model_dir)
                if epoch!=self.epoch:continue
                began=time.perf_counter()
                crop,_=crop_frame(frame,options[0])
                key=(epoch,frame.generation,crop.shape,options,hashlib.sha256(crop.tobytes()).digest())
                reused=key==cached_key
                if reused:regions=cached_regions;elapsed=(time.perf_counter()-began)*1000
                else:
                    regions,elapsed=recognizer.recognize(frame) if options==(None,1.5) else recognizer.recognize(frame,*options)
                    cached_key,cached_regions=key,regions
                if epoch==self.epoch:self._latest(self.results,TextResult(epoch,frame.generation,frame.timestamp,regions,elapsed,reused))
            except Exception as exc:
                if epoch==self.epoch:self._latest(self.events,(epoch,str(exc)))
