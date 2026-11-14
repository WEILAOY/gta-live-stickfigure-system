"""Reviewed V0.12 source, unmodified weights, excerpt and action evidence."""
from pathlib import Path
import json,hashlib,zipfile
base=Path(__file__).resolve().parents[1];project=base.parent;proof=project/'13_GTA6动作验证'
assert '__version__ = "0.12.0"' in (base/'stickfigure/__init__.py').read_text(encoding='utf-8')
commands=json.loads((proof/'test-commands.json').read_text(encoding='utf-8'))
assert commands['passed'] and commands['unit_checks']==48
reports={}
for name in ('smoke-result.json','video-smoke-result.json','detection-smoke-result.json','workflow-smoke-result.json',
             'gta6-workflow-result.json','performance-gta6.json','gta6-action-report.json'):
    report=json.loads((proof/name).read_text(encoding='utf-8'));assert report['passed'],name
    reports[name]=report
model_hashes={}
for meta,weight in (('model-info.json','yolox_nano.onnx'),('yolox-tiny-model-info.json','yolox_tiny.onnx'),
                    ('yolox-s-model-info.json','yolox_s.onnx'),('pose-model-info.json','pose_estimation_mediapipe_2023mar.onnx'),
                    ('road-model-info.json','segformer_b0_cityscapes.onnx')):
    digest=hashlib.sha256((base/'models'/weight).read_bytes()).hexdigest()
    assert digest==json.loads((base/'models'/meta).read_text(encoding='utf-8'))['sha256']
    model_hashes[weight]=digest
summary=dict(passed=True,unit_checks=48,integration_checks=sum(len(r.get('checks',[])) for r in reports.values()),
             models=model_hashes,gta6_workflow=reports['gta6-workflow-result.json'],performance=reports['performance-gta6.json'],
             note='21 presets do not imply 21 automatically recognized actions. No full-video accuracy ground truth.')
(proof/'regression-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in base.rglob('*') if p.is_file() and not {'.venv','runtime','__pycache__','.git'}.intersection(p.relative_to(base).parts)]
files += [p for p in (project/'03_测试素材').rglob('*') if p.is_file()]
files += [project/name for name in ('启动火柴人框架.cmd','打开GTA5测试片段.cmd','打开可见区域示例.cmd',
                                  '打开精细识别与楼群示例.cmd','打开GTA6完整视频.cmd','打开GTA6动作片段.cmd')]
files += [p for p in proof.iterdir() if p.is_file() and (p.suffix=='.md' or
          p.name in (*reports,'source-info.json','clip-mapping.json','test-commands.json','regression-summary.json',
                     '21种预设动作素材.png','预设人物动作演示.mp4') or p.name.startswith('auto_'))]
archive=project/'火柴人桌面框架_V0.12_GTA6人物动作版.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for p in sorted(set(files)):bundle.write(p,str(p.relative_to(project)))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    names=bundle.namelist()
    assert any(n.endswith('gta6_actions_test.mp4') for n in names)
    assert not any('/runtime/' in n or '/.venv/' in n for n in names)
print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(set(files)),crc_passed=True),ensure_ascii=False))
