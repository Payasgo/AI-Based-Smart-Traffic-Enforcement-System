from datetime import datetime, timedelta

import numpy as np

from detectors.wrong_way_detector import WrongWayDetector


class FakeLogger:
    def __init__(self):
        self.events = []

    def save_evidence(self, frame, violation_type, plate, timestamp):
        self.events.append(("evidence", violation_type, plate))
        return "evidence.jpg"

    def log_violation(self, **kwargs):
        self.events.append(("log", kwargs))


class FakeAlerts:
    def __init__(self):
        self.events = []

    def send_alert(self, *args):
        self.events.append(args)


class Config:
    WRONG_WAY_DIRECTION_X = 0.0
    WRONG_WAY_DIRECTION_Y = 1.0
    WRONG_WAY_MIN_DISPLACEMENT_PX = 30.0
    WRONG_WAY_CONFIRM_FRAMES = 2
    WRONG_WAY_TRACK_TIMEOUT_SECONDS = 5.0


def vehicle(y):
    return {1: {"centroid": (100, y), "bbox": (80, y - 20, 120, y + 20)}}


def test_flags_vehicle_moving_opposite_to_allowed_direction_once():
    logger, alerts = FakeLogger(), FakeAlerts()
    detector = WrongWayDetector(Config(), logger, alerts)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    start = datetime(2026, 1, 1, 12, 0, 0)

    detector.process(frame.copy(), vehicle(100), start)
    detector.process(frame.copy(), vehicle(80), start + timedelta(seconds=1))
    detector.process(frame.copy(), vehicle(60), start + timedelta(seconds=2))
    detector.process(frame.copy(), vehicle(40), start + timedelta(seconds=3))

    assert len(alerts.events) == 1
    assert alerts.events[0][0:3] == ("WRONG_WAY", "UNKNOWN", None)
    assert [event[1] for event in logger.events if event[0] == "evidence"] == ["WRONG_WAY"]


def test_vehicle_moving_in_allowed_direction_is_not_flagged():
    logger, alerts = FakeLogger(), FakeAlerts()
    detector = WrongWayDetector(Config(), logger, alerts)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    start = datetime(2026, 1, 1, 12, 0, 0)

    detector.process(frame.copy(), vehicle(60), start)
    detector.process(frame.copy(), vehicle(80), start + timedelta(seconds=1))
    detector.process(frame.copy(), vehicle(100), start + timedelta(seconds=2))

    assert alerts.events == []
    assert logger.events == []


def test_zero_direction_vector_is_rejected():
    class InvalidConfig(Config):
        WRONG_WAY_DIRECTION_X = 0.0
        WRONG_WAY_DIRECTION_Y = 0.0

    import pytest
    with pytest.raises(ValueError):
        WrongWayDetector(InvalidConfig(), FakeLogger(), FakeAlerts())
