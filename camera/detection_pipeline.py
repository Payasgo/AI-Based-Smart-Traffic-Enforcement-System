"""Per-camera visual detector suite for multi-camera operation.

Each instance owns its temporal detector state. Evidence and alert sinks are
shared by the runner; audio capture and lesson/voice services remain central.
"""
from datetime import datetime


class CameraDetectionPipeline:
    """Run the legacy visual detector sequence on one camera's frame stream."""

    def __init__(self, config, logger, alert_system):
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

        self.config = config
        self.parking_mode = bool(getattr(config, "PARKING_MODE", False))
        # Detector objects are intentionally created per camera: their
        # cooldowns, histories and track-associated state must not leak.
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

    def process(self, frame, tracked_vehicles, timestamp=None):
        timestamp = timestamp or datetime.now()
        if self.parking_mode:
            return self.parking.process(frame, tracked_vehicles, timestamp)

        frame = self.lane.process(frame, tracked_vehicles, timestamp)
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
