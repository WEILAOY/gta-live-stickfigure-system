"""Open the downloaded full source, or the bundled GTA6 excerpt on another PC."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1]
info=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))
source=Path(info['source']);position=info.get('start_at',0)
if '--sample' in sys.argv or not source.exists():
    source=base.parent/'03_测试素材'/info['fallback'];position=info.get('sample_start',0)
app=Application(base,initial_video=str(source),initial_position=position)
app.mainloop()
