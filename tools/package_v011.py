"""Package V0.11; exclude local OBS references, wheels and runtime files."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile


base = Path(__file__).resolve().parents[1]
assert '__version__ = "0.11.0"' in (base/'stickfigure/__init__.py').read_text(encoding='utf-8'), 'Package script version does not match source'
project = base.parent
evidence = project / '12_城市群与识别对照'
checks=json.loads((evidence/'test-commands.json').read_text(encoding='utf-8'))
assert checks['passed'] and checks['unit_checks']==39
assert json.loads((evidence/'gpu-switch-stress.json').read_text(encoding='utf-8'))['passed']
assert json.loads((evidence/'cpu-fallback-detection.json').read_text(encoding='utf-8'))['passed']
reports = {}
for name in ('smoke-result.json', 'video-smoke-result.json',
             'detection-smoke-result.json', 'workflow-smoke-result.json',
             'performance-result.json'):
    source = base / 'runtime' / 'smoke' / name
    report = json.loads(source.read_text(encoding='utf-8'))
    assert report['passed'], name
    reports[name] = report
    shutil.copy2(source, evidence / name)

model_checks = {}
for metadata, weight in (
        ('model-info.json', 'yolox_nano.onnx'),
        ('yolox-tiny-model-info.json', 'yolox_tiny.onnx'),
        ('yolox-s-model-info.json', 'yolox_s.onnx'),
        ('pose-model-info.json', 'pose_estimation_mediapipe_2023mar.onnx'),
        ('road-model-info.json', 'segformer_b0_cityscapes.onnx')):
    info = json.loads((base / 'models' / metadata).read_text(encoding='utf-8'))
    digest = hashlib.sha256((base / 'models' / weight).read_bytes()).hexdigest()
    assert digest == info['sha256'], weight
    model_checks[weight] = digest

summary = dict(passed=True, unit_checks=39,
               integration_checks=sum(len(r.get('checks', [])) for r in reports.values()),
               performance=reports['performance-result.json'],
               model_sha256=model_checks,
               note='39 unit checks plus integration, real CPU fallback and short GPU switching passed on 2026-11-07. Eight-frame manual object audit is not overall accuracy. No road/building accuracy ground truth.')
(evidence / 'regression-summary.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

files = [p for p in base.rglob('*') if p.is_file()
         and not {'.venv', '__pycache__', 'runtime', '.git'}.intersection(p.relative_to(base).parts)]
files += [project / '打开GTA5测试片段.cmd', project / '启动火柴人框架.cmd']
files += [project / '打开可见区域示例.cmd']
files += [project / '打开精细识别与楼群示例.cmd']
files += [project/'09_预设素材与画面裁剪验证'/name for name in ('ghost-before-samples.json','ghost-fix-result.json','performance-30hz-result.json')]
files += [p for p in (project / '03_测试素材').rglob('*') if p.is_file()]
# Only reviewed comparison images and JSON reports accompany the release.
files += [p for p in evidence.iterdir() if p.is_file()
          and (p.suffix in ('.json', '.md') or p.suffix == '.png')]
archive = project / '火柴人桌面框架_V0.11_GPU精细识别与楼群版.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
    for path in sorted(files):
        bundle.write(path, str(path.relative_to(project)))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    names = bundle.namelist()
    assert any(n.endswith('curbs.py') for n in names)
    assert any(n.endswith('ROAD_MODEL_LICENSE.txt') for n in names)
    assert not any('/.venv/' in n or '/runtime/' in n for n in names)
    assert not any('edgeyolo' in n.lower() and n.lower().endswith('.onnx') for n in names)
    assert any(n.endswith('inference.py') for n in names)
print(json.dumps(dict(archive=str(archive), files=len(files), bytes=archive.stat().st_size,
                      crc_passed=True, model_checks_passed=True), ensure_ascii=False))
