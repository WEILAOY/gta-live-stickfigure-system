"""Reference clip with the six-level comic shading defaults."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1]
source=Path(json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source'])
position=1400
if not source.exists():source=base.parent/'03_测试素材/gta6_shooting_test.mp4';position=.5
app=Application(base,initial_video=str(source),initial_position=position)
app.person_action_var.set('自动姿态');app.weapon_var.set('手枪');app.fps_var.set('30')
app.shadow_levels_var.set('6');app.shadow_density_var.set('中等');app.shadow_detail_var.set('标准')
app.shading_var.set(True);app.sky_var.set(True);app.shadow_mode_var.set('分区+投影');app._road_changed()
app.auto_fire_var.set(True);app._auto_fire_changed()
app.mainloop()
