"""Actual manual preview: selectable materials, views, fps and one-shot clear."""
from pathlib import Path
import sys,time,json,tkinter as tk
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.combat import CombatPreview
from stickfigure.assets import COMBAT_VIEWS,FLASH_STAGES
base=Path(__file__).resolve().parents[1];out=base.parent/'21_枪口火光素材验证';out.mkdir(exist_ok=True)
root=tk.Tk();root.withdraw();weapon=tk.StringVar(value='手枪');mirror=tk.BooleanVar(value=False);view=tk.StringVar(value='斜后方')
preview=CombatPreview(root,weapon,mirror,view);failed=False
cases=[(w,v,s,fps) for w in ('手枪','长枪') for v in COMBAT_VIEWS for s in FLASH_STAGES for fps in (15,30)]
index=0;pulses=[]
def orange_pixels():
    count=0
    for photo,bounds in preview.canvas._layer_cache.values():
        if photo is None:continue
        data=photo.tk.call(str(photo),'data','-format','png');p=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_UNCHANGED)
        count+=int(np.sum((p[:,:,2]>180)&(p[:,:,1]>90)&(p[:,:,0]<180)))
    return count
def fail():
    global failed
    failed=True
    import traceback;traceback.print_exc();preview.close();root.destroy()
def select():
    global index
    try:
        if index==len(cases):one_shot(15);return
        w,v,s,fps=cases[index];weapon.set(w);view.set(v);preview.flash_var.set(s);preview.fps_var.set(str(fps))
        root.after(110,verify)
    except Exception:fail()
def verify():
    global index
    try:
        assert orange_pixels()>0,cases[index]
        assert '静态预设' in preview.status.get()
        assert not preview.canvas.find_withtag('shade-background')
        index+=1;select()
    except Exception:fail()
def one_shot(fps):
    try:
        preview.fps_var.set(str(fps));preview.replay('fire')
        assert preview.flash_var.get()=='动画'
        started=time.perf_counter();state={'last':False,'starts':0,'last_active':0}
        def poll():
            try:
                elapsed=time.perf_counter()-started
                # Skip the old static frame until the new timer tick renders.
                if elapsed>.20:
                    active=orange_pixels()>0
                    if active and not state['last']:state['starts']+=1
                    state['last']=active
                    if active:state['last_active']=elapsed
                if elapsed<1.3:root.after(10,poll);return
                assert state['starts']==1,(fps,state)
                assert not state['last'] and state['last_active']<1.15,(fps,state)
                pulses.append(dict(fps=fps,pulses=state['starts'],last_active=state['last_active']))
                if fps==15:one_shot(30);return
                preview.replay('hit');root.after(150,finish)
            except Exception:fail()
        poll()
    except Exception:fail()
def finish():
    try:
        assert orange_pixels()==0
        preview.close();assert not preview.winfo_exists()
        (out/'muzzle-workflow-result.json').write_text(json.dumps(dict(passed=True,static_cases=len(cases),single_shot=pulses,checks=[
            'two weapons three phases four views at both fps show actual colored flash pixels','static selection explicitly labelled manual',
            'replay restores animation mode','15fps and 30fps single shot each creates exactly one visible pulse',
            'single shot clears instead of leaving residual flash','hit-only mode has no muzzle flash','no full-canvas flash layer',
            'preview timer closes with its window']),ensure_ascii=False,indent=2),encoding='utf-8')
        root.destroy();print('Actual muzzle preview workflow passed.')
    except Exception:fail()
root.after(150,select);root.mainloop();sys.exit(1 if failed else 0)
