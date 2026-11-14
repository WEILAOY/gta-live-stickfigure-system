"""Run release regressions sequentially to avoid competing GPU test apps."""
from pathlib import Path
import sys,json,subprocess,shutil
base=Path(__file__).resolve().parents[1];project=base.parent;out=project/'20_闪白修复验证';out.mkdir(exist_ok=True)
sample=project/'03_测试素材'
commands=[['-m','unittest','discover','-s','tools','-p','test_*.py'],['main.py','--smoke-test'],
 ['main.py','--video-smoke-test',str(sample/'gta6_actions_test.mp4')],
 ['main.py','--detect-smoke-test',str(sample/'gta5_test_01.mp4'),'--start-at','15'],
 ['main.py','--workflow-smoke-test',str(sample/'gta5_test_01.mp4'),'--start-at','90'],
 ['tools/check_gta6_workflow.py'],['tools/check_ocr_workflow.py'],['tools/check_combat_workflow.py'],['tools/check_v016_workflow.py'],['tools/check_motorcycle_video.py'],['tools/check_down_source.py'],['tools/check_down_workflow.py'],['tools/check_transport_v018.py'],['tools/check_flicker_workflow.py']]
records=[]
for i,command in enumerate(commands):
    result=subprocess.run([sys.executable,*command],cwd=base,capture_output=True,timeout=100)
    (out/f'check-{i+1}.log').write_bytes(result.stdout+result.stderr)
    records.append(dict(command=command,exit_code=result.returncode))
    print(i+1,command[0],result.returncode,flush=True)
    if result.returncode:print((result.stdout+result.stderr).decode('utf-8',errors='replace'),flush=True);break
success=len(records)==len(commands) and all(r['exit_code']==0 for r in records)
(out/'test-commands.json').write_text(json.dumps(dict(passed=success,unit_checks=81,commands=records),ensure_ascii=False,indent=2),encoding='utf-8')
if success:
    for folder,name in [('runtime/smoke',n) for n in ('smoke-result.json','video-smoke-result.json','detection-smoke-result.json','workflow-smoke-result.json')]+[
        ('../13_GTA6动作验证','gta6-workflow-result.json'),('../14_OCR文字验证','ocr-workflow-result.json'),('../15_极简战斗素材验证','combat-workflow-result.json'),('../17_载具与漫画阴影验证','comic-transport-workflow-result.json'),('../17_载具与漫画阴影验证','motorcycle-video-result.json'),('../17_载具与漫画阴影验证','material-export.json')]:
        shutil.copy2(base/folder/name,out/name)
sys.exit(0 if success else 1)
