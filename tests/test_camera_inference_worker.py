import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera.inference_worker import CameraInferenceWorker
from camera.multi_camera_runner import MultiCameraRunner

class FakeStream:
    def __init__(self, packets): self.packets = list(packets)
    def read(self, timeout=0.0):
        if self.packets: return self.packets.pop(0)
        time.sleep(min(timeout, 0.01)); return None

class FakeTracker:
    def __init__(self, marker): self.marker = marker; self.calls = 0
    def update(self, frame, timestamp):
        self.calls += 1
        return {self.marker: {"centroid": (1, 2), "bbox": (0, 0, 2, 4)}}

class FakeCameraManager:
    def __init__(self, streams): self.streams = streams; self.started = False; self.stopped = False
    def start(self): self.started = True
    def stop(self): self.stopped = True
    def health(self): return {key: {"running": True, "opened": True, "last_error": None} for key in self.streams}


def packet(camera_id, sequence=1):
    return SimpleNamespace(camera_id=camera_id, timestamp=datetime.now(timezone.utc),
                           frame=object(), sequence=sequence)

def test_inference_worker_uses_its_own_tracker_and_emits_camera_tagged_result():
    stream, tracker = FakeStream([packet("A")]), FakeTracker("track-A")
    worker = CameraInferenceWorker("A", stream, tracker)
    worker.start()
    deadline = time.time() + 1
    result = None
    while time.time() < deadline and result is None:
        result = worker.read_result(timeout=0.02)
    worker.stop()
    assert result.camera_id == "A"
    assert result.tracked_vehicles.keys() == {"track-A"}
    assert tracker.calls == 1


def test_multi_camera_runner_creates_distinct_tracker_instances():
    streams = {"A": FakeStream([]), "B": FakeStream([])}
    manager = FakeCameraManager(streams)
    created = []
    def factory(config):
        tracker = FakeTracker(config.YOLO_MODEL_PATH)
        created.append(tracker)
        return tracker
    runner = MultiCameraRunner(manager, tracker_factory=factory)
    assert len(created) == 2
    assert created[0] is not created[1]
    assert set(runner.workers) == {"A", "B"}
    runner.start()
    assert manager.started
    runner.stop()
    assert manager.stopped
