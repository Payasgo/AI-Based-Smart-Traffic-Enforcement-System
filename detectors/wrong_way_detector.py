"""Detect vehicles travelling opposite to a configured road direction.

This is a camera-view direction check, not a map/GPS route classifier. Configure
the allowed direction vector for each camera and restrict deployment to a
single, clearly visible road approach.
"""

import math

import cv2


class WrongWayDetector:
    """Raise one reviewable event when a tracked vehicle moves against traffic."""

    def __init__(self, config, logger, alert_system):
        self.config = config
        self.logger = logger
        self.alert_system = alert_system
        dx = float(getattr(config, "WRONG_WAY_DIRECTION_X", 0.0))
        dy = float(getattr(config, "WRONG_WAY_DIRECTION_Y", 1.0))
        magnitude = math.hypot(dx, dy)
        if magnitude == 0:
            raise ValueError("Wrong-way allowed direction vector cannot be zero")
        self.allowed_direction = (dx / magnitude, dy / magnitude)
        self.min_displacement = float(
            getattr(config, "WRONG_WAY_MIN_DISPLACEMENT_PX", 30.0)
        )
        self.confirm_frames = int(
            getattr(config, "WRONG_WAY_CONFIRM_FRAMES", 2)
        )
        self.timeout_seconds = float(
            getattr(config, "WRONG_WAY_TRACK_TIMEOUT_SECONDS", 5.0)
        )
        if self.min_displacement <= 0 or self.confirm_frames < 1:
            raise ValueError("Wrong-way thresholds must be positive")
        self._tracks = {}
        self._alerted = set()

    def process(self, frame, tracked_vehicles, timestamp):
        h, w = frame.shape[:2]
        # Display a direction arrow so installers can verify camera setup.
        cx, cy = w // 2, h - 35
        dx, dy = self.allowed_direction
        end = (int(cx + dx * 55), int(cy + dy * 55))
        cv2.arrowedLine(frame, (cx, cy), end, (255, 180, 0), 2, tipLength=0.25)
        cv2.putText(frame, "ALLOWED TRAFFIC DIRECTION",
                    (max(5, cx - 150), max(18, cy - 65)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 180, 0), 1)

        for vehicle_id, info in tracked_vehicles.items():
            x, y = map(float, info["centroid"])
            state = self._tracks.get(vehicle_id)
            if state is None:
                self._tracks[vehicle_id] = {
                    "anchor": (x, y), "previous": (x, y),
                    "opposite_frames": 0, "last_seen": timestamp,
                }
                continue

            px, py = state["previous"]
            step_projection = ((x - px) * dx + (y - py) * dy)
            if step_projection < -0.5:
                state["opposite_frames"] += 1
            elif step_projection > 0.5:
                state["opposite_frames"] = 0
                state["anchor"] = (x, y)

            ax, ay = state["anchor"]
            net_projection = ((x - ax) * dx + (y - ay) * dy)
            state["previous"] = (x, y)
            state["last_seen"] = timestamp

            if (vehicle_id not in self._alerted
                    and net_projection <= -self.min_displacement
                    and state["opposite_frames"] >= self.confirm_frames):
                self._alerted.add(vehicle_id)
                plate = self._read_plate(frame, info.get("bbox"))
                self._record_violation(frame, plate, timestamp)
                x1, y1, _, _ = info.get("bbox", (int(x), int(y), int(x), int(y)))
                cv2.putText(frame, "WRONG WAY - REVIEW",
                            (int(x1), max(20, int(y1) - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        self._expire_tracks(timestamp)
        return frame

    def _record_violation(self, frame, plate, timestamp):
        print(f"[REVIEW REQUIRED] WRONG_WAY | Plate: {plate}")
        evidence_path = self.logger.save_evidence(
            frame, "WRONG_WAY", plate, timestamp
        )
        self.logger.log_violation(
            violation_type="WRONG_WAY",
            license_plate=plate,
            speed_kmh=None,
            timestamp=timestamp,
            evidence_path=evidence_path,
        )
        self.alert_system.send_alert("WRONG_WAY", plate, None, timestamp)

    @staticmethod
    def _read_plate(frame, bbox):
        """Best-effort OCR only; UNKNOWN must never be treated as a plate match."""
        if not bbox:
            return "UNKNOWN"
        try:
            import pytesseract

            x1, y1, x2, y2 = map(int, bbox)
            height, width = frame.shape[:2]
            x1, x2 = max(0, x1), min(width, x2)
            y1, y2 = max(0, y1), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                return "UNKNOWN"
            roi = frame[y1 + int((y2 - y1) * 0.6):y2, x1:x2]
            if roi.size == 0:
                return "UNKNOWN"
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(
                gray,
                config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            ).strip().replace(" ", "").replace("\n", "")
            return text if text else "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def _expire_tracks(self, timestamp):
        expired = [
            vehicle_id for vehicle_id, state in self._tracks.items()
            if (timestamp - state["last_seen"]).total_seconds()
            > self.timeout_seconds
        ]
        for vehicle_id in expired:
            self._tracks.pop(vehicle_id, None)
            self._alerted.discard(vehicle_id)
