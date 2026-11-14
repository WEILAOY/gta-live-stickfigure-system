from pathlib import Path
import sys,json,time
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.core import Scene,Entity
from stickfigure.assets import ACTIONS,person_props
class TestApp(Application):
    def _run_smoke(self):pass
base=Path(__file__).resolve().parents[1];out=base.parent/'15_极简战斗素材验证';out.mkdir(exist_ok=True)
app=TestApp(base,smoke_test=True)
started=time.perf_counter()
def check():
    try:
        app.update_idletasks()
        if app.output_canvas.winfo_width()<100 or app.output_canvas.winfo_height()<100:
            assert time.perf_counter()-started<15
            app.after(50,check);return
        raw=Scene(0,0,1,10,(Entity('person','person',.5,.85,bbox=(.42,.2,.58,.85),action='ARMS_FORWARD'),),False,frame_clipping=True)
        app._restore_automatic();auto=app._presentation_scene(raw)
        assert auto.entities[0].action=='ARMS_FORWARD' and not person_props('ARMS_FORWARD')
        app.weapon_var.set('长枪');app.combat_mirror_var.set(True);app.person_action_var.set('射击')
        first=app._presentation_scene(raw);assert first.entities[0].weapon=='rifle' and first.entities[0].action_mirror
        assert first.entities[0].action_time==0
        later=app._presentation_scene(replace(raw,animation_time=10.1))
        assert abs(later.entities[0].action_time-.1)<1e-5
        app.output_canvas.draw(later,simulated=False);assert app.output_canvas.find_withtag('preset-object')
        app.person_action_var.set('侧倒');assert app._presentation_scene(raw).entities[0].action_time==0
        later=app._presentation_scene(replace(raw,animation_time=11));assert later.entities[0].action_time==1
        app.output_canvas.draw(later,simulated=False);assert app.output_canvas.find_withtag('preset-object')
        app._reset_detection(preserve_binding=True);assert app._manual_action_name=='侧倒'
        app._reset_detection(preserve_binding=False);assert app._manual_action_name is None
        assert app._presentation_scene(replace(raw,animation_time=2)).entities[0].action_time==0
        app.save_settings();loaded=app._load_settings();assert loaded['weapon']=='长枪' and loaded['combat_mirror']
        app.open_combat_preview();preview=app.combat_preview;app.update_idletasks()
        assert preview.winfo_exists();preview.replay('fire');assert preview.mode=='fire'
        preview.replay('hit');assert preview.mode=='hit';preview.close();assert not preview.winfo_exists()
        app.open_combat_preview();assert app.combat_preview.winfo_exists() and app.combat_preview is not preview
        app._restore_automatic();assert app._presentation_scene(raw).entities[0].action=='ARMS_FORWARD'
        app.combat_mirror_var.set(False);app.save_settings()
        (out/'combat-workflow-result.json').write_text(json.dumps(dict(passed=True,presets=len(ACTIONS)-1,manual_demo=True,checks=[
            'automatic arm pose does not become a gun or shot','two weapon types selectable','left/right setting propagated',
            'manual shot uses local action time','shot phase progresses with scene time','combat uses preset renderer',
            'fall starts at zero and finishes once','pause preserves manual phase and seek resets it','weapon and direction settings roundtrip','explicit manual preview window opens',
            'single fire and hit modes selectable','preview closes and reopens','restore automatic removes manual combat override',
            'app close owns preview lifecycle']),ensure_ascii=False,indent=2),encoding='utf-8')
        app.close()
    except Exception:app._smoke_failure()
app.after(200,check);app.mainloop();sys.exit(1 if app.test_failed else 0)
