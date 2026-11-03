"""Temporal aggregator for an upstream visual indicator classifier.
This is not a trained image model. Occluded/unobservable lamps remain UNKNOWN.
"""
from collections import deque

class IndicatorDetector:
    def __init__(self, threshold=0.65, min_samples=5, history_size=12):
        if not 0 < threshold <= 1: raise ValueError("threshold must be in (0, 1]")
        if min_samples < 1 or history_size < min_samples: raise ValueError("history_size must be >= min_samples >= 1")
        self.threshold, self.min_samples = float(threshold), int(min_samples)
        self._observations = deque(maxlen=history_size)

    def update(self, left_probability=None, right_probability=None, visible=False):
        if not visible or left_probability is None or right_probability is None:
            self._observations.append(None); return "UNKNOWN"
        left, right = float(left_probability), float(right_probability)
        if not 0 <= left <= 1 or not 0 <= right <= 1: raise ValueError("probabilities must be in [0, 1]")
        self._observations.append((left, right))
        valid = [v for v in self._observations if v is not None]
        if len(valid) < self.min_samples: return "UNKNOWN"
        left_on = sum(l >= self.threshold for l, _ in valid) >= self.min_samples
        right_on = sum(r >= self.threshold for _, r in valid) >= self.min_samples
        if left_on and right_on: return "BOTH"
        if left_on: return "LEFT"
        if right_on: return "RIGHT"
        return "OFF"
