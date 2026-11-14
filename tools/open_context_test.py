"""Three supplied reference scenes, with portable short-clip fallbacks."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1]
mode=sys.argv[1] if len(sys.argv)>1 else 'heli'
position,fallback={'heli':(845,'gta6_helicopter_test.mp4'),'burning':(959,'gta6_burning_test.mp4'),'phone':(240,'gta6_phone_test.mp4')}[mode]
source=Path(json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source'])
if not source.exists():source=base.parent/'03_测试素材'/fallback;position=2 if mode=='heli' else 0
app=Application(base,initial_video=str(source),initial_position=position)
app.person_action_var.set('自动姿态');app.vehicle_model_var.set('自动类别');app.vehicle_view_var.set('自动估计')
app.action_captions_var.set(True);app.action_captions.reset();app.auto_fire_var.set(True);app._auto_fire_changed()
app.mainloop()
