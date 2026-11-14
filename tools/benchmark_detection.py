"""Benchmark real game frames; exports annotated frames and measured timings."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import json
import statistics
import cv2
import numpy as np
from stickfigure.detection import YoloXDetector


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("video")
    args=parser.parse_args()
    base=Path(__file__).resolve().parents[1]
    out=base/"runtime"/"detection-benchmark"
    out.mkdir(parents=True,exist_ok=True)
    detector=YoloXDetector(base/"models"/"yolox_nano.onnx")
    cap=cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError("Cannot open test video")
    samples=[]
    for second in (0,15,30,45,60,90):
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000)
        ok,bgr=cap.read()
        if not ok:
            raise RuntimeError(f"Cannot decode frame at {second}")
        height=round(bgr.shape[0]*560/bgr.shape[1])
        bgr=cv2.resize(bgr,(560,height))
        rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
        for _ in range(3):
            detections,infer_ms,total_ms=detector.detect_rgb(rgb.tobytes(),560,height)
        timings=[]
        for _ in range(5):
            detections,infer_ms,total_ms=detector.detect_rgb(rgb.tobytes(),560,height)
            timings.append(total_ms)
        record={"second":second,"median_total_ms":statistics.median(timings),
                "detections":[dict(label=d.label,confidence=d.confidence,box=d.box) for d in detections]}
        samples.append(record)
        for detection in detections:
            x1,y1,x2,y2=detection.box
            p1,p2=(round(x1*560),round(y1*height)),(round(x2*560),round(y2*height))
            cv2.rectangle(bgr,p1,p2,(100,240,170),2)
            cv2.putText(bgr,f"{detection.label} {detection.confidence:.2f}",(p1[0],max(12,p1[1]-4)),
                        cv2.FONT_HERSHEY_SIMPLEX,.4,(100,240,170),1)
        cv2.imencode('.jpg',bgr)[1].tofile(str(out/f"sample_{second:03}.jpg"))
    cap.release()
    labels={d["label"] for item in samples for d in item["detections"]}
    report={"model":"YOLOX-Nano","backend":detector.backend,"input_shape":[detector.height,detector.width],
            "median_total_ms":statistics.median(s["median_total_ms"] for s in samples),
            "person_and_vehicle_found":"person" in labels and bool(labels&{"car","bus","truck"}),"samples":samples}
    (out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="samples"},indent=2))
    if not report["person_and_vehicle_found"]:
        raise AssertionError("No person/vehicle coverage in sampled test frames")


if __name__=="__main__":
    main()
