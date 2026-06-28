"""
Lane Detection and Lane Departure Warning.

Uses Hough Line Transform on a Canny-edge image within a trapezoidal ROI
to detect lane markings and warn when a vehicle's centroid crosses them.
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime


class LaneDetector:
    """
    Detects lane boundaries using classic computer-vision (no DNN required).
    Also issues Lane Departure Warnings when a tracked vehicle's centroid
    drifts outside its estimated lane corridor.
    """

    def __init__(self, config, logger, alert_system):
        self.config = config
        self.logger = logger
        self.alert_system = alert_system

        # Per-vehicle lane history for departure detection
        self._lane_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
        self._baseline_x: dict[int, float] = {}          # established centre-x per vehicle
        self._alerted: set = set()

        # Smoothed lane lines (exponential moving average)
        self._left_line = None
        self._right_line = None
        self._alpha = 0.15                               # EMA weight for line smoothing

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        """Detect lanes, draw them, and check for departure."""
        h, w = frame.shape[:2]

        # 1. Detect lane lines
        left, right = self._detect_lanes(frame, h, w)

        # 2. Smooth lines with EMA
        self._left_line  = self._ema_line(self._left_line,  left)
        self._right_line = self._ema_line(self._right_line, right)

        # 3. Draw overlay
        frame = self._draw_lanes(frame, h, w)

        # 4. Check each tracked vehicle for lane departure
        for vid, info in tracked_vehicles.items():
            cx, cy = info['centroid']
            self._lane_history[vid].append(cx)

            # Establish baseline after 15 stable frames
            if len(self._lane_history[vid]) == 15 and vid not in self._baseline_x:
                self._baseline_x[vid] = float(np.mean(self._lane_history[vid]))

            if vid in self._baseline_x:
                deviation = abs(cx - self._baseline_x[vid])
                if deviation > getattr(self.config, 'LANE_DEPARTURE_PIXELS', 60):
                    if vid not in self._alerted:
                        self._alerted.add(vid)
                        self._handle_departure(frame, info, timestamp)
                        self._baseline_x[vid] = cx   # reset baseline
                else:
                    self._alerted.discard(vid)

            # Draw per-vehicle deviation indicator
            if vid in self._baseline_x:
                dev = cx - self._baseline_x[vid]
                color = (0, 0, 255) if abs(dev) > getattr(self.config, 'LANE_DEPARTURE_PIXELS', 60) \
                        else (0, 255, 0)
                x1, y1, x2, y2 = info['bbox']
                cv2.putText(frame, f"LD:{dev:+.0f}px", (x1, y2 + 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        return frame

    # ------------------------------------------------------------------ #
    #  Lane detection internals                                            #
    # ------------------------------------------------------------------ #

    def _detect_lanes(self, frame, h, w):
        """Return (left_line, right_line) as (x1,y1,x2,y2) or None."""
        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur    = cv2.GaussianBlur(gray, (5, 5), 0)
        edges   = cv2.Canny(blur, 50, 150)
        roi     = self._roi_mask(edges, h, w)
        lines   = cv2.HoughLinesP(roi, 1, np.pi / 180, threshold=50,
                                   minLineLength=80, maxLineGap=120)

        left_lines, right_lines = [], []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 == x1:
                    continue
                slope = (y2 - y1) / (x2 - x1)
                if abs(slope) < 0.4:        # ignore near-horizontal
                    continue
                if slope < 0:
                    left_lines.append(line[0])
                else:
                    right_lines.append(line[0])

        left  = self._average_line(left_lines,  h) if left_lines  else None
        right = self._average_line(right_lines, h) if right_lines else None
        return left, right

    def _average_line(self, lines, h):
        """Fit a single line to a cluster of Hough segments."""
        x_coords, y_coords = [], []
        for x1, y1, x2, y2 in lines:
            x_coords += [x1, x2]
            y_coords += [y1, y2]
        poly = np.polyfit(y_coords, x_coords, 1)   # x = f(y)
        y1 = h
        y2 = int(h * 0.55)
        x1 = int(np.polyval(poly, y1))
        x2 = int(np.polyval(poly, y2))
        return (x1, y1, x2, y2)

    def _ema_line(self, prev, current):
        if current is None:
            return prev
        if prev is None:
            return current
        smoothed = tuple(int(self._alpha * c + (1 - self._alpha) * p)
                         for p, c in zip(prev, current))
        return smoothed

    def _roi_mask(self, img, h, w):
        mask = np.zeros_like(img)
        poly = np.array([[
            (int(w * 0.05), h),
            (int(w * 0.45), int(h * 0.55)),
            (int(w * 0.55), int(h * 0.55)),
            (int(w * 0.95), h),
        ]], dtype=np.int32)
        cv2.fillPoly(mask, poly, 255)
        return cv2.bitwise_and(img, mask)

    # ------------------------------------------------------------------ #
    #  Drawing                                                             #
    # ------------------------------------------------------------------ #

    def _draw_lanes(self, frame, h, w):
        overlay = frame.copy()
        if self._left_line and self._right_line:
            lx1, ly1, lx2, ly2 = self._left_line
            rx1, ry1, rx2, ry2 = self._right_line
            pts = np.array([[lx1, ly1], [lx2, ly2],
                             [rx2, ry2], [rx1, ry1]], dtype=np.int32)
            cv2.fillPoly(overlay, [pts], (0, 200, 0))
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

        for line, color in [(self._left_line, (0, 255, 100)),
                             (self._right_line, (0, 255, 100))]:
            if line:
                cv2.line(frame, (line[0], line[1]), (line[2], line[3]), color, 3)

        cv2.putText(frame, "LANE DETECTION", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 100), 1)
        return frame

    # ------------------------------------------------------------------ #
    #  Violation handling                                                  #
    # ------------------------------------------------------------------ #

    def _handle_departure(self, frame, info, timestamp):
        print("[VIOLATION] LANE DEPARTURE detected.")
        evidence_path = self.logger.save_evidence(frame, "LANE_DEPARTURE", "UNKNOWN", timestamp)
        self.logger.log_violation(
            violation_type="LANE_DEPARTURE",
            license_plate="UNKNOWN",
            speed_kmh=None,
            timestamp=timestamp,
            evidence_path=evidence_path,
        )
        self.alert_system.send_alert("LANE_DEPARTURE", "UNKNOWN", None, timestamp)
