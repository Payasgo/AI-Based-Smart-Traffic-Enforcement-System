"""Bounded, retrying background delivery for optional enforcement alerts.

Alerts are operational notifications only; this module never submits challans.
"""
import json
import queue
import threading
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen


class AlertSystem:
    def __init__(self, config, *, max_queue_size=500, max_attempts=3,
                 retry_backoff_seconds=1.0, request_timeout=5.0,
                 opener=None, autostart=True):
        self.config = config
        self.enabled = bool(getattr(config, "ENABLE_ALERTS", False))
        self.max_attempts = max(1, int(max_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.request_timeout = max(0.1, float(request_timeout))
        self._opener = opener or urlopen
        self._queue = queue.Queue(maxsize=max(1, int(max_queue_size)))
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._stats = {"queued": 0, "sent": 0, "failed": 0, "dropped": 0}
        if self.enabled and autostart:
            self.start()

    def start(self):
        if not self.enabled:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="traffic-alert-sender", daemon=True)
            self._thread.start()

    def send_alert(self, violation_type, license_plate, speed_kmh, timestamp,
                   *, camera_id="", site_id="", event_id="", review_status="PENDING_REVIEW"):
        if not self.enabled:
            return False
        stamp = timestamp or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        payload = {
            "event_id": event_id or None,
            "camera_id": camera_id or None,
            "site_id": site_id or None,
            "violation_type": str(violation_type),
            "license_plate": str(license_plate or ""),
            "speed_kmh": speed_kmh,
            "timestamp": stamp.astimezone(timezone.utc).isoformat(),
            "review_status": review_status,
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            with self._lock:
                self._stats["dropped"] += 1
            return False
        with self._lock:
            self._stats["queued"] += 1
        return True

    def _post(self, payload):
        endpoint = getattr(self.config, "ALERT_ENDPOINT_URL", "")
        if not endpoint or not endpoint.startswith("https://"):
            raise ValueError("Alert endpoint must be a configured HTTPS URL")
        api_key = getattr(self.config, "ALERT_API_KEY", "")
        if not api_key:
            raise ValueError("TRAFFIC_API_KEY is not configured")
        data = json.dumps(payload).encode("utf-8")
        req = Request(endpoint, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }, method="POST")
        with self._opener(req, timeout=self.request_timeout) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise RuntimeError(f"Alert endpoint returned HTTP {status}")

    def _run(self):
        while not self._stop.is_set() or not self._queue.empty():
            try:
                payload = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            sent = False
            for attempt in range(self.max_attempts):
                try:
                    self._post(payload)
                    sent = True
                    break
                except Exception as exc:
                    if attempt + 1 < self.max_attempts and self.retry_backoff_seconds:
                        self._stop.wait(self.retry_backoff_seconds * (2 ** attempt))
                    else:
                        print(f"[ALERT] Delivery failed after {attempt + 1} attempt(s): {exc}")
            with self._lock:
                self._stats["sent" if sent else "failed"] += 1
            self._queue.task_done()

    def health(self):
        with self._lock:
            result = dict(self._stats)
        result.update(enabled=self.enabled, pending=self._queue.qsize(),
                      worker_running=bool(self._thread and self._thread.is_alive()))
        return result

    def stop(self, timeout=10.0):
        if not self.enabled:
            return
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=max(0.0, timeout))
        if thread and thread.is_alive():
            raise TimeoutError("Alert sender did not drain its queue before shutdown")
