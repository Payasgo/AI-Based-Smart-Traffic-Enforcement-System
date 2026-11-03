"""Coordinates camera capture and per-camera YOLO inference workers."""
import threading
from camera.camera_manager import CameraManager
from camera.inference_worker import CameraInferenceWorker
from detectors.vehicle_tracker import VehicleTracker

class MultiCameraRunner:
    def __init__(self, camera_manager, tracker_factory=VehicleTracker,
                 result_queue_size=2):
        self.camera_manager = camera_manager
        self.workers = {}
        self._stop = threading.Event()
        for camera_id, stream in camera_manager.streams.items():
            # A fresh tracker/model per camera is essential for independent IDs
            # and safe ownership of temporal state.
            tracker = tracker_factory(self._camera_config(stream.config))
            self.workers[camera_id] = CameraInferenceWorker(
                camera_id, stream, tracker, result_queue_size=result_queue_size)

    @staticmethod
    def _camera_config(camera_config):
        """Build a lightweight Settings-compatible view for VehicleTracker."""
        from config.settings import Settings
        config = Settings()
        config.YOLO_MODEL_PATH = getattr(camera_config, "model_path", config.YOLO_MODEL_PATH)
        return config

    @classmethod
    def from_json(cls, path, tracker_factory=VehicleTracker):
        manager = CameraManager.from_json(path)
        return cls(manager, tracker_factory=tracker_factory)

    def start(self):
        self._stop.clear()
        self.camera_manager.start()
        started = []
        try:
            for worker in self.workers.values():
                worker.start()
                started.append(worker)
        except Exception:
            for worker in started:
                worker.stop()
            self.camera_manager.stop()
            raise

    def read_results(self, timeout=0.0):
        """Return the latest available result from each camera, keyed by ID."""
        output = {}
        for camera_id, worker in self.workers.items():
            result = worker.read_result(timeout=timeout)
            if result is not None:
                output[camera_id] = result
        return output

    def health(self):
        camera_health = self.camera_manager.health()
        return {
            camera_id: {
                **camera_health[camera_id],
                "inference_running": worker.is_running,
                "processed_frames": worker.processed_frames,
                "inference_error": worker.last_error,
            }
            for camera_id, worker in self.workers.items()
        }

    def stop(self):
        errors = []
        for worker in self.workers.values():
            try:
                worker.stop()
            except Exception as exc:
                errors.append(str(exc))
        try:
            self.camera_manager.stop()
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
