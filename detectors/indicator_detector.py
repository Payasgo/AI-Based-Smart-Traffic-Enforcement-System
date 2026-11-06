"""Temporal aggregator for per-frame visual turn-indicator probabilities.

Blinking lamps need not be active in every sampled frame. UNKNOWN is retained
when the lamp regions are not observable or too few valid samples are present.
"""
from collections import deque
from math import ceil


class IndicatorDetector:
    def __init__(self, threshold=0.65, min_samples=5, history_size=12,
                 min_active_fraction=0.30):
        if not 0 < threshold <= 1:
            raise ValueError("threshold must be in (0, 1]")
        if min_samples < 1 or history_size < min_samples:
            raise ValueError("history_size must be >= min_samples >= 1")
        if not 0 < min_active_fraction <= 1:
            raise ValueError("min_active_fraction must be in (0, 1]")
        self.threshold = float(threshold)
        self.min_samples = int(min_samples)
        self.min_active_fraction = float(min_active_fraction)
        self._observations = deque(maxlen=history_size)

    def update(self, left_probability=None, right_probability=None, visible=False):
        if not visible or left_probability is None or right_probability is None:
            self._observations.append(None)
            return "UNKNOWN"
        left, right = float(left_probability), float(right_probability)
        if not 0 <= left <= 1 or not 0 <= right <= 1:
            raise ValueError("probabilities must be in [0, 1]")
        self._observations.append((left, right))
        valid = [value for value in self._observations if value is not None]
        if len(valid) < self.min_samples:
            return "UNKNOWN"
        active_samples = max(1, ceil(self.min_samples * self.min_active_fraction))
        left_on = sum(l >= self.threshold for l, _ in valid) >= active_samples
        right_on = sum(r >= self.threshold for _, r in valid) >= active_samples
        if left_on and right_on:
            return "BOTH"
        if left_on:
            return "LEFT"
        if right_on:
            return "RIGHT"
        return "OFF"
