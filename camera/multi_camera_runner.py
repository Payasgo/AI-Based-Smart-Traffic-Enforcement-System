"""Coordinates capture, per-camera inference and per-camera detector suites."""
import threading

from camera.camera_manager import CameraManager
from camera.inference_worker import CameraInferenceWorker
from detectors.vehicle_tracker import VehicleTracker


class MultiCameraRunner:
    def __init__(self, camera_manager, tracker_factory=VehicleTracker,
                 result_queue_size=2, enable_detection_pipeline=True,
                 pipeline_factory=None):
        self.camera_manager = camera_manager
        self.workers = {}
        self.pipelines = {}
        self._stop = threading.Event()

        shared_config = self._camera_config(None)
        if enable_detection_pipeline:
            from utils.evidence_logger import EvidenceLogger
            from utils.alert_system import AlertSystem
            logger = EvidenceLogger(shared_config.LOG_DIR, shared_config.EVIDENCE_DIR)
            alert_system = AlertSystem(shared_config)

        for camera_id, stream in camera_manager.streams.items():
            camera_config = self._camera_config(stream.config)
            tracker = tracker_factory(camera_config)
            callback = None
            if enable_detection_pipeline:
                if pipeline_factory is None:
                    from camera.detection_pipeline import CameraDetectionPipeline
                    factory = CameraDetectionPipeline
                else:
                    factory = pipeline_factory
                pipeline = factory(camera_config, logger, alert_system)
                self.pipelines[camera_id] = pipeline
                callback = lambda result, p=pipeline: p.process(
                    result.frame, result.tracked_vehicles, result.timestamp
                )
            self.workers[camera_id] = CameraInferenceWorker(
                camera_id, stream, tracker, result_queue_size=result_queue_size,
                on_result=callback,
            )

    @staticmethod
    def _camera_config(camera_config):
        """Create an independent Settings object for a camera."""
        from config.settings import Settings
        config = Settings()
        if camera_config is not None:
            config.YOLO_MODEL_PATH = getattr(
                camera_config, "model_path", config.YOLO_MODEL_PATH
            )
            config.FRAME_WIDTH = camera_config.width
            config.FRAME_HEIGHT = camera_config.height
            # Optional per-camera overrides are accepted from extended config
            # objects without requiring them for existing JSON configurations.
            for name in (
                "SPEED_LIMIT_KMH", "WRONG_WAY_DIRECTION_X",
                "WRONG_WAY_DIRECTION_Y", "ROAD_RULE_ZONES",
                "ROAD_RULE_LINES", "TRAFFIC_STOP_LINE_Y",
            ):
                value = getattr(camera_config, name.lower(), None)
                if value is not None:
                    setattr(config, name, value)
        return config

    @classmethod
    def from_json(cls, path, tracker_factory=VehicleTracker,
                  enable_detection_pipeline=True, pipeline_factory=None):
        manager = CameraManager.from_json(path)
        return cls(
            manager, tracker_factory=tracker_factory,
            enable_detection_pipeline=enable_detection_pipeline,
            pipeline_factory=pipeline_factory,
        )

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
        """Return latest processed result from each camera, keyed by ID."""
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
