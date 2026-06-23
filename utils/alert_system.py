"""
Alert system: optionally POSTs violation data to an authority REST API.
"""

import json
import threading
from datetime import datetime


class AlertSystem:
    """Sends real-time alerts to an external endpoint (optional)."""

    def __init__(self, config):
        self.config  = config
        self.enabled = config.ENABLE_ALERTS

    def send_alert(self, violation_type, license_plate, speed_kmh, timestamp):
        if not self.enabled:
            return
        payload = {
            "violation_type": violation_type,
            "license_plate":  license_plate,
            "speed_kmh":      speed_kmh,
            "timestamp":      timestamp.isoformat(),
        }
        # Fire-and-forget in background thread
        t = threading.Thread(target=self._post, args=(payload,), daemon=True)
        t.start()

    def _post(self, payload):
        try:
            import urllib.request
            data = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(
                self.config.ALERT_ENDPOINT_URL,
                data=data,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {self.config.ALERT_API_KEY}",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"[ALERT] Sent → HTTP {resp.status}")
        except Exception as e:
            print(f"[ALERT] Failed to send alert: {e}")
