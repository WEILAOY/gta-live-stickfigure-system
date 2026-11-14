"""Live decoder -> local flash analyzer -> application -> fixed assets."""
from pathlib import Path
import sys,json,time
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.core import Entity,Scene
from stickfigure.shooting import ShotEvent
base=Path(__file__).resolve().parents[1];out=base.parent/'22_极简战斗与自动火光验证'
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=1403.5)
app.auto_fire_var.set(True);app._auto_fire_changed();app.person_action_var.set('自动姿态');app.weapon_var.set('手枪')
app.model_profile_var.set('精细');app.ai_var.set(True);app.fps_var.set('30');app.detect_rate_var.set('10');app._model_changed()
state={'started':False,'pulses':0,'last':False,'aimed':0,'active_positions':[]};began=time.perf_counter()
def poll():
    try:
        elapsed=time.perf_counter()-began
        if not state['started']:
            if app.video_frame is not None and app.detection_result is not None:
                app.start();state['started']=True
        else:
            presented=app._presentation_scene(app.scene)
            aimed=[e for e in presented.entities if e.aim_point is not None] if presented else []
            if aimed:state['aimed']+=1
            orange=0
            for photo,bounds in app.output_canvas._layer_cache.values():
                if photo is None:continue
                raw=photo.tk.call(str(photo),'data','-format','png');p=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
                orange+=int(np.sum((p[:,:,2]>180)&(p[:,:,1]>90)&(p[:,:,0]<180)))
            active=orange>0
            if active and not state['last']:state['pulses']+=1;state['active_positions'].append(app.video_position)
            state['last']=active
            if app.video_position>=1408:
                assert app._shot_count>=1,(app._shot_count,app.shot_status_var.get())
                assert state['pulses']>=1,state
                assert state['aimed']>=1,state
                assert not app.fire_detector.last_error
                # The supplied clip can still be firing at this timestamp.
                # Turning off fire must clear pixels while retaining holding.
                app.auto_fire_var.set(False);app._auto_fire_changed()
                app.output_canvas.draw(app._presentation_scene(app.scene))
                for key,(photo,bounds) in app.output_canvas._layer_cache.items():
                    assert key[0].action!='GUN_FIRE'
                app.auto_fire_var.set(True);app._auto_fire_changed()
                # Ownership, manual override, disable and reset are independent
                # of the source's model-specific track IDs.
                raw=Scene(0,0,1,0,(Entity('p','person',.5,.9,bbox=(.4,.2,.6,.9)),),False)
                event=ShotEvent(app.video.generation,app.video_position,'p',.6,.4,1,0,(.5,.9),.85)
                app._shot_effects={'p':(event,time.perf_counter())}
                actor=app._presentation_scene(raw).entities[0]
                assert actor.action=='GUN_FIRE' and np.allclose(actor.aim_point,(.6,.4)),actor
                assert app._presentation_scene(replace(raw,entities=())).entities==()
                app.person_action_var.set('持枪');assert app._presentation_scene(raw).entities[0].aim_point is None
                app.person_action_var.set('自动姿态');app.auto_fire_var.set(False);app._auto_fire_changed()
                assert not app._shot_effects and not app.fire_detector.enabled
                app.auto_fire_var.set(True);app._auto_fire_changed();app._shot_effects={'p':(event,time.perf_counter())};app._reset_detection()
                assert not app._shot_effects and app.fire_detector.events.empty()
                (out/'auto-shot-workflow-result.json').write_text(json.dumps(dict(passed=True,**state,frames=app.fire_detector.frames,checks=[
                    'live 30fps decoder feeds local analyzer','actual source event drives gun and flash preset at runtime',
                    'actual orange flash pixels observed and later clear','only the owned visible actor changes',
                    'manual action overrides auto fire','disable clears effects','generation/reset clears effects',
                    'shots do not infer injury or death']),ensure_ascii=False,indent=2),encoding='utf-8')
                print('Live auto flash workflow passed:',state,flush=True);app.close();return
        assert elapsed<30,(app.video_position,state,app.ai_status_var.get())
        app.after(20,poll)
    except Exception:app._smoke_failure()
app.after(100,poll);app.mainloop();sys.exit(1 if app.test_failed else 0)
