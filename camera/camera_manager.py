"""Lifecycle manager for independent camera capture workers."""
import json
from pathlib import Path
from camera.camera_config import CameraConfig
from camera.camera_stream import CameraStream

class CameraManager:
    def __init__(self, configs, stream_factory=CameraStream):
        ids = [item.camera_id for item in configs]
        if len(ids) != len(set(ids)): raise ValueError("camera_id values must be unique")
        self.streams = {item.camera_id: stream_factory(item) for item in configs if item.enabled}

    @classmethod
    def from_json(cls, path, stream_factory=CameraStream):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("cameras"), list): raise ValueError("config must contain a cameras list")
        return cls([CameraConfig.from_dict(item) for item in data["cameras"]], stream_factory)

    def start(self):
        started = []
        try:
            for stream in self.streams.values():
                stream.start(); started.append(stream)
        except Exception:
            for stream in started: stream.stop()
            raise

    def read(self, camera_id, timeout=0.0): return self.streams[camera_id].read(timeout)
    def health(self):
        return {key: {"running": s.is_running, "opened": s.is_opened, "last_error": s.last_error} for key, s in self.streams.items()}
    def stop(self):
        errors = []
        for stream in self.streams.values():
            try: stream.stop()
            except Exception as exc: errors.append(f"{stream.config.camera_id}: {exc}")
        if errors: raise RuntimeError("; ".join(errors))
