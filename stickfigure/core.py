"""Scene protocol, source interface and deterministic demonstration source.

Capture/detection implementations can replace SceneSource without changing UI
or rendering. Positions are normalized screen coordinates, NOT world positions.
"""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Protocol


class RunState(str, Enum):
    STOPPED = "已停止"
    RUNNING = "运行中"
    PAUSED = "已暂停"
    ERROR = "异常占位"
    ENDED = "播放结束"


@dataclass(frozen=True)
class Joint:
    x: float
    y: float
    confidence: float = 1.0


@dataclass(frozen=True)
class Horizon:
    left: float = .5
    right: float = .5
    confidence: float = 0.0
    method: str = "未锁定"


@dataclass(frozen=True)
class RoadGeometry:
    polygons: tuple[tuple[tuple[float,float],...],...] = ()
    coverage: float = 0.0
    confidence: float = 0.0
    left_edge: tuple[tuple[float,float],...] = ()
    right_edge: tuple[tuple[float,float],...] = ()
    driving_view: bool = False
    method: str = '未锁定路缘'


@dataclass(frozen=True)
class BuildingGeometry:
    outlines: tuple[tuple[tuple[float,float],...],...] = ()


@dataclass(frozen=True)
class Entity:
    track_id: str
    kind: str
    x: float
    y: float
    scale: float = 1.0
    action: str = "IDLE"
    primary: bool = False
    confidence: float = 1.0
    bbox: tuple[float,float,float,float] | None = None
    pose: tuple[Joint,...] = ()
    yaw: float = 0.0
    pitch: float = 22.0
    view_confidence: float = 0.0
    predicted: bool = False
    missing_age: float = 0.0
    velocity: tuple[float,float] = (0.0,0.0)
    sample_time: float = 0.0
    render_bbox: tuple[float,float,float,float] | None = None
    action_mirror: bool = False
    weapon: str = 'pistol'
    action_time: float | None = None
    combat_yaw: float = 35.0
    vehicle_type: str = 'car'
    posture_fit: bool = False
    aim_point: tuple[float,float] | None = None
    aim_direction: tuple[float,float] = (1.0,0.0)
    action_caption: str = ''
    action_manual: bool = False
    seated: bool = False
    seat_mirror: bool = False


@dataclass(frozen=True)
class ShadeRegion:
    tone: int
    points: tuple[tuple[float,float],...]
    holes: tuple[tuple[tuple[float,float],...],...] = ()


@dataclass(frozen=True)
class ColorRegion:
    color: str
    points: tuple[tuple[float,float],...]
    holes: tuple[tuple[tuple[float,float],...],...] = ()


@dataclass(frozen=True)
class TextRegion:
    text: str
    confidence: float
    box: tuple[float,float,float,float]


@dataclass(frozen=True)
class Scene:
    frame_id: int
    capture_time: float
    scene_epoch: int
    animation_time: float
    entities: tuple[Entity, ...] = field(default_factory=tuple)
    simulated: bool = True
    notice: str = ""
    horizon: Horizon | None = None
    road: RoadGeometry | None = None
    frame_clipping: bool = False
    buildings: BuildingGeometry | None = None
    texts: tuple[TextRegion,...] = ()
    shading: tuple[ShadeRegion,...] | None = None
    contact_shadows: bool = False
    shadow_density: str = '中等'
    colors: tuple[ColorRegion,...] | None = None
    skeleton_binding: bool = False


class SceneSource(Protocol):
    def start(self) -> None: ...
    def sample(self, dt: float, now: float) -> Scene: ...
    def stop(self) -> None: ...


class DemoSource:
    """Synthetic scene, no capture device, neural model or game connection."""
    def __init__(self):
        self.epoch = 0
        self.time = 0.0
        self.frame = 0
        self.mode = "walk"
        self.npc_count = 3
        self.vehicle_count = 3
        self.primary_id = "player"
        self.started = False

    def start(self):
        self.epoch += 1
        self.time = 0.0
        self.frame = 0
        self.started = True

    def stop(self):
        self.started = False

    def sample(self, dt: float, now: float) -> Scene:
        if not self.started:
            raise RuntimeError("Source is not running")
        self.time += min(max(dt, 0.0), 0.1)
        self.frame += 1
        t = self.time
        objects = []
        if self.mode != "occlusion" or t % 5 < 3.2:
            if self.mode != "drive":
                objects.append(Entity("player", "person", .48 + .085 * math.sin(t * .4), .80,
                                      1.05, "WALK", self.primary_id == "player"))
        for i in range(self.npc_count):
            x = .16 + i * .26 + .035 * math.sin(t * .6 + i)
            y = .59 + (i % 2) * .08
            ident = f"npc-{i+1}"
            objects.append(Entity(ident, "person", x, y, .56 + (i % 2) * .15,
                                  "WALK" if i % 2 == 0 else "IDLE", self.primary_id == ident))
        for i in range(self.vehicle_count):
            ident = f"car-{i+1}"
            x = (.20,.73,.82,.32)[i] + .025 * math.sin(t * .45 + i)
            y = .69 + (i % 2) * .16
            objects.append(Entity(ident, "car", x, y, .7 + (i % 2) * .35,
                                  "DRIVE" if self.mode == "drive" else "IDLE",
                                  (self.mode == "drive" and i == min(1,self.vehicle_count-1)) or self.primary_id == ident,
                                  yaw=(t*12+i*80)%360))
        notice = "遮挡演示：主角周期性隐藏" if self.mode == "occlusion" else ""
        horizon=Horizon(.43+.06*math.sin(t*.25),.43+.06*math.sin(t*.25)+.025*math.sin(t*.18),1,"模拟地平线")
        return Scene(self.frame, now, self.epoch, t, tuple(objects), True, notice,horizon)
