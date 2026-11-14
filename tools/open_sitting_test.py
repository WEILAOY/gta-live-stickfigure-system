"""Open the reviewed seated frame near the user's 40-second sequence."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1]
source=base.parent/'03_测试素材/gta6_actions_test.mp4'
app=Application(base,initial_video=str(source),initial_position=40)
app.person_action_var.set('自动姿态');app.ai_var.set(True);app.model_profile_var.set('精细');app._model_changed()
app.mainloop()
