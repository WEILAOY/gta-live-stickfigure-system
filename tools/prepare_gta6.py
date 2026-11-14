"""Make a compact action test montage; preserve the user's original video."""
from pathlib import Path
import json,subprocess
base=Path(__file__).resolve().parents[1];out=base.parent/'13_GTA6动作验证'
info=json.loads((out/'source-info.json').read_text(encoding='utf-8'))
source=Path(info['source']);assert source.exists()
parts=base/'runtime/gta6-parts';parts.mkdir(exist_ok=True)
segments=[(210,12,'conversation'),(236,10,'phone'),(294,12,'forward arms / pointing'),
          (538,6,'climbing'),(648,18,'seated conversation'),(718,6,'forward arms'),
          (1038,8,'lifting'),(1048,8,'rowing'),(1058,6,'drink / party'),
          (1077,6,'interaction'),(1097,8,'gestures'),(1397,8,'embrace / sway'),
          (1437,8,'handheld object'),(1498,8,'forward arms'),(1556,8,'seated gestures')]
mapping=[];offset=0
for index,(start,duration,description) in enumerate(segments):
    part=parts/f'{index:02}.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(source),
                    '-t',str(duration),'-an','-vf','fps=30','-c:v','libx264','-preset','fast','-crf','20','-threads','2',str(part)],check=True)
    mapping.append(dict(clip_start=offset,source_start=start,duration=duration,observed_scene=description))
    offset+=duration
concat=parts/'parts.txt';concat.write_text(''.join(f"file '{p.resolve().as_posix()}'\n" for p in sorted(parts.glob('[0-9][0-9].mp4'))),encoding='utf-8')
clip=base.parent/'03_测试素材/gta6_actions_test.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(clip)],check=True)
metadata=dict(source=str(source),source_duration=info['duration'],fps=30,width=852,height=480,
              clip=str(clip),clip_duration=offset,segments=mapping,
              note='Real source excerpts concatenated at scene boundaries; original unmodified. Silent test preview. No synthetic action labels applied to inference.')
(out/'clip-mapping.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
(base.parent/'03_测试素材/gta6-source.json').write_text(json.dumps(dict(source=str(source),start_at=240,sample_start=16,fallback='gta6_actions_test.mp4'),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(clip=str(clip),seconds=offset,bytes=clip.stat().st_size),ensure_ascii=False))
