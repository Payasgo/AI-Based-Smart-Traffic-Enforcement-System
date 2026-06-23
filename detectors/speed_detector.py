"""
Speed detection using virtual detection lines and frame timestamps.
"""

import cv2
import numpy as np
from datetime import datetime
from collections import defaultdict


class SpeedDetector:
    """
    Estimates vehicle speed by measuring time between two virtual lines.
    Speed (km/h) = (real_distance_m / time_s) * 3.6
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system

        # {vehicle_id: {'line1_time': datetime, 'line2_time': datetime}}
        self._crossing_times = defaultdict(dict)
        self._alerted        = set()   # IDs already alerted this session

    def process(self, frame, tracked_vehicles, timestamp):
        h, w = frame.shape[:2]
        line1_y = int(h * self.config.SPEED_LINE_1_Y)
        line2_y = int(h * self.config.SPEED_LINE_2_Y)

        # Draw detection lines
        cv2.line(frame, (0, line1_y), (w, line1_y), (255, 255, 0), 2)
        cv2.line(frame, (0, line2_y), (w, line2_y), (255, 255, 0), 2)
        cv2.putText(frame, "SPEED LINE 1", (5, line1_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
        cv2.putText(frame, "SPEED LINE 2", (5, line2_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

        for vid, info in tracked_vehicles.items():
            cx, cy = info['centroid']

            # Check line crossings
            if abs(cy - line1_y) < 6:
                if 'line1_time' not in self._crossing_times[vid]:
                    self._crossing_times[vid]['line1_time'] = timestamp

            if abs(cy - line2_y) < 6:
                if ('line1_time' in self._crossing_times[vid]
                        and 'line2_time' not in self._crossing_times[vid]):
                    self._crossing_times[vid]['line2_time'] = timestamp
                    speed = self._calculate_speed(vid)
                    if speed is not None:
                        self._annotate_speed(frame, info, speed)
                        if speed > self.config.SPEED_LIMIT_KMH and vid not in self._alerted:
                            self._alerted.add(vid)
                            plate = self._estimate_plate(frame, info['bbox'])
                            self._handle_violation(frame, info, speed, plate, timestamp)

            # Show estimated speed if available
            if ('line1_time' in self._crossing_times[vid]
                    and 'line2_time' in self._crossing_times[vid]):
                speed = self._calculate_speed(vid)
                if speed:
                    color = (0, 0, 255) if speed > self.config.SPEED_LIMIT_KMH else (0, 255, 0)
                    x1, y1, _, _ = info['bbox']
                    cv2.putText(frame, f"{speed:.1f} km/h", (x1, y1 - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        return frame

    def _calculate_speed(self, vid):
        times = self._crossing_times[vid]
        if 'line1_time' not in times or 'line2_time' not in times:
            return None
        dt = (times['line2_time'] - times['line1_time']).total_seconds()
        if dt <= 0:
            return None
        speed_mps = self.config.LINE_DISTANCE_METERS / dt
        return speed_mps * 3.6  # km/h

    def _annotate_speed(self, frame, info, speed):
        x1, y1, x2, y2 = info['bbox']
        color = (0, 0, 255) if speed > self.config.SPEED_LIMIT_KMH else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

    def _handle_violation(self, frame, info, speed, plate, timestamp):
        print(f"[VIOLATION] SPEED | Vehicle ID captured | {speed:.1f} km/h | Plate: {plate}")
        evidence_path = self.logger.save_evidence(frame, "SPEED", plate, timestamp)
        self.logger.log_violation(
            violation_type="SPEED",
            license_plate=plate,
            speed_kmh=speed,
            timestamp=timestamp,
            evidence_path=evidence_path
        )
        self.alert_system.send_alert("SPEED", plate, speed, timestamp)

    def _estimate_plate(self, frame, bbox):
        """Attempt OCR on the vehicle bounding box to extract license plate."""
        try:
            import pytesseract
            x1, y1, x2, y2 = bbox
            roi = frame[max(0, y2-50):y2, x1:x2]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(
                thresh, config="--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            ).strip()
            return text if text else "UNKNOWN"
        except Exception:
            return "UNKNOWN"
