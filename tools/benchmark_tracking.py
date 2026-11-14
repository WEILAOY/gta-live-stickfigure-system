"""Observed continuity of a prominent car; heuristic diagnostic, not GT accuracy."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,time,statistics
import cv2
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame


def main():
    base=Path(__file__).resolve().parents[1]
    detector=YoloXDetector(base/'models'/'yolox_nano.onnx')
    analyzer=SceneAnalyzer(base/'models')
    cap=cv2.VideoCapture(str(base.parent/'03_测试素材'/'gta5_test_01.mp4'))
    records=[];seed=None
    for i in range(51):
        second=60+i*.2
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000)
        ok,bgr=cap.read();assert ok
        rgb=cv2.cvtColor(cv2.resize(bgr,(560,315)),cv2.COLOR_BGR2RGB)
        start=time.perf_counter()
        detections,_,_=detector.detect_rgb(rgb.tobytes(),560,315)
        tracked,_=analyzer.analyze(VideoFrame(1,second,560,315,rgb.tobytes()),detections)
        elapsed=(time.perf_counter()-start)*1000
        cars=[d for d in tracked if d.label=='car' and not d.predicted]
        prominent=max(cars,key=lambda d:(d.box[2]-d.box[0])*(d.box[3]-d.box[1]),default=None)
        if seed is None and prominent:
            seed=prominent.track_id
        records.append(dict(second=second,total_ms=elapsed,prominent_id=prominent.track_id if prominent else None,
                            seed_observed=any(d.track_id==seed and not d.predicted for d in tracked),
                            seed_retained=any(d.track_id==seed for d in tracked)))
    cap.release()
    report=dict(seed_id=seed,frames=len(records),seed_observed_frames=sum(r['seed_observed'] for r in records),
                seed_retained_frames=sum(r['seed_retained'] for r in records),
                median_analysis_ms=statistics.median(r['total_ms'] for r in records),samples=records,
                note='Prominent-box continuity diagnostic; no manually annotated identity ground truth.')
    output=base.parent/'06_追踪与道路验证'
    output.mkdir(exist_ok=True)
    (output/'tracking-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=True))


if __name__=='__main__':
    main()
