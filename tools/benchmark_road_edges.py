from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np,json,statistics
from stickfigure.road import RoadSegmenter
from stickfigure.video import VideoFrame


def main():
    base=Path(__file__).resolve().parents[1]
    output=base.parent/'07_驾驶路缘与高频验证';output.mkdir(exist_ok=True)
    model=RoadSegmenter(base/'models'/'segformer_b0_cityscapes.onnx')
    cap=cv2.VideoCapture(str(base.parent/'03_测试素材'/'gta5_test_01.mp4'))
    records=[]
    for second in (0,30,60,70,90,90.2,90.4,105):
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,bgr=cap.read();assert ok
        bgr=cv2.resize(bgr,(560,315));rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
        geometry,elapsed=model.segment(VideoFrame(1,second,560,315,rgb.tobytes()))
        records.append(dict(second=second,total_ms=elapsed,driving_view=geometry.driving_view,
                            left_edge=geometry.left_edge,right_edge=geometry.right_edge,method=geometry.method))
        if geometry.driving_view:
            for edge,color in ((geometry.left_edge,(90,220,130)),(geometry.right_edge,(55,175,245))):
                if edge:
                    coords=np.array([(round(x*559),round(y*314)) for x,y in edge],np.int32)
                    cv2.polylines(bgr,[coords],False,color,3,cv2.LINE_AA)
        else:
            cv2.putText(bgr,'DRIVING VIEW NOT CONFIRMED',(12,28),cv2.FONT_HERSHEY_SIMPLEX,.45,(30,170,245),1,cv2.LINE_AA)
        cv2.imencode('.jpg',bgr)[1].tofile(str(output/f'curb_{second:05.1f}.jpg'))
    cap.release()
    report=dict(input_size=[384,256],median_road_ms=statistics.median(r['total_ms'] for r in records),
                samples=records,note='Open curb estimates, not closed road masks; no accuracy ground truth.')
    (output/'curb-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    sample=next(r for r in records if r['second']==90)
    assert sample['driving_view'] and sample['left_edge'] and sample['right_edge']
    assert not next(r for r in records if r['second']==30)['driving_view']
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}))


if __name__=='__main__':
    main()
