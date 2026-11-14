"""Tk control panel and independently capturable animation window."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import time
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog, ttk

from .core import DemoSource, RunState, Entity, Scene,Horizon
from .rendering import SceneCanvas
from .video import VideoPlayer
from .detection import DetectionWorker,MODEL_PROFILES,MAX_DOGS
from .assets import VEHICLE_VIEWS,VEHICLE_MODELS,MODEL_GALLERIES,ACTIONS,ACTION_GROUPS,WEAPONS,COMBAT_VIEWS,ANIMATED_ACTIONS
from .tracking import SceneSmoother
from .road import RoadWorker
from .scheduling import FrameCadence,analysis_max_age
from .ocr import TextWorker,normalize_roi
from .shooting import ShotDetector
from .captions import ActionCaptions

from .ui_shell import BG, PANEL, TEXT, MUTED
from .ui_theme import validated_theme
SOURCES = ("模拟演示（可运行）", "OBS 虚拟摄像机", "本地视频（可预览）")
DETECTION_RATES=(5,8,10,12,15,30)
ROAD_RATES=(2,3,5,8,30)


class QueueLogHandler(logging.Handler):
    def __init__(self, target):
        super().__init__()
        try:
            import cv2
            cv2.setNumThreads(2)
        except ImportError:pass
        self.target = target

    def emit(self, record):
        try:
            self.target.put_nowait(self.format(record))
        except queue.Full:
            pass


class Application(tk.Tk):
    def __init__(self, base: Path, smoke_test=False, initial_video=None, video_smoke=False, detection_smoke=False, initial_position=0,road_smoke=False,performance_smoke=False):
        super().__init__()
        self.base = base
        self.runtime = base / ("runtime/smoke" if smoke_test else "runtime")
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.test_failed = False
        self.smoke_test = smoke_test
        self.video = VideoPlayer()
        self.fire_detector=ShotDetector();self.video.frame_observer=self.fire_detector.submit
        self._shot_effects={};self._shot_count=0;self._unshown_shots=set()
        self.action_captions=ActionCaptions()
        self.video_info = None
        self.video_position = 0.0
        self.video_frame = None
        self.video_photo = None
        self._video_loading = False
        self._dragging_video = False
        self._live_deadline = 0.0
        self.video_smoke = video_smoke
        self.detection_smoke = detection_smoke
        self.detector = DetectionWorker(base/"models"/"yolox_nano.onnx")
        self.road_worker=RoadWorker(base/'models'/'segformer_b0_cityscapes.onnx')
        self.road_result=None
        self.text_worker=TextWorker(base/'models/ocr')
        self.text_result=None
        self.text_cadence=FrameCadence()
        self._last_road_submit=float('-inf')
        self.detect_cadence=FrameCadence()
        self.road_cadence=FrameCadence()
        self._detect_wall_times=[]
        self._road_wall_times=[]
        self.primary_id=None
        self._last_scene_revision=None
        self._render_pending_since=None
        self.smoother=SceneSmoother()
        self.road_smoke=road_smoke
        self.performance_smoke=performance_smoke
        self.detection_result = None
        self._last_detection_submit = float("-inf")
        self._accepted_detection_times = []
        self.state_value = RunState.STOPPED
        self.source = DemoSource()
        self.scene = None
        self.output = None
        self.output_canvas = None
        self.log_queue = queue.Queue(maxsize=1000)
        self.logger = logging.getLogger(f"stickfigure.{id(self)}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        file_handler = RotatingFileHandler(self.runtime / "app.log", maxBytes=2_000_000,
                                           backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", datefmt="%H:%M:%S")
        for handler in (file_handler, QueueLogHandler(self.log_queue)):
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.settings_path = self.runtime / "settings.json"
        settings = self._load_settings()
        self.theme_var = tk.StringVar(value=validated_theme(settings.get('theme')))
        self.auto_fire_var=tk.BooleanVar(value=not smoke_test and settings.get('auto_fire',True))
        self.action_captions_var=tk.BooleanVar(value=settings.get('action_captions',True))
        self.hud_assist_var=tk.BooleanVar(value=settings.get('hud_assist',True))
        self.auto_weapon_var=tk.BooleanVar(value=settings.get('auto_weapon',True))
        self.fire_detector.hud_enabled=self.hud_assist_var.get()
        self.detector.weapon_context_enabled=not self.hud_assist_var.get()
        self.shot_status_var=tk.StringVar(value='自动火光：只分析可见枪口闪光，等待画面')
        self.fire_detector.set_enabled(self.auto_fire_var.get())
        self.text_var=tk.BooleanVar(value=not smoke_test and settings.get('text_enabled',True))
        self.text_rate_var=tk.StringVar(value=str(settings.get('text_rate',1)))
        self.text_roi=settings.get('text_roi');self.text_scale=settings.get('text_scale',1.5)
        self.text_worker.configure(self.text_roi,self.text_scale)
        self.text_status_var=tk.StringVar(value='文字：等待画面')
        self.model_profile_var=tk.StringVar(value=settings.get('model_profile','精细'))
        self.down_recovery_var=tk.BooleanVar(value=not smoke_test and settings.get('down_recovery',True))
        self.detector.set_down_recovery(self.down_recovery_var.get())
        self.detector.set_model(base/'models'/MODEL_PROFILES[self.model_profile_var.get()])
        self.title("火柴人画面系统 · 工作室 0.34")
        self.configure(bg=BG)
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(1120, screen_w-65), min(740, screen_h-90)
        self.geometry(f"{width}x{height}+{max(15,(screen_w-width)//2)}+30")
        self.minsize(min(900, screen_w-65), min(620, screen_h-90))
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        self._style()
        self.source_var = tk.StringVar(value=SOURCES[0])
        self.device_var = tk.StringVar(value=settings.get("device", "UGREEN 45645"))
        self.video_var = tk.StringVar(value=settings.get("video", ""))
        self.fps_var = tk.StringVar(value=str(settings.get("fps",30)))
        self.npc_var = tk.StringVar(value=str(settings.get("npcs",3)))
        self.cars_var = tk.StringVar(value=str(settings.get("cars",3)))
        self.debug_var = tk.BooleanVar(value=settings.get("debug",False))
        self.status_var = tk.StringVar(value="已停止")
        self.hint_var = tk.StringVar(value="模拟演示；选择本地视频可运行真实人车检测。")
        self.fps_text = tk.StringVar(value="—")
        self.count_text = tk.StringVar(value="0")
        self.clock_text = tk.StringVar(value="00:00")
        self.primary_text = tk.StringVar(value="player")
        self.video_info_text = tk.StringVar(value="请选择本地视频。当前预览静音，音频播放后续接入。")
        self.video_time_text = tk.StringVar(value="00:00 / 00:00")
        self.video_scale_var = tk.DoubleVar(value=0)
        self.ai_var = tk.BooleanVar(value=detection_smoke or road_smoke or not smoke_test)
        self.ai_status_var = tk.StringVar(value="本地模型待加载")
        self.horizon_status_var = tk.StringVar(value="地平线：等待画面分析")
        self.vehicle_view_var=tk.StringVar(value=settings.get("vehicle_view","自动估计"))
        self.vehicle_model_var=tk.StringVar(value=settings.get('vehicle_model','自动类别'))
        self._vehicle_corrections={}
        self.person_action_var=tk.StringVar(value=settings.get("person_action","自动姿态"))
        self.skeleton_var=tk.BooleanVar(value=not smoke_test and settings.get('skeleton_binding',True))
        self.weapon_var=tk.StringVar(value=settings.get('weapon','手枪'))
        self.combat_mirror_var=tk.BooleanVar(value=settings.get('combat_mirror',False))
        self.combat_view_var=tk.StringVar(value=settings.get('combat_view','斜后方'))
        self.combat_preview=None
        self._manual_action_name=None;self._manual_action_start=0
        self.yaw_var=tk.DoubleVar(value=settings.get("yaw",0))
        self.pitch_var=tk.DoubleVar(value=settings.get("pitch",22))
        self.gallery_mode_var=tk.StringVar(value="车辆九视图")
        self._gallery_start=time.perf_counter()
        self.road_var=tk.BooleanVar(value=road_smoke or (not smoke_test and settings.get('road',True)))
        self.road_outline_var=tk.BooleanVar(value=settings.get('road_outline',True))
        self.buildings_var=tk.BooleanVar(value=road_smoke or (not smoke_test and settings.get('buildings',True)))
        self.shading_var=tk.BooleanVar(value=not smoke_test and settings.get('shading',True))
        self.color_var=tk.BooleanVar(value=not smoke_test and settings.get('color_enabled',False))
        self._shadow_setting_controls=[]
        self.sky_var=tk.BooleanVar(value=not smoke_test and settings.get('sky',True))
        self.shadow_mode_var=tk.StringVar(value=settings.get('shadow_mode','分区+投影'))
        self.shadow_levels_var=tk.StringVar(value=str(settings.get('shadow_levels',6)))
        self.shadow_density_var=tk.StringVar(value=settings.get('shadow_density','中等'))
        self.shadow_detail_var=tk.StringVar(value=settings.get('shadow_detail','标准'))
        self.road_status_var=tk.StringVar(value='驾驶路缘：等待画面分析')
        self.detect_rate_var=tk.StringVar(value=str(settings.get('detect_rate',10)))
        self.road_rate_var=tk.StringVar(value=str(settings.get('road_rate',5)))
        self.road_mode_var=tk.StringVar(value='始终检测' if road_smoke else settings.get('road_mode','驾驶自动'))
        self.binding_status_var=tk.StringVar(value='未绑定：点击动画中的目标，或从列表选择。')
        self.target_var=tk.StringVar(value='')
        self._target_options={}
        self._build_ui()
        self.open_output()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._last_tick = time.perf_counter()
        self._fps_start = self._last_tick
        self._frames = 0
        self._after_id = self.after(30, self._tick)
        self.logger.info("工作室 0.34 启动；现有关键点可驱动固定火柴人关节，低置信度回退预设。")
        self._refresh_controls()
        if initial_video:
            self.load_video(initial_video,initial_position)
        if performance_smoke:
            self._performance_started=time.perf_counter()
            self.after(100,self._performance_loaded)
        elif road_smoke:
            self._workflow_test_started=time.perf_counter()
            self.after(100,self._workflow_smoke_loaded)
        elif detection_smoke:
            self._detection_test_started = time.perf_counter()
            self.after(100,self._detection_smoke_loaded)
        elif video_smoke:
            self._video_test_started = time.perf_counter()
            self.after(100,self._video_smoke_loaded)
        elif smoke_test:
            self.after(100, self._run_smoke)

    def _style(self):
        from .ui_shell import apply_style
        apply_style(self)

    def _label(self, parent, text="", **kwargs):
        kwargs.setdefault("fg",self._ui_theme.colors['text'])
        return tk.Label(parent, text=text, bg=parent.cget("bg"), **kwargs)

    def _card(self, parent, title):
        card = tk.Frame(parent, bg=self._ui_theme.colors['panel'], padx=15, pady=10)
        card.pack(fill="x", padx=14, pady=(0,9))
        self._label(card,title,font=("Microsoft YaHei UI",11,"bold")).pack(anchor="w",pady=(0,8))
        return card

    def _build_ui(self):
        from .ui_shell import build_ui
        build_ui(self, SOURCES, DETECTION_RATES, ROAD_RATES, MODEL_PROFILES,
                 VEHICLE_VIEWS, VEHICLE_MODELS, ACTIONS, WEAPONS, COMBAT_VIEWS,
                 MODEL_GALLERIES, ACTION_GROUPS, SceneCanvas)

    def _load_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(data,dict):
                raise ValueError("settings must be an object")
            result = {}
            result['theme'] = validated_theme(data.get('theme'))
            for key,options in (("fps",(15,30,60)),("npcs",(0,1,2,3)),("cars",(1,2,3,4))):
                if type(data.get(key)) is int and data[key] in options:
                    result[key] = data[key]
            for key in ("device","video"):
                if isinstance(data.get(key),str):
                    result[key] = data[key][:4096]
            if data.get("vehicle_view") in VEHICLE_VIEWS:
                result["vehicle_view"]=data["vehicle_view"]
            if data.get('vehicle_model') in VEHICLE_MODELS:result['vehicle_model']=data['vehicle_model']
            if data.get("person_action") in ACTIONS:
                result["person_action"]=data["person_action"]
            if type(data.get('skeleton_binding')) is bool:result['skeleton_binding']=data['skeleton_binding']
            if data.get('weapon') in WEAPONS:result['weapon']=data['weapon']
            if type(data.get('combat_mirror')) is bool:result['combat_mirror']=data['combat_mirror']
            if data.get('combat_view') in COMBAT_VIEWS:result['combat_view']=data['combat_view']
            if type(data.get('shading')) is bool:result['shading']=data['shading']
            if type(data.get('color_enabled')) is bool:result['color_enabled']=data['color_enabled']
            if type(data.get('sky')) is bool:result['sky']=data['sky']
            if type(data.get('down_recovery')) is bool:result['down_recovery']=data['down_recovery']
            if type(data.get('auto_fire')) is bool:result['auto_fire']=data['auto_fire']
            if type(data.get('action_captions')) is bool:result['action_captions']=data['action_captions']
            for key in ('hud_assist','auto_weapon'):
                if type(data.get(key)) is bool:result[key]=data[key]
            if data.get('shadow_mode') in ('分区+投影','明暗分区','仅脚下投影'):result['shadow_mode']=data['shadow_mode']
            if type(data.get('shadow_levels')) is int and data['shadow_levels'] in (3,4,6):result['shadow_levels']=data['shadow_levels']
            if data.get('shadow_density') in ('疏','中等','密'):result['shadow_density']=data['shadow_density']
            if data.get('shadow_detail') in ('粗略','标准','精细'):result['shadow_detail']=data['shadow_detail']
            for key,upper in (("yaw",360),("pitch",85)):
                if isinstance(data.get(key),(int,float)) and 0<=data[key]<=upper:
                    result[key]=data[key]
            if type(data.get("debug")) is bool:
                result["debug"] = data["debug"]
            for key in ('road','road_outline','buildings'):
                if type(data.get(key)) is bool:
                    result[key]=data[key]
            for key,values in (('detect_rate',DETECTION_RATES),('road_rate',ROAD_RATES)):
                if type(data.get(key)) is int and data[key] in values:
                    result[key]=data[key]
            if data.get('road_mode') in ('驾驶自动','始终检测'):
                result['road_mode']=data['road_mode']
            if data.get('model_profile') in MODEL_PROFILES:
                result['model_profile']=data['model_profile']
            if type(data.get('text_enabled')) is bool:result['text_enabled']=data['text_enabled']
            if type(data.get('text_rate')) in (int,float) and data['text_rate'] in (.25,.5,1,2,3,5):result['text_rate']=data['text_rate']
            try:result['text_roi']=normalize_roi(data.get('text_roi'))
            except (ValueError,TypeError):pass
            if data.get('text_scale') in (1.,1.5):result['text_scale']=float(data['text_scale'])
            return result
        except FileNotFoundError:
            return {}
        except (ValueError,OSError) as exc:
            self.logger.warning("配置读取失败，使用默认值：%s",exc)
            return {}

    def _write_settings_patch(self, updates):
        """Merge only requested keys, preserving settings from newer versions."""
        try:
            original = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            original = {}
        if not isinstance(original, dict):
            raise ValueError('settings must be an object')
        original.update(updates)
        temp = self.settings_path.with_suffix('.tmp')
        temp.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.settings_path)

    def toggle_theme(self):
        value = 'light' if self.theme_var.get() == 'dark' else 'dark'
        self._ui_theme.apply(value)
        try:
            # Do not commit any pending recognition or playback edits here.
            self._write_settings_patch({'theme': value})
        except (OSError, ValueError) as exc:
            self.logger.error('主题偏好保存失败：%s', exc)

    def save_settings(self):
        data = dict(device=self.device_var.get(),video=self.video_var.get(),fps=int(self.fps_var.get()),
                    npcs=int(self.npc_var.get()),cars=int(self.cars_var.get()),debug=self.debug_var.get(),
                    vehicle_view=self.vehicle_view_var.get(),person_action=self.person_action_var.get(),
                    yaw=self.yaw_var.get(),pitch=self.pitch_var.get(),road=self.road_var.get(),road_outline=self.road_outline_var.get(),
                    detect_rate=int(self.detect_rate_var.get()),road_rate=int(self.road_rate_var.get()),road_mode=self.road_mode_var.get(),buildings=self.buildings_var.get(),model_profile=self.model_profile_var.get(),text_enabled=self.text_var.get(),text_rate=float(self.text_rate_var.get()))
        data.update(text_roi=self.text_roi,text_scale=self.text_scale)
        data.update(weapon=self.weapon_var.get(),combat_mirror=self.combat_mirror_var.get())
        data.update(combat_view=self.combat_view_var.get(),shading=self.shading_var.get(),shadow_mode=self.shadow_mode_var.get())
        data.update(color_enabled=self.color_var.get())
        data.update(skeleton_binding=self.skeleton_var.get())
        data.update(shadow_levels=int(self.shadow_levels_var.get()),shadow_density=self.shadow_density_var.get(),shadow_detail=self.shadow_detail_var.get())
        data.update(vehicle_model=self.vehicle_model_var.get(),sky=self.sky_var.get())
        data.update(down_recovery=self.down_recovery_var.get())
        data.update(auto_fire=self.auto_fire_var.get(),action_captions=self.action_captions_var.get())
        data.update(hud_assist=self.hud_assist_var.get(),auto_weapon=self.auto_weapon_var.get())
        data.update(theme=validated_theme(self.theme_var.get()))
        try:
            self._write_settings_patch(data)
            self.logger.info("配置已保存。下次启动仍默认模拟模式。")
        except (OSError, ValueError) as exc:
            self.logger.error("配置保存失败：%s",exc)

    def _skeleton_changed(self):
        # The existing detection already contains landmarks. A mode switch
        # only changes their presentation, including on a paused frame.
        self.save_settings()

    def _source_changed(self, event=None):
        self.video.cancel()
        self._reset_detection()
        self._video_loading = False
        self.scene = None
        self.state_value = RunState.STOPPED
        if self.source_var.get() == SOURCES[0]:
            hint = "模拟场景；真实人车检测请切换本地视频。"
            self.primary_text.set(self.source.primary_id)
            self.count_text.set("0")
        elif self.source_var.get() == SOURCES[1]:
            self.video_info = None
            self.video_frame = None
            self.video_position = 0.0
            hint = "在 OBS 启动虚拟摄像机，再点击连接 OBS。"
            self.video_info_text.set(hint)
            self._update_video_time()
            self._draw_video()
        else:
            if self.video_var.get():
                self.load_video(self.video_var.get())
                return
            hint = "请选择本地视频；解码在后台运行，当前为静音预览。"
        self.hint_var.set(hint)
        self._refresh_controls()

    def choose_video(self):
        if self.state_value != RunState.STOPPED:
            self.logger.info("请先停止播放或演示，再更换视频。")
            return
        path = filedialog.askopenfilename(parent=self,title="选择本地测试视频",
                                          filetypes=[("视频文件","*.mp4 *.mkv *.mov *.avi"),("所有文件","*.*")])
        if path:
            self.load_video(path)

    @staticmethod
    def _time_label(seconds):
        seconds = max(0,int(seconds))
        return f"{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}" if seconds>=3600 else f"{seconds//60:02}:{seconds%60:02}"

    def load_video(self,path,position=0):
        self._reset_detection()
        self.source.stop()
        self.scene = None
        self.state_value = RunState.STOPPED
        self.source_var.set(SOURCES[2])
        self.video_var.set(str(Path(path).resolve()))
        self.video_info = None
        self.video_frame = None
        self.video_position = max(0,float(position))
        self._video_loading = True
        self.count_text.set("—")
        self.primary_text.set("未绑定")
        self.video_info_text.set("正在后台读取视频信息与首帧……")
        self.hint_var.set("正在读取："+Path(path).name)
        self.video.request(path,self.video_position,False)
        self.tabs.select(self.preview_tab)
        self._refresh_controls()
        self._draw_video()
        self.logger.info("加载本地视频：%s",Path(path).name)

    def _update_video_time(self):
        if self.source_var.get()==SOURCES[1]:
            self.video_time_text.set(f"实时 · {self._time_label(self.video_position)}")
            return
        duration = self.video_info.duration if self.video_info else 0
        position = duration if self.state_value==RunState.ENDED else self.video_position
        self.video_time_text.set(f"{self._time_label(position)} / {self._time_label(duration)}")
        self.clock_text.set(self._time_label(position))
        if not self._dragging_video:
            self.video_scale_var.set(position)

    def _draw_video(self):
        if self.tabs.select()!=str(self.preview_tab):return
        canvas = self.video_canvas
        canvas.delete("all")
        width,height = max(2,canvas.winfo_width()),max(2,canvas.winfo_height())
        if self.video_frame is None:
            self.video_photo = None
            palette = self._ui_theme.colors
            center_x, center_y = width/2, height/2
            canvas.create_rectangle(center_x-25,center_y-47,center_x+25,center_y-12,
                                    outline=palette['placeholder'],width=2)
            canvas.create_polygon(center_x-5,center_y-39,center_x-5,center_y-20,
                                  center_x+10,center_y-29,fill=palette['placeholder'],outline="")
            simulated = self.source_var.get() == SOURCES[0]
            running = self.state_value == RunState.RUNNING
            title = ("模拟演示运行中" if running else "模拟演示已准备好") if simulated else "等待输入画面"
            hint = ("动画正在独立输出窗口中显示" if running else "点击开始演示，在独立输出窗口查看动画") if simulated else "选择本地视频，或启动 OBS 虚拟摄像机后连接"
            canvas.create_text(center_x,center_y+12,text=title,fill=palette['text'],font=("Microsoft YaHei UI",13,"bold"))
            canvas.create_text(center_x,center_y+42,text=hint,fill=palette['muted'],font=("Microsoft YaHei UI",9))
            return
        frame = self.video_frame
        key=(frame.generation,frame.timestamp,width,height)
        if self.video_photo is None or getattr(self,'_preview_photo_key',None)!=key:
            ratio = min(1,width/frame.width,height/frame.height)
            if ratio<.999:
                try:
                    import cv2
                    import numpy as np
                    rgb = np.frombuffer(frame.pixels,dtype=np.uint8).reshape(frame.height,frame.width,3)
                    dw,dh = max(1,round(frame.width*ratio)),max(1,round(frame.height*ratio))
                    resized = cv2.resize(rgb,(dw,dh),interpolation=cv2.INTER_AREA)
                    ppm = f"P6\n{dw} {dh}\n255\n".encode("ascii")+resized.tobytes()
                    self.video_photo = tk.PhotoImage(data=ppm,format="PPM")
                except ImportError:
                    photo = tk.PhotoImage(data=frame.ppm(),format="PPM")
                    self.video_photo = photo.subsample(max(1,int(1/ratio+.999)))
            else:
                self.video_photo = tk.PhotoImage(data=frame.ppm(),format="PPM")
            self._preview_photo_key=key
        canvas.create_image(width/2,height/2,image=self.video_photo)
        dw,dh=self.video_photo.width(),self.video_photo.height()
        left,top=(width-dw)/2,(height-dh)/2
        if self._buildings_is_current():
            for outline in self.road_result.buildings.outlines:
                coords=[v for x,y in outline for v in (left+x*dw,top+y*dh)]
                canvas.create_line(coords,fill='#bfadfa',width=1.8,tags='building-preview')
        if self._road_display_current():
            for edge,color in ((self.road_result.geometry.left_edge,'#4bd99d'),(self.road_result.geometry.right_edge,'#f2bb62')):
                if len(edge)>=2:
                    coords=[value for x,y in edge for value in (left+x*dw,top+y*dh)]
                    canvas.create_line(coords,fill=color,width=2.5,smooth=True,tags='road-preview')
        if self.debug_var.get() and self._detection_is_current():
            dw,dh = self.video_photo.width(),self.video_photo.height()
            left,top = (width-dw)/2,(height-dh)/2
            for detection in self.detection_result.detections:
                x1,y1,x2,y2 = detection.box
                a,b,c,d = left+x1*dw,top+y1*dh,left+x2*dw,top+y2*dh
                canvas.create_rectangle(a,b,c,d,outline=self._ui_theme.colors['accent'],width=2,tags="detection-box")
                canvas.create_text(a,max(top+12,b-3),anchor="sw",fill=self._ui_theme.colors['accent'],
                    text=f"{detection.label} {detection.confidence:.0%}",font=("Segoe UI",9))
            horizon=self.detection_result.horizon
            if horizon:
                canvas.create_line(left,top+horizon.left*dh,left+dw,top+horizon.right*dh,
                                   fill="#eeac52",width=2,dash=() if horizon.confidence>=.3 else (5,4),tags="horizon-guide")

    def seek_video(self,position):
        self._dragging_video = False
        if self.source_var.get()!=SOURCES[2] or self.video_info is None:
            return
        position = min(max(0,float(position)),max(0,self.video_info.duration-.05))
        self._reset_detection()
        playing = self.state_value==RunState.RUNNING
        if self.state_value in (RunState.ENDED,RunState.ERROR):
            self.state_value = RunState.PAUSED
        self.video_position = position
        self.video_frame = None
        self.video.request(self.video_var.get(),position,playing)
        self._update_video_time()
        self._draw_video()
        self._refresh_controls()
        self.logger.info("跳转到 %s；旧帧已失效。",self._time_label(position))

    def _poll_video(self):
        for _ in range(32):
            try:
                generation,kind,payload = self.video.events.get_nowait()
            except queue.Empty:
                break
            if generation!=self.video.generation or self.source_var.get() not in SOURCES[1:]:
                continue
            if kind=="loaded":
                self.video_info = payload
                self._video_loading = False
                if self.source_var.get()==SOURCES[1]:
                    self.video_info_text.set(f"OBS Virtual Camera · {payload.width} × {payload.height} · 30 FPS 输入上限")
                    self.hint_var.set("OBS 实时画面已接入。")
                    self._refresh_controls()
                    continue
                audio = "含音轨，当前静音预览" if payload.has_audio else "无音轨"
                self.video_info_text.set(f"{payload.width} × {payload.height}  ·  {payload.fps:.2f} FPS  ·  "
                                         f"{self._time_label(payload.duration)}\n{audio}\n{Path(payload.path).name}")
                self.hint_var.set("本地视频已就绪；点击播放视频开始，可拖动时间轴跳转。")
                self.video_scale.configure(to=payload.duration)
                self._refresh_controls()
                self._update_video_time()
            elif kind=="ended":
                self.state_value = RunState.ENDED
                self.video_position = payload
                self.fps_text.set("—")
                self._update_video_time()
                self._refresh_controls()
                self.logger.info("视频播放结束，可重新开始。")
            elif kind=="error":
                self._video_error(payload)
        latest = None
        for _ in range(2):
            try:
                frame = self.video.frames.get_nowait()
                if frame.generation==self.video.generation and self.source_var.get() in SOURCES[1:]:
                    latest = frame
            except queue.Empty:
                break
        if latest is not None:
            if self.source_var.get()==SOURCES[1]:
                self._live_deadline = time.perf_counter()+4
            self.video_frame = latest
            self.video_position = latest.timestamp
            if self.text_var.get() and self.text_cadence.ready(latest.timestamp,float(self.text_rate_var.get())):
                self.text_worker.submit(latest)
            if self.ai_var.get() and self.detect_cadence.ready(latest.timestamp,float(self.detect_rate_var.get())):
                self._last_detection_submit = latest.timestamp
                self.detector.submit(latest)
            if self._environment_enabled() and self.road_cadence.ready(latest.timestamp,float(self.road_rate_var.get())):
                self._last_road_submit=latest.timestamp
                self.road_worker.submit(latest,self._shadow_exclusions(),self._shadow_options())
            self._draw_video()
            self._update_video_time()
            if self.state_value==RunState.RUNNING:
                self._frames += 1
                now = time.perf_counter()
                if now-self._fps_start>=1:
                    self.fps_text.set(f"{self._frames/(now-self._fps_start):.1f}")
                    self._frames = 0
                    self._fps_start = now

        elif self.source_var.get()==SOURCES[1] and self.state_value==RunState.RUNNING:
            if time.perf_counter()>self._live_deadline:
                self._video_error("OBS 虚拟摄像机未送达画面。请确认 OBS 已开启虚拟摄像机，再重新连接。")

    def _video_error(self,message):
        self._video_loading = False
        self.video.cancel()
        self._reset_detection()
        self.state_value = RunState.ERROR
        self.video_frame = None
        self.video_info_text.set("读取失败："+message)
        self.hint_var.set(message)
        self.fps_text.set("—")
        self._draw_video()
        self._refresh_controls()
        self.logger.error("画面输入错误：%s",message)

    def _reset_detection(self,preserve_binding=False,reset_road=True):
        self.fire_detector.reset();self._shot_effects.clear();self._unshown_shots.clear();self._shot_count=0
        self._render_pending_since=None
        self._reset_text()
        self.detector.reset(preserve_tracking=preserve_binding)
        self.smoother.reset()
        if not preserve_binding:
            self.action_captions.reset()
            self._manual_action_name=None
            self.clear_primary(log=False)
            self._last_scene_revision=None
            self._target_options={}
            self.target_var.set('')
            self.target_combo.configure(values=())
        if reset_road:
            self._reset_road()
        self.detection_result = None
        self._last_detection_submit = float("-inf")
        self.detect_cadence.reset()
        self._detect_wall_times=[]
        self._accepted_detection_times = []
        if self.source_var.get() in SOURCES[1:]:
            self.scene = None
            self.count_text.set("—")
        self.ai_status_var.set(f"等待视频帧 · 上限 {self.detect_rate_var.get()}Hz" if self.ai_var.get() else "人车检测已关闭")
        self.horizon_status_var.set("地平线：等待画面分析")

    def _detection_changed(self):
        self._reset_detection(reset_road=False)
        if self.text_var.get() and self.video_frame and self.source_var.get() in SOURCES[1:]:
            self.text_cadence.ready(self.video_frame.timestamp,float(self.text_rate_var.get()))
            self.text_worker.submit(self.video_frame)
        if self.ai_var.get() and self.video_frame and self.source_var.get() in SOURCES[1:]:
            self.detect_cadence.ready(self.video_frame.timestamp,float(self.detect_rate_var.get()))
            self._last_detection_submit = self.video_frame.timestamp
            self.detector.submit(self.video_frame)
        self._draw_video()
        self.logger.info("人车检测%s。","开启" if self.ai_var.get() else "关闭")

    def _model_changed(self,event=None):
        profile=self.model_profile_var.get()
        self.detector.set_model(self.base/'models'/MODEL_PROFILES[profile])
        self._detection_changed()
        self.logger.info('识别档位：%s；目标 Hz 为上限，实际速度见识别设置中的分析状态。',profile)

    def _down_recovery_changed(self):
        self.detector.set_down_recovery(self.down_recovery_var.get())
        self._detection_changed()
        self.logger.info('躺卧补检%s；增加±90°人物检测，实际频率见识别设置中的分析状态。','开启' if self.down_recovery_var.get() else '关闭')

    def _auto_fire_changed(self):
        self.fire_detector.set_enabled(self.auto_fire_var.get());self._shot_effects.clear();self._unshown_shots.clear();self._shot_count=0
        if self.detection_result and self._detection_is_current():
            r=self.detection_result;self.fire_detector.set_targets(r.detections,r.generation,r.timestamp)
        if self.video_frame and self.hud_assist_var.get():self.fire_detector.submit(self.video_frame)
        self.shot_status_var.set('自动火光：等待可见枪口闪光' if self.auto_fire_var.get() else '自动火光已关闭')

    def _hud_changed(self):
        self.fire_detector.hud_enabled=self.hud_assist_var.get();self.detector.weapon_context_enabled=not self.hud_assist_var.get();self._auto_fire_changed()

    def _poll_shots(self):
        if self.fire_detector.last_error:
            self.auto_fire_var.set(False);self.shot_status_var.set('自动火光不可用：'+self.fire_detector.last_error[:70])
            self.fire_detector.last_error='';self._shot_effects.clear();self._unshown_shots.clear()
        if not self.auto_fire_var.get():return
        now=time.perf_counter()
        for _ in range(12):
            try:event=self.fire_detector.events.get_nowait()
            except queue.Empty:break
            freshness=min(1.2,max(.65,self._detection_max_age(self.detection_result))) if self.detection_result else .65
            if self.source_var.get() not in SOURCES[1:] or event.generation!=self.video.generation or abs(event.timestamp-self.video_position)>freshness:continue
            self._shot_effects[event.owner]=(event,now);self._shot_count+=1
            self._unshown_shots.add(event.owner)
        self._shot_effects={k:v for k,v in self._shot_effects.items() if now-v[1]<(1.2 if k in self._unshown_shots else .6)}
        self._unshown_shots.intersection_update(self._shot_effects)
        hud=self.fire_detector.hud_observation
        if hud and hud.weapon=='molotov':
            owner=self.fire_detector.foreground_id
            self._shot_effects.pop(owner,None);self._unshown_shots.discard(owner)
        context={'rifle':'长枪','pistol':'手枪','molotov':'非枪械'}.get(hud.weapon,'') if hud else ''
        self.shot_status_var.set(f'自动火光：开火候选 {self._shot_count} 次 · '+('HUD识别 '+context if context else '画面枪械核验'))

    def _mark_shots_presented(self,scene):
        if scene is None:return
        now=time.perf_counter()
        for actor in scene.entities:
            if actor.track_id in self._unshown_shots and actor.action=='GUN_FIRE' and actor.aim_point is not None:
                effect=self._shot_effects.get(actor.track_id)
                if effect:self._shot_effects[actor.track_id]=(effect[0],max(effect[1],now-.05))
                self._unshown_shots.discard(actor.track_id)

    def _detection_max_age(self,result):
        return analysis_max_age(self.detect_rate_var.get(),result.total_ms,self._detect_wall_times)

    def _detection_is_current(self):
        result = self.detection_result
        return bool(self.ai_var.get() and result and self.video_frame
                    and self.source_var.get() in SOURCES[1:] and self.state_value!=RunState.ERROR
                    and result.epoch==self.detector.epoch and result.generation==self.video.generation
                    and abs(self.video_position-result.timestamp)<=self._detection_max_age(result))

    def _poll_detection(self):
        for _ in range(8):
            try:
                epoch,kind,payload = self.detector.events.get_nowait()
            except queue.Empty:
                break
            if epoch!=self.detector.epoch or not self.ai_var.get():
                continue
            if kind=="loading":
                self.ai_status_var.set(payload)
            elif kind=="error":
                self.ai_var.set(False)
                self._reset_detection()
                self.ai_status_var.set("检测不可用："+payload[:100])
                self.logger.error("检测已降级为普通预览：%s",payload)
                self._draw_video()
        for _ in range(2):
            try:
                result = self.detector.results.get_nowait()
            except queue.Empty:
                break
            if (not self.ai_var.get() or self.source_var.get() not in SOURCES[1:]
                    or result.epoch!=self.detector.epoch or result.generation!=self.video.generation
                    or abs(self.video_position-result.timestamp)>self._detection_max_age(result)):
                continue
            self.detection_result = result
            if self._last_scene_revision is not None and self._last_scene_revision!=result.scene_revision:
                self.clear_primary(log=False)
                self.smoother.reset()
                self._reset_road()
                self._reset_text()
                self.fire_detector.reset();self._shot_effects.clear();self._unshown_shots.clear()
                if self.text_var.get() and self.video_frame:self.text_worker.submit(self.video_frame)
                if self._environment_enabled() and self.video_frame:
                    self.road_cadence.ready(self.video_frame.timestamp,float(self.road_rate_var.get()))
                    self._last_road_submit=self.video_frame.timestamp
                    self.road_worker.submit(self.video_frame,self._shadow_exclusions(),self._shadow_options())
                self.logger.info('场景切换：旧主角绑定与道路结果已清除。')
            self._last_scene_revision=result.scene_revision
            self.fire_detector.set_targets(result.detections,result.generation,result.timestamp)
            self._accepted_detection_times.append(result.timestamp)
            self._accepted_detection_times = self._accepted_detection_times[-50:]
            observed=[d for d in result.detections if not d.predicted and d.confirmed]
            people = sum(d.label=="person" for d in observed)
            dogs = sum(d.label=='dog' for d in observed)
            poses=sum(bool(d.pose) for d in result.detections)
            self._detect_wall_times=(self._detect_wall_times+[time.perf_counter()])[-30:]
            actual=self._rate_text(self._detect_wall_times)
            backend='GPU' if result.backend.startswith('GPU') else 'CPU'
            self.ai_status_var.set(f"检测 {actual} / 目标 {self.detect_rate_var.get()}Hz · {backend} {result.total_ms:.0f}ms · 人 {people}/车 {len(observed)-people-dogs}/狗 {dogs}")
            target_types={'person':'人物','dog':'狗'}
            self._target_options={f'{d.track_id} · {target_types.get(d.label,"车辆")}':d.track_id for d in observed}
            self.target_combo.configure(values=tuple(self._target_options))
            if self.primary_id:
                match=next((d for d in result.detections if d.track_id==self.primary_id),None)
                if match and not match.predicted:
                    self.binding_status_var.set(f'已绑定 {self.primary_id}；点击其他目标可更换。')
                elif match:
                    self.binding_status_var.set(f'{self.primary_id} 暂被遮挡，保留身份 {match.missing_age:.1f} 秒。')
                else:
                    self.binding_status_var.set(f'{self.primary_id} 已丢失；不会自动换人，可重新绑定。')
            if result.horizon:
                horizon=result.horizon
                self.horizon_status_var.set(f"地平线：{horizon.method} · 高度 {(horizon.left+horizon.right)/2:.0%} · 评分 {horizon.confidence:.0%}")
            self._draw_video()
        if self.source_var.get() not in SOURCES[1:]:
            return
        if not self._detection_is_current():
            self.scene = None
            if self.ai_var.get():
                self.count_text.set("—")
            return
        result = self.detection_result
        entities = []
        visible=[d for d in result.detections if not d.predicted and d.confirmed]
        visible.sort(key=lambda d:(d.track_id!=self.primary_id,d.predicted,-d.confidence))
        actors=[d for d in visible if d.label!='dog'][:12]
        actors.extend([d for d in visible if d.label=='dog'][:MAX_DOGS])
        for i,detection in enumerate(actors):
            x1,y1,x2,y2 = detection.box
            kind=detection.label if detection.label in ('person','dog') else 'car'
            entities.append(Entity(detection.track_id or f"检测{i+1}",kind,
                                   (x1+x2)/2,y2,action=detection.action,action_mirror=detection.action_mirror,confidence=detection.confidence,bbox=detection.box,
                                   seated=detection.seated,seat_mirror=detection.seat_mirror,pose=detection.pose,yaw=detection.yaw,pitch=22,view_confidence=detection.view_confidence,
                                   primary=detection.track_id==self.primary_id,predicted=detection.predicted,missing_age=detection.missing_age,
                                   velocity=detection.velocity,sample_time=result.timestamp,render_bbox=detection.render_box,
                                   vehicle_type={'motorcycle':'motorcycle','truck':'truck','bus':'truck','boat':'boat','helicopter':'helicopter'}.get(detection.label,'car'),posture_fit=detection.action=='DOWN'))
        self.scene = Scene(round(result.timestamp*30),time.perf_counter(),result.generation*1000000+result.scene_revision,self.video_position,
                           tuple(entities),False,"",result.horizon)
        self.count_text.set(str(sum(not e.predicted for e in entities)))

    def _reset_road(self):
        self.road_worker.reset()
        self.road_result=None
        self._last_road_submit=float('-inf')
        self.road_cadence.reset()
        self._road_wall_times=[]
        self.road_status_var.set(f'环境：等待画面 · 目标 {self.road_rate_var.get()}Hz' if self._environment_enabled() else '环境分析已关闭')

    def _road_changed(self):
        self._reset_road()
        if (self._environment_enabled() and self.video_frame and self.source_var.get() in SOURCES[1:]
                and self.video_frame.generation==self.video.generation):
            self.road_cadence.ready(self.video_frame.timestamp,float(self.road_rate_var.get()))
            self._last_road_submit=self.video_frame.timestamp
            self.road_worker.submit(self.video_frame,self._shadow_exclusions(),self._shadow_options())
        self._draw_video()

    def open_shadow_settings(self):
        window=getattr(self,'shadow_window',None)
        if window is not None and window.winfo_exists():window.lift();return
        self.shadow_window=window=tk.Toplevel(self)
        window.title('背景颜色与阴影设置');window.configure(bg=PANEL);window.resizable(False,False)
        ttk.Checkbutton(window,text='颜色代替阴影',variable=self.color_var,command=self._color_changed).pack(anchor='w',padx=18,pady=(12,0))
        self._shadow_setting_controls=[]
        for label,variable,values in (('阴影层次',self.shadow_levels_var,(3,4,6)),
                ('纹理密度',self.shadow_density_var,('疏','中等','密')),
                ('分区精度',self.shadow_detail_var,('粗略','标准','精细'))):
            row=tk.Frame(window,bg=PANEL);row.pack(fill='x',padx=18,pady=(10,0))
            self._label(row,label,width=12,anchor='w',fg=MUTED).pack(side='left')
            combo=ttk.Combobox(row,textvariable=variable,values=values,state='readonly',width=12)
            combo.pack(side='left');combo.bind('<<ComboboxSelected>>',self._shadow_options_changed)
            if label!='分区精度':self._shadow_setting_controls.append(combo)
        self._sync_background_controls()
        self._label(window,'颜色开启时替代排线和脚下投影；分区精度对两种模式均有效。',fg=MUTED,wraplength=320,justify='left').pack(padx=18,pady=10)
        ttk.Button(window,text='保存配置',command=self.save_settings).pack(pady=(0,12))
        self._ui_theme.refresh(window)

    def _shadow_options(self):
        return (int(self.shadow_levels_var.get()),self.shadow_detail_var.get(),self.color_var.get())

    def _sync_background_controls(self):
        colored=self.color_var.get()
        for name in ('shading_checkbox','sky_checkbox'):
            widget=getattr(self,name,None)
            if widget is not None:widget.configure(state='disabled' if colored else 'normal')
        widget=getattr(self,'shadow_mode_combo',None)
        if widget is not None:widget.configure(state='disabled' if colored else 'readonly')
        for widget in self._shadow_setting_controls:
            if widget.winfo_exists():widget.configure(state='disabled' if colored else 'readonly')

    def _color_changed(self):
        self._sync_background_controls()
        self._road_changed()
        self.save_settings()

    def _shadow_options_changed(self,event=None):
        self._road_changed()

    def _environment_enabled(self):
        return self.color_var.get() or self.road_var.get() or self.buildings_var.get() or self.sky_var.get() or (self.shading_var.get() and self.shadow_mode_var.get()!='仅脚下投影')

    def _shadow_exclusions(self):
        boxes=[]
        result=self.detection_result
        if result and self.video_frame and result.generation==self.video.generation and abs(result.timestamp-self.video_frame.timestamp)<.25:
            boxes.extend(d.box for d in result.detections if not d.predicted)
        if self._text_is_current():boxes.extend(r.box for r in self.text_result.regions)
        return tuple(boxes)

    def _environment_is_current(self):
        result=self.road_result
        return bool(self._environment_enabled() and result and self.video_frame and self.source_var.get() in SOURCES[1:]
                    and self.state_value!=RunState.ERROR and result.epoch==self.road_worker.epoch
                    and result.generation==self.video.generation and abs(self.video_position-result.timestamp)<=self._road_max_age())

    def _road_is_current(self):
        return self.road_var.get() and self._environment_is_current()

    def _buildings_is_current(self):
        return bool(self.buildings_var.get() and self._environment_is_current() and self.road_result.buildings)

    def _road_max_age(self,result=None):
        result=result or self.road_result
        return analysis_max_age(self.road_rate_var.get(),result.total_ms if result else 0,self._road_wall_times)

    def _road_display_current(self):
        if not self._road_is_current():
            return False
        geometry=self.road_result.geometry
        if not (geometry.left_edge or geometry.right_edge):
            return False
        bound_car=self.primary_id and self.scene and any(e.track_id==self.primary_id and e.kind=='car' for e in self.scene.entities)
        return bool(self.road_mode_var.get()=='始终检测' or geometry.driving_view or bound_car)

    @staticmethod
    def _rate_text(samples):
        if len(samples)<4 or samples[-1]-samples[0]<.3:
            return '采样中'
        return f'{(len(samples)-1)/(samples[-1]-samples[0]):.1f}Hz'

    def _rates_changed(self,event=None):
        self.detect_cadence.reset()
        self.road_cadence.reset()
        self._detect_wall_times=[]
        self._road_wall_times=[]
        self.logger.info('检测目标频率：人车 %sHz，环境（路缘/建筑/明暗）%sHz。',self.detect_rate_var.get(),self.road_rate_var.get())

    def _poll_road(self):
        for _ in range(4):
            try:
                epoch,message=self.road_worker.events.get_nowait()
            except queue.Empty:
                break
            if epoch==self.road_worker.epoch:
                self.road_var.set(False)
                self.buildings_var.set(False)
                self.shading_var.set(False)
                self.color_var.set(False)
                self.sky_var.set(False)
                self._sync_background_controls()
                self._reset_road()
                self.road_status_var.set('环境分析不可用：'+message[:80])
                self.logger.error('道路及建筑分析已关闭，人车功能继续：%s',message)
        for _ in range(2):
            try:
                result=self.road_worker.results.get_nowait()
            except queue.Empty:
                break
            if not self._environment_enabled() or result.epoch!=self.road_worker.epoch or result.generation!=self.video.generation or abs(self.video_position-result.timestamp)>self._road_max_age(result):
                continue
            self.road_result=result
            geometry=result.geometry
            self._road_wall_times=(self._road_wall_times+[time.perf_counter()])[-20:]
            actual=self._rate_text(self._road_wall_times)
            count=len(result.buildings.outlines) if result.buildings and self.buildings_var.get() else 0
            shades=sum(r.tone!=3 for r in result.shading or ()) if self.shading_var.get() and self.shadow_mode_var.get()!='仅脚下投影' else 0
            skies=sum(r.tone==3 for r in result.shading or ()) if self.sky_var.get() else 0
            appearance=f'颜色{len(result.colors or ())}区' if self.color_var.get() else f'阴影{shades}区/天空{skies}区'
            self.road_status_var.set(f'环境 {actual} / 目标 {self.road_rate_var.get()}Hz · {result.total_ms:.0f}ms · {geometry.method if self.road_var.get() else "路缘关闭"} · 建筑 {count}组 · {appearance}')
            self._draw_video()

    def _view_changed(self,event=None):
        name=self.vehicle_view_var.get()
        if name!="自由角度" and VEHICLE_VIEWS.get(name):
            yaw,pitch=VEHICLE_VIEWS[name]
            self.yaw_var.set(yaw)
            self.pitch_var.set(pitch)

    def _free_view_changed(self,value=None):
        self.vehicle_view_var.set("自由角度")
        self.gallery_mode_var.set("单车旋转")

    def _restore_automatic(self):
        self.vehicle_view_var.set("自动估计")
        self.vehicle_model_var.set('自动类别')
        self._vehicle_corrections.clear()
        self.person_action_var.set("自动姿态")
        self.logger.info("已恢复自动车辆视角估计与人物姿态。")

    def _gallery_clicked(self,ident):
        if ident in VEHICLE_VIEWS:
            kind=MODEL_GALLERIES.get(self.gallery_mode_var.get())
            material=next((name for name,value in VEHICLE_MODELS.items() if value==kind),None) if kind else None
            if material:self.vehicle_model_var.set(material)
            self.vehicle_view_var.set(ident)
            self._view_changed()
        elif ident in ACTIONS:
            self.person_action_var.set(ident)
            self._manual_action_name=None

    def open_combat_preview(self):
        if self.combat_preview and self.combat_preview.winfo_exists():
            self.combat_preview.lift();self.combat_preview.replay();return
        from .combat import CombatPreview
        self.combat_preview=CombatPreview(self,self.weapon_var,self.combat_mirror_var,self.combat_view_var)
        self._ui_theme.refresh(self.combat_preview)

    def open_text_region(self):
        if not self.video_frame:
            self.text_status_var.set('请先加载视频，再划定文字识别范围');return
        existing=getattr(self,'text_region_dialog',None)
        if existing is not None and existing.winfo_exists():existing.lift();return
        from .ocr_region import OcrRegionDialog
        self.text_region_dialog=OcrRegionDialog(self,self.video_frame,self.text_roi,self.text_scale,self._apply_text_region)
        self._ui_theme.refresh(self.text_region_dialog)

    def _apply_text_region(self,roi,scale):
        self.text_roi=normalize_roi(roi);self.text_scale=scale
        self._text_changed();self.save_settings()
        self.logger.info('OCR范围：%s；缩放 %s',self.text_roi or '全画面',scale)

    def _reset_text(self):
        self.text_worker.configure(self.text_roi,self.text_scale);self.text_result=None;self.text_cadence.reset()
        self.text_status_var.set('文字：等待识别' if self.text_var.get() else '文字识别已关闭')

    def _text_changed(self,event=None):
        self._reset_text()
        if self.text_var.get() and self.video_frame and self.source_var.get() in SOURCES[1:]:
            self.text_cadence.ready(self.video_frame.timestamp,float(self.text_rate_var.get()))
            self.text_worker.submit(self.video_frame)

    def _text_is_current(self):
        r=self.text_result
        return bool(self.text_var.get() and r and self.video_frame and self.source_var.get() in SOURCES[1:]
                    and self.state_value!=RunState.ERROR and r.epoch==self.text_worker.epoch
                    and r.generation==self.video.generation
                    and abs(self.video_position-r.timestamp)<=max(.7,1/float(self.text_rate_var.get())+.15+min(.9,r.total_ms/1000)))

    def _poll_text(self):
        for _ in range(4):
            try:epoch,message=self.text_worker.events.get_nowait()
            except queue.Empty:break
            if epoch==self.text_worker.epoch and self.text_var.get():
                self.text_var.set(False);self._reset_text()
                self.text_status_var.set('文字识别不可用：'+message[:90]);self.logger.error('OCR：%s',message)
        for _ in range(2):
            try:r=self.text_worker.results.get_nowait()
            except queue.Empty:break
            if not self.text_var.get() or r.epoch!=self.text_worker.epoch or r.generation!=self.video.generation:continue
            self.text_result=r
            self.text_status_var.set(f'文字 {len(r.regions)} 行 · '+('相同区域复用' if r.reused else f'CPU {r.total_ms:.0f}ms')+f' · 目标 {self.text_rate_var.get()}Hz · '+('自定范围' if self.text_roi else '全画面'))

    def _presentation_scene(self,scene):
        road=self.road_result.geometry if self._road_display_current() and self.road_outline_var.get() else None
        buildings=self.road_result.buildings if self._buildings_is_current() else None
        texts=self.text_result.regions if self._text_is_current() else ()
        shading=None
        colors=None
        colored=self.color_var.get()
        comic=not colored and self.shading_var.get() and self.shadow_mode_var.get()!='仅脚下投影'
        if colored and self._environment_is_current():colors=self.road_result.colors
        if not colored and (comic or self.sky_var.get()) and self._environment_is_current() and self.road_result.shading is not None:
            shading=tuple(r for r in self.road_result.shading if (r.tone==3 and self.sky_var.get()) or (r.tone!=3 and comic))
        contact=not colored and self.shading_var.get() and self.shadow_mode_var.get()!='明暗分区'
        if not scene:
            if road is None and buildings is None and not texts and shading is None and colors is None:
                return None
            scene=Scene(0,time.perf_counter(),self.video.generation,self.video_position,(),False)
        scene=replace(scene,road=road,buildings=buildings,texts=texts,shading=shading,colors=colors,contact_shadows=contact,shadow_density=self.shadow_density_var.get(),
                      skeleton_binding=self.skeleton_var.get())
        if self.source_var.get() in SOURCES[1:]:
            scene=replace(scene,frame_clipping=True)
            scene=self.smoother.update(scene,self.video_position,time.perf_counter(),self.state_value==RunState.RUNNING)
        name=self.vehicle_view_var.get()
        view=(self.yaw_var.get(),self.pitch_var.get()) if name=="自由角度" else VEHICLE_VIEWS.get(name)
        action=ACTIONS.get(self.person_action_var.get())
        if self._manual_action_name!=self.person_action_var.get():
            self._manual_action_name=self.person_action_var.get();self._manual_action_start=scene.animation_time
        entities=[]
        held=self.fire_detector.get_holds(self.video.generation,self.video_position) if self.source_var.get() in SOURCES[1:] else {}
        for entity in scene.entities:
            if entity.kind=="car":
                if view:entity=replace(entity,yaw=view[0],pitch=view[1],view_confidence=1)
                material=VEHICLE_MODELS[self.vehicle_model_var.get()]
                if material:entity=replace(entity,vehicle_type=material)
                if entity.track_id in self._vehicle_corrections:
                    entity=replace(entity,yaw=(entity.yaw+self._vehicle_corrections[entity.track_id])%360)
            elif entity.kind=="person" and action:
                combat=action in ('GUN_HOLD','GUN_FIRE','HIT','FALL','DOWN')
                entity=replace(entity,action=action,seated=action in ('SIT','SIT_GESTURE'),pose=(),action_mirror=self.combat_mirror_var.get() if combat else False,
                               posture_fit=False,action_manual=True,weapon=WEAPONS[self.weapon_var.get()],combat_yaw=COMBAT_VIEWS[self.combat_view_var.get()],action_time=max(0,scene.animation_time-self._manual_action_start) if combat else None)
            elif entity.kind=='person' and entity.action not in ('DOWN','FALL','PHONE','PHONE_LOOK','DRINK') and not entity.predicted:
                effect=self._shot_effects.get(entity.track_id) if self.auto_fire_var.get() else None
                pose=held.get(entity.track_id)
                if effect or pose:
                    age=time.perf_counter()-effect[1] if effect else 1
                    if effect and entity.track_id in self._unshown_shots:age=.05
                    firing=bool(effect and age<.120)
                    event=effect[0] if effect and (firing or not pose) else pose
                    point=(event.x+entity.x-event.owner_center[0],event.y+entity.y-event.owner_center[1])
                    weapon=(event.weapon_type or (pose.weapon_type if pose else '')) if self.auto_weapon_var.get() else ''
                    weapon_action='GUN_FIRE' if firing else entity.action if entity.action in ('WALK','RUN') else 'GUN_HOLD'
                    entity=replace(entity,action=weapon_action,pose=(),weapon=weapon or WEAPONS[self.weapon_var.get()],
                                   action_mirror=event.dx<0,
                                   action_time=age if firing else None if weapon_action in ('WALK','RUN') else 0,aim_point=point,aim_direction=(event.dx,event.dy))
            entities.append(entity)
        scope=('video',scene.scene_epoch%1000000) if self.source_var.get() in SOURCES[1:] else None
        return self.action_captions.apply(replace(scene,entities=tuple(entities)),self.action_captions_var.get(),scope=scope)

    def _draw_asset_gallery(self):
        if self.tabs.select()!=str(self.appearance_tab):
            return
        mode=self.gallery_mode_var.get()
        now=time.perf_counter()
        key=(mode,self.weapon_var.get(),self.combat_mirror_var.get(),self.combat_view_var.get(),
             self.vehicle_model_var.get(),self.yaw_var.get(),self.pitch_var.get(),
             self.gallery_canvas.winfo_width(),self.gallery_canvas.winfo_height())
        animated=(MODEL_GALLERIES.get(mode)=='helicopter' or
                  any(ACTIONS[name] in ANIMATED_ACTIONS for name in ACTION_GROUPS.get(mode,())))
        if key==getattr(self,'_gallery_draw_key',None):
            if not animated or now-getattr(self,'_gallery_draw_time',0)<1/15:return
        self._gallery_draw_key=key;self._gallery_draw_time=now
        entities=[]
        t=now-self._gallery_start
        if mode in MODEL_GALLERIES:
            material=MODEL_GALLERIES[mode]
            names=("车尾","右后斜视","右侧","右前斜视","车头","左前斜视","左侧","左后斜视","俯视")
            for i,name in enumerate(names):
                x,y=.18+.32*(i%3),.27+.30*(i//3)
                yaw,pitch=VEHICLE_VIEWS[name]
                entities.append(Entity(name,"car",x,y,bbox=(x-.12,y-.19,x+.12,y),yaw=yaw,pitch=pitch,vehicle_type=material))
        elif mode in ACTION_GROUPS:
            for i,name in enumerate(ACTION_GROUPS[mode]):
                x,y=.18+.32*(i%3),.47+.45*(i//3)
                action=ACTIONS[name]
                entities.append(Entity(name,"person",x,y,bbox=(x-.10,y-.32,x+.10,y),action=action,
                    weapon=WEAPONS[self.weapon_var.get()],action_mirror=self.combat_mirror_var.get() if mode=='人物·战斗' else False,
                    action_time=t%2 if action=='FALL' else None,combat_yaw=COMBAT_VIEWS[self.combat_view_var.get()]))
        elif mode=="动物·狗":
            for x,mirror,name in ((.27,False,"狗 · 朝右"),(.73,True,"狗 · 朝左")):
                entities.append(Entity(name,"dog",x,.73,bbox=(x-.19,.28,x+.19,.73),action_mirror=mirror))
        else:
            entities.append(Entity("自由旋转预览","car",.5,.85,bbox=(.10,.18,.90,.85),
                                   yaw=self.yaw_var.get(),pitch=self.pitch_var.get(),vehicle_type=VEHICLE_MODELS[self.vehicle_model_var.get()] or 'car'))
        scene=Scene(0,time.perf_counter(),0,t,tuple(entities),True)
        self.gallery_canvas.draw(scene,gallery=True)

    def start(self):
        if self.source_var.get()==SOURCES[1]:
            if self.state_value==RunState.RUNNING:
                return
            self._reset_detection()
            self.source.stop()
            self.video_frame = self.video_info = None
            self.video_position = 0.0
            self._video_loading = True
            self._live_deadline = time.perf_counter()+8
            self.video_info_text.set("正在连接 OBS 虚拟摄像机……")
            self.video.request_obs()
            self.state_value = RunState.RUNNING
            self._fps_start = time.perf_counter()
            self._frames = 0
            self.open_output()
            self.tabs.select(self.preview_tab)
            self._update_video_time()
            self._refresh_controls()
            self.logger.info("连接 OBS Virtual Camera。")
            return
        if self.source_var.get()==SOURCES[2]:
            if self.state_value==RunState.RUNNING or self._video_loading:
                return
            if not self.video_var.get():
                self.logger.warning("请先选择本地视频。")
                return
            if self.state_value in (RunState.ENDED,RunState.ERROR):
                self.video_position = 0.0
            preserve=self.video_frame is not None and self.state_value in (RunState.STOPPED,RunState.PAUSED)
            keep_frame=preserve and (self._detection_is_current() or self._environment_is_current() or self._text_is_current())
            self._reset_detection(preserve_binding=preserve)
            if keep_frame:self._render_pending_since=time.perf_counter()
            self.video.request(self.video_var.get(),self.video_position,True)
            self.state_value = RunState.RUNNING
            self._fps_start = time.perf_counter()
            self._frames = 0
            self._refresh_controls()
            self.logger.info("本地视频播放；人车检测%s，静音预览。","开启" if self.ai_var.get() else "关闭")
            return
        if self.source_var.get() != SOURCES[0]:
            self.logger.warning("所选输入尚未接入，请切换到模拟演示。")
            return
        if self.state_value == RunState.RUNNING:
            return
        if self.state_value != RunState.PAUSED:
            self.source.start()
        self.state_value = RunState.RUNNING
        self._last_tick = self._fps_start = time.perf_counter()
        self._frames = 0
        self.open_output()
        self._refresh_controls()
        self.logger.info("模拟演示运行中（无真实识别）。")

    def pause(self):
        if self.source_var.get()==SOURCES[1]:
            return
        if self.state_value == RunState.RUNNING:
            if self.source_var.get() in SOURCES[1:]:
                keep_frame=self._detection_is_current() or self._environment_is_current() or self._text_is_current()
                self._reset_detection(preserve_binding=True)
                if keep_frame:self._render_pending_since=time.perf_counter()
                self.video.request(self.video_var.get(),self.video_position,False)
            self.state_value = RunState.PAUSED
            self.fps_text.set("—")
            self._refresh_controls()
            self.logger.info("已暂停，播放或场景时间冻结。")
        elif self.state_value == RunState.PAUSED:
            self.start()

    def stop(self):
        self.video.cancel()
        self._reset_detection()
        self._video_loading = False
        self.state_value = RunState.STOPPED
        if self.source_var.get() in SOURCES[1:]:
            self.video_position = 0.0
            self.video_frame = None
            self._update_video_time()
            self._draw_video()
        self.source.stop()
        self.state_value = RunState.STOPPED
        self.scene = None
        self.count_text.set("0")
        self.clock_text.set("00:00")
        self.fps_text.set("—")
        self._refresh_controls()
        self.logger.info("已停止，输出回到待机占位。")

    def set_mode(self, mode):
        if self.source_var.get()!=SOURCES[0]:
            self.logger.info("场景演示按钮仅适用于模拟模式。")
            return
        self.source.mode = mode
        self.logger.info("模拟场景切换：%s",{"walk":"步行","drive":"驾驶","occlusion":"遮挡"}[mode])

    def trigger_error(self):
        if self.state_value not in (RunState.RUNNING,RunState.PAUSED):
            self.logger.info("请先开始演示，再测试异常占位。")
            return
        self.source.stop()
        self.video.cancel()
        self._reset_detection()
        self.state_value = RunState.ERROR
        self.scene = None
        self.count_text.set("0")
        self.fps_text.set("—")
        self._refresh_controls()
        self.logger.warning("演示异常占位已触发；点击重新开始可恢复。")

    def bind_primary(self, ident):
        if self.source_var.get() in SOURCES[1:]:
            if not self.scene or not any(e.track_id==ident for e in self.scene.entities):
                return
            self.primary_id=ident
            self.primary_text.set(ident)
            self.binding_status_var.set(f'已绑定 {ident}；暂停/继续保留，跳转/切场景清除。')
            self._draw_video()
            self.logger.info('真实主角目标已绑定：%s',ident)
            return
        if self.source_var.get()!=SOURCES[0]:
            return
        self.source.primary_id = ident
        self.primary_text.set(ident)
        self.logger.info("模拟目标已绑定：%s",ident)

    def _bind_selected(self):
        ident=self._target_options.get(self.target_var.get())
        if ident:
            self.bind_primary(ident)

    def clear_primary(self,log=True):
        self._vehicle_corrections.clear()
        self.primary_id=None
        self.primary_text.set('未绑定')
        self.binding_status_var.set('未绑定：点击动画中的目标，或从列表选择。')
        if log:
            self.logger.info('主角绑定已解除。')

    def _correct_vehicle(self,offset):
        if not self.scene or not any(e.track_id==self.primary_id and e.kind=='car' for e in self.scene.entities):
            self.logger.info('先在动画窗口点击并绑定需要校正的载具。');return
        if offset is None:self._vehicle_corrections.pop(self.primary_id,None)
        else:self._vehicle_corrections[self.primary_id]=(self._vehicle_corrections.get(self.primary_id,0)+offset)%360
        self.logger.info('绑定载具方向校正：%s°；切场景或解除绑定时清除。',self._vehicle_corrections.get(self.primary_id,0))

    def _refresh_controls(self):
        state = self.state_value
        self.status_var.set(state.value)
        is_video = self.source_var.get() in SOURCES[1:]
        live = self.source_var.get()==SOURCES[1]
        allowed = (not is_video or live or bool(self.video_var.get())) and state!=RunState.RUNNING and not self._video_loading
        self.video_scale.state(["disabled"] if live else ["!disabled"])
        self.start_button.configure(state="normal" if allowed else "disabled",
                                    text="连接 OBS" if live else "继续" if state==RunState.PAUSED else "重新开始" if state in (RunState.ERROR,RunState.ENDED) else "播放视频" if is_video else "开始演示")
        self.pause_button.configure(state="normal" if not live and state==RunState.RUNNING else "disabled",
                                    text="暂停")
        self.stop_button.configure(state="normal" if state!=RunState.STOPPED else "disabled")
        self.source_combo.configure(state="readonly" if state in (RunState.STOPPED,RunState.ENDED) else "disabled")
        if self.video_frame is None:
            self._draw_video()

    def open_output(self):
        if self.output is not None and self.output.winfo_exists():
            self.output.deiconify()
            self.output.lift()
            return
        self.output = tk.Toplevel(self,bg="#070d16")
        self.output.title("火柴人动画输出")
        sw,sh = self.winfo_screenwidth(),self.winfo_screenheight()
        width = min(960,max(640,sw-750))
        height = round(width*9/16)
        self.output.geometry(f"{width}x{height}+{min(710,max(0,sw-width-20))}+{max(30,(sh-height)//2)}")
        self.output.minsize(480,270)
        self.output_canvas = SceneCanvas(self.output,self.bind_primary)
        self.output_canvas.pack(fill="both",expand=True)
        self.output.protocol("WM_DELETE_WINDOW",self.output.withdraw)

    def open_logs(self):
        os.startfile(str(self.runtime))

    def _waiting_for_output(self,now):
        since=self._render_pending_since
        if since is None:return False
        ready=(not self.ai_var.get() or self._detection_is_current()) and (not self._environment_enabled() or self._environment_is_current())
        if not self.ai_var.get() and not self._environment_enabled():
            ready=self._text_is_current() if self.text_var.get() else bool(self.video_frame and self.video_frame.generation==self.video.generation)
        if ready or now-since>=1.5:
            self._render_pending_since=None;return False
        return True

    def _tick(self):
        began = time.perf_counter()
        dt = began-self._last_tick
        self._last_tick = began
        try:
            self._poll_video()
            self._poll_road()
            self._poll_detection()
            self._poll_text()
            self._poll_shots()
            self._draw_asset_gallery()
            is_video = self.source_var.get() in SOURCES[1:]
            if self.state_value == RunState.RUNNING and not is_video:
                self.source.npc_count = int(self.npc_var.get())
                self.source.vehicle_count = int(self.cars_var.get())
                self.scene = self.source.sample(dt,began)
                self.count_text.set(str(len(self.scene.entities)))
                seconds = int(self.scene.animation_time)
                self.clock_text.set(f"{seconds//60:02}:{seconds%60:02}")
            overlay = {RunState.STOPPED:"等待开始",RunState.PAUSED:"演示已暂停",RunState.ERROR:"信号异常 · 演示占位"}.get(self.state_value,"")
            if is_video:
                if self.state_value==RunState.ERROR:
                    overlay = "视频异常 · 请检查日志"
                elif not self.ai_var.get():
                    overlay = "" if self._environment_is_current() or self._text_is_current() else "人车检测已关闭"
                elif self.scene is None:
                    overlay = "" if self._text_is_current() else "等待有效检测结果"
                else:
                    overlay = "" if self.scene.entities or self._environment_is_current() or self._text_is_current() else "本帧未检出人车"
            if self.output_canvas and self.output.state() != "withdrawn":
                if not (is_video and self._waiting_for_output(time.perf_counter())):
                    presented=self._presentation_scene(self.scene)
                    self.output_canvas.draw(presented,overlay,self.debug_var.get(),simulated=not is_video)
                    self._mark_shots_presented(presented)
                if self.state_value == RunState.RUNNING and not is_video:
                    self._frames += 1
                    if began-self._fps_start >= 1:
                        self.fps_text.set(f"{self._frames/(began-self._fps_start):.1f}")
                        self._frames = 0
                        self._fps_start = began
            elif not is_video:
                self.fps_text.set("—")
                self._frames = 0
                self._fps_start = began
        except Exception:
            self.logger.exception("更新失败，进入异常占位。")
            self.trigger_error()
        self._drain_logs()
        delay = max(1,round(1000/int(self.fps_var.get())-(time.perf_counter()-began)*1000))
        self._after_id = self.after(delay,self._tick)

    def _drain_logs(self):
        messages = []
        for _ in range(100):
            try:
                messages.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if messages:
            self.log_widget.configure(state="normal")
            self.log_widget.insert("end","\n".join(messages)+"\n")
            lines = int(self.log_widget.index("end-1c").split(".")[0])
            if lines>500:
                self.log_widget.delete("1.0",f"{lines-500}.0")
            self.log_widget.see("end")
            self.log_widget.configure(state="disabled")

    def report_callback_exception(self, exc_type, exc, tb):
        if hasattr(self,"logger"):
            self.logger.error("界面回调异常",exc_info=(exc_type,exc,tb))
        else:
            super().report_callback_exception(exc_type,exc,tb)
        if self.smoke_test:
            self.test_failed = True

    def _run_smoke(self):
        try:
            self.start()
            assert self.state_value == RunState.RUNNING
            self._last_tick -= .04
            # Callbacks run normally between scheduled checks.
            self.after(200,self._smoke_pause)
        except Exception:
            self._smoke_failure()

    def _smoke_pause(self):
        try:
            assert self.scene and len(self.scene.entities)==7
            self.pause()
            self._paused_time = self.source.time
            self.after(100,self._smoke_resume)
        except Exception:
            self._smoke_failure()

    def _smoke_resume(self):
        try:
            assert self.source.time==self._paused_time
            self.start()
            self.set_mode("drive")
            self.after(120,self._smoke_finish)
        except Exception:
            self._smoke_failure()

    def _smoke_finish(self):
        try:
            assert self.scene and any(o.action=="DRIVE" for o in self.scene.entities)
            self.bind_primary("npc-1")
            self.trigger_error()
            assert self.state_value==RunState.ERROR and self.scene is None
            self.start()
            assert self.state_value==RunState.RUNNING
            self.output.withdraw()
            self.open_output()
            assert self.output.state()!="withdrawn"
            self.stop()
            assert self.state_value==RunState.STOPPED and not self.source.started
            self.save_settings()
            assert self._load_settings()["fps"]==30
            self.source_var.set(SOURCES[1])
            self._source_changed()
            assert self.state_value==RunState.STOPPED
            assert str(self.start_button["state"])=="normal"
            assert "disabled" in self.video_scale.state()
            (self.runtime/"smoke-result.json").write_text(json.dumps({"passed":True,
                "checks":["scene generation","pause freezes time","resume","driving scene",
                          "binding","error placeholder","recovery","output reopen","stop",
                          "settings roundtrip","live source ready without seek"]},indent=2),encoding="utf-8")
            self.after(50,self.close)
        except Exception:
            self._smoke_failure()

    def _smoke_failure(self):
        self.test_failed = True
        self.logger.exception("Smoke test failed")
        self.close()

    def _video_smoke_loaded(self):
        try:
            if not (self.video_info and self.video_frame):
                if time.perf_counter()-self._video_test_started>15:
                    raise AssertionError("视频未能加载首帧")
                self.after(100,self._video_smoke_loaded)
                return
            assert self.video_info.width>0 and self.video_info.duration>1
            assert self.scene is None and self.count_text.get()=="—"
            self.start()
            self.after(500,self._video_smoke_pause)
        except Exception:
            self._smoke_failure()

    def _video_smoke_pause(self):
        try:
            assert self.video_position>0 and self.video_frame
            self.pause()
            self._video_test_position = self.video_position
            self.after(350,self._video_smoke_seek)
        except Exception:
            self._smoke_failure()

    def _video_smoke_seek(self):
        try:
            assert abs(self.video_position-self._video_test_position)<.1
            self._video_test_target = min(60,self.video_info.duration/2)
            self.seek_video(min(10,self.video_info.duration/4))
            self.seek_video(min(20,self.video_info.duration/3))
            self.seek_video(self._video_test_target)
            self._video_test_seek_started = time.perf_counter()
            self.after(100,self._video_smoke_seek_check)
        except Exception:
            self._smoke_failure()

    def _video_smoke_seek_check(self):
        try:
            if not self.video_frame or abs(self.video_position-self._video_test_target)>.15:
                if time.perf_counter()-self._video_test_seek_started>10:
                    raise AssertionError("定位未生效")
                self.after(100,self._video_smoke_seek_check)
                return
            assert self.state_value==RunState.PAUSED
            self.start()
            self.after(250,self._video_smoke_end)
        except Exception:
            self._smoke_failure()

    def _video_smoke_end(self):
        try:
            assert self.video_position>=self._video_test_target
            self.seek_video(self.video_info.duration-.3)
            self._video_test_seek_started = time.perf_counter()
            self.after(100,self._video_smoke_end_check)
        except Exception:
            self._smoke_failure()

    def _video_smoke_end_check(self):
        try:
            if self.state_value!=RunState.ENDED:
                if time.perf_counter()-self._video_test_seek_started>10:
                    raise AssertionError("播放结束状态未触发")
                self.after(100,self._video_smoke_end_check)
                return
            self.start()
            assert self.state_value==RunState.RUNNING and self.video_position==0
            self.stop()
            assert self.video_scale_var.get()==0
            self.start()
            self.after(250,self._video_smoke_stop)
        except Exception:
            self._smoke_failure()

    def _video_smoke_stop(self):
        try:
            self.stop()
            assert self.video_position==0 and self.video_frame is None and self.scene is None
            # Test missing-file failure and a responsive main loop as well.
            self.load_video(self.runtime/"missing-video.mp4")
            self.after(200,self._video_smoke_error)
        except Exception:
            self._smoke_failure()

    def _video_smoke_error(self):
        try:
            assert self.state_value==RunState.ERROR
            assert self.video.frames.qsize()<=2
            (self.runtime/"video-smoke-result.json").write_text(json.dumps({"passed":True,
                "checks":["metadata","first frame","real playback","pause freezes time","seek",
                          "resume","end of file","replay","stop clears frame and progress","invalid file error",
                          "no synthetic detections in video mode","bounded frame queue"]},indent=2),encoding="utf-8")
            self.after(50,self.close)
        except Exception:
            self._smoke_failure()

    def _detection_smoke_loaded(self):
        try:
            if not (self.video_info and self.detection_result and self.scene):
                if time.perf_counter()-self._detection_test_started>20:
                    raise AssertionError("首帧检测未能完成："+self.ai_status_var.get())
                self.after(100,self._detection_smoke_loaded)
                return
            self.debug_var.set(True)
            self.seek_video(30)
            assert self.scene is None and self.detection_result is None
            self._detection_test_started = time.perf_counter()
            self.after(100,self._detection_smoke_boxes)
        except Exception:
            self._smoke_failure()

    def _detection_smoke_boxes(self):
        try:
            result = self.detection_result
            if not (result and abs(result.timestamp-30)<.15):
                if time.perf_counter()-self._detection_test_started>10:
                    raise AssertionError("定位后的检测未完成")
                self.after(100,self._detection_smoke_boxes)
                return
            labels = {d.label for d in result.detections}
            assert "person" in labels and "car" in labels
            assert self.scene and not self.scene.simulated
            assert all(e.bbox is not None and not e.primary for e in self.scene.entities)
            assert self.scene.horizon is not None
            assert any(len(e.pose)==33 for e in self.scene.entities if e.kind=="person")
            assert len(self.video_canvas.find_withtag("detection-box"))==len(result.detections)
            self.update_idletasks()
            assert self.preview_play.winfo_rooty()+self.preview_play.winfo_height() <= self.preview_tab.winfo_rooty()+self.preview_tab.winfo_height()
            assert self.video_canvas.winfo_height()>80
            assert result.generation==self.video.generation
            self.vehicle_view_var.set("车头")
            self.person_action_var.set("抬手")
            presented=self._presentation_scene(self.scene)
            assert all(e.yaw==180 for e in presented.entities if e.kind=="car")
            assert all(e.action=="RAISE" and not e.pose for e in presented.entities if e.kind=="person")
            self._restore_automatic()
            self.start()
            # Six distinct results need a longer window for the CPU precision model.
            self.after(2200,self._detection_smoke_running)
        except Exception:
            self._smoke_failure()

    def _detection_smoke_running(self):
        try:
            assert len(self._accepted_detection_times)>=3
            assert all(b-a>=.035 for a,b in zip(self._accepted_detection_times,self._accepted_detection_times[1:]))
            assert len(self._accepted_detection_times)>=6
            self.pause()
            self.seek_video(60)
            assert self.scene is None and self.detection_result is None
            self._detection_test_started = time.perf_counter()
            self.after(100,self._detection_smoke_finish)
        except Exception:
            self._smoke_failure()

    def _detection_smoke_finish(self):
        try:
            result = self.detection_result
            if not (result and abs(result.timestamp-60)<.15):
                if time.perf_counter()-self._detection_test_started>10:
                    raise AssertionError("暂停定位后的检测未完成")
                self.after(100,self._detection_smoke_finish)
                return
            assert any(d.label=="car" for d in result.detections)
            assert self.scene and self.scene.entities
            self.output_canvas.draw(self._presentation_scene(self.scene),simulated=False)
            assert self.output_canvas.hitboxes
            self.ai_var.set(False)
            self._detection_changed()
            assert self.scene is None and self.detection_result is None
            assert not self.video_canvas.find_withtag("detection-box")
            self.stop()
            assert self.scene is None and self.detection_result is None
            (self.runtime/"detection-smoke-result.json").write_text(json.dumps({"passed":True,
                "model_profile":self.model_profile_var.get(),
                "backend":result.backend,
                "checks":["real model first frame","person and car detected","multi-view car and articulated figure rendered",
                          "raw preview boxes","real pose landmarks and estimated horizon","higher frequency scheduling",
                          "seek invalidates detections","pause and seek redetect","generation check",
                          "AI disable clears output","stop clears detections","manual view and action override"]},indent=2),encoding="utf-8")
            self.after(50,self.close)
        except Exception:
            self._smoke_failure()

    def _workflow_smoke_loaded(self):
        try:
            if not (self.scene and self.scene.entities and self._road_is_current()):
                if time.perf_counter()-self._workflow_test_started>20:
                    raise AssertionError('道路或追踪未就绪：'+self.road_status_var.get())
                self.after(100,self._workflow_smoke_loaded)
                return
            assert self.road_result.geometry.left_edge or self.road_result.geometry.right_edge
            presentation=self._presentation_scene(self.scene)
            assert presentation.road and (presentation.road.left_edge or presentation.road.right_edge)
            assert presentation.frame_clipping
            assert presentation.buildings and presentation.buildings.outlines
            self.output_canvas.draw(presentation,simulated=False)
            assert self.output_canvas.find_withtag('preset-object')
            assert len(self.output_canvas.find_withtag('building-outline'))==len(presentation.buildings.outlines)
            assert self.video_canvas.find_withtag('building-preview')
            self.buildings_var.set(False)
            assert self._presentation_scene(self.scene).buildings is None
            self.buildings_var.set(True)
            outlines=self.output_canvas.find_withtag('road-boundary')
            assert outlines and all(self.output_canvas.type(item)=='line' for item in outlines)
            assert not self.road_result.geometry.polygons
            assert self.video_canvas.find_withtag('road-preview')
            entity=next((e for e in self.scene.entities if e.kind=='person'),self.scene.entities[0])
            self.bind_primary(entity.track_id)
            self._workflow_target=entity.track_id
            self.start()
            assert self.primary_id==self._workflow_target
            self.after(650,self._workflow_smoke_pause)
        except Exception:
            self._smoke_failure()

    def _workflow_smoke_pause(self):
        try:
            assert self.primary_id==self._workflow_target
            assert self.detection_result and any(d.track_id==self._workflow_target for d in self.detection_result.detections)
            self.pause()
            assert self.primary_id==self._workflow_target
            self._workflow_test_started=time.perf_counter()
            self.after(400,self._workflow_smoke_seek)
        except Exception:
            self._smoke_failure()

    def _workflow_smoke_seek(self):
        try:
            assert self.primary_id==self._workflow_target
            if not (self.detection_result and self.detection_result.generation==self.video.generation):
                if time.perf_counter()-self._workflow_test_started>10:
                    raise AssertionError('暂停后当前画面检测未就绪')
                self.after(100,self._workflow_smoke_seek)
                return
            assert self.detection_result and self.detection_result.generation==self.video.generation
            assert self.scene and any(e.primary for e in self.scene.entities)
            self.seek_video(90)
            assert self.primary_id is None and self.road_result is None and self.scene is None
            self._workflow_test_started=time.perf_counter()
            self.after(100,self._workflow_smoke_finish)
        except Exception:
            self._smoke_failure()

    def _workflow_smoke_finish(self):
        try:
            if not (self.scene and self._road_is_current() and abs(self.road_result.timestamp-90)<.2):
                if time.perf_counter()-self._workflow_test_started>15:
                    raise AssertionError('跳转后的道路结果未就绪')
                self.after(100,self._workflow_smoke_finish)
                return
            result=self.road_result
            self.road_mode_var.set('驾驶自动')
            assert result.geometry.driving_view and self._road_display_current()
            self.road_result=replace(result,timestamp=result.timestamp-2)
            assert not self._road_is_current()
            assert not self._buildings_is_current()
            self.road_result=result
            self.road_outline_var.set(False)
            assert self._presentation_scene(self.scene).road is None
            self.road_outline_var.set(True)
            self.road_var.set(False)
            self._road_changed()
            assert self.road_result is None and self.ai_var.get()
            presentation=self._presentation_scene(self.scene)
            assert presentation.road is None and presentation.frame_clipping and presentation.entities
            self.output_canvas.draw(presentation,simulated=False)
            assert self.output_canvas.find_withtag('preset-object')
            self._workflow_test_started=time.perf_counter()
            self.after(100,self._workflow_buildings_without_road)
        except Exception:
            self._smoke_failure()

    def _workflow_buildings_without_road(self):
        try:
            if not self._buildings_is_current():
                if time.perf_counter()-self._workflow_test_started>10:
                    raise AssertionError('关闭道路后建筑分析未恢复')
                self.after(100,self._workflow_buildings_without_road)
                return
            presentation=self._presentation_scene(self.scene)
            assert presentation.road is None and presentation.buildings and presentation.buildings.outlines
            self.buildings_var.set(False)
            self._road_changed()
            assert self._presentation_scene(self.scene).buildings is None
            self.stop()
            assert self.primary_id is None and self.road_result is None
            (self.runtime/'workflow-smoke-result.json').write_text(json.dumps({'passed':True,'checks':[
                'open left/right curb lines','no closed road polygons','raw curb preview overlay',
                'manual primary binding','play preserves binding','pause preserves binding',
                'seek clears binding and old road','seek resegments current frame','old road expires',
                'outline toggle','road disable preserves person detection','stop clears state',
                'frame-only clipping enabled','preset material renderer used','no road dependency for preset objects',
                'real building outer outlines and preview','building toggle','stale building geometry expires',
                'buildings independent of road visibility']},indent=2),encoding='utf-8')
            self.after(50,self.close)
        except Exception:
            self._smoke_failure()

    def _performance_loaded(self):
        try:
            if not (self.scene and self.scene.entities and self._road_display_current()):
                if time.perf_counter()-self._performance_started>20:
                    raise AssertionError('并行测速未就绪')
                self.after(100,self._performance_loaded)
                return
            self.road_mode_var.set('驾驶自动')
            self.start()
            self.after(6500,self._performance_finish)
        except Exception:
            self._smoke_failure()

    def _performance_finish(self):
        try:
            def hz(samples):
                return (len(samples)-1)/(samples[-1]-samples[0]) if len(samples)>1 else 0
            human,road=hz(self._detect_wall_times),hz(self._road_wall_times)
            report=dict(passed=human>=min(8,float(self.detect_rate_var.get())*.80) and road>=min(4,float(self.road_rate_var.get())*.80),human_target_hz=float(self.detect_rate_var.get()),
                        model_profile=self.model_profile_var.get(),
                        backend=self.detection_result.backend,
                        environment_backend=self.road_result.backend,
                        road_target_hz=float(self.road_rate_var.get()),human_measured_hz=human,road_measured_hz=road,
                        latest_human_ms=self.detection_result.total_ms,latest_road_ms=self.road_result.total_ms,
                        preview_fps=self.fps_text.get(),duration_seconds=6.5,
                        source_fps=self.video_info.fps if self.video_info else None,
                        human_target_reached=human>=float(self.detect_rate_var.get())*.9,
                        road_target_reached=road>=float(self.road_rate_var.get())*.9,
                        building_outlines=len(self.road_result.buildings.outlines) if self.road_result.buildings else 0,
                        note='Short concurrent desktop test on this clip, not a sustained performance guarantee.')
            (self.runtime/'performance-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            assert report['passed'],str(report)
            self.after(50,self.close)
        except Exception:
            self._smoke_failure()

    def close(self):
        if self.combat_preview and self.combat_preview.winfo_exists():self.combat_preview.close()
        self.source.stop()
        self.video.close()
        self.fire_detector.close()
        self.detector.close()
        self.road_worker.close()
        self.text_worker.close()
        for worker in (self.detector,self.road_worker,self.video,self.text_worker):
            worker._thread.join(timeout=3)
        if hasattr(self,"_after_id"):
            self.after_cancel(self._after_id)
        self.logger.info("程序退出。")
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
        self.destroy()
