"""
Basic unit tests for detector utilities.
Run with: pytest tests/
"""

import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from detectors.drunk_driver_detector import eye_aspect_ratio
from detectors.vehicle_tracker import CentroidTracker


class TestEAR:
    def test_open_eye(self):
        # Wide-open eye points → EAR should be > threshold (0.25)
        pts = [(0,0), (1,2), (2,2), (3,0), (2,-2), (1,-2)]
        assert eye_aspect_ratio(pts) > 0.25

    def test_closed_eye(self):
        # Nearly closed eye → EAR near 0
        pts = [(0,0), (1,0.05), (2,0.05), (3,0), (2,-0.05), (1,-0.05)]
        assert eye_aspect_ratio(pts) < 0.25


class TestCentroidTracker:
    def test_register_objects(self):
        tracker = CentroidTracker()
        result  = tracker.update([(10, 10, 50, 50), (100, 100, 150, 150)])
        assert len(result) == 2

    def test_disappear_and_deregister(self):
        tracker = CentroidTracker(max_disappeared=2)
        tracker.update([(10, 10, 50, 50)])
        tracker.update([])
        tracker.update([])
        tracker.update([])  # Should deregister after 2 empty frames
        assert len(tracker.objects) == 0

    def test_consistent_ids(self):
        tracker = CentroidTracker()
        r1 = tracker.update([(10, 10, 50, 50)])
        r2 = tracker.update([(12, 11, 52, 51)])  # Slight movement
        assert list(r1.keys()) == list(r2.keys())
