import pytest

from camera.camera_config import CameraConfig


def test_speed_calibration_requires_positive_distance_when_verified():
    with pytest.raises(ValueError, match="requires line_distance_meters"):
        CameraConfig("CAM1", 0, calibration={"speed_calibration_verified": True})


def test_speed_calibration_rejects_equal_lines():
    with pytest.raises(ValueError, match="different positions"):
        CameraConfig("CAM1", 0, calibration={
            "speed_line_1_y": 0.4,
            "speed_line_2_y": 0.4,
        })


def test_speed_calibration_rejects_out_of_range_line():
    with pytest.raises(ValueError, match="normalized to 0..1"):
        CameraConfig("CAM1", 0, calibration={"speed_line_1_y": 1.2})


def test_speed_calibration_rejects_nonpositive_distance():
    with pytest.raises(ValueError, match="must be > 0"):
        CameraConfig("CAM1", 0, calibration={"line_distance_meters": 0})


def test_unverified_speed_calibration_is_valid_but_not_enabled_for_enforcement():
    from camera.multi_camera_runner import MultiCameraRunner
    camera = CameraConfig("CAM1", 0, calibration={"speed_limit_kmh": 40})
    config = MultiCameraRunner._camera_config(camera)
    assert config.SPEED_CALIBRATION_VERIFIED is False
    assert config.SPEED_LIMIT_KMH == 40


def test_verified_speed_calibration_requires_explicit_flag_and_measured_distance():
    from camera.multi_camera_runner import MultiCameraRunner
    camera = CameraConfig("CAM1", 0, calibration={
        "speed_line_1_y": 0.35,
        "speed_line_2_y": 0.65,
        "line_distance_meters": 12.5,
        "speed_calibration_verified": True,
    })
    config = MultiCameraRunner._camera_config(camera)
    assert config.SPEED_CALIBRATION_VERIFIED is True
    assert config.LINE_DISTANCE_METERS == 12.5
