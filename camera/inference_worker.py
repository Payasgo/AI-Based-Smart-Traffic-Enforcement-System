"""One independent YOLO/tracking pipeline per camera.

Each worker owns its VehicleTracker instance so track IDs and tracker history
cannot leak across camera views. Capture is owned by CameraManager.
"""
from dataclasses import dataclass
import queue
import threading
from datetime import datetime, timezone

@dataclass(frozen=True)
class InferenceResult:
    camera_id: str
    timestamp: object
    frame: object
    tracked_vehicles: dict
    sequence: int

class CameraInferenceWorker:
    def __init__(self, camera_id, stream, tracker, result_queue_size=2,
                 clock=None, on_result=None):
        self.camera_id = camera_id
        self.stream = stream
        self.tracker = tracker
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.on_result = on_result
        self.results = queue.Queue(maxsize=result_queue_size)
        self._stop = threading.Event()
        self._thread = None
        self.last_error = None
        self.processed_frames = 0

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run,
            name=f"inference-{self.camera_id}", daemon=True)
        self._thread.start()

    def read_result(self, timeout=0.0):
        try:
            item = self.results.get(timeout=timeout)
        except queue.Empty:
            return None
        while True:
            try:
                item = self.results.get_nowait()
            except queue.Empty:
                return item

    def stop(self, timeout=5.0):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
        if self._thread and self._thread.is_alive():
            raise TimeoutError(f"Inference worker {self.camera_id} did not stop")

    def _publish(self, item):
        if self.on_result is not None:
            self.on_result(item)
        try:
            self.results.put_nowait(item)
        except queue.Full:
            try:
                self.results.get_nowait()
            except queue.Empty:
                pass
            try:
                self.results.put_nowait(item)
            except queue.Full:
                pass

    def _run(self):
        while not self._stop.is_set():
            packet = self.stream.read(timeout=0.2)
            if packet is None:
                continue
            try:
                # Tracker state and model instance are private to this camera.
                tracks = self.tracker.update(packet.frame, packet.timestamp)
                self.processed_frames += 1
                self.last_error = None
                self._publish(InferenceResult(
                    camera_id=self.camera_id,
                    timestamp=packet.timestamp or self.clock(),
                    frame=packet.frame,
                    tracked_vehicles=tracks,
                    sequence=packet.sequence,
                ))
            except Exception as exc:
                self.last_error = str(exc)
