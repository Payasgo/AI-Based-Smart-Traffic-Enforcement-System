"""One independent YOLO/tracking pipeline per camera."""
from dataclasses import dataclass
import queue, threading
from datetime import datetime, timezone

@dataclass(frozen=True)
class InferenceResult:
    camera_id: str
    timestamp: object
    frame: object
    tracked_vehicles: dict
    sequence: int

class CameraInferenceWorker:
    def __init__(self,camera_id,stream,tracker,result_queue_size=2,clock=None,on_result=None):
        self.camera_id,self.stream,self.tracker=camera_id,stream,tracker
        self.clock=clock or (lambda:datetime.now(timezone.utc)); self.on_result=on_result
        self.results=queue.Queue(maxsize=result_queue_size); self._stop=threading.Event(); self._thread=None
        self.last_error=None; self.error_count=0; self.last_error_at=None
        self.processed_frames=0; self.last_success_at=None; self.last_sequence=None
    @property
    def is_running(self): return self._thread is not None and self._thread.is_alive()
    def start(self):
        if self.is_running:return
        self._stop.clear(); self._thread=threading.Thread(target=self._run,name=f"inference-{self.camera_id}",daemon=True); self._thread.start()
    def read_result(self,timeout=0.0):
        try:item=self.results.get(timeout=timeout)
        except queue.Empty:return None
        while True:
            try:item=self.results.get_nowait()
            except queue.Empty:return item
    def stop(self,timeout=5.0):
        self._stop.set()
        if self._thread and self._thread.is_alive():self._thread.join(timeout)
        if self._thread and self._thread.is_alive():raise TimeoutError(f"Inference worker {self.camera_id} did not stop")
    def _publish(self,item):
        try:self.results.put_nowait(item)
        except queue.Full:
            try:self.results.get_nowait()
            except queue.Empty:pass
            try:self.results.put_nowait(item)
            except queue.Full:pass
    def _run(self):
        while not self._stop.is_set():
            try:
                packet=self.stream.read(timeout=0.2)
                if packet is None:continue
                tracks=self.tracker.update(packet.frame,packet.timestamp)
                result=InferenceResult(self.camera_id,packet.timestamp or self.clock(),packet.frame,tracks,packet.sequence)
                if self.on_result is not None:self.on_result(result)
                self.processed_frames+=1; self.last_sequence=packet.sequence
                self.last_success_at=self.clock().isoformat(); self.last_error=None
                self._publish(result)
            except Exception as exc:
                self.last_error=f"{type(exc).__name__}: {exc}"; self.last_error_at=self.clock().isoformat(); self.error_count+=1
