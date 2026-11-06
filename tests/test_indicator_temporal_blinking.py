import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detectors.indicator_detector import IndicatorDetector


def test_blinking_lamp_can_be_detected_with_intermittent_active_frames():
    detector = IndicatorDetector(min_samples=5, history_size=8)
    states = [
        detector.update(0.95, 0.05, visible=True),
        detector.update(0.05, 0.05, visible=True),
        detector.update(0.95, 0.05, visible=True),
        detector.update(0.05, 0.05, visible=True),
        detector.update(0.05, 0.05, visible=True),
    ]
    assert states[-1] == "LEFT"


def test_unobservable_sample_does_not_become_indicator_off():
    detector = IndicatorDetector(min_samples=3, history_size=5)
    assert detector.update(visible=False) == "UNKNOWN"
    assert detector.update(0.0, 0.0, visible=True) == "UNKNOWN"
    assert detector.update(0.0, 0.0, visible=True) == "UNKNOWN"
