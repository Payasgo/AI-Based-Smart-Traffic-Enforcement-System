from collections import deque
from types import SimpleNamespace
import numpy as np
from detectors.road_scene_detectors import TrafficLightDetector


def test_signal_state_requires_temporal_consensus_and_returns_unknown_first():
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._signal_history = deque(maxlen=7)
    detector._signal_min_samples = 5
    detector._signal_min_ratio = 0.01
    detector._signal_min_margin = 0.20
    detector._signal_roi = [0.0, 0.0, 1.0, 1.0]
    detector.state_confidence = 0.0
    red = np.zeros((100, 100, 3), dtype=np.uint8)
    red[30:70, 30:70] = (0, 0, 255)
    assert detector._detect_state(red) == "UNKNOWN"
    assert detector._detect_state(red) == "UNKNOWN"
    assert detector._detect_state(red) == "UNKNOWN"
    assert detector._detect_state(red) == "UNKNOWN"
    assert detector._detect_state(red) == "RED"


def test_signal_conflict_or_blank_frame_is_unknown():
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._signal_history = deque(maxlen=7)
    detector._signal_min_samples = 5
    detector._signal_min_ratio = 0.02
    detector._signal_min_margin = 0.20
    detector._signal_roi = [0.0, 0.0, 1.0, 1.0]
    detector.state_confidence = 0.0
    blank = np.zeros((100, 100, 3), dtype=np.uint8)
    assert detector._detect_state(blank) == "UNKNOWN"