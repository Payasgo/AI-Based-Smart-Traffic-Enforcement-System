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

from detectors.speed_detector import SpeedDetector
from detectors.drunk_driver_detector import DrunkDriverDetector
from detectors.honk_detector import HonkDetector
from detectors.vehicle_tracker import VehicleTracker
from utils.evidence_logger import EvidenceLogger
from utils.alert_system import AlertSystem
from config.settings import Settings


class TrafficEnforcementSystem:
    """Main orchestrator for the AI-based traffic enforcement system."""

    def __init__(self, config: Settings):
        self.config = config
        self.logger = EvidenceLogger(config.LOG_DIR, config.EVIDENCE_DIR)
        self.alert_system = AlertSystem(config)

        self.vehicle_tracker = VehicleTracker(config)
        self.speed_detector = SpeedDetector(config, self.logger, self.alert_system)
        self.drunk_detector = DrunkDriverDetector(config, self.logger, self.alert_system)
        self.honk_detector = HonkDetector(config, self.logger, self.alert_system)

        self.running = False
        self.frame_count = 0

    def start(self):
        """Start all detection subsystems."""
        self.running = True
        print("[INFO] Traffic Enforcement System starting...")

        # Start honk detection in separate thread (audio)
        honk_thread = threading.Thread(target=self.honk_detector.start_listening, daemon=True)
        honk_thread.start()

        # Open video source
        cap = cv2.VideoCapture(self.config.VIDEO_SOURCE)
        if not cap.isOpened():
            print(f"[ERROR] Cannot open video source: {self.config.VIDEO_SOURCE}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        print(f"[INFO] Video source opened. FPS: {fps}")
        print("[INFO] Press 'q' to quit.")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Frame grab failed, retrying...")
                time.sleep(0.1)
                continue

            self.frame_count += 1
            timestamp = datetime.now()

            # Track all vehicles in the frame
            tracked_vehicles = self.vehicle_tracker.update(frame, timestamp)

            # Run detectors on the frame
            frame = self.speed_detector.process(frame, tracked_vehicles, timestamp)
            frame = self.drunk_detector.process(frame, tracked_vehicles, timestamp)

            # Draw system overlay
            frame = self._draw_overlay(frame, tracked_vehicles)

            if self.config.SHOW_DISPLAY:
                cv2.imshow("Traffic Enforcement System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        cap.release()
        cv2.destroyAllWindows()
        self.stop()

    def stop(self):
        """Stop all subsystems gracefully."""
        self.running = False
        self.honk_detector.stop()
        print("[INFO] System stopped.")

    def _draw_overlay(self, frame, vehicles):
        """Draw HUD overlay on the frame."""
        h, w = frame.shape[:2]
        overlay = frame.copy()

        cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"AI Traffic Enforcement | {ts} | Vehicles: {len(vehicles)}",
                    (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

        cv2.putText(frame, f"Frame: {self.frame_count}",
                    (w - 150, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        return frame


def parse_args():
    parser = argparse.ArgumentParser(description="AI Traffic Enforcement System")
    parser.add_argument("--source", type=str, default="0",
                        help="Video source: camera index (0,1) or video file path")
    parser.add_argument("--speed-limit", type=float, default=60.0,
                        help="Speed limit in km/h (default: 60)")
    parser.add_argument("--no-display", action="store_true",
                        help="Disable video display (headless mode)")
    parser.add_argument("--log-dir", type=str, default="logs",
                        help="Directory for CSV logs")
    parser.add_argument("--evidence-dir", type=str, default="evidence",
                        help="Directory for saved evidence images")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    config = Settings()
    config.VIDEO_SOURCE = int(args.source) if args.source.isdigit() else args.source
    config.SPEED_LIMIT_KMH = args.speed_limit
    config.SHOW_DISPLAY = not args.no_display
    config.LOG_DIR = args.log_dir
    config.EVIDENCE_DIR = args.evidence_dir

    system = TrafficEnforcementSystem(config)
    try:
        system.start()
    except KeyboardInterrupt:
        system.stop()
