"""Frozen-frame rectangle editor; OCR crops only analysis, never output art."""
import tkinter as tk
from tkinter import ttk
from .ocr import normalize_roi

def canvas_roi(start,end,viewport):
    x,y,w,h=viewport
    clamp=lambda v:max(0.,min(1.,v))
    a,c=sorted((clamp((start[0]-x)/w),clamp((end[0]-x)/w)))
    b,d=sorted((clamp((start[1]-y)/h),clamp((end[1]-y)/h)))
    if (c-a)*w<8 or (d-b)*h<8:raise ValueError('范围太小，请重新拖拽')
    return normalize_roi((a,b,c,d))

class OcrRegionDialog(tk.Toplevel):
    def __init__(self,parent,frame,roi,scale,on_apply):
        super().__init__(parent);self.title('文字识别范围');self.transient(parent)
        self.resizable(False,False);self.roi=roi;self.start=None;self.on_apply=on_apply
        ttk.Label(self,text='在这张静态预览上拖拽框选；只识别框内文字，输出位置保持原画面坐标。').pack(padx=12,pady=8)
        import cv2,numpy as np
        rgb=np.frombuffer(frame.pixels,np.uint8).reshape(frame.height,frame.width,3)
        ratio=min(720/frame.width,405/frame.height)
        w,h=round(frame.width*ratio),round(frame.height*ratio)
        rgb=cv2.resize(rgb,(w,h));self.viewport=(0,0,w,h)
        self.photo=tk.PhotoImage(data=f'P6\n{w} {h}\n255\n'.encode()+rgb.tobytes(),format='PPM',master=self)
        self.canvas=tk.Canvas(self,width=w,height=h,highlightthickness=0,cursor='crosshair');self.canvas.pack(padx=12)
        self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',self.release)
        row=ttk.Frame(self);row.pack(fill='x',padx=12,pady=8)
        ttk.Button(row,text='全画面',command=lambda:self.choose(None)).pack(side='left')
        ttk.Button(row,text='底部字幕区',command=lambda:self.choose((0,.72,1,1))).pack(side='left',padx=6)
        ttk.Label(row,text='识别精度：').pack(side='left',padx=(15,0))
        self.quality=tk.StringVar(value='原尺寸（较省）' if scale==1 else '放大1.5倍（较细）')
        ttk.Combobox(row,textvariable=self.quality,values=('原尺寸（较省）','放大1.5倍（较细）'),state='readonly',width=20).pack(side='left')
        self.message=tk.StringVar();ttk.Label(self,textvariable=self.message).pack(padx=12,pady=(0,5))
        row=ttk.Frame(self);row.pack(fill='x',padx=12,pady=(0,10))
        ttk.Button(row,text='取消',command=self.destroy).pack(side='right')
        self.apply_button=ttk.Button(row,text='应用并保存',command=self.apply);self.apply_button.pack(side='right',padx=8)
        self.choose(roi)
    def choose(self,roi):
        self.roi=roi;self.valid=True;self.paint();self.apply_button.state(['!disabled'])
        self.message.set('全画面识别' if roi is None else f'识别范围占画面 {(roi[2]-roi[0])*(roi[3]-roi[1]):.0%}；范围外的文字不会输出')
    def paint(self):
        self.canvas.delete('selection');a,b,c,d=self.roi or (0,0,1,1);_,_,w,h=self.viewport
        self.canvas.create_rectangle(a*w,b*h,c*w,d*h,outline='#49e5c2',width=3,tags='selection')
    def press(self,event):self.start=(event.x,event.y);self.valid=False;self.apply_button.state(['disabled'])
    def drag(self,event):
        if self.start is None:return
        self.canvas.delete('selection');self.canvas.create_rectangle(*self.start,event.x,event.y,outline='#49e5c2',width=3,tags='selection')
    def release(self,event):
        if self.start is None:return
        try:self.choose(canvas_roi(self.start,(event.x,event.y),self.viewport))
        except ValueError as exc:self.message.set(str(exc))
        finally:self.start=None
    def apply(self):
        if self.valid:
            self.on_apply(self.roi,1. if self.quality.get().startswith('原尺寸') else 1.5);self.destroy()
