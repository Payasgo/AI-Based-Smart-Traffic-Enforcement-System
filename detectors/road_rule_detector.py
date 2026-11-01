"""Configurable camera-zone and road-marking enforcement.

This module turns camera-calibrated polygons/lines into reviewable violation
candidates. Empty zone/line lists are intentionally safe defaults: configure
coordinates for each camera before enabling enforcement.
"""
import cv2
import numpy as np


class RoadRuleDetector:
    """Detect parking/crosswalk zone occupancy and configured line crossings."""

    def __init__(self, config, logger, alert_system):
        self.config = config
        self.logger = logger
        self.alert_system = alert_system
        self.zones = list(getattr(config, "ROAD_RULE_ZONES", []))
        self.lines = list(getattr(config, "ROAD_RULE_LINES", []))
        self.fines = dict(getattr(config, "FINE_SCHEDULE_INR", {}))
        self.stationary_px = float(getattr(config, "PARKING_STATIONARY_PIXELS", 5.0))
        self._zone_state = {}
        self._previous = {}
        self._alerted = set()

    @staticmethod
    def _point(point, width, height):
        return (int(float(point[0]) * width), int(float(point[1]) * height))

    @classmethod
    def _zone_polygon(cls, zone, width, height):
        return np.asarray([cls._point(p, width, height)
                           for p in zone["polygon"]], dtype=np.int32)

    @staticmethod
    def _side(point, line_start, line_end):
        return ((line_end[0] - line_start[0]) * (point[1] - line_start[1])
                - (line_end[1] - line_start[1]) * (point[0] - line_start[0]))

    def process(self, frame, tracked_vehicles, timestamp, signal_state="UNKNOWN"):
        height, width = frame.shape[:2]
        current_ids = set(tracked_vehicles)

        for zone in self.zones:
            polygon = self._zone_polygon(zone, width, height)
            cv2.polylines(frame, [polygon], True, (0, 165, 255), 2)
            cv2.putText(frame, zone.get("name", "RESTRICTED ZONE"),
                        tuple(polygon[0]), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (0, 165, 255), 1)
            for vehicle_id, info in tracked_vehicles.items():
                cx, cy = map(float, info["centroid"])
                inside = cv2.pointPolygonTest(
                    polygon, (cx, cy), False) >= 0
                key = (vehicle_id, zone.get("name", "zone"))
                state = self._zone_state.get(key)
                if not inside:
                    self._zone_state.pop(key, None)
                    continue
                if state is None:
                    self._zone_state[key] = {
                        "since": timestamp, "anchor": (cx, cy)
                    }
                    continue
                ax, ay = state["anchor"]
                if np.hypot(cx - ax, cy - ay) > self.stationary_px:
                    state["since"] = timestamp
                    state["anchor"] = (cx, cy)
                dwell = (timestamp - state["since"]).total_seconds()
                required = float(zone.get("dwell_seconds", 10.0))
                if dwell >= required:
                    violation = zone.get("violation_type", "ILLEGAL_PARKING")
                    self._raise(frame, vehicle_id, info, timestamp,
                                violation, key, zone.get("name", "zone"))

        for rule in self.lines:
            p1 = self._point(rule["start"], width, height)
            p2 = self._point(rule["end"], width, height)
            cv2.line(frame, p1, p2, (255, 100, 0), 2)
            for vehicle_id, info in tracked_vehicles.items():
                point = tuple(map(float, info["centroid"]))
                previous = self._previous.get((vehicle_id, rule["name"]))
                side = self._side(point, p1, p2)
                if previous is not None:
                    old_side = previous
                    direction = rule.get("direction", "either")
                    crossed = old_side * side < 0
                    allowed = (direction == "either" or
                               (direction == "negative_to_positive"
                                and old_side < 0 < side) or
                               (direction == "positive_to_negative"
                                and old_side > 0 > side))
                    key = (vehicle_id, rule["name"])
                    if crossed and allowed:
                        self._raise(frame, vehicle_id, info, timestamp,
                                    rule.get("violation_type", "RESTRICTED_LINE_CROSSING"),
                                    key, rule["name"])
                self._previous[(vehicle_id, rule["name"])] = side

        # A red-light event requires an observed crossing, not merely a
        # vehicle already beyond the stop line while the signal is red.
        stop_y = int(height * float(getattr(
            self.config, "TRAFFIC_STOP_LINE_Y", 0.70)))
        cv2.line(frame, (0, stop_y), (width, stop_y), (0, 0, 255), 1)
        for vehicle_id, info in tracked_vehicles.items():
            _, y = map(float, info["centroid"])
            old_y = self._previous.get((vehicle_id, "__stop_line__"))
            if signal_state == "RED" and old_y is not None and old_y <= stop_y < y:
                self._raise(frame, vehicle_id, info, timestamp,
                            "RED_LIGHT", (vehicle_id, "red-light"), "stop line")
            self._previous[(vehicle_id, "__stop_line__")] = y

        # Remove state for tracks that have left the current tracker output.
        for key in list(self._zone_state):
            if key[0] not in current_ids:
                self._zone_state.pop(key, None)
        for key in list(self._previous):
            if key[0] not in current_ids:
                self._previous.pop(key, None)
        self._alerted = {key for key in self._alerted if key[0] in current_ids}
        return frame

    def _raise(self, frame, vehicle_id, info, timestamp,
               violation, event_key, rule_name):
        if event_key in self._alerted:
            return
        self._alerted.add(event_key)
        plate = info.get("plate", "UNKNOWN")
        fine = self.fines.get(violation)
        fine_text = f" | indicative fine INR {fine}" if fine is not None else ""
        print(f"[REVIEW REQUIRED] {violation} | rule={rule_name} "
              f"| plate={plate}{fine_text}")
        x1, y1, x2, y2 = map(int, info["bbox"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(frame, f"{violation} - REVIEW",
                    (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (0, 0, 255), 2)
        evidence = self.logger.save_evidence(
            frame, violation, plate, timestamp)
        self.logger.log_violation(
            violation_type=violation, license_plate=plate, speed_kmh=None,
            timestamp=timestamp, evidence_path=evidence)
        self.alert_system.send_alert(violation, plate, None, timestamp)
