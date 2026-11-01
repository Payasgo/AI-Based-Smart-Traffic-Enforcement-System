from datetime import datetime, timedelta

from detectors.speed_detector import SpeedDetector


def test_line_crossing_detects_motion_in_expected_direction():
    assert SpeedDetector._crossed(100, 140, 120, 1)
    assert not SpeedDetector._crossed(140, 100, 120, 1)
    assert SpeedDetector._crossed(140, 100, 120, -1)


def test_line_crossing_detects_skipped_over_line():
    # The sampled points are on either side of the line; no exact frame
    # needs to land on the line itself.
    assert SpeedDetector._crossed(90, 150, 120, 1)


def test_crossing_timestamp_is_interpolated():
    start = datetime(2026, 1, 1, 12, 0, 0)
    end = start + timedelta(seconds=1)
    crossing = SpeedDetector._crossing_timestamp(100, 200, 150, start, end)
    assert crossing == start + timedelta(milliseconds=500)
