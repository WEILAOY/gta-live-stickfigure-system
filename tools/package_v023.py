"""Package verified V0.23 source, model hashes and current proof."""
from pathlib import Path
import hashlib,json,zipfile,shutil
base=Path(__file__).resolve().parents[1];project=base.parent;proof=project/'24_动作角标与识别修正验证'
for name in ('down-source-result.json','down-workflow-result.json'):
    shutil.copy2(project/'18_倒地人物验证'/name,proof/name)
shutil.copy2(project/'19_货车船与方向验证'/'transport-view-result.json',proof/'transport-view-result.json')
for name in ('flicker-workflow-result.json','flicker-after.json'):
    shutil.copy2(project/'20_闪白修复验证'/name,proof/name)

for name in ('auto-shot-source-result.json','auto-shot-workflow-result.json','muzzle-workflow-result.json','muzzle-export-result.json'):
    shutil.copy2(project/'22_极简战斗与自动火光验证'/name,proof/name)
shutil.copy2(project/'21_枪口火光素材验证/muzzle-workflow-result.json',proof/'muzzle-workflow-result.json')
for name in ('shadow-export-result.json','shadow-workflow-result.json'):
    shutil.copy2(project/'23_六档漫画阴影验证'/name,proof/name)
assert '__version__ = "0.23.0"' in (base/'stickfigure/__init__.py').read_text(encoding='utf-8')
checks=json.loads((proof/'test-commands.json').read_text(encoding='utf-8'));assert checks['passed'] and checks['unit_checks']==116
reports={}
for name in ('context-source-result.json','action-caption-workflow-result.json','shadow-export-result.json','shadow-workflow-result.json','auto-shot-source-result.json','auto-shot-workflow-result.json','muzzle-workflow-result.json','muzzle-export-result.json','flicker-workflow-result.json','flicker-after.json','transport-view-result.json','down-source-result.json','down-workflow-result.json','comic-transport-workflow-result.json','motorcycle-video-result.json','combat-workflow-result.json','material-export.json','gta6-workflow-result.json','ocr-workflow-result.json','smoke-result.json','video-smoke-result.json','detection-smoke-result.json','workflow-smoke-result.json'):
    r=json.loads((proof/name).read_text(encoding='utf-8'));assert r['passed'],name;reports[name]=r
hashes={}
for meta,weight in (('model-info.json','yolox_nano.onnx'),('yolox-tiny-model-info.json','yolox_tiny.onnx'),('yolox-s-model-info.json','yolox_s.onnx'),('pose-model-info.json','pose_estimation_mediapipe_2023mar.onnx'),('road-model-info.json','segformer_b0_cityscapes.onnx')):
    digest=hashlib.sha256((base/'models'/weight).read_bytes()).hexdigest()
    assert digest==json.loads((base/'models'/meta).read_text(encoding='utf-8'))['sha256'];hashes[weight]=digest
for name,digest in json.loads((base/'models/ocr/model-info.json').read_text(encoding='utf-8'))['models'].items():
    assert hashlib.sha256((base/'models/ocr'/name).read_bytes()).hexdigest()==digest;hashes['ocr/'+name]=digest
for meta in json.loads((base/'models/context/model-info.json').read_text(encoding='utf-8')):
    assert hashlib.sha256((base/'models/context'/meta['file']).read_bytes()).hexdigest()==meta['sha256']
    hashes['context/'+meta['file']]=meta['sha256']
(proof/'regression-summary.json').write_text(json.dumps(dict(passed=True,unit_checks=116,integration_checks=sum(len(r.get('checks',[])) for r in reports.values()),model_hashes=hashes,note='Strict locally observed gun plus wrist/muzzle flash evidence; explicit helicopter detection mapped to fixed mesh; per-person native action-change notices expire after 2 video seconds. Actual 14m/16m/23m and phone/down workflows checked. Extra local inference adds latency; no full-video accuracy guarantee.'),ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in base.rglob('*') if p.is_file() and not {'.venv','runtime','__pycache__','.git','research_not_shipped'}.intersection(p.relative_to(base).parts)]
files += [p for p in (project/'03_测试素材').rglob('*') if p.is_file()]
files += list(project.glob('*.cmd'))
allowed_shots={f"自动火光_{e['timestamp']:.3f}s.png" for e in reports['auto-shot-source-result.json']['events']}
files += [p for p in proof.iterdir() if p.is_file() and (p.name in reports or p.name in ('regression-summary.json','test-commands.json','V0.23_实施与验证.md','14分_直升机自动识别.png','16分_烧车不触发射击.png','23分25秒_持枪证据与开枪角标.png','04分_自动玩手机角标.png'))]
files += [p for p in (project/'22_极简战斗与自动火光验证').iterdir() if p.is_file() and p.name in ('23分20秒片段自动火光对比.png','枪口连接四视角.png','两套火光三态素材.png')]
files += [p for p in (project/'19_货车船与方向验证').iterdir() if p.is_file() and p.suffix=='.png']
files += [p for p in (project/'17_载具与漫画阴影验证').iterdir() if p.is_file() and p.suffix in ('.png','.mp4')]
files += [project/'13_GTA6动作验证'/name for name in ('21种预设动作素材.png','预设人物动作演示.mp4')]
archive=project/'火柴人桌面框架_V0.23_识别修正与动作角标版.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,str(p.relative_to(project)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/runtime/' in n or '/.venv/' in n for n in z.namelist())
print(json.dumps(dict(archive=str(archive),files=len(set(files)),bytes=archive.stat().st_size,crc_passed=True),ensure_ascii=False))
