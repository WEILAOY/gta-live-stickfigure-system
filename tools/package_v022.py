"""Package verified V0.22 source, model hashes and current proof."""
from pathlib import Path
import hashlib,json,zipfile,shutil
base=Path(__file__).resolve().parents[1];project=base.parent;proof=project/'23_六档漫画阴影验证'
for name in ('down-source-result.json','down-workflow-result.json'):
    shutil.copy2(project/'18_倒地人物验证'/name,proof/name)
shutil.copy2(project/'19_货车船与方向验证'/'transport-view-result.json',proof/'transport-view-result.json')
for name in ('flicker-workflow-result.json','flicker-after.json'):
    shutil.copy2(project/'20_闪白修复验证'/name,proof/name)

for name in ('auto-shot-source-result.json','auto-shot-workflow-result.json','muzzle-workflow-result.json','muzzle-export-result.json'):
    shutil.copy2(project/'22_极简战斗与自动火光验证'/name,proof/name)
shutil.copy2(project/'21_枪口火光素材验证/muzzle-workflow-result.json',proof/'muzzle-workflow-result.json')
assert '__version__ = "0.22.0"' in (base/'stickfigure/__init__.py').read_text(encoding='utf-8')
checks=json.loads((proof/'test-commands.json').read_text(encoding='utf-8'));assert checks['passed'] and checks['unit_checks']==101
reports={}
for name in ('shadow-export-result.json','shadow-workflow-result.json','auto-shot-source-result.json','auto-shot-workflow-result.json','muzzle-workflow-result.json','muzzle-export-result.json','flicker-workflow-result.json','flicker-after.json','transport-view-result.json','down-source-result.json','down-workflow-result.json','comic-transport-workflow-result.json','motorcycle-video-result.json','combat-workflow-result.json','material-export.json','gta6-workflow-result.json','ocr-workflow-result.json','smoke-result.json','video-smoke-result.json','detection-smoke-result.json','workflow-smoke-result.json'):
    r=json.loads((proof/name).read_text(encoding='utf-8'));assert r['passed'],name;reports[name]=r
hashes={}
for meta,weight in (('model-info.json','yolox_nano.onnx'),('yolox-tiny-model-info.json','yolox_tiny.onnx'),('yolox-s-model-info.json','yolox_s.onnx'),('pose-model-info.json','pose_estimation_mediapipe_2023mar.onnx'),('road-model-info.json','segformer_b0_cityscapes.onnx')):
    digest=hashlib.sha256((base/'models'/weight).read_bytes()).hexdigest()
    assert digest==json.loads((base/'models'/meta).read_text(encoding='utf-8'))['sha256'];hashes[weight]=digest
for name,digest in json.loads((base/'models/ocr/model-info.json').read_text(encoding='utf-8'))['models'].items():
    assert hashlib.sha256((base/'models/ocr'/name).read_bytes()).hexdigest()==digest;hashes['ocr/'+name]=digest
(proof/'regression-summary.json').write_text(json.dumps(dict(passed=True,unit_checks=101,integration_checks=sum(len(r.get('checks',[])) for r in reports.values()),model_hashes=hashes,note='Six fixed comic tone materials, 120x68 default background geometry, bounded temporal stabilization and two-zone dotted contacts. Source comparisons and live options/fire checked; 30fps output is a target, not guaranteed end-to-end throughput.'),ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in base.rglob('*') if p.is_file() and not {'.venv','runtime','__pycache__','.git'}.intersection(p.relative_to(base).parts)]
files += [p for p in (project/'03_测试素材').rglob('*') if p.is_file()]
files += list(project.glob('*.cmd'))
allowed_shots={f"自动火光_{e['timestamp']:.3f}s.png" for e in reports['auto-shot-source-result.json']['events']}
files += [p for p in proof.iterdir() if p.is_file() and p.suffix in ('.png','.md','.json','.mp4') and (not p.name.startswith(('自动火光_','candidate_','source_')) or p.name in allowed_shots)]
files += [p for p in (project/'22_极简战斗与自动火光验证').iterdir() if p.is_file() and p.name in ('23分20秒片段自动火光对比.png','枪口连接四视角.png','两套火光三态素材.png')]
files += [p for p in (project/'19_货车船与方向验证').iterdir() if p.is_file() and p.suffix=='.png']
files += [p for p in (project/'17_载具与漫画阴影验证').iterdir() if p.is_file() and p.suffix in ('.png','.mp4')]
files += [project/'13_GTA6动作验证'/name for name in ('21种预设动作素材.png','预设人物动作演示.mp4')]
archive=project/'火柴人桌面框架_V0.22_六档漫画阴影版.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,str(p.relative_to(project)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/runtime/' in n or '/.venv/' in n for n in z.namelist())
print(json.dumps(dict(archive=str(archive),files=len(set(files)),bytes=archive.stat().st_size,crc_passed=True),ensure_ascii=False))
