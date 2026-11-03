import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera.camera_config import CameraConfig
from camera.camera_manager import CameraManager
from camera.camera_stream import CameraStream
from analytics.trajectory_analyzer import TrajectoryAnalyzer
from detectors.indicator_detector import IndicatorDetector
from detectors.lane_change_detector import LaneChangeDetector
from detectors.reckless_driving_detector import RecklessDrivingDetector

class FakeCapture:
    def __init__(self, source): self.frames, self.released = [object(), object(), object()], False
    def isOpened(self): return True
    def set(self, *_args): return True
    def read(self): return (True, self.frames.pop(0)) if self.frames else (False, None)
    def release(self): self.released = True

def test_camera_config_validates_and_converts_numeric_source():
    assert CameraConfig.from_dict({"camera_id": "A", "source": "0"}).source == 0
    with pytest.raises(ValueError): CameraConfig(camera_id="", source=0)

def test_manager_rejects_duplicate_camera_ids():
    cfg = CameraConfig("A", 0)
    with pytest.raises(ValueError): CameraManager([cfg, cfg])

def test_camera_stream_publishes_timestamped_frames_and_stops():
    created = []
    def factory(source):
        cap = FakeCapture(source); created.append(cap); return cap
    stream = CameraStream(CameraConfig("A", 0, reconnect=False, queue_size=3), factory)
    stream.start(); packet = stream.read(timeout=1.0); stream.stop()
    assert packet is not None and packet.camera_id == "A"
    assert packet.timestamp.tzinfo == timezone.utc and packet.sequence >= 1
    assert created[0].released

def test_trajectory_analyzer_detects_lane_transitions_in_window():
    analyzer, now = TrajectoryAnalyzer(), datetime.now(timezone.utc)
    analyzer.update(7, now, (10, 20), "lane-1")
    analyzer.update(7, now + timedelta(seconds=1), (20, 20), "lane-2")
    analyzer.update(7, now + timedelta(seconds=2), (30, 20), "lane-1")
    assert len(analyzer.lane_transitions(7, 5)) == 2

def test_lane_change_detector_flags_repeated_changes_and_cooldown():
    detector, now = LaneChangeDetector(3, 5, 10), datetime.now(timezone.utc)
    changes = [(now + timedelta(seconds=i), f"lane-{i%2}", f"lane-{(i+1)%2}") for i in range(3)]
    assert detector.update(3, changes)["event_type"] == "SUSPECTED_REPEATED_LANE_CHANGES"
    assert detector.update(3, changes) is None

def test_indicator_detector_returns_unknown_when_not_visible():
    assert IndicatorDetector(min_samples=3, history_size=5).update(0.1, 0.1, visible=False) == "UNKNOWN"

def test_indicator_detector_classifies_persistent_left_signal():
    detector = IndicatorDetector(min_samples=3, history_size=5)
    states = [detector.update(0.9, 0.1, visible=True) for _ in range(3)]
    assert states[-1] == "LEFT"

def test_reckless_detector_never_calls_unknown_indicator_non_use():
    detector = RecklessDrivingDetector()
    assert detector.evaluate(1, indicator_state="UNKNOWN", manoeuvre_direction="LEFT", indicator_visible=False) is None

def test_reckless_detector_emits_review_event_for_observed_indicator_mismatch():
    event = RecklessDrivingDetector().evaluate(1, indicator_state="RIGHT", manoeuvre_direction="LEFT", indicator_visible=True)
    assert event["review_required"] and not event["legal_violation_confirmed"]
    assert "INDICATOR_DIRECTION_MISMATCH" in event["reasons"]
