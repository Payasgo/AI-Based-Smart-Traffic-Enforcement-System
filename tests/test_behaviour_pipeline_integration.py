import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera.camera_config import CameraConfig
from camera.detection_pipeline import CameraDetectionPipeline


class Sink:
    def __init__(self):
        self.events = []
    def save_evidence(self, frame, event_type, plate, timestamp):
        return f"/evidence/{event_type}.jpg"
    def log_violation(self, **kwargs):
        self.events.append(kwargs)


class Alerts:
    def __init__(self):
        self.events = []
    def send_alert(self, *args, **kwargs):
        self.events.append((args, kwargs))


def behaviour_pipeline(calibration=None, indicator_classifier=None, ttc_estimator=None):
    # Exercise temporal analytics without loading heavyweight visual detectors.
    obj = CameraDetectionPipeline.__new__(CameraDetectionPipeline)
    obj.config = SimpleNamespace()
    obj.logger = Sink()
    obj.alert_system = Alerts()
    obj.trajectory = __import__("analytics.trajectory_analyzer", fromlist=["TrajectoryAnalyzer"]).TrajectoryAnalyzer()
    obj.lane_changes = __import__("detectors.lane_change_detector", fromlist=["LaneChangeDetector"]).LaneChangeDetector(3, 8, 0)
    obj.reckless = __import__("detectors.reckless_driving_detector", fromlist=["RecklessDrivingDetector"]).RecklessDrivingDetector()
    from collections import defaultdict
    from detectors.indicator_detector import IndicatorDetector
    obj.indicators = defaultdict(IndicatorDetector)
    obj.indicator_classifier = indicator_classifier
    obj.ttc_estimator = ttc_estimator
    obj.lane_polygons = tuple((calibration or {}).get("lane_polygons", ()))
    return obj


def test_lane_polygon_config_is_validated():
    CameraConfig("north", 0, calibration={"lane_polygons": [
        {"lane_id": "left", "polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]},
        {"lane_id": "right", "polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]},
    ]})
    import pytest
    with pytest.raises(ValueError, match="unique"):
        CameraConfig("north", 0, calibration={"lane_polygons": [
            {"lane_id": "same", "polygon": [[0, 0], [1, 0], [1, 1]]},
            {"lane_id": "same", "polygon": [[0, 0], [1, 0], [1, 1]]},
        ]})


def test_lane_geometry_drives_trajectory_and_repeated_change_event():
    pipeline = behaviour_pipeline({"lane_polygons": [
        {"lane_id": "left", "polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]},
        {"lane_id": "right", "polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]},
    ]})
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    now = datetime.now(timezone.utc)
    for index, x in enumerate((25, 75, 25, 75)):
        pipeline._process_behaviour(frame, {7: {"centroid": (x, 50), "bbox": (x-2, 40, x+2, 60)}},
                                    now + timedelta(seconds=index))
    assert len(pipeline.trajectory.lane_transitions(7, 8)) == 3
    assert any(event["violation_type"] == "SUSPECTED_REPEATED_LANE_CHANGES"
               for event in pipeline.logger.events)


def test_indicator_unobservable_is_unknown_and_never_called_off():
    pipeline = behaviour_pipeline()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    state = pipeline._indicator_state(frame, 3, {"bbox": (1, 1, 10, 10)}, datetime.now(timezone.utc))
    assert state == "UNKNOWN"
    assert pipeline.reckless.evaluate(3, indicator_state=state,
                                      manoeuvre_direction="LEFT",
                                      indicator_visible=False) is None


def test_injected_indicator_classifier_is_temporally_aggregated():
    def classifier(frame, bbox, track_id, timestamp):
        return {"left_probability": 0.95, "right_probability": 0.05, "visible": True}
    pipeline = behaviour_pipeline(indicator_classifier=classifier)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    now = datetime.now(timezone.utc)
    states = [pipeline._indicator_state(frame, 3, {"bbox": (1, 1, 10, 10)}, now)
              for _ in range(5)]
    assert states[-1] == "LEFT"


def test_ttc_estimator_can_raise_review_only_high_risk_event():
    pipeline = behaviour_pipeline(ttc_estimator=lambda *args: 1.0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    now = datetime.now(timezone.utc)
    pipeline._process_behaviour(frame, {9: {"centroid": (50, 50), "bbox": (40, 40, 60, 60)}}, now)
    assert any(event["violation_type"] == "SUSPECTED_UNSAFE_DRIVING_BEHAVIOUR"
               for event in pipeline.logger.events)
    assert pipeline.logger.events[-1]["speed_kmh"] is None
