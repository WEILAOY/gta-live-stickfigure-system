"""Record real video evidence for pose/horizon and measured full analysis cost."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,time,statistics
import cv2
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame
from stickfigure.assets import BODY_LINKS


def main():
    base=Path(__file__).resolve().parents[1]
    output=base.parent/'05_视觉升级验证'
    output.mkdir(exist_ok=True)
    detector=YoloXDetector(base/'models'/'yolox_nano.onnx')
    analyzer=SceneAnalyzer(base/'models')
    cap=cv2.VideoCapture(str(base.parent/'03_测试素材'/'gta5_test_01.mp4'))
    records=[]
    for second in (0,15,15.2,15.4,15.6,15.8,30,30.2,30.4,60,60.2,60.4,90):
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000)
        ok,bgr=cap.read()
        if not ok:
            raise RuntimeError('Cannot read test frame')
        rgb=cv2.cvtColor(cv2.resize(bgr,(560,315)),cv2.COLOR_BGR2RGB)
        began=time.perf_counter()
        detections,_,_=detector.detect_rgb(rgb.tobytes(),560,315)
        detections,horizon=analyzer.analyze(VideoFrame(1,second,560,315,rgb.tobytes()),detections)
        elapsed=(time.perf_counter()-began)*1000
        records.append(dict(second=second,total_ms=elapsed,horizon=dict(left=horizon.left,right=horizon.right,
            score=horizon.confidence,method=horizon.method),objects=[dict(label=d.label,pose_points=len(d.pose),
            action=d.action,yaw=d.yaw,view_score=d.view_confidence) for d in detections]))
        image=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
        cv2.line(image,(0,round(horizon.left*315)),(559,round(horizon.right*315)),(30,170,245),2,cv2.LINE_AA)
        for detection in detections:
            if detection.pose:
                pose=detection.pose
                for a,b in BODY_LINKS:
                    if pose[a].confidence>.45 and pose[b].confidence>.45:
                        cv2.line(image,(round(pose[a].x*560),round(pose[a].y*315)),
                            (round(pose[b].x*560),round(pose[b].y*315)),(80,220,120),2,cv2.LINE_AA)
        cv2.imencode('.jpg',image)[1].tofile(str(output/f'analysis_{second:.1f}.jpg'))
    cap.release()
    report=dict(median_analysis_ms=statistics.median(r['total_ms'] for r in records),
                max_analysis_ms=max(r['total_ms'] for r in records),samples=records,
                note='Image-derived estimates; no ground-truth horizon/view/action accuracy measured.')
    (output/'analysis-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert any(any(d['pose_points']==33 for d in r['objects']) for r in records)
    heights=[(r['horizon']['left']+r['horizon']['right'])/2 for r in records if r['horizon']['score']>.3]
    assert heights and max(heights)-min(heights)>.05
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=True))


if __name__=='__main__':
    main()
