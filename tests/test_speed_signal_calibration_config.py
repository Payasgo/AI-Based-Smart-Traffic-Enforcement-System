import pytest
from camera.camera_config import CameraConfig


def test_verified_speed_calibration_requires_surveyed_lines_distance_and_version():
    with pytest.raises(ValueError, match="calibration_version"):
        CameraConfig.from_dict({"camera_id":"cam","source":0,"calibration":{
            "speed_calibration_verified":True, "line_distance_meters":12.0,
            "speed_line_1_y":0.3, "speed_line_2_y":0.7
        }})


def test_verified_speed_calibration_accepts_complete_survey_metadata():
    camera = CameraConfig.from_dict({"camera_id":"cam","source":0,"calibration":{
        "speed_calibration_verified":True, "line_distance_meters":12.0,
        "speed_line_1_y":0.3, "speed_line_2_y":0.7,
        "calibration_version":"site-a-v2"
    }})
    assert camera.calibration["speed_calibration_verified"] is True


def test_traffic_signal_roi_must_be_normalized_and_ordered():
    with pytest.raises(ValueError, match="traffic_signal_roi"):
        CameraConfig.from_dict({"camera_id":"cam","source":0,"calibration":{
            "traffic_signal_roi":[0.8,0.1,0.2,0.9]
        }})