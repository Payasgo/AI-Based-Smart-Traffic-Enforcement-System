import sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.alert_system import AlertSystem
from camera.alert_context import CameraAlertContext

class FakeResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False

class Config:
    ENABLE_ALERTS = True
    ALERT_ENDPOINT_URL = "https://alerts.example.test/events"
    ALERT_API_KEY = "test-key"

def test_alert_queue_sends_camera_scoped_payload():
    received = []
    def opener(req, timeout):
        import json
        received.append(json.loads(req.data.decode("utf-8")))
        return FakeResponse()
    sender = AlertSystem(Config(), opener=opener, retry_backoff_seconds=0)
    scoped = CameraAlertContext(sender, "CAM-9", "SITE-2")
    try:
        assert scoped.send_alert("SPEEDING", "AP01AB1234", 72.5, datetime.now(timezone.utc))
        deadline = time.time() + 2
        while time.time() < deadline and sender.health()["sent"] != 1: time.sleep(.01)
        assert sender.health()["sent"] == 1
        assert received[0]["camera_id"] == "CAM-9"
        assert received[0]["site_id"] == "SITE-2"
        assert received[0]["review_status"] == "PENDING_REVIEW"
    finally:
        sender.stop()

def test_alert_queue_is_bounded_and_counts_drops():
    entered = threading.Event()
    release = threading.Event()
    def blocked(req, timeout):
        entered.set(); release.wait(1); return FakeResponse()
    sender = AlertSystem(Config(), max_queue_size=1, opener=blocked, max_attempts=1)
    try:
        assert sender.send_alert("A", "", None, datetime.now(timezone.utc))
        assert entered.wait(1)
        assert sender.send_alert("B", "", None, datetime.now(timezone.utc))
        assert not sender.send_alert("C", "", None, datetime.now(timezone.utc))
        assert sender.health()["dropped"] == 1
    finally:
        release.set(); sender.stop(timeout=2)

def test_alert_delivery_retries_then_records_failure():
    calls = []
    def failing(req, timeout):
        calls.append(1)
        raise OSError("offline")
    sender = AlertSystem(Config(), opener=failing, max_attempts=3, retry_backoff_seconds=0)
    try:
        sender.send_alert("TEST", "", None, datetime.now(timezone.utc))
        deadline = time.time() + 2
        while time.time() < deadline and sender.health()["failed"] != 1: time.sleep(.01)
        assert len(calls) == 3
        assert sender.health()["failed"] == 1
    finally:
        sender.stop()

def test_alert_endpoint_requires_https_and_api_key():
    config = Config(); config.ALERT_ENDPOINT_URL = "http://insecure.example.test"
    sender = AlertSystem(config, autostart=False)
    import pytest
    with pytest.raises(ValueError, match="HTTPS"): sender._post({})
