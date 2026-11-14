"""Repeat the diagnosed interval and compare duplicate-track symptoms, not GT accuracy."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,cv2
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame
from stickfigure.tracking import overlap,family


def main():
    base=Path(__file__).resolve().parents[1]
    before=json.loads((base.parent/'09_预设素材与画面裁剪验证/ghost-before-samples.json').read_text(encoding='utf-8'))
    detector=YoloXDetector(base/'models/yolox_nano.onnx');analyzer=SceneAnalyzer(base/'models')
    cap=cv2.VideoCapture(str(base.parent/'03_测试素材/gta5_test_01.mp4'))
    records=[]
    for previous in before:
        second=previous['second']
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,bgr=cap.read();assert ok
        rgb=cv2.cvtColor(cv2.resize(bgr,(560,315)),cv2.COLOR_BGR2RGB)
        frame=VideoFrame(1,second,560,315,rgb.tobytes())
        raw,_,_=detector.detect_rgb(frame.pixels,560,315)
        tracked,_=analyzer.analyze(frame,raw)
        seen=[d for d in tracked if not d.predicted]
        held=[d for d in tracked if d.predicted]
        drawn=[d for d in tracked if not d.predicted and d.confirmed]
        duplicates=[(h.track_id,d.track_id) for h in held for d in seen if family(h.label)==family(d.label) and overlap(h.box,d.box)>.4]
        records.append(dict(second=second,seen=len(seen),held=len(held),drawn=len(drawn),duplicates=duplicates,
                            drawn_predicted=sum(d.predicted for d in drawn)))
    cap.release()
    report=dict(frames=len(records),before_frames_with_held=sum(r['held']>0 for r in before),
                before_max_held=max(r['held'] for r in before),
                before_duplicate_frames=sum(bool(r['duplicates']) for r in before),
                after_duplicate_frames=sum(bool(r['duplicates']) for r in records),
                after_drawn_predicted=sum(r['drawn_predicted'] for r in records),
                note='Same sampled interval; duplicate-track symptom diagnostic, not annotated detection accuracy.',samples=records)
    assert report['after_drawn_predicted']==0
    target=base.parent/'09_预设素材与画面裁剪验证/ghost-fix-result.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}))


if __name__=='__main__':
    main()
