"""Package verified V0.19 source, model hashes and current proof."""
from pathlib import Path
import hashlib,json,zipfile,shutil
base=Path(__file__).resolve().parents[1];project=base.parent;proof=project/'20_闪白修复验证'
for name in ('down-source-result.json','down-workflow-result.json'):
    shutil.copy2(project/'18_倒地人物验证'/name,proof/name)
shutil.copy2(project/'19_货车船与方向验证'/'transport-view-result.json',proof/'transport-view-result.json')
assert '__version__ = "0.19.0"' in (base/'stickfigure/__init__.py').read_text(encoding='utf-8')
checks=json.loads((proof/'test-commands.json').read_text(encoding='utf-8'));assert checks['passed'] and checks['unit_checks']==81
reports={}
for name in ('flicker-workflow-result.json','flicker-after.json','transport-view-result.json','down-source-result.json','down-workflow-result.json','comic-transport-workflow-result.json','motorcycle-video-result.json','combat-workflow-result.json','material-export.json','gta6-workflow-result.json','ocr-workflow-result.json','smoke-result.json','video-smoke-result.json','detection-smoke-result.json','workflow-smoke-result.json'):
    r=json.loads((proof/name).read_text(encoding='utf-8'));assert r['passed'],name;reports[name]=r
hashes={}
for meta,weight in (('model-info.json','yolox_nano.onnx'),('yolox-tiny-model-info.json','yolox_tiny.onnx'),('yolox-s-model-info.json','yolox_s.onnx'),('pose-model-info.json','pose_estimation_mediapipe_2023mar.onnx'),('road-model-info.json','segformer_b0_cityscapes.onnx')):
    digest=hashlib.sha256((base/'models'/weight).read_bytes()).hexdigest()
    assert digest==json.loads((base/'models'/meta).read_text(encoding='utf-8'))['sha256'];hashes[weight]=digest
for name,digest in json.loads((base/'models/ocr/model-info.json').read_text(encoding='utf-8'))['models'].items():
    assert hashlib.sha256((base/'models/ocr'/name).read_bytes()).hexdigest()==digest;hashes['ocr/'+name]=digest
(proof/'regression-summary.json').write_text(json.dumps(dict(passed=True,unit_checks=81,integration_checks=sum(len(r.get('checks',[])) for r in reports.values()),model_hashes=hashes,note='Atomic hidden-frame staging, retained image references, bounded latency-aware analysis freshness and pause/resume presentation handoff. New negative detections still remove actors immediately.'),ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in base.rglob('*') if p.is_file() and not {'.venv','runtime','__pycache__','.git'}.intersection(p.relative_to(base).parts)]
files += [p for p in (project/'03_测试素材').rglob('*') if p.is_file()]
files += list(project.glob('*.cmd'))
files += [p for p in proof.iterdir() if p.is_file() and p.suffix in ('.png','.md','.json','.mp4')]
files += [p for p in (project/'19_货车船与方向验证').iterdir() if p.is_file() and p.suffix=='.png']
files += [p for p in (project/'17_载具与漫画阴影验证').iterdir() if p.is_file() and p.suffix in ('.png','.mp4')]
files += [project/'13_GTA6动作验证'/name for name in ('21种预设动作素材.png','预设人物动作演示.mp4')]
archive=project/'火柴人桌面框架_V0.19_闪白修复版.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,str(p.relative_to(project)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/runtime/' in n or '/.venv/' in n for n in z.namelist())
print(json.dumps(dict(archive=str(archive),files=len(set(files)),bytes=archive.stat().st_size,crc_passed=True),ensure_ascii=False))
