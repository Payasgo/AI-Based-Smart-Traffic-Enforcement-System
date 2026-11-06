"""Camera-scoped adapter for the shared evidence logger."""
class CameraEvidenceLogger:
    def __init__(self, logger, camera_id, site_id, calibration_version="", model_version=""):
        self._logger = logger
        self.camera_id = camera_id
        self.site_id = site_id
        self.calibration_version = calibration_version
        self.model_version = model_version

    def save_evidence(self, frame, violation_type, plate, timestamp):
        return self._logger.save_evidence(frame, violation_type, plate, timestamp, camera_id=self.camera_id)

    def log_violation(self, violation_type, license_plate, speed_kmh, timestamp,
                      evidence_path, location="N/A", **metadata):
        return self._logger.log_violation(
            violation_type, license_plate, speed_kmh, timestamp, evidence_path, location,
            camera_id=self.camera_id, site_id=self.site_id,
            calibration_version=self.calibration_version,
            model_version=self.model_version, **metadata,
        )
