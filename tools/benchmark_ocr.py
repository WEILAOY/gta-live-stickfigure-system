"""OCR string evidence and font-only proof images; no source-edge copying."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from stickfigure.ocr import TextRecognizer
from stickfigure.video import VideoFrame
base=Path(__file__).resolve().parents[1];out=base.parent/'14_OCR文字验证';out.mkdir(exist_ok=True)
full=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
recognizer=TextRecognizer(base/'models/ocr');records=[]
fontfile='C:/Windows/Fonts/msyh.ttc';large=ImageFont.truetype(fontfile,22)
for name,path,second in (('opening',full,6),('subtitle',str(base.parent/'03_测试素材/gta6_actions_test.mp4'),95),
                         ('sign',str(base.parent/'03_测试素材/gta6_actions_test.mp4'),50)):
    cap=cv2.VideoCapture(path);cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,bgr=cap.read();cap.release();assert ok
    h,w=bgr.shape[:2];rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
    frame=VideoFrame(1,second,w,h,rgb.tobytes());regions,ms=recognizer.recognize(frame)
    result=Image.new('RGB',(w,h),'#f7f9fc');draw=ImageDraw.Draw(result)
    for r in regions:
        a,b,c,d=r.box;size=max(1,round((d-b)*h*.85))
        while True:
            font=ImageFont.truetype(fontfile,size)
            bounds=draw.textbbox((0,0),r.text,font=font)
            if size<=1 or (bounds[2]-bounds[0]<=(c-a)*w and bounds[3]-bounds[1]<=(d-b)*h):break
            size-=1
        draw.text((a*w,b*h-bounds[1]),r.text,font=font,fill='#22374d')
    proof=Image.new('RGB',(w*2,h+130),'#f7f9fc');proof.paste(Image.fromarray(rgb),(0,40));proof.paste(result,(w,40))
    draw=ImageDraw.Draw(proof);draw.text((12,5),'原画面 / OCR 字符串字体排版（文字对照，不含人车）',font=large,fill='#22374d')
    draw.text((12,h+48),'识别内容：'+' / '.join(r.text for r in regions),font=large,fill='#22374d')
    proof.save(out/f'ocr_{name}.png')
    records.append(dict(name=name,second=second,ms=ms,regions=[dict(text=r.text,confidence=r.confidence,box=r.box) for r in regions]))
blank=VideoFrame(1,0,852,480,np.full((480,852,3),255,np.uint8).tobytes())
regions,ms=recognizer.recognize(blank);assert not regions
(out/'ocr-samples.json').write_text(json.dumps(dict(passed=True,blank_no_text=True,samples=records),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(records,ensure_ascii=False))
