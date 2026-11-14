"""Small manually reviewed GTA audit; never equate confidence with accuracy.

Optional OBS reference: model data extracted locally, no plugin DLL executed.
OBS's EdgeYOLO model emits decoded boxes; adapt these to the raw YOLOX
postprocessor only for this experiment. It is not shipped with the software.
"""
from pathlib import Path
import sys,json,time,statistics,argparse,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from stickfigure.detection import YoloXDetector
from stickfigure.tracking import overlap

BASE=Path(__file__).resolve().parents[1]
OUT=BASE.parent/'12_城市群与识别对照'
# Visible-object boxes, manually inspected in the native 852x480 source.
# Ignore regions cover ambiguous or <20 px objects, not known model errors.
LABELS=[
    (15,[('person',(340,227,441,480))],[(403,235,469,302)]),
    (30,[('person',(305,235,411,480)),('vehicle',(374,199,675,333)),
         ('vehicle',(415,235,852,480)),('vehicle',(115,148,155,171))],[]),
    (35,[('vehicle',(20,168,852,480))],[]),
    (55.6,[('vehicle',(330,245,532,384)),('vehicle',(260,210,356,275)),
           ('vehicle',(437,214,468,245))],[(348,225,407,244),(109,116,121,141)]),
    (64,[('vehicle',(265,248,536,410)),('person',(648,190,658,216))],
        [(637,197,648,219),(602,190,621,204)]),
    (70,[('vehicle',(339,245,533,386)),('vehicle',(284,223,360,265)),
         ('vehicle',(457,212,482,236))],[]),
    (90,[('vehicle',(337,250,526,380)),('person',(796,207,852,302))],[]),
    (105,[('vehicle',(337,250,526,375))],[(0,140,92,193),(389,180,442,232)]),
]

class DecodedOutput:
    def __init__(self,detector):
        self.session,self.grid,self.strides=detector.session,detector.grid,detector.strides
    def run(self,*args,**kwargs):
        outputs=self.session.run(*args,**kwargs)
        output=outputs[0].copy()
        output[0,:,:2]=output[0,:,:2]/self.strides-self.grid
        output[0,:,2:4]=np.log(np.maximum(output[0,:,2:4],1e-8)/self.strides)
        return [output,*outputs[1:]]

def family(label):return 'person' if label=='person' else 'vehicle'

def main():
    import onnxruntime as ort
    parser=argparse.ArgumentParser()
    parser.add_argument('--cpu',action='store_true')
    parser.add_argument('--report-stem',default='model-audit')
    args=parser.parse_args()
    if args.cpu:os.environ['STICKFIGURE_CPU']='1'
    OUT.mkdir(exist_ok=True)
    configs=[('baseline_nano_560',BASE/'models/yolox_nano.onnx',560),
             ('快速',BASE/'models/yolox_nano.onnx',960),
             ('均衡',BASE/'models/yolox_tiny.onnx',960),
             ('精细',BASE/'models/yolox_s.onnx',960)]
    reference=BASE/'runtime/obs-reference/edgeyolo_small.onnx'
    if reference.exists():configs.append(('OBS_EdgeYOLO_reference',reference,960))
    cap=cv2.VideoCapture(str(BASE.parent/'03_测试素材/gta5_test_01.mp4'))
    images={}
    for second,_,_ in LABELS:
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,img=cap.read();assert ok
        images[second]=img
    cap.release()
    records=[];summaries=[]
    for name,path,max_width in configs:
        detector=YoloXDetector(path)
        if path==reference:detector.session=DecodedOutput(detector)
        timings=[];counts={'tp':0,'fp':0,'fn':0,'ignored':0}
        for second,boxes,ignore in LABELS:
            original=images[second];h,w=original.shape[:2]
            width=min(max_width,w);height=round(h*width/w)
            img=cv2.resize(original,(width,height))
            pixels=cv2.cvtColor(img,cv2.COLOR_BGR2RGB).tobytes()
            detector.detect_rgb(pixels,width,height)
            elapsed=[]
            for _ in range(3):
                detections,_,total=detector.detect_rgb(pixels,width,height);elapsed.append(total)
            total=statistics.median(elapsed);timings.append(total)
            gt=[(label,tuple(v/d for v,d in zip(box,(w,h,w,h)))) for label,box in boxes]
            ignores=[tuple(v/d for v,d in zip(box,(w,h,w,h))) for box in ignore]
            available=set(range(len(gt)));predictions=[]
            display=original.copy()
            for label,box in boxes:cv2.rectangle(display,box[:2],box[2:],(255,180,30),1)
            for box in ignore:cv2.rectangle(display,box[:2],box[2:],(150,150,150),1)
            frame_counts={k:0 for k in counts}
            for det in detections:
                candidates=[i for i in available if family(det.label)==gt[i][0]]
                best=max(candidates,key=lambda i:overlap(det.box,gt[i][1]),default=None)
                if best is not None and overlap(det.box,gt[best][1])>=.5:
                    status='tp';available.remove(best)
                elif any(r[0]<=(det.box[0]+det.box[2])/2<=r[2] and
                         r[1]<=(det.box[1]+det.box[3])/2<=r[3] for r in ignores):
                    status='ignored'
                else:status='fp'
                frame_counts[status]+=1
                predictions.append(dict(label=det.label,score=det.confidence,box=det.box,status=status))
                p=tuple(round(v*d) for v,d in zip(det.box,(w,h,w,h)))
                color=(60,220,80) if status=='tp' else (130,130,130) if status=='ignored' else (60,60,245)
                cv2.rectangle(display,p[:2],p[2:],color,2)
                cv2.putText(display,f'{det.label} {det.confidence:.2f} {status}',(p[0],max(12,p[1]-4)),
                            cv2.FONT_HERSHEY_SIMPLEX,.42,color,1,cv2.LINE_AA)
            frame_counts['fn']=len(available)
            for k in counts:counts[k]+=frame_counts[k]
            safe={'快速':'nano','均衡':'tiny','精细':'s'}.get(name,name)
            cv2.imencode('.png',display)[1].tofile(str(OUT/f'audit_{safe}_{second:05.1f}.png'))
            records.append(dict(model=name,second=second,source_size=[w,h],input_frame=[width,height],
                                median_ms=total,counts=frame_counts,missed_gt=sorted(available),predictions=predictions))
        summaries.append(dict(model=name,backend=detector.backend,median_ms=statistics.median(timings),**counts))
    report=dict(runtime_version=ort.__version__,scope='8 manually reviewed frames, 852x480 GTA sample; visible targets ~20px or larger; IoU>=.5; car/bus/truck one family; ambiguous/tiny regions ignored. Raw detector, no tracking. Not overall accuracy or OBS plugin end-to-end benchmark.',
                manual_annotations=[dict(second=s,boxes=b,ignore=i) for s,b,i in LABELS],summary=summaries,frames=records)
    (OUT/(args.report_stem+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summaries,ensure_ascii=False))

if __name__=='__main__':main()
