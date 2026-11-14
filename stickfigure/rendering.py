"""Blank-canvas renderer: detected horizon, articulated people, 3D vehicle art."""
import math
import time
import tkinter as tk
from tkinter import font as tkfont
from .sprite_cache import SpriteCache,preset_key
from .assets import detail_for_size,bind_pose,bound_person_props
from .core import Scene,Horizon
from .assets import vehicle_drawing,dog_drawing,DOG_ASPECT,preset_pose,person_pose,person_props,fallen_box,down_render_box,down_bounds,combat_drawing,combat_render_box,aimed_gun_drawing,BODY_LINKS,PERSON_ASPECT,ANIMATED_ACTIONS

BG="#f7f9fc"
CYAN="#168a86"


class SceneCanvas(tk.Canvas):
    def __init__(self,parent,bind_callback=None,**kwargs):
        super().__init__(parent,bg=BG,highlightthickness=0,**kwargs)
        self.bind_callback=bind_callback
        self.hitboxes=[]
        self._poses={}
        self._images=[]
        self._layer_cache={}
        self._sprite_cache=SpriteCache()
        self._detail_levels={}
        self._text_fonts={}
        self._caption_fonts={}
        self._background_cache=None
        self._contact_cache={}
        self._frame_serial=0
        self._staging_tag=None
        self.bind("<Button-1>",self._clicked)

    def _clicked(self,event):
        for x1,y1,x2,y2,ident in reversed(self.hitboxes):
            if x1<=event.x<=x2 and y1<=event.y<=y2:
                if self.bind_callback:
                    self.bind_callback(ident)
                return

    @staticmethod
    def _bound_people(scene,gallery=False):
        if not scene or not scene.skeleton_binding or gallery:return {}
        result={}
        for obj in scene.entities:
            if (obj.kind!='person' or obj.action_manual or obj.predicted or
                    obj.aim_point is not None or obj.action in ('GUN_HOLD','GUN_FIRE')):continue
            raw=obj.render_bbox or obj.bbox
            box=[v*(1280 if i%2==0 else 720) for i,v in enumerate(raw)] if raw else (
                obj.x*1280-32*obj.scale,obj.y*720-120*obj.scale,
                obj.x*1280+32*obj.scale,obj.y*720)
            bound=bind_pose(obj.pose,box,obj.action,obj.action_mirror,obj.seated,obj.seat_mirror)
            if bound:result[obj.track_id]=bound
        return result

    def _create(self,itemType,args,kw):
        if self._staging_tag is not None:
            kw=dict(kw);tags=kw.get('tags',())
            if isinstance(tags,str):tags=(tags,)
            kw['tags']=(*tags,self._staging_tag);kw['state']='hidden'
        return super()._create(itemType,args,kw)

    def draw(self,scene:Scene|None,overlay="",debug=False,simulated=True,gallery=False):
        old_items=self.find_all()
        # Tk images need Python references until the old frame is removed.
        fields=('_images','_layer_cache','_background_cache','_contact_cache','_contact_images')
        previous={name:getattr(self,name,[]) for name in fields}
        hitboxes=list(self.hitboxes);poses=dict(self._poses);epoch=getattr(self,'_epoch',None)
        self._frame_serial+=1;tag=f'frame-{self._frame_serial}'
        self._staging_tag=tag
        try:
            self._draw(scene,overlay,debug,simulated,gallery)
            self.itemconfigure(tag,state='normal')
            if old_items:self.delete(*old_items)
            self.dtag(tag,tag)
        except Exception:
            self.delete(tag)
            for name,value in previous.items():setattr(self,name,value)
            self.hitboxes=hitboxes;self._poses=poses;self._epoch=epoch
            raise
        finally:self._staging_tag=None

    def _draw(self,scene:Scene|None,overlay="",debug=False,simulated=True,gallery=False):
        self.hitboxes.clear()
        self._images=[]
        w,h=max(2,self.winfo_width()),max(2,self.winfo_height())
        scale=min(w/1280,h/720)
        ox,oy=(w-1280*scale)/2,(h-720*scale)/2
        now=time.perf_counter()
        epoch=scene.scene_epoch if scene else -1
        if getattr(self,"_epoch",None)!=epoch:
            self._poses.clear()
            self._layer_cache.clear()
            self._sprite_cache.clear()
            self._detail_levels.clear()
            self._epoch=epoch

        def pts(coords):
            return [v*scale+(ox if i%2==0 else oy) for i,v in enumerate(coords)]
        layer=None
        def line(coords,**opts):
            if layer is not None:
                return layer.paint('line',pts(coords),**opts)
            return self.create_line(*pts(coords),**opts)
        def polygon(coords,**opts):
            if layer is not None:
                return layer.paint('polygon',pts(coords),**opts)
            return self.create_polygon(*pts(coords),**opts)
        def oval(coords,**opts):
            if layer is not None:
                return layer.paint('oval',pts(coords),**opts)
            return self.create_oval(*pts(coords),**opts)
        def text(x,y,value,size=14,color="#62758a",**opts):
            return self.create_text(*pts([x,y]),text=value,fill=color,
                font=("Microsoft YaHei UI",max(8,round(size*scale))),**opts)

        self._contact_images=[]
        next_contacts={}
        bound_poses=self._bound_people(scene,gallery)
        has_background=bool(scene and (scene.shading is not None or scene.colors is not None))
        if has_background and not gallery:
            import cv2
            from .shading import comic_pixels
            colored=scene.colors is not None
            regions=scene.colors if colored else scene.shading
            key=(regions,round(1280*scale),round(720*scale),colored,scene.shadow_density)
            if self._background_cache is None or self._background_cache[0]!=key:
                if colored:
                    from .coloring import color_pixels
                    pixels=color_pixels(regions,key[1],key[2])
                else:pixels=comic_pixels(regions,key[1],key[2],density=key[-1])
                # The background is opaque paper. PPM avoids PNG compression
                # on the UI thread whenever environment geometry changes.
                rgb=cv2.cvtColor(pixels,cv2.COLOR_BGRA2RGB)
                ppm=f'P6\n{key[1]} {key[2]}\n255\n'.encode('ascii')+rgb.tobytes()
                photo=tk.PhotoImage(data=ppm,format='PPM',master=self)
                self._background_cache=(key,photo)
            tags=('color-background','color-region') if colored else ('comic-background','shade-background','shade-region')
            self.create_image(ox,oy,image=self._background_cache[1],anchor='nw',tags=tags)
        if scene and scene.contact_shadows and not gallery:
            import cv2
            from .shading import contact_layer,contact_shadow_boxes
            for box in contact_shadow_boxes(scene.entities,bound_poses):
                key=(box,round(1280*scale),round(720*scale),scene.shadow_density)
                cached=self._contact_cache.get(key)
                if cached is None:
                    pixels,bounds=contact_layer(*key)
                    if not pixels.size:continue
                    cached=(tk.PhotoImage(data=cv2.imencode('.png',pixels)[1].tobytes(),master=self),bounds)
                next_contacts[key]=cached
                photo,bounds=cached;self._contact_images.append(photo)
                self.create_image(ox+bounds[0],oy+bounds[1],image=photo,anchor='nw',tags='contact-shadow')
        self._contact_cache=next_contacts
        if scene and scene.buildings and not gallery:
            from .ocr import text_free_outlines
            for outline in text_free_outlines(scene.buildings.outlines,scene.texts):
                line([v for x,y in outline for v in (x*1280,y*720)],fill='#8396a6',
                     width=max(1,1.6*scale),tags='building-outline')
        if scene and scene.road and not gallery:
            for side,edge in (('left',scene.road.left_edge),('right',scene.road.right_edge)):
                if len(edge)>=2:
                    coords=[value for x,y in edge for value in (x*1280,y*720)]
                    line(coords,fill='#688d98',width=max(1.3,2.2*scale),smooth=True,
                         tags=('road-boundary',f'curb-{side}'))

        horizon=scene.horizon if scene and scene.horizon else Horizon()
        if not gallery:
            line([0,horizon.left*720,1280,horizon.right*720],fill="#8398aa",
                 width=max(1,1.5*scale),dash=() if horizon.confidence>=.3 else (6,5),tags="horizon")
            if debug:
                text(24,25,f"地平线：{horizon.method} · 评分 {horizon.confidence:.0%}",13,anchor="w")
        active=set()
        next_cache={}
        clip=bool(scene and scene.frame_clipping and not gallery)
        if scene:
            for obj in sorted(scene.entities,key=lambda item:item.y):
                if clip and obj.predicted:
                    continue
                active.add(obj.track_id)
                sprite_key=None
                vehicle_art=None
                kind_tag='vehicle' if obj.kind=='car' else obj.kind
                action_time=scene.animation_time if obj.action_time is None else obj.action_time
                rotor=(int(scene.animation_time*12)%8)*22.5 if obj.vehicle_type=='helicopter' else 0
                if obj.bbox:
                    x1,y1,x2,y2=obj.bbox
                    box=[x1*1280,y1*720,x2*1280,y2*720]
                else:
                    bw,bh={'person':(64,120),'dog':(112,68)}.get(obj.kind,(162,90))
                    box=[obj.x*1280-bw*obj.scale/2,obj.y*720-bh*obj.scale,
                         obj.x*1280+bw*obj.scale/2,obj.y*720]
                visible_box=box
                auto_gun=auto_hands=None
                manual_gun=obj.kind=='person' and obj.action in ('GUN_HOLD','GUN_FIRE') and obj.aim_point is None
                if obj.kind=='person' and obj.aim_point is not None:
                    auto_gun,auto_hands=aimed_gun_drawing(obj.weapon,(obj.aim_point[0]*1280,obj.aim_point[1]*720),obj.aim_direction,
                                                        max(35,min(300,(visible_box[3]-visible_box[1])*.45)),obj.action,action_time)
                fitted_down=obj.kind=='person' and obj.action=='DOWN' and obj.posture_fit
                fitted_seat=obj.kind=='person' and (obj.seated or obj.action in ('SIT','SIT_GESTURE'))
                bound=bound_poses.get(obj.track_id)
                rig_props=bound_person_props(bound,obj.action,obj.action_mirror,obj.weapon) if bound else ()
                object_tags=(kind_tag,'preset-object','skeleton-person') if bound else (kind_tag,'preset-object')
                if clip:
                    from .frame_clipping import FrameLayer,render_extent,clipped_bounds
                    raw=obj.render_bbox or obj.bbox
                    if raw:
                        box=[raw[0]*1280,raw[1]*720,raw[2]*1280,raw[3]*720]
                    if obj.kind=='car':
                        vehicle_art_detail=detail_for_size((box[3]-box[1])*scale,self._detail_levels.get(obj.track_id))
                        vehicle_art=vehicle_drawing(round(obj.yaw,1),round(obj.pitch,1),obj.vehicle_type,rotor,detail=vehicle_art_detail)
                        aspect=vehicle_art.aspect
                    elif obj.kind=='dog':
                        aspect=DOG_ASPECT
                    else:
                        aspect=.82 if obj.seated else PERSON_ASPECT.get(obj.action,.38)
                    if bound:
                        box=bound.frame
                        art_bounds=list(bound.bounds)
                    else:
                        if fitted_down:
                            a,b,c,d=down_bounds(obj.action_mirror);aspect=(c-a)/(d-b)
                        if obj.kind=='person' and not fitted_down and not fitted_seat:
                            # A first-seen upper-body fragment still gets a full
                            # predefined body; hidden legs are not compressed.
                            box[3]=max(box[3],box[1]+(box[2]-box[0])/aspect)
                        if not fitted_seat:box=render_extent(box,visible_box,aspect)
                        tight_bounds=box
                        if fitted_down:box=down_render_box(box,obj.action_mirror)
                        elif obj.kind=='person' and obj.action in ('FALL','DOWN'):box=fallen_box(box,obj.action_mirror)
                        if manual_gun:box=combat_render_box(box,obj.action_mirror)
                        art_bounds=list(tight_bounds if fitted_down else box)
                    animated=obj.kind=='person' and not bound and obj.action in ANIMATED_ACTIONS
                    key=(obj,w,h,has_background,rotor,action_time if animated else 0,bool(bound))
                    screen_props=auto_gun or rig_props
                    if screen_props:
                        xs=[v for p in screen_props for v in p.points[::2]];ys=[v for p in screen_props for v in p.points[1::2]]
                        art_bounds=[min(art_bounds[0],min(xs)),min(art_bounds[1],min(ys)),max(art_bounds[2],max(xs)),max(art_bounds[3],max(ys))]
                    viewport=(ox,oy,1280*scale,720*scale)
                    bounds=clipped_bounds(pts(art_bounds),viewport)
                    detail=detail_for_size((box[3]-box[1])*scale,self._detail_levels.get(obj.track_id))
                    self._detail_levels[obj.track_id]=detail
                    gun_points=pts([v for shape in auto_gun for v in shape.points]) if auto_gun else ()
                    rig_points=pts([v for p in bound.joints if p.confidence>.25 for v in (p.x,p.y)]+[v for shape in rig_props for v in shape.points]) if bound else ()
                    sprite_key=preset_key(obj,pts(box),bounds,scale,detail,rotor,action_time,
                                          animated,has_background,gun_points,rig_points)
                    cached=self._sprite_cache.get(sprite_key) if not debug else None
                    if cached is not None:
                        photo,local_pose=cached
                        next_cache[key]=(photo,bounds)
                        self._images.append(photo)
                        self.create_image(bounds[0],bounds[1],image=photo,anchor='nw',tags=object_tags)
                        self.hitboxes.append((*bounds,obj.track_id))
                        if local_pose:
                            self._poses[obj.track_id]=([( (x+bounds[0]-ox)/scale,(y+bounds[1]-oy)/scale,c)
                                                       for x,y,c in local_pose],now)
                        if obj.primary:
                            text((box[0]+box[2])/2,max(14,box[1]-14),'主角',14,CYAN)
                        continue
                    layer=FrameLayer(pts(art_bounds),viewport,opaque_light=obj.action in ('GUN_HOLD','GUN_FIRE') or obj.vehicle_type in ('truck','boat','motorcycle','helicopter'),halo=has_background)
                    if not layer.pixels.size:
                        next_cache[key]=(None,layer.bounds)
                        layer=None
                        continue
                if not clip:
                    if bound:box=bound.frame
                    elif fitted_down:box=down_render_box(box,obj.action_mirror)
                    elif obj.kind=='person' and obj.action in ('FALL','DOWN'):box=fallen_box(box,obj.action_mirror)
                    if manual_gun:box=combat_render_box(box,obj.action_mirror)
                bx,by,ex,ey=box
                detail=detail_for_size((ey-by)*scale,self._detail_levels.get(obj.track_id))
                self._detail_levels[obj.track_id]=detail
                color=CYAN if obj.primary else '#9baab4' if obj.predicted else "#34495e"
                fine_scale=.72 if detail=='compact' else 1.0
                if obj.kind in ('car','dog'):
                    if obj.kind=='dog':
                        shapes,aspect=dog_drawing(obj.action_mirror,detail=detail),DOG_ASPECT
                    else:
                        drawing=vehicle_art if vehicle_art is not None and vehicle_art_detail==detail else vehicle_drawing(round(obj.yaw,1),round(obj.pitch,1),obj.vehicle_type,rotor,detail=detail)
                        shapes,aspect=drawing.shapes,drawing.aspect
                    height=min(ey-by,(ex-bx)/aspect)
                    width=height*aspect
                    left=(bx+ex-width)/2
                    top=ey-height
                    for shape in shapes:
                        coords=[left+v*width if i%2==0 else top+v*height for i,v in enumerate(shape.points)]
                        if shape.kind=="line":
                            line(coords,fill=color if obj.primary or obj.predicted else shape.stroke,width=max(.8,shape.width*scale*fine_scale),tags=kind_tag)
                        else:
                            paint=oval if shape.kind=='oval' else polygon
                            paint(coords,fill=shape.fill,outline=color if obj.primary or obj.predicted else shape.stroke,
                                dash=(4,3) if obj.predicted else (),width=max(.8,shape.width*scale*fine_scale),tags=kind_tag)
                elif manual_gun:
                    drawing=combat_drawing(obj.action,action_time,obj.weapon,obj.combat_yaw,mirror=obj.action_mirror)
                    for shape in drawing.shapes:
                        coords=[bx+v*(ex-bx) if i%2==0 else by+v*(ey-by) for i,v in enumerate(shape.points)]
                        tags=('person','preset-prop','muzzle-flash') if shape.role=='muzzle-flash' else ('person','preset-prop')
                        if shape.kind=='line':
                            line(coords,fill=shape.stroke,width=max(1,shape.width*scale),tags=tags)
                        else:
                            paint=oval if shape.kind=='oval' else polygon
                            paint(coords,fill=shape.fill,outline=shape.stroke,width=max(1,shape.width*scale),tags=tags)
                else:
                    # Keypoint directions may articulate the fixed figure;
                    # missing evidence retains complete fallback segments.
                    if bound:target=[(p.x,p.y,p.confidence) for p in bound.joints]
                    else:
                        joints=person_pose(obj.action,action_time,obj.action_mirror,obj.seated,obj.seat_mirror)
                        target=[(bx+p.x*(ex-bx),by+p.y*(ey-by),p.confidence) for p in joints]
                    person_tags=('person','skeleton-person') if bound else 'person'
                    if auto_hands:
                        for shoulder,elbow,hand,point in ((11,13,15,auto_hands[0]),(12,14,16,auto_hands[1])):
                            sx,sy,_=target[shoulder];hx,hy=point
                            distance=math.hypot(hx-sx,hy-sy);bend=max(0,(ey-by)*.15-distance*.15)
                            target[hand]=(hx,hy,1);target[elbow]=((sx+hx)/2,(sy+hy)/2+bend,1)
                    self._poses[obj.track_id]=(target,now)
                    def visible(i):
                        return target[i][2]>.25
                    if all(visible(i) for i in (11,12,23,24)):
                        torso=[v for i in (11,12,24,23) for v in target[i][:2]]
                        polygon(torso,fill='' if auto_hands else '#e3ecef',outline=color,width=max(.8,scale*(1.0 if detail=='compact' else 1.7)),tags=person_tags)
                    for a,b in BODY_LINKS:
                        if visible(a) and visible(b):
                            uncertain=min(target[a][2],target[b][2])<.45
                            line([*target[a][:2],*target[b][:2]],fill="#a2b0bb" if uncertain else color,
                                 width=max(.8,(1.2 if detail=='compact' else 2 if uncertain else 3)*scale),dash=(4,3) if uncertain else (),capstyle=tk.ROUND,tags=person_tags)
                    for i in ((13,14,15,16,23,24,25,26,27,28) if detail!='compact' else ()):
                        if visible(i):
                            x,y,_=target[i];r=max(1.8,2.7*scale)/scale
                            oval([x-r,y-r,x+r,y+r],fill=BG,outline=color,width=max(1,1.4*scale),tags=person_tags)
                    if visible(0) or (visible(11) and visible(12)):
                        if visible(0):
                            hx,hy=target[0][:2]
                        else:
                            hx=(target[11][0]+target[12][0])/2
                            hy=(target[11][1]+target[12][1])/2-(ey-by)*.14
                        radius=max(2.5/scale,bound.head_radius if bound else (ey-by)*.065)
                        if visible(11) and visible(12):
                            neckx=(target[11][0]+target[12][0])/2
                            necky=(target[11][1]+target[12][1])/2
                            length=max(1,math.hypot(neckx-hx,necky-hy))
                            line([hx+(neckx-hx)*radius/length,hy+(necky-hy)*radius/length,neckx,necky],fill=color,width=max(.8,(1.1 if detail=='compact' else 2.4)*scale),tags=person_tags)
                        oval([hx-radius,hy-radius*1.15,hx+radius,hy+radius*1.15],
                                         fill=BG,outline=color,width=max(.8,(1.1 if detail=='compact' else 2.4)*scale),tags=person_tags)
                        if detail!='compact' and target[2][2]>.45 and target[5][2]>.45:
                            for i in (2,5):
                                xx,yy=target[i][:2]
                                oval([xx-1.2,yy-1.2,xx+1.2,yy+1.2],fill=color,outline="",tags=person_tags)
                    for shape in (rig_props if bound else auto_gun if auto_gun else person_props(obj.action,action_time,obj.action_mirror,obj.weapon)):
                        coords=list(shape.points) if bound or auto_gun else [bx+v*(ex-bx) if i%2==0 else by+v*(ey-by) for i,v in enumerate(shape.points)]
                        if shape.kind=='line':
                            line(coords,fill=color if obj.primary else shape.stroke,width=max(1,shape.width*scale),tags='preset-prop')
                        else:
                            polygon(coords,fill=shape.fill,outline=color if obj.primary else shape.stroke,width=max(1,shape.width*scale),tags='preset-prop')
                if clip:
                    encoded=layer.png()
                    bounds=layer.bounds
                    photo=tk.PhotoImage(data=encoded,master=self) if encoded else None
                    next_cache[key]=(photo,bounds)
                    if photo is not None and sprite_key is not None:
                        target_pose=self._poses.get(obj.track_id,([],0))[0] if obj.kind=='person' and not manual_gun else ()
                        local_pose=tuple((x*scale+ox-bounds[0],y*scale+oy-bounds[1],c) for x,y,c in target_pose)
                        self._sprite_cache.put(sprite_key,(photo,local_pose),
                                               max(0,bounds[2]-bounds[0])*max(0,bounds[3]-bounds[1])*4)
                    layer=None
                    if photo is not None:
                        self._images.append(photo)
                        self.create_image(bounds[0],bounds[1],image=photo,anchor='nw',tags=object_tags)
                        self.hitboxes.append((*bounds,obj.track_id))
                if debug or gallery:
                    if debug and not gallery:
                        self.create_rectangle(*pts(box),outline="#b4c1cc",dash=(3,4),tags="debug-box")
                    label=obj.track_id if gallery else f"{obj.track_id} · {obj.action}" if obj.kind=="person" else f"{obj.track_id} · 狗" if obj.kind=='dog' else f"{obj.track_id} · {obj.yaw:.0f}°"
                    text((bx+ex)/2,by-13,label,13,color)
                elif obj.primary:
                    text((bx+ex)/2,max(14,by-14),'主角 · 短时估计' if obj.predicted else '主角',14,CYAN)
                if not clip:
                    self.hitboxes.append((*pts(bound.bounds if bound else box),obj.track_id))
        if scene and not gallery:
            occupied=[(ox+r.box[0]*1280*scale,oy+r.box[1]*720*scale,ox+r.box[2]*1280*scale,oy+r.box[3]*720*scale) for r in scene.texts]
            for obj in scene.entities:
                if not obj.action_caption or obj.predicted or obj.kind!='person':continue
                a,b,c,d=obj.render_bbox or obj.bbox or (obj.x-.04,obj.y-.2,obj.x+.04,obj.y)
                if c<=0 or a>=1 or d<=0 or b>=1:continue
                font_size=max(12,round(18*scale))
                font=self._caption_fonts.get(font_size)
                if font is None:
                    font=tkfont.Font(root=self,family='Microsoft YaHei UI',size=-font_size);self._caption_fonts[font_size]=font
                tw,th=font.measure(obj.action_caption)+12,font.metrics('linespace')+6
                x=max(ox+2,min(ox+1280*scale-tw-2,ox+(a+c)*640*scale-tw/2))
                y=max(oy+2,min(oy+720*scale-th-2,oy+b*720*scale-th-5))
                for _ in range(8):
                    if not any(x<r and x+tw>l and y<bottom and y+th>top for l,top,r,bottom in occupied):break
                    y+=th+3
                    if y+th>oy+720*scale:y=oy+2;break
                occupied.append((x,y,x+tw,y+th))
                self.create_rectangle(x,y,x+tw,y+th,fill='#edf6fa',outline='#89a3b4',tags='action-caption-background')
                self.create_text(x+6,y+3,anchor='nw',text=obj.action_caption,font=font,fill='#23465b',tags='action-caption')
            for region in scene.texts:
                a,b,c,d=region.box
                left,top=ox+a*1280*scale,oy+b*720*scale
                width,height=(c-a)*1280*scale,(d-b)*720*scale
                size=max(1,min(144,int(height*.9)))
                while True:
                    font=self._text_fonts.get(size)
                    if font is None:
                        font=tkfont.Font(root=self,family='Microsoft YaHei UI',size=-size)
                        self._text_fonts[size]=font
                    if size<=1 or (font.measure(region.text)<=width and font.metrics('linespace')<=height):break
                    size-=1
                tw,th=font.measure(region.text),font.metrics('linespace')
                y=max(oy,top+(height-th)/2)
                self.create_rectangle(left,y,left+tw,y+th,fill=BG,outline='',tags='ocr-text-background')
                self.create_text(left,y,text=region.text,font=font,anchor='nw',fill='#22374d',tags='ocr-text')
        self._layer_cache=next_cache
        self._poses={key:value for key,value in self._poses.items() if key in active}
        self._detail_levels={key:value for key,value in self._detail_levels.items() if key in active}
        if debug and not gallery:
            text(20,699,"模拟数据" if simulated else "画面分析估计 · 手动选项可覆盖视角与动作",12,anchor="w")
        if overlay:
            text(640,340,overlay,25,"#63778b")
