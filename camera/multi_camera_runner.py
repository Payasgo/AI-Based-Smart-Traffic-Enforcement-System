"""Coordinates capture, per-camera inference and detector suites."""
import threading
from camera.camera_manager import CameraManager
from camera.camera_config import CameraConfig
from camera.inference_worker import CameraInferenceWorker
from detectors.vehicle_tracker import VehicleTracker


class MultiCameraRunner:
    def __init__(self,camera_manager,tracker_factory=VehicleTracker,result_queue_size=2,enable_detection_pipeline=False,pipeline_factory=None):
        self.camera_manager=camera_manager;self.workers={};self.pipelines={};self._stop=threading.Event()
        shared=self._camera_config(None)
        if enable_detection_pipeline:
            from utils.evidence_logger import EvidenceLogger
            from utils.alert_system import AlertSystem
            logger=EvidenceLogger(shared.LOG_DIR,shared.EVIDENCE_DIR);alerts=AlertSystem(shared)
        for camera_id,stream in camera_manager.streams.items():
            # CameraStream exposes .config; lightweight test/custom streams may not.
            # Fall back to a safe default config rather than crashing runner construction.
            stream_config=getattr(stream, "config", None)
            if stream_config is None:
                stream_config=CameraConfig(camera_id=camera_id, source=getattr(stream, "source", 0))
            config=self._camera_config(stream_config);tracker=tracker_factory(config);callback=None
            if enable_detection_pipeline:
                if pipeline_factory is None:
                    from camera.detection_pipeline import CameraDetectionPipeline
                    factory=CameraDetectionPipeline
                else:factory=pipeline_factory
                from camera.evidence_context import CameraEvidenceLogger
                scoped=CameraEvidenceLogger(logger,camera_id,config.CAMERA_SITE_ID,config.CALIBRATION_VERSION)
                pipeline=factory(config,scoped,alerts);self.pipelines[camera_id]=pipeline
                callback=lambda result,p=pipeline:p.process(result.frame,result.tracked_vehicles,result.timestamp)
            self.workers[camera_id]=CameraInferenceWorker(camera_id,stream,tracker,result_queue_size=result_queue_size,on_result=callback)

    @staticmethod
    def _camera_config(camera_config):
        from config.settings import Settings
        config=Settings()
        if camera_config is None:return config
        config.YOLO_MODEL_PATH=camera_config.model_path or config.YOLO_MODEL_PATH
        config.FRAME_WIDTH=camera_config.width;config.FRAME_HEIGHT=camera_config.height
        config.CAMERA_ID=camera_config.camera_id;config.CAMERA_SITE_ID=camera_config.location_id
        cal=camera_config.calibration or {}
        config.CALIBRATION_VERSION=cal.get("calibration_version","unversioned")
        jurisdiction=cal.get("jurisdiction",config.TRAFFIC_JURISDICTION)
        if jurisdiction not in config.SUPPORTED_JURISDICTIONS:raise ValueError(f"Unsupported jurisdiction for camera {camera_config.camera_id}: {jurisdiction}")
        config.TRAFFIC_JURISDICTION=jurisdiction
        if "speed_limit_kmh" in cal:config.SPEED_LIMIT_KMH=float(cal["speed_limit_kmh"])
        if "wrong_way_direction" in cal:config.WRONG_WAY_DIRECTION_X,config.WRONG_WAY_DIRECTION_Y=cal["wrong_way_direction"]
        if "road_rule_zones" in cal:config.ROAD_RULE_ZONES=cal["road_rule_zones"]
        if "road_rule_lines" in cal:config.ROAD_RULE_LINES=cal["road_rule_lines"]
        if "traffic_stop_line_y" in cal:config.TRAFFIC_STOP_LINE_Y=float(cal["traffic_stop_line_y"])
        return config

    @classmethod
    def from_json(cls,path,tracker_factory=VehicleTracker,enable_detection_pipeline=True,pipeline_factory=None):
        return cls(CameraManager.from_json(path),tracker_factory=tracker_factory,enable_detection_pipeline=enable_detection_pipeline,pipeline_factory=pipeline_factory)

    def start(self):
        self._stop.clear();self.camera_manager.start();started=[]
        try:
            for worker in self.workers.values():worker.start();started.append(worker)
        except Exception:
            for worker in started:worker.stop()
            self.camera_manager.stop();raise

    def read_results(self,timeout=0.0):
        output={}
        for camera_id,worker in self.workers.items():
            result=worker.read_result(timeout=timeout)
            if result is not None:output[camera_id]=result
        return output

    def health(self):
        states=self.camera_manager.health()
        return {key:{**states[key],"inference_running":w.is_running,"processed_frames":w.processed_frames,"inference_error":w.last_error,"inference_error_count":w.error_count,"last_inference_error_at":w.last_error_at,"last_successful_inference_at":w.last_success_at,"last_sequence":w.last_sequence} for key,w in self.workers.items()}

    def stop(self):
        errors=[]
        for worker in self.workers.values():
            try:worker.stop()
            except Exception as exc:errors.append(str(exc))
        try:self.camera_manager.stop()
        except Exception as exc:errors.append(str(exc))
        if errors:raise RuntimeError("; ".join(errors))
