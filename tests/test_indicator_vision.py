import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detectors.indicator_vision import AmberIndicatorVision


def _rear_frame(left_on=False, right_on=False):
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    # Bright neutral vehicle body ensures the lamp regions are observable.
    frame[10:110, 10:190] = (150, 150, 150)
    # Amber BGR patches in the expected left/right rear lamp zones.
    if left_on:
        frame[55:95, 15:65] = (0, 140, 255)
    if right_on:
        frame[55:95, 135:185] = (0, 140, 255)
    return frame


def test_detects_left_and_right_amber_lamps():
    model = AmberIndicatorVision(active_ratio=0.02)
    left = model.predict(_rear_frame(left_on=True), (10, 10, 190, 110))
    right = model.predict(_rear_frame(right_on=True), (10, 10, 190, 110))
    assert left["visible"] and left["left_probability"] > left["right_probability"]
    assert right["visible"] and right["right_probability"] > right["left_probability"]


def test_unobservable_or_invalid_vehicle_crop_is_unknown():
    model = AmberIndicatorVision()
    assert model.predict(None, (0, 0, 10, 10))["visible"] is False
    assert model.predict(_rear_frame(), (-5, -5, -1, -1))["visible"] is False


def test_no_amber_returns_low_probabilities_when_roi_is_visible():
    model = AmberIndicatorVision()
    result = model.predict(_rear_frame(), (10, 10, 190, 110))
    assert result["visible"] is True
    assert result["left_probability"] == 0.0
    assert result["right_probability"] == 0.0


def test_camera_config_accepts_and_validates_indicator_settings():
    from camera.camera_config import CameraConfig
    camera = CameraConfig.from_dict({
        "camera_id": "rear-01", "source": 0, "role": "rear",
        "calibration": {"indicator_detection": {
            "enabled": True, "active_ratio": 0.04,
            "min_samples": 4, "history_size": 8
        }}
    })
    assert camera.calibration["indicator_detection"]["enabled"] is True
    import pytest
    with pytest.raises(ValueError, match="history_size"):
        CameraConfig.from_dict({
            "camera_id": "rear-02", "source": 1, "role": "rear",
            "calibration": {"indicator_detection": {
                "enabled": True, "min_samples": 9, "history_size": 5
            }}
        })
