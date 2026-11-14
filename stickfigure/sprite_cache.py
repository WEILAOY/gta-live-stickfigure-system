"""Bounded, translation-independent cache of already rasterized preset art."""
from collections import OrderedDict


class SpriteCache:
    def __init__(self, max_bytes=24*1024*1024, max_items=192):
        self.max_bytes=max_bytes
        self.max_items=max_items
        self.items=OrderedDict()
        self.bytes=0
        self.hits=0
        self.misses=0

    def clear(self):
        self.items.clear()
        self.bytes=0

    def get(self,key):
        found=self.items.get(key)
        if found is None:
            self.misses+=1
            return None
        self.items.move_to_end(key)
        self.hits+=1
        return found[0]

    def put(self,key,value,cost):
        if cost>self.max_bytes:return
        old=self.items.pop(key,None)
        if old is not None:self.bytes-=old[1]
        self.items[key]=(value,cost)
        self.bytes+=cost
        while self.bytes>self.max_bytes or len(self.items)>self.max_items:
            _,(_,removed)=self.items.popitem(last=False)
            self.bytes-=removed


def relative_coordinates(coords,origin):
    # Round only floating point arithmetic noise. Fractional-pixel phase is
    # retained, so a translated cached image does not undo subpixel drawing.
    return tuple(round(v-origin[i%2],6) for i,v in enumerate(coords))


def preset_key(obj,box,bounds,scale,detail,rotor,action_time,animated,halo,gun_points=(),rig_points=()):
    return (obj.kind,obj.vehicle_type,obj.action,obj.action_mirror,obj.weapon,
            obj.seated,obj.seat_mirror,round(obj.yaw,1),round(obj.pitch,1),
            obj.combat_yaw,obj.primary,obj.predicted,rotor,
            action_time if animated else 0,detail,round(scale,8),bool(halo),
            bounds[2]-bounds[0],bounds[3]-bounds[1],
            relative_coordinates(box,bounds[:2]),
            relative_coordinates(gun_points,bounds[:2]),
            relative_coordinates(rig_points,bounds[:2]))
