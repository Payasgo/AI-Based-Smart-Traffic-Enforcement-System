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
    allowed = {"speed_limit_kmh","speed_line_1_y","speed_line_2_y","line_distance_meters","speed_calibration_verified","wrong_way_direction","road_rule_zones","road_rule_lines","traffic_stop_line_y","traffic_signal_roi","calibration_version","jurisdiction","lane_polygons","indicator_detection"}
    unknown = set(cal)-allowed
    if unknown: raise ValueError(f"unknown calibration keys: {', '.join(sorted(unknown))}")
    if "speed_limit_kmh" in cal and (not isinstance(cal["speed_limit_kmh"],(int,float)) or cal["speed_limit_kmh"]<=0): raise ValueError("calibration.speed_limit_kmh must be > 0")
    for key in ("speed_line_1_y", "speed_line_2_y"):
        value = cal.get(key)
        if value is not None and (not isinstance(value, (int, float)) or not 0 <= value <= 1):
            raise ValueError(f"calibration.{key} must be normalized to 0..1")
    if "speed_line_1_y" in cal and "speed_line_2_y" in cal and cal["speed_line_1_y"] == cal["speed_line_2_y"]:
        raise ValueError("speed measurement lines must be at different positions")
    distance = cal.get("line_distance_meters")
    if distance is not None and (not isinstance(distance, (int, float)) or distance <= 0):
        raise ValueError("calibration.line_distance_meters must be > 0")
    if "speed_calibration_verified" in cal and not isinstance(cal["speed_calibration_verified"], bool):
        raise ValueError("calibration.speed_calibration_verified must be a boolean")
    if cal.get("speed_calibration_verified") and (distance is None or "speed_line_1_y" not in cal or "speed_line_2_y" not in cal or not cal.get("calibration_version")):
        raise ValueError("verified speed calibration requires speed_line_1_y, speed_line_2_y, line_distance_meters and calibration_version")
    lane_polygons = cal.get("lane_polygons", [])
    if not isinstance(lane_polygons, list): raise ValueError("calibration.lane_polygons must be a list")
    seen_lane_ids = set()
    for i, lane in enumerate(lane_polygons):
        if not isinstance(lane, dict) or not isinstance(lane.get("lane_id"), str) or not lane["lane_id"].strip():
            raise ValueError(f"calibration.lane_polygons[{i}] requires a lane_id")
        if lane["lane_id"] in seen_lane_ids: raise ValueError("calibration.lane_polygons lane_id values must be unique")
        seen_lane_ids.add(lane["lane_id"])
        if not isinstance(lane.get("polygon"), list) or len(lane["polygon"]) < 3:
            raise ValueError(f"calibration.lane_polygons[{i}].polygon needs at least 3 points")
        for point in lane["polygon"]: _point(point, f"calibration.lane_polygons[{i}].polygon")
    indicator = cal.get("indicator_detection")
    if indicator is not None:
        if not isinstance(indicator, dict): raise ValueError("calibration.indicator_detection must be an object")
        allowed_indicator = {"enabled", "active_ratio", "min_samples", "history_size", "threshold", "hue_low", "hue_high", "saturation_min", "value_min", "visibility_value_min"}
        unknown_indicator = set(indicator) - allowed_indicator
        if unknown_indicator: raise ValueError(f"unknown indicator_detection keys: {', '.join(sorted(unknown_indicator))}")
        if "enabled" in indicator and not isinstance(indicator["enabled"], bool): raise ValueError("indicator_detection.enabled must be a boolean")
        if "active_ratio" in indicator and (not isinstance(indicator["active_ratio"], (int, float)) or not 0 < indicator["active_ratio"] <= 1): raise ValueError("indicator_detection.active_ratio must be in (0, 1]")
        if "threshold" in indicator and (not isinstance(indicator["threshold"], (int, float)) or not 0 < indicator["threshold"] <= 1): raise ValueError("indicator_detection.threshold must be in (0, 1]")
        samples = indicator.get("min_samples", 5); history = indicator.get("history_size", 12)
        if not isinstance(samples, int) or not isinstance(history, int) or samples < 1 or history < samples: raise ValueError("indicator_detection requires history_size >= min_samples >= 1")
        for key in ("hue_low", "hue_high"):
            if key in indicator and (not isinstance(indicator[key], int) or not 0 <= indicator[key] <= 179): raise ValueError(f"indicator_detection.{key} must be an integer in 0..179")
        if indicator.get("hue_low", 8) >= indicator.get("hue_high", 35): raise ValueError("indicator_detection hue_low must be less than hue_high")
        for key in ("saturation_min", "value_min", "visibility_value_min"):
            if key in indicator and (not isinstance(indicator[key], int) or not 0 <= indicator[key] <= 255): raise ValueError(f"indicator_detection.{key} must be an integer in 0..255")
    direction=cal.get("wrong_way_direction")
    if direction is not None and (not isinstance(direction,(list,tuple)) or len(direction)!=2 or not all(isinstance(v,(int,float)) for v in direction) or (direction[0]==0 and direction[1]==0)): raise ValueError("calibration.wrong_way_direction must be a non-zero [x, y] vector")
    stop=cal.get("traffic_stop_line_y")
    if stop is not None and (not isinstance(stop,(int,float)) or not 0<=stop<=1): raise ValueError("calibration.traffic_stop_line_y must be normalized to 0..1")
    signal_roi = cal.get("traffic_signal_roi")
    if signal_roi is not None and (not isinstance(signal_roi, list) or len(signal_roi) != 4 or not all(isinstance(v, (int,float)) and 0 <= v <= 1 for v in signal_roi) or signal_roi[0] >= signal_roi[2] or signal_roi[1] >= signal_roi[3]):
        raise ValueError("calibration.traffic_signal_roi must be normalized [x1,y1,x2,y2]")
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
