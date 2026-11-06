"""OpenCV baseline for rear turn-indicator visual observations.

This is a colour/geometry heuristic, not a trained neural network. It is
intended for controlled evaluation and as a replaceable classifier backend.
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class IndicatorObservation:
    left_probability: float
    right_probability: float
    visible: bool
    left_amber_ratio: float
    right_amber_ratio: float


class AmberIndicatorVision:
    """Estimate amber activity in left/right rear-lamp regions of a vehicle box.

    Coordinates are relative to a rear-facing vehicle bounding box. A camera
    must be explicitly configured for rear views before this classifier is used.
    """

    def __init__(self, hue_low=8, hue_high=35, saturation_min=80,
                 value_min=100, active_ratio=0.035, visibility_value_min=28,
                 min_roi_pixels=12):
        if not (0 <= hue_low < hue_high <= 179):
            raise ValueError("HSV hue bounds must satisfy 0 <= low < high <= 179")
        if not (0 <= saturation_min <= 255 and 0 <= value_min <= 255):
            raise ValueError("HSV saturation/value thresholds must be in 0..255")
        if not 0 < active_ratio <= 1:
            raise ValueError("active_ratio must be in (0, 1]")
        if not 0 <= visibility_value_min <= 255 or min_roi_pixels < 1:
            raise ValueError("invalid visibility settings")
        self.hue_low, self.hue_high = int(hue_low), int(hue_high)
        self.saturation_min, self.value_min = int(saturation_min), int(value_min)
        self.active_ratio = float(active_ratio)
        self.visibility_value_min = int(visibility_value_min)
        self.min_roi_pixels = int(min_roi_pixels)

    @staticmethod
    def _clip_box(bbox, width, height):
        if bbox is None or len(bbox) != 4:
            return None
        x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return x1, y1, x2, y2

    def _lamp_ratio(self, hsv_roi):
        if hsv_roi.size == 0:
            return 0.0, False
        mask = cv2.inRange(
            hsv_roi,
            np.array([self.hue_low, self.saturation_min, self.value_min], dtype=np.uint8),
            np.array([self.hue_high, 255, 255], dtype=np.uint8),
        )
        ratio = float(np.count_nonzero(mask)) / float(mask.size)
        mean_value = float(np.mean(hsv_roi[:, :, 2]))
        observable = hsv_roi.shape[0] * hsv_roi.shape[1] >= self.min_roi_pixels
        observable = observable and mean_value >= self.visibility_value_min
        probability = min(1.0, ratio / self.active_ratio)
        return probability, observable

    def predict(self, frame, bbox, track_id=None, timestamp=None):
        """Return the callback contract consumed by CameraDetectionPipeline."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.ndim != 3:
            return {"left_probability": None, "right_probability": None, "visible": False}
        height, width = frame.shape[:2]
        box = self._clip_box(bbox, width, height)
        if box is None:
            return {"left_probability": None, "right_probability": None, "visible": False}
        x1, y1, x2, y2 = box
        vehicle = frame[y1:y2, x1:x2]
        vh, vw = vehicle.shape[:2]
        # Rear lamp zones: outer quarters in the lower half of the vehicle box.
        # These ratios must be calibrated for the camera/viewpoint and vehicle class.
        lamp_y1, lamp_y2 = int(vh * 0.35), int(vh * 0.90)
        left_x2 = max(1, int(vw * 0.35))
        right_x1 = min(vw - 1, int(vw * 0.65))
        if lamp_y2 <= lamp_y1 or right_x1 >= vw:
            return {"left_probability": None, "right_probability": None, "visible": False}
        hsv = cv2.cvtColor(vehicle, cv2.COLOR_BGR2HSV)
        left = hsv[lamp_y1:lamp_y2, 0:left_x2]
        right = hsv[lamp_y1:lamp_y2, right_x1:vw]
        left_probability, left_visible = self._lamp_ratio(left)
        right_probability, right_visible = self._lamp_ratio(right)
        visible = left_visible and right_visible
        return {
            "left_probability": left_probability if visible else None,
            "right_probability": right_probability if visible else None,
            "visible": visible,
        }
