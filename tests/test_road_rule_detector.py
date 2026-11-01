from datetime import datetime, timedelta

import numpy as np

from detectors.road_rule_detector import RoadRuleDetector


class Logger:
    def __init__(self):
        self.events = []

    def save_evidence(self, frame, kind, plate, timestamp):
        self.events.append(("evidence", kind, plate))
        return "evidence.jpg"

    def log_violation(self, **kwargs):
        self.events.append(("log", kwargs))


class Alerts:
    def __init__(self):
        self.events = []

    def send_alert(self, *args):
        self.events.append(args)


class Config:
    ROAD_RULE_ZONES = [{
        "name": "NO_PARKING",
        "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        "violation_type": "ILLEGAL_PARKING",
        "dwell_seconds": 10,
    }]
    ROAD_RULE_LINES = [{
        "name": "SOLID_LINE",
        "start": [0.5, 0.1],
        "end": [0.5, 0.9],
        "violation_type": "SOLID_LINE_CROSSING",
        "direction": "positive_to_negative",
    }]
    PARKING_STATIONARY_PIXELS = 5
    TRAFFIC_STOP_LINE_Y = 0.7
    FINE_SCHEDULE_INR = {}


def vehicle(x=100, y=100):
    return {1: {"centroid": (x, y), "bbox": (x - 10, y - 10, x + 10, y + 10)}}


def setup():
    logger, alerts = Logger(), Alerts()
    return RoadRuleDetector(Config(), logger, alerts), logger, alerts


def test_parking_zone_requires_dwell_and_emits_once():
    detector, logger, alerts = setup()
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    start = datetime(2026, 1, 1, 12)
    detector.process(frame.copy(), vehicle(), start)
    detector.process(frame.copy(), vehicle(101, 100), start + timedelta(seconds=5))
    detector.process(frame.copy(), vehicle(101, 100), start + timedelta(seconds=11))
    detector.process(frame.copy(), vehicle(101, 100), start + timedelta(seconds=12))
    assert len(alerts.events) == 1
    assert alerts.events[0][0] == "ILLEGAL_PARKING"
    assert logger.events[0][1] == "ILLEGAL_PARKING"


def test_solid_line_crossing_only_in_configured_direction():
    detector, _, alerts = setup()
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    now = datetime(2026, 1, 1, 12)
    detector.process(frame.copy(), vehicle(80, 100), now)
    detector.process(frame.copy(), vehicle(120, 100), now + timedelta(seconds=1))
    assert len(alerts.events) == 1
    assert alerts.events[0][0] == "SOLID_LINE_CROSSING"


def test_red_light_requires_observed_stop_line_crossing():
    detector, _, alerts = setup()
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    now = datetime(2026, 1, 1, 12)
    detector.process(frame.copy(), vehicle(100, 100), now, signal_state="RED")
    detector.process(frame.copy(), vehicle(100, 180), now + timedelta(seconds=1),
                     signal_state="RED")
    assert any(event[0] == "RED_LIGHT" for event in alerts.events)


def test_vehicle_already_beyond_stop_line_is_not_flagged_on_red():
    detector, _, alerts = setup()
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    now = datetime(2026, 1, 1, 12)
    detector.process(frame.copy(), vehicle(100, 180), now, signal_state="RED")
    detector.process(frame.copy(), vehicle(100, 185), now + timedelta(seconds=1),
                     signal_state="RED")
    assert not any(event[0] == "RED_LIGHT" for event in alerts.events)

def test_line_extension_outside_segment_does_not_trigger():
    detector, _, alerts = setup()
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    now = datetime(2026, 1, 1, 12)
    # Cross the infinite vertical line's extension, but below the configured
    # finite segment (the segment ends at y=180).
    detector.process(frame.copy(), vehicle(80, 195), now)
    detector.process(frame.copy(), vehicle(120, 195), now + timedelta(seconds=1))
    assert not any(event[0] == "SOLID_LINE_CROSSING" for event in alerts.events)
