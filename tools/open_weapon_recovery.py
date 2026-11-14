"""Open the two supplied firearm scenes with automatic holding restored."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1]
mode=sys.argv[1] if len(sys.argv)>1 else 'rifle'
position,fallback,offset={'rifle':(846.8,'gta6_helicopter_test.mp4',3.8),
                          'pistol':(1403.5,'gta6_shooting_test.mp4',4.0)}[mode]
source=Path(json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source'])
if not source.exists():source=base.parent/'03_测试素材'/fallback;position=offset
app=Application(base,initial_video=str(source),initial_position=position)
app.person_action_var.set('自动姿态');app.weapon_var.set('长枪' if mode=='rifle' else '手枪')
app.hud_assist_var.set(True);app.auto_weapon_var.set(True);app.auto_fire_var.set(True);app._hud_changed()
app.mainloop()
