"""Validated configuration for independent camera streams."""
from dataclasses import dataclass
from typing import Union
CameraSource = Union[int, str]

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

    def __post_init__(self):
        if not self.camera_id.strip(): raise ValueError("camera_id must not be empty")
        if self.role not in {"front", "rear", "overview", "side"}: raise ValueError("invalid camera role")
        if min(self.width, self.height, self.fps, self.queue_size) <= 0: raise ValueError("dimensions, fps and queue_size must be positive")
        if self.reconnect_delay_seconds < 0: raise ValueError("reconnect delay must be >= 0")

    @classmethod
    def from_dict(cls, data):
        values = dict(data)
        source = values.get("source")
        if isinstance(source, str) and source.isdigit(): values["source"] = int(source)
        return cls(**values)
