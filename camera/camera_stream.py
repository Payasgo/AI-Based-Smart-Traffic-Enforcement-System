"""Threaded capture worker. Drops stale frames instead of building latency."""
from dataclasses import dataclass
from datetime import datetime, timezone
import queue
import threading

@dataclass(frozen=True)
class FramePacket:
    camera_id: str
    timestamp: datetime
    frame: object
    sequence: int

class CameraStream:
    def __init__(self, config, capture_factory=None):
        self.config = config
        self._capture_factory = capture_factory or self._default_capture_factory
        self._frames = queue.Queue(maxsize=config.queue_size)
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._opened = False
        self._last_error = None
        self._sequence = 0

    @staticmethod
    def _default_capture_factory(source):
        import cv2
        return cv2.VideoCapture(source)

    @property
    def is_running(self): return self._thread is not None and self._thread.is_alive()
    @property
    def is_opened(self):
        with self._lock: return self._opened
    @property
    def last_error(self):
        with self._lock: return self._last_error

    def start(self):
        if self.is_running: return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, name=f"camera-{self.config.camera_id}", daemon=True)
        self._thread.start()

    def read(self, timeout=1.0):
        try: packet = self._frames.get(timeout=timeout)
        except queue.Empty: return None
        while True:
            try: packet = self._frames.get_nowait()
            except queue.Empty: return packet

    def stop(self, timeout=5.0):
        self._stop_event.set()
        if self._thread and self._thread.is_alive(): self._thread.join(timeout)
        if self._thread and self._thread.is_alive(): raise TimeoutError(f"Camera {self.config.camera_id} did not stop")

    def _status(self, opened=None, error=None):
        with self._lock:
            if opened is not None: self._opened = opened
            self._last_error = error

    def _publish(self, packet):
        try: self._frames.put_nowait(packet)
        except queue.Full:
            try: self._frames.get_nowait()
            except queue.Empty: pass
            try: self._frames.put_nowait(packet)
            except queue.Full: pass

    def _capture_loop(self):
        while not self._stop_event.is_set():
            capture = None
            try:
                capture = self._capture_factory(self.config.source)
                if not capture.isOpened(): raise RuntimeError("Video source could not be opened")
                self._status(opened=True, error=None)
                try:
                    import cv2
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                    capture.set(cv2.CAP_PROP_FPS, self.config.fps)
                except ImportError: pass
                while not self._stop_event.is_set():
                    ok, frame = capture.read()
                    if not ok or frame is None: raise RuntimeError("Frame capture failed")
                    self._sequence += 1
                    self._publish(FramePacket(self.config.camera_id, datetime.now(timezone.utc), frame, self._sequence))
            except Exception as exc:
                self._status(opened=False, error=str(exc))
                if not self.config.reconnect or self._stop_event.is_set(): break
                self._stop_event.wait(self.config.reconnect_delay_seconds)
            finally:
                self._status(opened=False)
                if capture is not None:
                    try: capture.release()
                    except Exception: pass
