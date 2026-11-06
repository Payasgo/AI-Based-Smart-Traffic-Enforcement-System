"""
Speed estimation from calibrated virtual-line crossings.

The detector keeps its existing process(frame, tracked_vehicles, timestamp)
interface. LINE_DISTANCE_METERS must be measured on the road plane for the
camera installation; this module does not infer physical distance from pixels.
"""

import cv2


class SpeedDetector:
    """Estimate speed from the elapsed time between two road-plane lines."""

    def __init__(self, config, logger, alert_system):
        self.config = config
        self.logger = logger
        self.alert_system = alert_system
        self._tracks = {}
        self._alerted = set()
        self.speed_calibration_verified = bool(
            getattr(config, "SPEED_CALIBRATION_VERIFIED", False)
        )
        self.track_timeout_seconds = float(
            getattr(config, "SPEED_TRACK_TIMEOUT_SECONDS", 5.0)
        )

    @staticmethod
    def _crossed(previous_y, current_y, line_y, direction):
        """True only when a point crosses a line in the expected direction."""
        if direction > 0:
            return previous_y < line_y <= current_y
        return previous_y > line_y >= current_y

    @staticmethod
    def _crossing_timestamp(previous_y, current_y, line_y, previous_time, current_time):
        """Interpolate the crossing instant between two sampled frames."""
        delta_y = current_y - previous_y
        if delta_y == 0:
            return current_time
        fraction = (line_y - previous_y) / delta_y
        fraction = min(1.0, max(0.0, fraction))
        return previous_time + (current_time - previous_time) * fraction

    def process(self, frame, tracked_vehicles, timestamp):
        h, w = frame.shape[:2]
        line1_y = int(h * self.config.SPEED_LINE_1_Y)
        line2_y = int(h * self.config.SPEED_LINE_2_Y)

        cv2.line(frame, (0, line1_y), (w, line1_y), (255, 255, 0), 2)
        cv2.line(frame, (0, line2_y), (w, line2_y), (255, 255, 0), 2)
        cv2.putText(frame, "SPEED LINE 1", (5, max(15, line1_y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
        cv2.putText(frame, "SPEED LINE 2", (5, max(15, line2_y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

        # The configured line order defines the valid travel direction.
        direction = 1 if line2_y > line1_y else -1

        for vid, info in tracked_vehicles.items():
            _, cy = info["centroid"]
            cy = float(cy)

            state = self._tracks.get(vid)
            if state is None:
                self._tracks[vid] = {
                    "previous_y": cy,
                    "previous_time": timestamp,
                    "line1_time": None,
                    "line2_time": None,
                    "last_seen": timestamp,
                }
                continue

            previous_y = state["previous_y"]
            previous_time = state["previous_time"]
            state["last_seen"] = timestamp

            # Record the actual crossing time, including when a frame skips
            # over the line instead of landing within a narrow pixel band.
            if state["line1_time"] is None and self._crossed(
                previous_y, cy, line1_y, direction
            ):
                state["line1_time"] = self._crossing_timestamp(
                    previous_y, cy, line1_y, previous_time, timestamp
                )

            if (state["line1_time"] is not None and state["line2_time"] is None
                    and self._crossed(previous_y, cy, line2_y, direction)):
                state["line2_time"] = self._crossing_timestamp(
                    previous_y, cy, line2_y, previous_time, timestamp
                )
                speed = self._calculate_speed(vid)
                if speed is not None:
                    self._annotate_speed(frame, info, speed)
                    if (self.speed_calibration_verified
                            and speed > self.config.SPEED_LIMIT_KMH
                            and vid not in self._alerted):
                        self._alerted.add(vid)
                        plate = self._estimate_plate(frame, info["bbox"])
                        self._handle_violation(
                            frame, info, speed, plate, timestamp
                        )

            state["previous_y"] = cy
            state["previous_time"] = timestamp

            if state["line2_time"] is not None:
                speed = self._calculate_speed(vid)
                if speed is not None:
                    color = ((0, 165, 255) if not self.speed_calibration_verified
                             else ((0, 0, 255) if speed > self.config.SPEED_LIMIT_KMH
                                   else (0, 255, 0)))
                    x1, y1, _, _ = info["bbox"]
                    cv2.putText(
                        frame, (f"{speed:.1f} km/h" if self.speed_calibration_verified
                                else f"UNVERIFIED ~{speed:.1f} km/h"), (x1, max(15, y1 - 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
                    )

        self._expire_tracks(timestamp)
        return frame

    def _expire_tracks(self, timestamp):
        """Bound memory use when vehicles leave the scene."""
        expired = [
            vid for vid, state in self._tracks.items()
            if (timestamp - state["last_seen"]).total_seconds()
            > self.track_timeout_seconds
        ]
        for vid in expired:
            self._tracks.pop(vid, None)
            self._alerted.discard(vid)

    def _calculate_speed(self, vid):
        state = self._tracks.get(vid)
        if not state or state["line1_time"] is None or state["line2_time"] is None:
            return None

        elapsed = (state["line2_time"] - state["line1_time"]).total_seconds()
        if elapsed <= 0:
            return None

        distance_m = float(self.config.LINE_DISTANCE_METERS)
        if distance_m <= 0:
            return None
        return (distance_m / elapsed) * 3.6

    def _annotate_speed(self, frame, info, speed):
        x1, y1, x2, y2 = info["bbox"]
        color = ((0, 165, 255) if not self.speed_calibration_verified
                 else ((0, 0, 255) if speed > self.config.SPEED_LIMIT_KMH
                       else (0, 255, 0)))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

    def _handle_violation(self, frame, info, speed, plate, timestamp):
        print(f"[REVIEW REQUIRED] SPEED | {speed:.1f} km/h | Plate: {plate}")
        evidence_path = self.logger.save_evidence(
            frame, "SPEED", plate, timestamp
        )
        self.logger.log_violation(
            violation_type="SPEED",
            license_plate=plate,
            speed_kmh=speed,
            timestamp=timestamp,
            evidence_path=evidence_path,
        )
        self.alert_system.send_alert("SPEED", plate, speed, timestamp)

    def _estimate_plate(self, frame, bbox):
        """Legacy OCR fallback; a dedicated plate detector should replace this."""
        try:
            import pytesseract

            x1, y1, x2, y2 = map(int, bbox)
            height, width = frame.shape[:2]
            x1, x2 = max(0, x1), min(width, x2)
            y1, y2 = max(0, y1), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                return "UNKNOWN"

            # Keep the lower-vehicle ROI as a fallback only. A dedicated
            # plate detector is still required for dependable ANPR.
            plate_y1 = y1 + int((y2 - y1) * 0.65)
            roi = frame[plate_y1:y2, x1:x2]
            if roi.size == 0:
                return "UNKNOWN"
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            text = pytesseract.image_to_string(
                thresh,
                config="--psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            ).strip()
            return text if text else "UNKNOWN"
        except Exception:
            return "UNKNOWN"
