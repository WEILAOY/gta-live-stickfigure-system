"""Task-oriented desktop controls; theme updates keep the live widgets intact."""
import tkinter as tk
from tkinter import ttk

BG = '#f4f6f8'
PANEL = '#ffffff'
TEXT = '#253248'
MUTED = '#788598'
ACCENT = '#148e78'
LINE = '#e4e9ef'
SOFT = '#eaf6f2'
FONT = 'Microsoft YaHei UI'


def apply_style(app):
    from .ui_theme import ThemeManager
    if not hasattr(app, '_ui_theme'):
        app._ui_theme = ThemeManager(app)
    else:
        app._ui_theme.apply(app.theme_var.get())


def label(parent, text='', **kw):
    kw.setdefault('bg', parent.cget('bg'))
    kw.setdefault('fg', TEXT)
    kw.setdefault('font', (FONT, 10))
    kw.setdefault('anchor', 'w')
    widget = tk.Label(parent, text=text, **kw)
    if kw.get('wraplength'):
        def resize(event):
            width = max(120, event.width)
            if int(float(widget.cget('wraplength'))) != width:
                widget.configure(wraplength=width)
        widget.bind('<Configure>', resize)
    return widget


def panel(parent, title, description='', pack=True, **pack_kw):
    outer = tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    if pack:
        outer.pack(fill='x', pady=(0, 16), **pack_kw)
    inner = tk.Frame(outer, bg=PANEL, padx=20, pady=17)
    inner.pack(fill='both', expand=True)
    label(inner, title, font=(FONT, 11, 'bold')).pack(anchor='w')
    if description:
        label(inner, description, fg=MUTED, font=(FONT, 9), justify='left', wraplength=650).pack(anchor='w', pady=(5, 0))
    tk.Frame(inner, bg=PANEL, height=12).pack()
    return inner


def scroll_page(app, parent):
    canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, borderwidth=0)
    bar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
    bar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=bar.set)
    body = tk.Frame(canvas, bg=BG)
    item = canvas.create_window((0, 0), window=body, anchor='nw')
    body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(item, width=max(1, e.width)))
    app._ui_scroll_areas.append((body, canvas))
    return body


def field(parent, title, variable, values, command=None, width=16):
    box = tk.Frame(parent, bg=PANEL)
    label(box, title, fg=MUTED, font=(FONT, 9)).pack(anchor='w', pady=(0, 6))
    combo = ttk.Combobox(box, textvariable=variable, values=values, state='readonly', width=width)
    combo.pack(fill='x')
    if command:
        combo.bind('<<ComboboxSelected>>', command)
    return box, combo


def fields(parent, entries):
    row = tk.Frame(parent, bg=PANEL)
    row.pack(fill='x', pady=(0, 11))
    for i, entry in enumerate(entries):
        box, combo = field(row, *entry)
        box.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 9, 0 if i == len(entries)-1 else 9))
        row.columnconfigure(i, weight=1, uniform='fields')
    return row


def toggle(parent, text, variable, command=None, description=''):
    row = tk.Frame(parent, bg=PANEL)
    row.pack(fill='x', pady=(0, 5))
    check = ttk.Checkbutton(row, text=text, variable=variable, command=command)
    check.pack(anchor='w')
    if description:
        label(row, description, fg=MUTED, font=(FONT, 9), wraplength=650,
              justify='left').pack(anchor='w', padx=(20, 0), pady=(0, 4))
    return check


def _icon(canvas, kind, color):
    canvas.delete('all')
    p = dict(fill=color, width=1.6)
    if kind == 'work':
        for x, y in ((3, 3), (12, 3), (3, 12), (12, 12)):
            canvas.create_rectangle(x, y, x+5, y+5, outline=color, width=1.5)
    elif kind == 'recognition':
        for x, y, dx, dy in ((3, 3, 5, 5), (17, 3, -5, 5), (3, 17, 5, -5), (17, 17, -5, -5)):
            canvas.create_line(x, y+dy, x, y, x+dx, y, **p)
        canvas.create_oval(7, 7, 13, 13, outline=color, width=1.5)
    elif kind == 'style':
        canvas.create_oval(3, 3, 17, 17, outline=color, width=1.5)
        for x, y in ((7, 7), (12, 6), (14, 11)):
            canvas.create_oval(x-1, y-1, x+1, y+1, fill=color, outline=color)
        canvas.create_line(4, 14, 10, 14, 10, 17, **p)
    elif kind == 'materials':
        canvas.create_rectangle(3, 5, 17, 17, outline=color, width=1.5)
        canvas.create_line(7, 3, 17, 3, 17, 5, **p)
        canvas.create_line(5, 14, 9, 10, 12, 13, 15, 9, **p)
    else:
        canvas.create_rectangle(4, 2, 16, 18, outline=color, width=1.5)
        for y in (7, 11, 15):
            canvas.create_line(7, y, 13, y, **p)


def build_ui(app, sources, detection_rates, road_rates, model_profiles, vehicle_views,
             vehicle_models, actions, weapons, combat_views, model_galleries, action_groups, scene_canvas):
    app._ui_scroll_areas = []
    app.columnconfigure(1, weight=1)
    app.rowconfigure(0, weight=1)
    sidebar = tk.Frame(app, bg=PANEL, width=174, highlightthickness=0)
    sidebar.grid(row=0, column=0, sticky='ns')
    sidebar.grid_propagate(False)
    tk.Frame(app, bg=LINE, width=1).grid(row=0, column=0, sticky='nse')
    brand = tk.Frame(sidebar, bg=PANEL)
    brand.pack(fill='x', padx=15, pady=(28, 29))
    logo = tk.Canvas(brand, width=35, height=35, bg=SOFT, highlightthickness=0)
    app._ui_logo = logo
    logo.pack(side='left', padx=(0, 9))
    logo.create_oval(14, 5, 21, 12, outline=ACCENT, width=2, tags='ui-accent-outline')
    logo.create_line(17.5, 13, 17.5, 23, 11, 30, fill=ACCENT, width=2, tags='ui-accent-line')
    logo.create_line(17.5, 23, 24, 30, fill=ACCENT, width=2, tags='ui-accent-line')
    logo.create_line(10, 16, 17.5, 19, 25, 15, fill=ACCENT, width=2, tags='ui-accent-line')
    names = tk.Frame(brand, bg=PANEL)
    names.pack(side='left')
    label(names, '火柴人画面系统', font=(FONT, 9, 'bold')).pack(anchor='w')
    label(names, '工作室', fg=MUTED, font=(FONT, 8)).pack(anchor='w')
    label(sidebar, '创作空间', fg='#a0abb8', font=(FONT, 8)).pack(anchor='w', padx=24, pady=(0, 9))

    main = tk.Frame(app, bg=BG)
    main.grid(row=0, column=1, sticky='nsew')
    header = tk.Frame(main, bg=BG)
    header.pack(fill='x', padx=26, pady=(24, 19))
    app._ui_page_title = tk.StringVar(value='工作台')
    app._ui_page_description = tk.StringVar(value='选择输入，开始转换。')
    titles = tk.Frame(header, bg=BG)
    titles.pack(side='left', fill='x', expand=True)
    label(titles, textvariable=app._ui_page_title, font=(FONT, 20, 'bold')).pack(anchor='w')
    label(titles, textvariable=app._ui_page_description, fg=MUTED, font=(FONT, 9)).pack(anchor='w', pady=(5, 0))
    ttk.Button(header, text='打开输出窗口', command=app.open_output).pack(side='right', padx=(12, 0))
    badge = tk.Frame(header, bg=SOFT, padx=11, pady=7)
    badge.pack(side='right')
    label(badge, '●', fg=ACCENT, font=('Segoe UI', 8)).pack(side='left', padx=(0, 5))
    label(badge, textvariable=app.status_var, fg=ACCENT, font=(FONT, 9)).pack(side='left')

    tabs = ttk.Notebook(main, style='Workspace.TNotebook')
    tabs.pack(fill='both', expand=True, padx=(26, 20), pady=(0, 22))
    app.tabs = tabs
    pages = []
    definitions = (
        ('work', '工作台', '选择输入，开始转换。'),
        ('recognition', '识别设置', '集中调整识别功能与分析频率。'),
        ('style', '画面样式', '设置背景、人物动作与载具外观。'),
        ('materials', '素材演示', '点击素材会应用手动动作与视角；演示不代表自动识别结果。'),
        ('logs', '运行日志', '查看运行状态与问题记录。'),
    )
    app._ui_nav = []
    for key, title, subtitle in definitions:
        page = tk.Frame(tabs, bg=BG)
        tabs.add(page, text=title)
        pages.append(page)
        row = tk.Frame(sidebar, bg=PANEL, height=43, cursor='hand2')
        row.pack(fill='x', padx=12, pady=3)
        row.pack_propagate(False)
        icon = tk.Canvas(row, width=21, height=21, bg=PANEL, highlightthickness=0)
        icon.pack(side='left', padx=(13, 10))
        _icon(icon, key, MUTED)
        text = label(row, title, fg=MUTED, font=(FONT, 10), cursor='hand2')
        text.pack(side='left')
        for widget in (row, icon, text):
            widget.bind('<Button-1>', lambda e, p=page: tabs.select(p))
        app._ui_nav.append((page, row, icon, text, key, title, subtitle))
    app.preview_tab, app.recognition_tab, app.style_tab, app.appearance_tab, app.logs_tab = pages

    def changed(event=None):
        selected = tabs.select()
        palette = app._ui_theme.colors
        for page, row, icon, text, key, title, subtitle in app._ui_nav:
            active = selected == str(page)
            color, background = (palette['accent'], palette['soft']) if active else (palette['muted'], palette['panel'])
            row.configure(bg=background)
            text.configure(bg=background, fg=color, font=(FONT, 10, 'bold' if active else 'normal'))
            icon.configure(bg=background)
            _icon(icon, key, color)
            if active:
                app._ui_page_title.set(title)
                app._ui_page_description.set(subtitle)
        app.after_idle(app._draw_video)
    tabs.bind('<<NotebookTabChanged>>', changed)
    app._ui_refresh_nav = changed

    foot = tk.Frame(sidebar, bg=PANEL)
    foot.pack(side='bottom', fill='x', padx=16, pady=19)
    app.theme_button = ttk.Button(foot, textvariable=app._ui_theme.button_text,
                                 command=app.toggle_theme)
    app.theme_button.pack(fill='x', pady=(0, 7))
    ttk.Button(foot, text='保存当前配置', style='Quiet.TButton', command=app.save_settings).pack(fill='x')
    tk.Frame(foot, bg=LINE, height=1).pack(fill='x', pady=(15, 14))
    label(foot, '火柴人画面系统', fg=MUTED, font=(FONT, 8)).pack(anchor='w', padx=7)
    label(foot, 'V0.34  ·  本地运行', fg='#a0abb8', font=(FONT, 8)).pack(anchor='w', padx=7, pady=(4, 0))

    def scroll(event):
        target = app.winfo_containing(event.x_root, event.y_root)
        if target is None or target.winfo_class() in ('TCombobox', 'TScale', 'Text'):
            return
        for body, canvas in app._ui_scroll_areas:
            widget = target
            while widget is not None:
                if widget == body or widget == canvas:
                    if body.winfo_height() > canvas.winfo_height():
                        canvas.yview_scroll(-int(event.delta/120), 'units')
                        return 'break'
                    return
                widget = getattr(widget, 'master', None)
    app.bind('<MouseWheel>', scroll, add='+')

    # Workbench: one source selector, one transport, one preview.
    work = app.preview_tab
    input_card = panel(work, '输入画面')
    toolbar = tk.Frame(input_card, bg=PANEL)
    toolbar.pack(fill='x')
    app.source_combo = ttk.Combobox(toolbar, textvariable=app.source_var, values=sources, state='readonly', width=22)
    app.source_combo.pack(side='left')
    app.source_combo.bind('<<ComboboxSelected>>', app._source_changed)
    ttk.Button(toolbar, text='选择视频', command=app.choose_video).pack(side='left', padx=(9, 0))
    app.stop_button = ttk.Button(toolbar, text='停止', command=app.stop, width=5)
    app.stop_button.pack(side='right')
    app.pause_button = ttk.Button(toolbar, text='暂停', command=app.pause, width=5)
    app.pause_button.pack(side='right', padx=7)
    app.start_button = ttk.Button(toolbar, text='开始演示', style='Accent.TButton', command=app.start, width=9)
    app.start_button.pack(side='right', padx=(12, 0))
    app.preview_play, app.preview_pause, app.preview_stop = app.start_button, app.pause_button, app.stop_button
    label(input_card, textvariable=app.hint_var, fg=MUTED, font=(FONT, 9), wraplength=780,
          justify='left').pack(anchor='w', pady=(11, 0))

    preview_outer = tk.Frame(work, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    preview_outer.pack(fill='both', expand=True)
    preview_header = tk.Frame(preview_outer, bg=PANEL, padx=18, pady=13)
    preview_header.pack(fill='x')
    label(preview_header, '输入预览', font=(FONT, 10, 'bold')).pack(side='left')
    label(preview_header, '动画结果在独立输出窗口中显示', fg=MUTED, font=(FONT, 8)).pack(side='right')
    metrics = tk.Frame(preview_outer, bg=PANEL)
    metrics.pack(side='bottom', fill='x', padx=18, pady=(0, 13))
    for i, (name, variable) in enumerate((('预览 / 绘制 FPS', app.fps_text), ('识别对象', app.count_text), ('播放时间', app.clock_text), ('主角', app.primary_text))):
        cell = tk.Frame(metrics, bg=PANEL)
        cell.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 14, 0))
        metrics.columnconfigure(i, weight=1, uniform='metric')
        label(cell, textvariable=variable, font=('Segoe UI', 17, 'bold'), fg=TEXT).pack(anchor='w')
        label(cell, name, fg=MUTED, font=(FONT, 8)).pack(anchor='w', pady=(2, 0))
    timeline = tk.Frame(preview_outer, bg=PANEL)
    timeline.pack(side='bottom', fill='x', padx=18, pady=(7, 10))
    app.video_scale = ttk.Scale(timeline, from_=0, to=1, variable=app.video_scale_var)
    app.video_scale.pack(side='left', fill='x', expand=True)
    label(timeline, textvariable=app.video_time_text, fg=MUTED, font=('Segoe UI', 9), width=14,
          anchor='e').pack(side='right', padx=(10, 0))
    app.video_scale.bind('<ButtonPress-1>', lambda e: setattr(app, '_dragging_video', True))
    app.video_scale.bind('<ButtonRelease-1>', lambda e: app.seek_video(app.video_scale_var.get()))
    app.video_scale.bind('<KeyRelease>', lambda e: app.seek_video(app.video_scale_var.get()))
    app.video_canvas = tk.Canvas(preview_outer, bg='#f7f9fb', height=260, highlightthickness=0)
    app.video_canvas.pack(fill='both', expand=True, padx=18)
    app.video_canvas.bind('<Configure>', lambda e: app._draw_video())

    # Recognition controls live here, away from the primary transport.
    body = scroll_page(app, app.recognition_tab)
    card = panel(body, '识别与频率', '频率为调度目标，实际速度取决于画面与设备。')
    fields(card, [('识别档位', app.model_profile_var, tuple(model_profiles), app._model_changed),
                  ('人车分析 / Hz', app.detect_rate_var, detection_rates, app._rates_changed),
                  ('环境分析 / Hz', app.road_rate_var, road_rates, app._rates_changed)])
    fields(card, [('输出刷新目标 / FPS', app.fps_var, (15, 30, 60))])
    toggle(card, '启用人车检测', app.ai_var, app._detection_changed)
    toggle(card, '躺卧人物补检', app.down_recovery_var, app._down_recovery_changed,
           '提高横向人物的检出机会，也会增加分析负担。')
    toggle(card, '显示调试标记', app.debug_var, app._draw_video)
    card = panel(body, '文字识别')
    toggle(card, '识别画面文字', app.text_var, app._text_changed)
    row = tk.Frame(card, bg=PANEL)
    row.pack(fill='x', pady=(6, 0))
    label(row, '分析频率 / Hz', fg=MUTED).pack(side='left', padx=(0, 10))
    combo = ttk.Combobox(row, textvariable=app.text_rate_var, values=(.25, .5, 1, 2, 3, 5), state='readonly', width=7)
    combo.pack(side='left')
    combo.bind('<<ComboboxSelected>>', app._text_changed)
    ttk.Button(row, text='设置识别范围', command=app.open_text_region).pack(side='left', padx=12)
    label(card, textvariable=app.text_status_var, fg=MUTED, font=(FONT, 9), wraplength=700,
          justify='left').pack(anchor='w', pady=(9, 0))
    card = panel(body, '枪械与事件')
    toggle(card, '自动枪口火光', app.auto_fire_var, app._auto_fire_changed)
    toggle(card, '游戏 HUD 辅助', app.hud_assist_var, app._hud_changed)
    toggle(card, '自动选择枪型', app.auto_weapon_var)
    label(card, textvariable=app.shot_status_var, fg=MUTED, font=(FONT, 9), wraplength=700,
          justify='left').pack(anchor='w', pady=(6, 0))
    card = panel(body, '分析状态')
    for variable in (app.ai_status_var, app.horizon_status_var, app.road_status_var):
        label(card, textvariable=variable, fg=MUTED, font=(FONT, 9), wraplength=700,
              justify='left').pack(anchor='w', pady=(0, 8))

    # Visual parameters are consolidated into the style page.
    body = scroll_page(app, app.style_tab)
    card = panel(body, '背景样式')
    app.color_checkbox = toggle(card, '背景颜色', app.color_var, app._color_changed,
                                '开启简化配色；关闭后恢复漫画阴影。')
    app.shading_checkbox = toggle(card, '漫画阴影', app.shading_var, app._road_changed)
    app.sky_checkbox = toggle(card, '淡蓝天空', app.sky_var, app._road_changed)
    row = tk.Frame(card, bg=PANEL)
    row.pack(fill='x', pady=(7, 0))
    label(row, '阴影范围', fg=MUTED).pack(side='left', padx=(0, 10))
    app.shadow_mode_combo = ttk.Combobox(row, textvariable=app.shadow_mode_var, values=('分区+投影', '明暗分区', '仅脚下投影'), state='readonly', width=14)
    app.shadow_mode_combo.pack(side='left')
    app.shadow_mode_combo.bind('<<ComboboxSelected>>', lambda e: app._road_changed())
    ttk.Button(row, text='阴影与分区设置', command=app.open_shadow_settings).pack(side='left', padx=12)
    card = panel(body, '场景轮廓')
    toggle(card, '分析驾驶路缘', app.road_var, app._road_changed)
    toggle(card, '显示道路边缘', app.road_outline_var)
    toggle(card, '显示建筑轮廓', app.buildings_var, app._road_changed)
    fields(card, [('道路分析模式', app.road_mode_var, ('驾驶自动', '始终检测'))])
    card = panel(body, '人物与载具')
    toggle(card, '骨骼驱动动作', app.skeleton_var, app._skeleton_changed,
           '最多 3 人；关键点不可靠时回退完整预设。')
    toggle(card, '动作变化角标', app.action_captions_var, app.action_captions.reset)
    fields(card, [('人物动作', app.person_action_var, tuple(actions), lambda e: setattr(app, '_manual_action_name', None)),
                  ('载具素材', app.vehicle_model_var, tuple(vehicle_models))])
    fields(card, [('载具视角', app.vehicle_view_var, tuple(vehicle_views), app._view_changed),
                  ('战斗枪型', app.weapon_var, tuple(weapons)),
                  ('战斗视角', app.combat_view_var, tuple(combat_views))])
    toggle(card, '战斗素材朝左', app.combat_mirror_var)
    label(card, '选择自动姿态与自动估计可跟随画面；手动选项会覆盖自动结果。', fg=MUTED,
          font=(FONT, 9), wraplength=700).pack(anchor='w', pady=(6, 0))
    for title, variable, maximum in (('水平角度', app.yaw_var, 360), ('俯视角度', app.pitch_var, 85)):
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill='x', pady=(12, 0))
        label(row, title, fg=MUTED, width=10).pack(side='left')
        ttk.Scale(row, from_=0, to=maximum, variable=variable, command=app._free_view_changed).pack(side='left', fill='x', expand=True)
    ttk.Button(card, text='恢复自动动作与视角', command=app._restore_automatic).pack(anchor='w', pady=(14, 0))
    card = panel(body, '主角绑定', '也可以直接点击输出窗口中的人物或车辆。')
    row = tk.Frame(card, bg=PANEL)
    row.pack(fill='x')
    app.target_combo = ttk.Combobox(row, textvariable=app.target_var, values=(), state='readonly', width=22)
    app.target_combo.pack(side='left', fill='x', expand=True)
    ttk.Button(row, text='绑定', command=app._bind_selected).pack(side='left', padx=8)
    ttk.Button(row, text='解除', command=app.clear_primary).pack(side='left')
    label(card, textvariable=app.binding_status_var, fg=MUTED, font=(FONT, 9), wraplength=700,
          justify='left').pack(anchor='w', pady=(11, 0))
    row = tk.Frame(card, bg=PANEL)
    row.pack(fill='x', pady=(12, 0))
    for title, value in (('载具转 90°', 90), ('载具转 180°', 180), ('清除方向校正', None)):
        ttk.Button(row, text=title, command=lambda v=value: app._correct_vehicle(v)).pack(side='left', padx=(0, 8))
    app._sync_background_controls()

    # The asset browser and demo controls are deliberately lower frequency.
    material = app.appearance_tab
    browser = tk.Frame(material, bg=PANEL, highlightbackground=LINE, highlightthickness=1, padx=17, pady=13)
    browser.pack(fill='x', pady=(0, 14))
    ttk.Combobox(browser, textvariable=app.gallery_mode_var,
                 values=(*model_galleries, *action_groups, '动物·狗', '单车旋转'), state='readonly', width=20).pack(side='left')
    ttk.Button(browser, text='战斗素材演示', command=app.open_combat_preview).pack(side='right')
    app.gallery_canvas = scene_canvas(material, app._gallery_clicked)
    app.gallery_canvas.pack(fill='both', expand=True)
    demo = tk.Frame(material, bg=PANEL, highlightbackground=LINE, highlightthickness=1, padx=15, pady=12)
    demo.pack(fill='x', pady=(13, 0))
    label(demo, '模拟场景', fg=MUTED, font=(FONT, 9)).pack(side='left', padx=(0, 10))
    for title, mode in (('步行', 'walk'), ('驾驶', 'drive'), ('遮挡', 'occlusion')):
        ttk.Button(demo, text=title, command=lambda m=mode: app.set_mode(m), width=5).pack(side='left', padx=(0, 7))
    ttk.Button(demo, text='异常占位', command=app.trigger_error).pack(side='left')
    label(demo, '  人物', fg=MUTED, font=(FONT, 9)).pack(side='left')
    ttk.Combobox(demo, textvariable=app.npc_var, values=(0, 1, 2, 3), state='readonly', width=3).pack(side='left', padx=5)
    label(demo, '车辆', fg=MUTED, font=(FONT, 9)).pack(side='left')
    ttk.Combobox(demo, textvariable=app.cars_var, values=(1, 2, 3, 4), state='readonly', width=3).pack(side='left', padx=5)

    logs = app.logs_tab
    info = panel(logs, '当前输入')
    label(info, textvariable=app.video_info_text, fg=MUTED, font=(FONT, 9), wraplength=740,
          justify='left').pack(anchor='w')
    row = tk.Frame(info, bg=PANEL)
    row.pack(fill='x', pady=(10, 0))
    label(row, '设备备注', fg=MUTED, font=(FONT, 9)).pack(side='left', padx=(0, 10))
    ttk.Entry(row, textvariable=app.device_var, width=23).pack(side='left')
    ttk.Button(row, text='打开日志目录', command=app.open_logs).pack(side='right')
    log_outer = tk.Frame(logs, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    log_outer.pack(fill='both', expand=True)
    app.log_widget = tk.Text(log_outer, bg=PANEL, fg='#536277', font=('Consolas', 10),
                            relief='flat', borderwidth=0, padx=17, pady=15, wrap='word', state='disabled')
    log_bar = ttk.Scrollbar(log_outer, orient='vertical', command=app.log_widget.yview)
    log_bar.pack(side='right', fill='y')
    app.log_widget.configure(yscrollcommand=log_bar.set)
    app.log_widget.pack(fill='both', expand=True)
    app._ui_theme.refresh()
    changed()
