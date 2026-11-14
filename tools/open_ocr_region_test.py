"""Open an explicit subtitle-ROI trial without overwriting saved settings."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1]
app=Application(base,initial_video=str(base.parent/'03_测试素材/gta6_actions_test.mp4'),initial_position=95)
app.text_var.set(True);app.text_rate_var.set('.5')
app.text_roi=(0,.72,1,1);app.text_scale=1.;app._text_changed()
app.mainloop()
