"""Open a labelled static flash material, ready for phase/view/fps review."""
from pathlib import Path
import sys,tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.combat import CombatPreview
root=tk.Tk();root.withdraw()
preview=CombatPreview(root,tk.StringVar(root,value='长枪'),tk.BooleanVar(root,value=False))
preview.flash_var.set('最亮')
def close():preview.close();root.destroy()
preview.protocol('WM_DELETE_WINDOW',close)
root.mainloop()
