"""Validated configuration for independent camera streams and calibration."""
from dataclasses import dataclass
from typing import Union
CameraSource = Union[int, str]

def _point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(isinstance(v, (int, float)) for v in value):
        raise ValueError(f"{name} must be a numeric [x, y] point")
    if not all(0 <= v <= 1 for v in value):
        raise ValueError(f"{name} coordinates must be normalized to 0..1")

def _validate_calibration(cal):
    if cal is None: return
    if not isinstance(cal, dict): raise ValueError("calibration must be an object")
    allowed = {"speed_limit_kmh","wrong_way_direction","road_rule_zones","road_rule_lines","traffic_stop_line_y","calibration_version","jurisdiction"}
    unknown = set(cal)-allowed
    if unknown: raise ValueError(f"unknown calibration keys: {', '.join(sorted(unknown))}")
    if "speed_limit_kmh" in cal and (not isinstance(cal["speed_limit_kmh"],(int,float)) or cal["speed_limit_kmh"]<=0): raise ValueError("calibration.speed_limit_kmh must be > 0")
    direction=cal.get("wrong_way_direction")
    if direction is not None and (not isinstance(direction,(list,tuple)) or len(direction)!=2 or not all(isinstance(v,(int,float)) for v in direction) or (direction[0]==0 and direction[1]==0)): raise ValueError("calibration.wrong_way_direction must be a non-zero [x, y] vector")
    stop=cal.get("traffic_stop_line_y")
    if stop is not None and (not isinstance(stop,(int,float)) or not 0<=stop<=1): raise ValueError("calibration.traffic_stop_line_y must be normalized to 0..1")
    if cal.get("jurisdiction") not in (None,"ANDHRA_PRADESH","TELANGANA"): raise ValueError("calibration.jurisdiction must be ANDHRA_PRADESH or TELANGANA")
    for i,z in enumerate(cal.get("road_rule_zones",[])):
        if not isinstance(z,dict) or not isinstance(z.get("polygon"),list) or len(z["polygon"])<3: raise ValueError(f"road_rule_zones[{i}].polygon needs at least 3 points")
        for p in z["polygon"]: _point(p,f"road_rule_zones[{i}].polygon")
    for i,line in enumerate(cal.get("road_rule_lines",[])):
        if not isinstance(line,dict): raise ValueError(f"road_rule_lines[{i}] must be an object")
        _point(line.get("start"),f"road_rule_lines[{i}].start"); _point(line.get("end"),f"road_rule_lines[{i}].end")

@dataclass(frozen=True)
class CameraConfig:
    camera_id: str
    source: CameraSource
    role: str = "overview"
    location_id: str = "site-1"
    enabled: bool = True
    width: int = 1280
    height: int = 720
    fps: int = 15
    reconnect: bool = True
    reconnect_delay_seconds: float = 2.0
    queue_size: int = 2
    model_path: str = None
    calibration: dict = None
    def __post_init__(self):
        if not isinstance(self.camera_id,str) or not self.camera_id.strip(): raise ValueError("camera_id must not be empty")
        if self.role not in {"front","rear","overview","side"}: raise ValueError("invalid camera role")
        if min(self.width,self.height,self.fps,self.queue_size)<=0: raise ValueError("dimensions, fps and queue_size must be positive")
        if self.reconnect_delay_seconds<0: raise ValueError("reconnect delay must be >= 0")
        _validate_calibration(self.calibration)
    @classmethod
    def from_dict(cls,data):
        values=dict(data); source=values.get("source")
        if isinstance(source,str) and source.isdigit(): values["source"]=int(source)
        return cls(**values)
