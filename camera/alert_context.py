"""Inject camera/site identity into alerts while preserving detector APIs."""
class CameraAlertContext:
    def __init__(self, alert_system, camera_id, site_id):
        self.alert_system = alert_system
        self.camera_id = camera_id
        self.site_id = site_id

    def send_alert(self, violation_type, license_plate, speed_kmh, timestamp, **kwargs):
        return self.alert_system.send_alert(
            violation_type, license_plate, speed_kmh, timestamp,
            camera_id=self.camera_id, site_id=self.site_id, **kwargs
        )
