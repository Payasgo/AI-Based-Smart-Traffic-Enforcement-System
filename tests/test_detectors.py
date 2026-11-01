"""
Unit tests for detector utilities.
Run with: pytest tests/ -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from detectors.drunk_driver_detector import eye_aspect_ratio
from detectors.vehicle_tracker import CentroidTracker


class TestEAR:
    def test_open_eye(self):
        pts = [(0, 0), (1, 2), (2, 2), (3, 0), (2, -2), (1, -2)]
        assert eye_aspect_ratio(pts) > 0.25

    def test_closed_eye(self):
        pts = [(0, 0), (1, 0.05), (2, 0.05), (3, 0), (2, -0.05), (1, -0.05)]
        assert eye_aspect_ratio(pts) < 0.25


class TestCentroidTracker:
    def test_register_objects(self):
        tracker = CentroidTracker()
        result = tracker.update([(10, 10, 50, 50), (100, 100, 150, 150)])
        assert len(result) == 2

    def test_disappear_and_deregister(self):
        tracker = CentroidTracker(max_disappeared=2)
        tracker.update([(10, 10, 50, 50)])
        tracker.update([])
        tracker.update([])
        tracker.update([])
        assert len(tracker.objects) == 0

    def test_consistent_ids_for_small_movement(self):
        tracker = CentroidTracker()
        first = tracker.update([(10, 10, 50, 50)])
        second = tracker.update([(12, 11, 52, 51)])
        assert list(first) == list(second)

    def test_distance_gate_prevents_unreasonable_match(self):
        tracker = CentroidTracker(max_distance=25)
        first = tracker.update([(0, 0, 20, 20)])
        old_id = next(iter(first))

        second = tracker.update([(500, 500, 520, 520)])
        assert old_id in second
        assert len(second) == 2
        assert second[old_id]["centroid"] == first[old_id]["centroid"]

    def test_invalid_bbox_is_rejected(self):
        tracker = CentroidTracker()
        with pytest.raises(ValueError):
            tracker.update([(20, 20, 10, 10)])

    def test_missed_track_expires_after_configured_frames(self):
        tracker = CentroidTracker(max_disappeared=1)
        tracker.update([(0, 0, 20, 20)])
        tracker.update([])
        assert len(tracker.objects) == 1
        tracker.update([])
        assert len(tracker.objects) == 0
