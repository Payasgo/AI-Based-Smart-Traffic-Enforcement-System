import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera.inference_worker import CameraInferenceWorker


class Stream:
    def __init__(self, packet): self.packet = packet
    def read(self, timeout=0.0):
        if self.packet is None:
            time.sleep(min(timeout, 0.01))
            return None
        packet, self.packet = self.packet, None
        return packet


class Tracker:
    def update(self, frame, timestamp):
        return {1: {"centroid": (1, 1), "bbox": (0, 0, 2, 2)}}


def test_on_result_pipeline_runs_before_result_is_published():
    frame = {"processed": False}
    packet = SimpleNamespace(
        camera_id="north", timestamp=datetime.now(timezone.utc),
        frame=frame, sequence=1,
    )

    def process(result):
        result.frame["processed"] = True

    worker = CameraInferenceWorker(
        "north", Stream(packet), Tracker(), on_result=process
    )
    worker.start()
    result = None
    deadline = time.time() + 1
    while time.time() < deadline and result is None:
        result = worker.read_result(timeout=0.02)
    worker.stop()

    assert result is not None
    assert result.frame["processed"] is True