"""Per-camera visual and temporal driving-behaviour detection pipeline.

Lane-change analytics require surveyed lane polygons in camera calibration.
Indicator probabilities and TTC are accepted only from optional upstream
classifiers/estimators; without them the result remains UNKNOWN/unavailable.
All behaviour outputs are review candidates, never legal conclusions.
"""
from collections import defaultdict
from datetime import datetime, timezone

from analytics.trajectory_analyzer import TrajectoryAnalyzer
from detectors.indicator_detector import IndicatorDetector
from detectors.lane_change_detector import LaneChangeDetector
from detectors.reckless_driving_detector import RecklessDrivingDetector


class CameraDetectionPipeline:
    """Run visual detectors and per-track behaviour analytics for one camera."""

    def __init__(self, config, logger, alert_system,
                 indicator_classifier=None, ttc_estimator=None):
        from detectors.speed_detector import SpeedDetector
        from detectors.wrong_way_detector import WrongWayDetector
        from detectors.road_rule_detector import RoadRuleDetector
        from detectors.drunk_driver_detector import DrunkDriverDetector
        from detectors.lane_detector import LaneDetector
        from detectors.safety_detectors import (
            HelmetDetector, SeatbeltDetector, PhoneUsageDetector,
            DistractionDetector,
        )
        from detectors.road_scene_detectors import (
            TrafficLightDetector, TrafficSignRecognizer, CollisionWarning,
            PedestrianDetector, ObstacleDetector, BlindSpotDetector,
            ParkingAssistant,
        )

        self.config, self.logger, self.alert_system = config, logger, alert_system
        self.parking_mode = bool(getattr(config, "PARKING_MODE", False))
        self.lane = LaneDetector(config, logger, alert_system)
        self.speed = SpeedDetector(config, logger, alert_system)
        self.wrong_way = WrongWayDetector(config, logger, alert_system)
        self.drunk = DrunkDriverDetector(config, logger, alert_system)
        self.traffic_light = TrafficLightDetector(config, logger, alert_system)
        self.road_rules = RoadRuleDetector(config, logger, alert_system)
        self.signs = TrafficSignRecognizer(config, logger, alert_system)
        self.collision = CollisionWarning(config, logger, alert_system)
        self.pedestrians = PedestrianDetector(config, logger, alert_system)
        self.obstacles = ObstacleDetector(config, logger, alert_system)
        self.blind_spot = BlindSpotDetector(config, logger, alert_system)
        self.helmet = HelmetDetector(config, logger, alert_system)
        self.seatbelt = SeatbeltDetector(config, logger, alert_system)
        self.phone = PhoneUsageDetector(config, logger, alert_system)
        self.distraction = DistractionDetector(config, logger, alert_system)
        self.parking = ParkingAssistant(config, logger, alert_system)

        self.trajectory = TrajectoryAnalyzer()
        self.lane_changes = LaneChangeDetector(
            min_changes=int(getattr(config, "RECKLESS_LANE_CHANGE_THRESHOLD", 3)),
            window_seconds=float(getattr(config, "RECKLESS_LANE_CHANGE_WINDOW_SECONDS", 8.0)),
            cooldown_seconds=float(getattr(config, "RECKLESS_EVENT_COOLDOWN_SECONDS", 10.0)),
        )
        self.reckless = RecklessDrivingDetector(
            lane_change_threshold=int(getattr(config, "RECKLESS_LANE_CHANGE_THRESHOLD", 3)),
            ttc_warning_seconds=float(getattr(config, "RECKLESS_TTC_WARNING_SECONDS", 2.0)),
        )
        indicator_settings = calibration.get("indicator_detection", {}) or {}
        self.indicator_classifier = indicator_classifier
        # Only explicitly enabled rear-facing cameras use the OpenCV baseline.
        if (self.indicator_classifier is None
                and getattr(config, "CAMERA_ROLE", None) == "rear"
                and indicator_settings.get("enabled", False)):
            from detectors.indicator_vision import AmberIndicatorVision
            self.indicator_classifier = AmberIndicatorVision(
                hue_low=indicator_settings.get("hue_low", 8),
                hue_high=indicator_settings.get("hue_high", 35),
                saturation_min=indicator_settings.get("saturation_min", 80),
                value_min=indicator_settings.get("value_min", 100),
                active_ratio=indicator_settings.get("active_ratio", 0.035),
                visibility_value_min=indicator_settings.get("visibility_value_min", 28),
            )
        self.ttc_estimator = ttc_estimator
        self.indicators = defaultdict(lambda: IndicatorDetector(
            threshold=indicator_settings.get("threshold", 0.65),
            min_samples=indicator_settings.get("min_samples", 5),
            history_size=indicator_settings.get("history_size", 12),
        ))
        calibration = getattr(config, "CAMERA_CALIBRATION", {}) or {}
        self.lane_polygons = tuple(calibration.get("lane_polygons", ()))
        self._lane_centers = {
            lane["lane_id"]: sum(point[0] for point in lane["polygon"]) / len(lane["polygon"])
            for lane in self.lane_polygons
        }

    @staticmethod
    def _inside_polygon(point, polygon):
        """Ray-casting point-in-polygon; inputs are normalized coordinates."""
        x, y = point
        inside = False
        j = len(polygon) - 1
        for i, (xi, yi) in enumerate(polygon):
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)):
                crossing_x = (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
                if x < crossing_x:
                    inside = not inside
            j = i
        return inside

    def _lane_id(self, centroid, frame_shape):
        if not self.lane_polygons:
            return None
        height, width = frame_shape[:2]
        point = (float(centroid[0]) / max(width, 1),
                 float(centroid[1]) / max(height, 1))
        matches = [lane["lane_id"] for lane in self.lane_polygons
                   if self._inside_polygon(point, lane["polygon"])]
        # Ambiguous overlaps are deliberately UNKNOWN, not an arbitrary lane.
        return matches[0] if len(matches) == 1 else None

    def _indicator_state(self, frame, track_id, info, timestamp):
        if self.indicator_classifier is None:
            return self.indicators[track_id].update(visible=False)
        try:
            observation = self.indicator_classifier(frame, info.get("bbox"),
                                                    track_id, timestamp)
            if not isinstance(observation, dict):
                raise ValueError("indicator classifier must return a mapping")
            return self.indicators[track_id].update(
                observation.get("left_probability"),
                observation.get("right_probability"),
                visible=bool(observation.get("visible", False)),
            )
        except Exception:
            # A classifier failure is unobservable, never evidence of OFF.
            return self.indicators[track_id].update(visible=False)

    def _record_behaviour_event(self, frame, event, timestamp):
        event_type = event["event_type"]
        plate = "UNKNOWN"
        evidence_path = None
        try:
            evidence_path = self.logger.save_evidence(
                frame, event_type, plate, timestamp
            )
            self.logger.log_violation(
                violation_type=event_type, license_plate=plate,
                speed_kmh=None, timestamp=timestamp,
                evidence_path=evidence_path,
            )
        except Exception as exc:
            # Keep analytics alive, but surface evidence failures to worker health.
            raise RuntimeError(f"could not persist behaviour review event: {exc}") from exc
        self.alert_system.send_alert(event_type, plate, None, timestamp)

    def _process_behaviour(self, frame, tracked_vehicles, timestamp):
        height, width = frame.shape[:2]
        for track_id, info in tracked_vehicles.items():
            centroid = info.get("centroid")
            if not centroid:
                continue
            lane_id = self._lane_id(centroid, (height, width, 3))
            self.trajectory.update(track_id, timestamp, centroid, lane_id)
            transitions = self.trajectory.lane_transitions(track_id, window_seconds=8.0)
            lane_event = self.lane_changes.update(track_id, transitions)
            indicator_state = self._indicator_state(frame, track_id, info, timestamp)
            manoeuvre = None
            if transitions:
                previous_lane, current_lane = transitions[-1][1], transitions[-1][2]
                if previous_lane in self._lane_centers and current_lane in self._lane_centers:
                    manoeuvre = "LEFT" if self._lane_centers[current_lane] < self._lane_centers[previous_lane] else "RIGHT"
            ttc = None
            if self.ttc_estimator is not None:
                try:
                    ttc = self.ttc_estimator(track_id, info, tracked_vehicles, timestamp)
                except Exception:
                    ttc = None
            event = self.reckless.evaluate(
                track_id,
                lane_change_count=(lane_event or {}).get("transition_count", 0),
                indicator_state=indicator_state,
                manoeuvre_direction=manoeuvre,
                ttc_seconds=ttc,
                indicator_visible=(indicator_state != "UNKNOWN"),
            )
            if lane_event:
                self._record_behaviour_event(frame, lane_event, timestamp)
            if event:
                self._record_behaviour_event(frame, event, timestamp)
                x1, y1, _, _ = info.get("bbox", (int(centroid[0]), int(centroid[1]), 0, 0))
                import cv2
                cv2.putText(frame, f"DRIVING RISK: {event['risk_level']} - REVIEW",
                            (int(x1), max(20, int(y1) - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 2)

    def process(self, frame, tracked_vehicles, timestamp=None):
        timestamp = timestamp or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if self.parking_mode:
            return self.parking.process(frame, tracked_vehicles, timestamp)

        frame = self.lane.process(frame, tracked_vehicles, timestamp)
        self._process_behaviour(frame, tracked_vehicles, timestamp)
        frame = self.speed.process(frame, tracked_vehicles, timestamp)
        frame = self.wrong_way.process(frame, tracked_vehicles, timestamp)
        frame = self.drunk.process(frame, tracked_vehicles, timestamp)
        frame = self.traffic_light.process(frame, tracked_vehicles, timestamp)
        frame = self.road_rules.process(
            frame, tracked_vehicles, timestamp,
            signal_state=self.traffic_light.current_state,
        )
        frame = self.signs.process(frame, tracked_vehicles, timestamp)
        frame = self.collision.process(frame, tracked_vehicles, timestamp)
        frame = self.pedestrians.process(frame, tracked_vehicles, timestamp)
        frame = self.obstacles.process(frame, tracked_vehicles, timestamp)
        frame = self.blind_spot.process(frame, tracked_vehicles, timestamp)
        frame = self.helmet.process(frame, tracked_vehicles, timestamp)
        frame = self.seatbelt.process(frame, tracked_vehicles, timestamp)
        frame = self.phone.process(frame, tracked_vehicles, timestamp)
        frame = self.distraction.process(frame, tracked_vehicles, timestamp)
        return frame
