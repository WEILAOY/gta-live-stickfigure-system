"""Repaint application chrome without rebuilding controls or touching scene art."""
import tkinter as tk
from tkinter import ttk
from weakref import WeakKeyDictionary


LIGHT = dict(bg='#f4f6f8', panel='#ffffff', text='#253248', muted='#788598',
             accent='#148e78', line='#e4e9ef', soft='#eaf6f2', subtle='#a0abb8',
             preview='#f7f9fb', placeholder='#c8d4df', log='#536277',
             button='#f0f3f6', button_disabled='#f4f5f7', button_pressed='#dfe7ee',
             button_active='#e6edf2', disabled_text='#acb5c1', quiet_active='#f1f5f7',
             accent_pressed='#0e705e', accent_active='#107e69', accent_disabled='#d8e8e3',
             accent_disabled_text='#94b0a7', field_disabled='#f3f5f7',
             border_active='#bdcbd7', track='#e2e9ed', thumb_disabled='#c6d2d7',
             scrollbar='#cbd4df', scrollbar_active='#aab8c7')
DARK = dict(bg='#171c24', panel='#222a35', text='#e6ebf2', muted='#a5b2c3',
            accent='#64ceb6', line='#364353', soft='#28453f', subtle='#91a0b2',
            preview='#1c232d', placeholder='#566a80', log='#cad3df',
            button='#303c4b', button_disabled='#28313d', button_pressed='#435367',
            button_active='#3a4b5f', disabled_text='#788697', quiet_active='#303d4b',
            accent_pressed='#339e87', accent_active='#81dfc9', accent_disabled='#304b44',
            accent_disabled_text='#7b9c93', field_disabled='#28313d',
            border_active='#6d8199', track='#46566a', thumb_disabled='#637387',
            scrollbar='#526378', scrollbar_active='#70849d')
PALETTES = {'light': LIGHT, 'dark': DARK}


def validated_theme(value):
    return value if isinstance(value, str) and value in PALETTES else 'light'


class ThemeManager:
    def __init__(self, app):
        self.app = app
        self.roles = WeakKeyDictionary()
        self.button_text = tk.StringVar(master=app)
        self.colors = PALETTES[validated_theme(app.theme_var.get())]
        self._style = ttk.Style(app)
        self._style.theme_use('clam')
        # Persistent image elements are updated in place on every switch.
        self.images = tuple(tk.PhotoImage(master=app, width=w, height=h)
                            for w, h in ((128, 128), (128, 4), (18, 18), (18, 18), (18, 18)))
        flat, track, thumb, pressed, disabled = self.images
        self._style.element_create('FlatNotebook.client', 'image', flat, border=0, sticky='nsew')
        self._style.layout('Workspace.TNotebook', [('FlatNotebook.client', {'sticky': 'nsew'})])
        self._style.layout('Workspace.TNotebook.Tab', [])
        self._style.element_create('Clean.Horizontal.Scale.trough', 'image', track, border=1, sticky='we')
        self._style.element_create('Clean.Horizontal.Scale.slider', 'image', thumb,
                                   ('disabled', disabled), ('pressed', pressed), ('active', pressed))
        self._style.layout('Horizontal.TScale', [('Clean.Horizontal.Scale.trough', {'sticky': 'we', 'children': [
            ('Clean.Horizontal.Scale.slider', {'side': 'left', 'sticky': ''})]})])
        app._ui_theme_images = self.images
        self.configure_style()

    def configure_style(self):
        c = self.colors
        style = self._style
        style.configure('.', font=('Microsoft YaHei UI', 10), background=c['panel'], foreground=c['text'])
        style.configure('TFrame', background=c['panel'])
        style.configure('TLabel', background=c['panel'], foreground=c['text'])
        style.configure('Workspace.TNotebook', background=c['bg'], borderwidth=0, tabmargins=0)
        flat, track, thumb, pressed, disabled = self.images
        flat.put(c['bg'], to=(0, 0, 128, 128))
        track.put(c['track'], to=(0, 0, 128, 4))
        for image, edge in ((thumb, c['accent']), (pressed, c['accent_pressed']), (disabled, c['thumb_disabled'])):
            image.blank()
            for y in range(18):
                for x in range(18):
                    radius = ((x-8.5)**2+(y-8.5)**2)**.5
                    if radius <= 7.7:
                        image.put(edge if radius > 5.9 else c['panel'], (x, y))
        style.configure('TButton', background=c['button'], foreground=c['text'],
                        borderwidth=0, focusthickness=0, padding=(14, 9), anchor='center')
        style.map('TButton', background=[('disabled', c['button_disabled']), ('pressed', c['button_pressed']), ('active', c['button_active'])],
                  foreground=[('disabled', c['disabled_text'])])
        style.configure('Accent.TButton', background=c['accent'], foreground='#122d25' if self.app.theme_var.get() == 'dark' else 'white', padding=(20, 9))
        style.map('Accent.TButton', background=[('disabled', c['accent_disabled']), ('pressed', c['accent_pressed']), ('active', c['accent_active'])],
                  foreground=[('disabled', c['accent_disabled_text'])])
        style.configure('Quiet.TButton', background=c['panel'], foreground=c['muted'])
        style.map('Quiet.TButton', background=[('disabled', c['panel']), ('pressed', c['button_pressed']), ('active', c['quiet_active'])],
                  foreground=[('disabled', c['disabled_text']), ('active', c['text'])])
        style.configure('TCombobox', background=c['button'], fieldbackground=c['panel'], foreground=c['text'],
                        arrowcolor=c['muted'], bordercolor=c['line'], lightcolor=c['line'], darkcolor=c['line'], padding=(9, 7), arrowsize=13)
        style.map('TCombobox', fieldbackground=[('readonly', c['panel']), ('disabled', c['field_disabled'])],
                  foreground=[('disabled', c['disabled_text']), ('readonly', c['text'])],
                  selectbackground=[('readonly', c['soft'])], selectforeground=[('readonly', c['text'])],
                  bordercolor=[('focus', c['accent']), ('active', c['border_active'])])
        style.configure('TEntry', fieldbackground=c['panel'], foreground=c['text'], insertcolor=c['text'],
                        selectbackground=c['soft'], selectforeground=c['text'], bordercolor=c['line'],
                        lightcolor=c['line'], darkcolor=c['line'], padding=(9, 7))
        style.map('TEntry', bordercolor=[('focus', c['accent'])],
                  fieldbackground=[('disabled', c['field_disabled'])], foreground=[('disabled', c['disabled_text'])])
        style.configure('TCheckbutton', background=c['panel'], foreground=c['text'], padding=(0, 5), focusthickness=0,
                        indicatorbackground=c['panel'], indicatorforeground=c['accent'], bordercolor=c['line'])
        style.map('TCheckbutton', background=[('active', c['panel'])], foreground=[('disabled', c['disabled_text'])],
                  indicatorbackground=[('disabled', c['field_disabled']), ('selected', c['accent']), ('active', c['soft'])],
                  indicatorforeground=[('selected', '#122d25' if self.app.theme_var.get() == 'dark' else 'white')])
        style.configure('Horizontal.TScale', background=c['panel'], troughcolor=c['track'], borderwidth=0,
                        lightcolor=c['panel'], darkcolor=c['panel'], sliderlength=20, sliderthickness=12)
        style.configure('Vertical.TScrollbar', background=c['scrollbar'], troughcolor=c['bg'],
                        arrowcolor=c['muted'], bordercolor=c['bg'], borderwidth=0, arrowsize=11,
                        lightcolor=c['bg'], darkcolor=c['bg'])
        style.map('Vertical.TScrollbar', background=[('active', c['scrollbar_active'])])
        for option, role in (('background', 'panel'), ('foreground', 'text'), ('selectBackground', 'soft'), ('selectForeground', 'text')):
            self.app.option_add('*TCombobox*Listbox.'+option, c[role])
        self.app.option_add('*TCombobox*Listbox.relief', 'flat')
        for option, role in (('background', 'panel'), ('foreground', 'text'), ('activeBackground', 'soft'),
                             ('activeForeground', 'accent'), ('disabledForeground', 'disabled_text'), ('selectColor', 'accent')):
            self.app.option_add('*Menu.'+option, c[role])
        self.button_text.set('切换为浅色模式' if self.app.theme_var.get() == 'dark' else '切换为夜间模式')

    def _excluded(self, widget):
        # These canvases contain authored material; the UI theme must not recolor it.
        return widget is getattr(self.app, 'output', None) or widget.__class__.__name__ == 'SceneCanvas'

    def _capture(self, widget, popup=False):
        if self._excluded(widget):
            return
        if widget not in self.roles and not isinstance(widget, ttk.Widget):
            available = widget.keys()
            roles = {}
            by_color = {value: role for palette in PALETTES.values() for role, value in palette.items()}
            for option in ('background', 'foreground', 'highlightbackground', 'highlightcolor',
                           'insertbackground', 'selectbackground', 'selectforeground',
                           'activebackground', 'activeforeground', 'disabledforeground'):
                if option not in available:
                    continue
                role = by_color.get(str(widget.cget(option)).lower())
                if role:
                    roles[option] = role
            if isinstance(widget, tk.Toplevel):
                roles['background'] = 'panel'
            if isinstance(widget, (tk.Text, tk.Entry, tk.Listbox)):
                roles.setdefault('background', 'panel')
                roles.setdefault('foreground', 'text')
                for option, role in (('insertbackground', 'text'), ('selectbackground', 'soft'), ('selectforeground', 'text')):
                    if option in available:
                        roles[option] = role
            if isinstance(widget, tk.Menu):
                roles.update(background='panel', foreground='text', activebackground='soft', activeforeground='accent', disabledforeground='disabled_text')
            self.roles[widget] = roles
        for child in widget.winfo_children():
            self._capture(child, popup)

    def _combobox_list(self, widget):
        if not isinstance(widget, ttk.Combobox):
            return
        c = self.colors
        # Existing popdowns are Tcl widgets, not Python children; defaults only affect new ones.
        popdown = widget.tk.call('ttk::combobox::PopdownWindow', str(widget))
        widget.tk.call(str(popdown)+'.f.l', 'configure', '-background', c['panel'], '-foreground', c['text'],
                       '-selectbackground', c['soft'], '-selectforeground', c['text'], '-highlightbackground', c['line'])

    def refresh(self, root=None):
        root = self.app if root is None else root
        self._capture(root)
        c = self.colors
        def paint(widget):
            if self._excluded(widget):
                return
            roles = self.roles.get(widget, {})
            if roles:
                widget.configure(**{option: c[role] for option, role in roles.items()})
            self._combobox_list(widget)
            for child in widget.winfo_children():
                paint(child)
        paint(root)
        # Only these explicitly tagged canvas items are part of the UI.
        logo = getattr(self.app, '_ui_logo', None)
        if logo is not None:
            logo.itemconfigure('ui-accent-line', fill=c['accent'])
            logo.itemconfigure('ui-accent-outline', outline=c['accent'])
        callback = getattr(self.app, '_ui_refresh_nav', None)
        if callback:
            callback()

    def apply(self, value):
        value = validated_theme(value)
        self.app.theme_var.set(value)
        self.colors = PALETTES[value]
        self.configure_style()
        self.refresh()
        self.app._draw_video()
