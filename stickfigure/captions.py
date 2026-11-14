"""Short per-person action-change notices, separate from source OCR."""
from dataclasses import replace

CAPTIONS={'WALK':'行走','RUN':'奔跑','RAISE':'抬手','CROUCH':'下蹲','SIT':'坐姿',
    'WAVE':'挥手','POINT':'指向','GESTURE':'交谈手势','HAND_FACE':'手靠面部',
    'PHONE_LOOK':'玩手机','PHONE':'打电话','DRINK':'举杯','ARMS_FORWARD':'双臂前伸',
    'SIT_GESTURE':'坐姿交流','HUG':'搂抱','DANCE':'舞动','LIFT':'举重','ROW':'划桨',
    'CLIMB':'攀爬','PUNCH':'挥拳','GUN_FIRE':'开枪','HIT':'中弹','FALL':'倒下','DOWN':'倒地'}

class ActionCaptions:
    def __init__(self):self.reset()
    def reset(self):self.epoch=None;self.timestamp=None;self.tracks={}
    def apply(self,scene,enabled=True,scope=None):
        if scene is None:return None
        t=scene.animation_time
        epoch=scene.scene_epoch if scope is None else scope
        if self.epoch!=epoch or self.timestamp is None or t<self.timestamp-.02:
            self.reset();self.epoch=epoch
        self.timestamp=t;current={};entities=[]
        for actor in scene.entities:
            if actor.kind!='person' or actor.predicted:
                entities.append(replace(actor,action_caption=''));continue
            previous=self.tracks.get(actor.track_id)
            key=(actor.action,actor.action_manual,actor.seated)
            text=CAPTIONS.get(actor.action,'')
            if actor.seated and actor.action not in ('SIT','SIT_GESTURE'):
                text='坐姿·'+text if text else '坐姿'
            if text and actor.action_manual:text='手动·'+text
            if previous is None:previous=(key,'',t)
            if text and (previous[0]!=key or actor.track_id not in self.tracks):
                previous=(key,text,t)
            else:previous=(key,previous[1],previous[2])
            current[actor.track_id]=previous
            caption=previous[1] if enabled and 0<=t-previous[2]<2 else ''
            entities.append(replace(actor,action_caption=caption))
        self.tracks=current
        return replace(scene,entities=tuple(entities))
