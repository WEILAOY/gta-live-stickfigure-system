"""Package minimal manual combat materials with verified source, models and evidence."""
from pathlib import Path
import hashlib,json,zipfile
base=Path(__file__).resolve().parents[1];project=base.parent;proof=project/'15_极简战斗素材验证'
assert '__version__ = "0.14.0"' in (base/'stickfigure/__init__.py').read_text(encoding='utf-8')
checks=json.loads((proof/'test-commands.json').read_text(encoding='utf-8'));assert checks['passed'] and checks['unit_checks']==59
reports={}
for name in ('combat-workflow-result.json','material-export.json','gta6-workflow-result.json','ocr-workflow-result.json','smoke-result.json','video-smoke-result.json','detection-smoke-result.json','workflow-smoke-result.json'):
    r=json.loads((proof/name).read_text(encoding='utf-8'));assert r['passed'],name;reports[name]=r
hashes={}
for meta,weight in (('model-info.json','yolox_nano.onnx'),('yolox-tiny-model-info.json','yolox_tiny.onnx'),
                    ('yolox-s-model-info.json','yolox_s.onnx'),('pose-model-info.json','pose_estimation_mediapipe_2023mar.onnx'),
                    ('road-model-info.json','segformer_b0_cityscapes.onnx')):
    digest=hashlib.sha256((base/'models'/weight).read_bytes()).hexdigest()
    assert digest==json.loads((base/'models'/meta).read_text(encoding='utf-8'))['sha256'];hashes[weight]=digest
for name,digest in json.loads((base/'models/ocr/model-info.json').read_text(encoding='utf-8'))['models'].items():
    assert hashlib.sha256((base/'models/ocr'/name).read_bytes()).hexdigest()==digest;hashes['ocr/'+name]=digest
(proof/'regression-summary.json').write_text(json.dumps(dict(passed=True,unit_checks=59,integration_checks=sum(len(r.get('checks',[])) for r in reports.values()),model_hashes=hashes,
    note='Manual preset combat only; no automatic video gunshot, hit or fall recognition. OCR and video regressions passed.'),ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in base.rglob('*') if p.is_file() and not {'.venv','runtime','__pycache__','.git'}.intersection(p.relative_to(base).parts)]
files += [p for p in (project/'03_测试素材').rglob('*') if p.is_file()]
files += list(project.glob('*.cmd'))
files += [p for p in proof.iterdir() if p.is_file() and p.suffix in ('.png','.md','.json','.mp4')]
files += [project/'13_GTA6动作验证'/name for name in ('21种预设动作素材.png','预设人物动作演示.mp4')]
archive=project/'火柴人桌面框架_V0.14_极简战斗素材版.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,str(p.relative_to(project)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/runtime/' in n or '/.venv/' in n for n in z.namelist())
print(json.dumps(dict(archive=str(archive),files=len(set(files)),bytes=archive.stat().st_size,crc_passed=True),ensure_ascii=False))
