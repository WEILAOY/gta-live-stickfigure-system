"""Minimal, explicitly manual material preview; no inferred combat events."""
import time,tkinter as tk
from dataclasses import replace
from tkinter import ttk
from .core import Scene,Entity,Horizon
from .assets import WEAPONS,COMBAT_VIEWS,FLASH_STAGES,flash_stage
from .rendering import SceneCanvas

def combat_scene(t,weapon='pistol',mirror=False,mode='full',yaw=35):
    fire_at=.8
    shooter='GUN_FIRE' if mode!='hit' and fire_at<=t<fire_at+.24 else 'GUN_HOLD'
    hit_at=1.0 if mode=='full' else .15
    elapsed=t-hit_at
    action='IDLE';phase=0
    if mode!='fire' and elapsed>=0:
        if elapsed<.28:action='HIT';phase=elapsed
        elif elapsed<.93:action='FALL';phase=elapsed-.28
        else:action='DOWN'
    def actor(name,x,action,phase):
        return Entity(name,'person',x,.85,bbox=(x-.064125,.25,x+.064125,.85),action=action,
                      action_time=phase,action_mirror=mirror,weapon=weapon,combat_yaw=yaw)
    x1,x2=(.73,.38) if mirror else (.27,.62)
    people=(actor('射击素材',x1,shooter,t-fire_at if shooter=='GUN_FIRE' else 0),actor('受击素材',x2,action,phase))
    return Scene(0,time.perf_counter(),1,t,people,True,notice='手动预设演示 · 非视频自动识别',frame_clipping=True,
                 horizon=Horizon(.85,.85,1,'素材演示地面'),contact_shadows=True)

class CombatPreview(tk.Toplevel):
    def __init__(self,parent,weapon_var,mirror_var,view_var=None):
        super().__init__(parent);self.title('极简战斗素材演示（手动）');self.geometry('900x600+130+80');self.minsize(680,460)
        self.weapon_var,self.mirror_var=weapon_var,mirror_var
        self.view_var=view_var if view_var is not None else tk.StringVar(value='斜后方')
        self.started=time.perf_counter();self.mode='full';self._timer=None
        ttk.Label(self,text='手动预设素材演示 · 不代表从视频自动识别开火或中弹',padding=10).pack(anchor='w')
        row=ttk.Frame(self);row.pack(fill='x',padx=10)
        ttk.Label(row,text='枪械：').pack(side='left')
        ttk.Combobox(row,textvariable=weapon_var,values=tuple(WEAPONS),state='readonly',width=7).pack(side='left')
        ttk.Combobox(row,textvariable=self.view_var,values=tuple(COMBAT_VIEWS),state='readonly',width=7).pack(side='left',padx=5)
        ttk.Checkbutton(row,text='左右镜像',variable=mirror_var).pack(side='left',padx=10)
        for label,mode in (('完整演示','full'),('只开火','fire'),('中弹倒地','hit')):
            ttk.Button(row,text=label,command=lambda m=mode:self.replay(m)).pack(side='left',padx=4)
        row=ttk.Frame(self);row.pack(fill='x',padx=10,pady=(5,0))
        self.flash_var=tk.StringVar(value='动画');self.fps_var=tk.StringVar(value='30')
        ttk.Label(row,text='火光素材：').pack(side='left')
        ttk.Combobox(row,textvariable=self.flash_var,values=('动画',*FLASH_STAGES),state='readonly',width=7).pack(side='left')
        ttk.Label(row,text='  预览 FPS：').pack(side='left')
        ttk.Combobox(row,textvariable=self.fps_var,values=('15','30'),state='readonly',width=4).pack(side='left')
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,padding=8).pack(anchor='w')
        self.canvas=SceneCanvas(self);self.canvas.pack(fill='both',expand=True,padx=10,pady=(0,10))
        self.protocol('WM_DELETE_WINDOW',self.close);self._tick()
    def replay(self,mode='full'):
        self.mode=mode;self.started=time.perf_counter();self.flash_var.set('动画')
    def _tick(self):
        t=time.perf_counter()-self.started
        scene=combat_scene(t,WEAPONS[self.weapon_var.get()],self.mirror_var.get(),self.mode,COMBAT_VIEWS[self.view_var.get()])
        selected=self.flash_var.get()
        if selected in FLASH_STAGES:
            phase=(.010,.050,.105)[FLASH_STAGES.index(selected)]
            scene=replace(scene,entities=(replace(scene.entities[0],action='GUN_FIRE',action_time=phase),))
        shooter=scene.entities[0];stage=flash_stage(shooter.action_time) if shooter.action=='GUN_FIRE' else None
        label='火光：'+(FLASH_STAGES[stage] if stage is not None else '无')
        self.status.set(('静态预设 · ' if selected!='动画' else '动作：')+' / '.join({'GUN_HOLD':'持枪','GUN_FIRE':'开火','IDLE':'站立','HIT':'中弹后仰','FALL':'侧倒','DOWN':'倒地保持'}[e.action] for e in scene.entities)+' · '+label)
        self.canvas.draw(scene,simulated=True)
        self._timer=self.after(round(1000/int(self.fps_var.get())),self._tick)
    def close(self):
        if self._timer is not None:self.after_cancel(self._timer)
        self.destroy()
