"""
Smarter Roads, Safer Lives — AI at the Service of Traffic Enforcement
Author: Kranthi Kumar Yarlagadda
Contact: payasgo55@gmail.com | kranthikumar.yarli@gmail.com
"""

import cv2
import time
import threading
import argparse
from datetime import datetime

# ── Existing detectors ──────────────────────────────────────────────────────
from detectors.speed_detector    import SpeedDetector
from detectors.drunk_driver_detector import DrunkDriverDetector
from detectors.honk_detector     import HonkDetector
from detectors.vehicle_tracker   import VehicleTracker

# ── New detectors ───────────────────────────────────────────────────────────
from detectors.lane_detector     import LaneDetector
from detectors.safety_detectors  import (
    HelmetDetector, SeatbeltDetector,
    PhoneUsageDetector, DistractionDetector,
)
from detectors.road_scene_detectors import (
    TrafficLightDetector, TrafficSignRecognizer,
    CollisionWarning, PedestrianDetector,
    ObstacleDetector, BlindSpotDetector, ParkingAssistant,
)
from detectors.driver_assessment import (
    DriverSkillClassifier, DrivingLessonTracker, VoiceCoach,
)

# ── Utils ────────────────────────────────────────────────────────────────────
from utils.evidence_logger import EvidenceLogger
from utils.alert_system    import AlertSystem
from config.settings       import Settings


class TrafficEnforcementSystem:
    """Main orchestrator for the AI-based traffic enforcement system."""

    def __init__(self, config: Settings):
        self.config = config

        # Core infrastructure
        self.logger       = EvidenceLogger(config.LOG_DIR, config.EVIDENCE_DIR)
        self.alert_system = AlertSystem(config)

        # ── Driver assessment (init first so others can reference) ──────
        self.voice_coach    = VoiceCoach(config)
        self.lesson_tracker = DrivingLessonTracker(config)
        self.skill_clf      = DriverSkillClassifier(
            config,
            lesson_tracker=self.lesson_tracker,
            voice_coach=self.voice_coach,
        )

        # ── Vehicle tracking ────────────────────────────────────────────
        self.vehicle_tracker = VehicleTracker(config)

        # ── Violation detectors ─────────────────────────────────────────
        self.speed_detector    = SpeedDetector(config, self.logger, self.alert_system)
        self.drunk_detector    = DrunkDriverDetector(config, self.logger, self.alert_system)
        self.honk_detector     = HonkDetector(config, self.logger, self.alert_system)

        # New – road features
        self.lane_detector     = LaneDetector(config, self.logger, self.alert_system)
        self.tl_detector       = TrafficLightDetector(config, self.logger, self.alert_system)
        self.sign_recognizer   = TrafficSignRecognizer(config, self.logger, self.alert_system)
        self.collision_warning = CollisionWarning(config, self.logger, self.alert_system)
        self.ped_detector      = PedestrianDetector(config, self.logger, self.alert_system)
        self.obstacle_detector = ObstacleDetector(config, self.logger, self.alert_system)
        self.blind_spot        = BlindSpotDetector(config, self.logger, self.alert_system)
        self.parking_assist    = ParkingAssistant(config, self.logger, self.alert_system)

        # New – safety checks
        self.helmet_detector   = HelmetDetector(config, self.logger, self.alert_system)
        self.seatbelt_detector = SeatbeltDetector(config, self.logger, self.alert_system)
        self.phone_detector    = PhoneUsageDetector(config, self.logger, self.alert_system)
        self.distraction_det   = DistractionDetector(config, self.logger, self.alert_system)

        # Subscribe alert_system to forward events to skill classifier
        self._patch_alert_system()

        self.running     = False
        self.frame_count = 0

    # ────────────────────────────────────────────────────────────────────────
    def _patch_alert_system(self):
        """Wrap send_alert so every fired event also updates the skill score."""
        original_send = self.alert_system.send_alert

        def patched_send(violation_type, license_plate, speed_kmh, timestamp):
            original_send(violation_type, license_plate, speed_kmh, timestamp)
            self.skill_clf.record_event(violation_type, {
                "license_plate": license_plate,
                "speed_kmh":     speed_kmh,
            })

        self.alert_system.send_alert = patched_send

    # ────────────────────────────────────────────────────────────────────────
    def start(self):
        """Start all detection subsystems."""
        self.running = True
        print("[INFO] Traffic Enforcement System starting...")

        # Audio thread
        honk_thread = threading.Thread(
            target=self.honk_detector.start_listening, daemon=True)
        honk_thread.start()

        # Skill score recovery ticker
        skill_thread = threading.Thread(target=self._skill_tick_loop, daemon=True)
        skill_thread.start()

        # Open video source
        cap = cv2.VideoCapture(self.config.VIDEO_SOURCE)
        if not cap.isOpened():
            print(f"[ERROR] Cannot open video source: {self.config.VIDEO_SOURCE}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.config.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.FRAME_HEIGHT)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        print(f"[INFO] Video source opened. FPS: {fps}")
        print("[INFO] Press 'q' to quit.")

        # Parking assist mode is optional
        parking_mode = getattr(self.config, 'PARKING_MODE', False)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Frame grab failed, retrying...")
                time.sleep(0.1)
                continue

            self.frame_count += 1
            timestamp = datetime.now()

            # ── Core tracking ────────────────────────────────────────
            tracked_vehicles = self.vehicle_tracker.update(frame, timestamp)

            if parking_mode:
                # Parking mode: only show proximity grid
                frame = self.parking_assist.process(frame, tracked_vehicles, timestamp)
            else:
                # ── Full pipeline ────────────────────────────────────
                frame = self.lane_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.speed_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.drunk_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.tl_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.sign_recognizer.process(frame, tracked_vehicles, timestamp)
                frame = self.collision_warning.process(frame, tracked_vehicles, timestamp)
                frame = self.ped_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.obstacle_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.blind_spot.process(frame, tracked_vehicles, timestamp)
                frame = self.helmet_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.seatbelt_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.phone_detector.process(frame, tracked_vehicles, timestamp)
                frame = self.distraction_det.process(frame, tracked_vehicles, timestamp)

                # Driver HUD overlays
                frame = self.skill_clf.draw_overlay(frame)
                frame = self.lesson_tracker.draw_overlay(frame)

            # ── System HUD ───────────────────────────────────────────
            frame = self._draw_overlay(frame, tracked_vehicles)

            if self.config.SHOW_DISPLAY:
                cv2.imshow("Traffic Enforcement System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        cap.release()
        cv2.destroyAllWindows()
        self.stop()

    # ────────────────────────────────────────────────────────────────────────
    def stop(self):
        """Stop all subsystems gracefully."""
        self.running = False
        self.honk_detector.stop()
        self.voice_coach.stop()

        # End lesson session
        report_path = self.lesson_tracker.end_session(
            self.skill_clf.score, self.skill_clf.current_grade)
        print(f"[INFO] Lesson report saved → {report_path}")
        print("[INFO] System stopped.")

    # ────────────────────────────────────────────────────────────────────────
    def _skill_tick_loop(self):
        """Slowly recover skill score when no violations occur."""
        while self.running:
            time.sleep(1.0)
            self.skill_clf.tick()

    # ────────────────────────────────────────────────────────────────────────
    def _draw_overlay(self, frame, vehicles):
        """Draw HUD overlay on the frame."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame,
                    f"AI Traffic Enforcement | {ts} | Vehicles: {len(vehicles)}",
                    (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        cv2.putText(frame, f"Frame: {self.frame_count}",
                    (w - 150, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        return frame


# ─────────────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="AI Traffic Enforcement System")
    parser.add_argument("--source",      type=str,   default="0",
                        help="Video source: camera index (0,1) or video file path")
    parser.add_argument("--speed-limit", type=float, default=60.0,
                        help="Speed limit in km/h (default: 60)")
    parser.add_argument("--no-display",  action="store_true",
                        help="Disable video display (headless mode)")
    parser.add_argument("--log-dir",     type=str,   default="logs")
    parser.add_argument("--evidence-dir",type=str,   default="evidence")
    parser.add_argument("--parking",     action="store_true",
                        help="Enable parking-assist mode")
    parser.add_argument("--dashboard",   action="store_true",
                        help="Launch web dashboard alongside the detector")
    parser.add_argument("--dash-port",   type=int,   default=5000)
    return parser.parse_args()


if __name__ == "__main__":
    args   = parse_args()
    config = Settings()
    config.VIDEO_SOURCE   = int(args.source) if args.source.isdigit() else args.source
    config.SPEED_LIMIT_KMH = args.speed_limit
    config.SHOW_DISPLAY   = not args.no_display
    config.LOG_DIR        = args.log_dir
    config.EVIDENCE_DIR   = args.evidence_dir
    config.PARKING_MODE   = args.parking

    # Optionally start the web dashboard in a background thread
    if args.dashboard:
        from utils.dashboard import create_app
        import threading
        dash_app, dash_cache = create_app(
            f"{args.log_dir}/violations.csv")
        dash_thread = threading.Thread(
            target=lambda: dash_app.run(
                host="0.0.0.0", port=args.dash_port,
                debug=False, use_reloader=False),
            daemon=True)
        dash_thread.start()
        print(f"[DASHBOARD] Running at http://localhost:{args.dash_port}")

    system = TrafficEnforcementSystem(config)
    try:
        system.start()
    except KeyboardInterrupt:
        system.stop()
