"""
Drunk / drowsy driver detection using facial landmarks (Eye Aspect Ratio)
and erratic lane behaviour (centroid swerve detection).
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from scipy.spatial import distance as dist


def eye_aspect_ratio(eye_points):
    """
    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
    eye_points: list of 6 (x,y) tuples
    """
    A = dist.euclidean(eye_points[1], eye_points[5])
    B = dist.euclidean(eye_points[2], eye_points[4])
    C = dist.euclidean(eye_points[0], eye_points[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


class DrunkDriverDetector:
    """
    Detects drowsiness via Eye Aspect Ratio and erratic driving via
    vehicle centroid swerve analysis.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system

        self.detector  = None
        self.predictor = None
        self._load_models()

        # Per-vehicle state
        self.ear_counters   = defaultdict(int)    # frames below EAR threshold
        self.swerve_history = defaultdict(lambda: deque(maxlen=60))
        self.swerve_counters = defaultdict(int)
        self._alerted        = set()

    def _load_models(self):
        try:
            import dlib
            self.detector  = dlib.get_frontal_face_detector()
            self.predictor = dlib.shape_predictor(self.config.DLIB_LANDMARK_MODEL)
            print("[INFO] Dlib face detector loaded.")
        except Exception as e:
            print(f"[WARNING] Dlib not loaded ({e}). Drowsiness detection limited.")

    def process(self, frame, tracked_vehicles, timestamp):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for vid, info in tracked_vehicles.items():
            cx, cy = info['centroid']
            x1, y1, x2, y2 = info['bbox']

            # ── Swerve / erratic driving detection ──────────────────
            self.swerve_history[vid].append(cx)
            if len(self.swerve_history[vid]) >= 10:
                xs    = list(self.swerve_history[vid])
                swerve = max(xs) - min(xs)
                if swerve > self.config.SWERVE_PIXEL_THRESHOLD:
                    self.swerve_counters[vid] += 1
                    if (self.swerve_counters[vid] >= self.config.SWERVE_CONSEC_FRAMES
                            and vid not in self._alerted):
                        self._alerted.add(vid)
                        self._handle_violation(frame, info, "ERRATIC_DRIVING", timestamp)
                        self.swerve_counters[vid] = 0
                else:
                    self.swerve_counters[vid] = max(0, self.swerve_counters[vid] - 1)

            # ── Face / eye analysis within vehicle ROI ───────────────
            if self.detector and self.predictor:
                roi_gray = gray[max(0, y1):y2, max(0, x1):x2]
                faces = self.detector(roi_gray, 0)
                for face in faces:
                    shape = self.predictor(roi_gray, face)
                    pts   = [(shape.part(i).x + x1, shape.part(i).y + y1)
                             for i in range(68)]

                    left_eye  = pts[36:42]
                    right_eye = pts[42:48]
                    ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0

                    # Draw EAR on frame
                    cv2.putText(frame, f"EAR:{ear:.2f}", (x1, y2 + 16),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 100, 255), 1)

                    if ear < self.config.EYE_AR_THRESHOLD:
                        self.ear_counters[vid] += 1
                        if (self.ear_counters[vid] >= self.config.EYE_AR_CONSEC_FRAMES
                                and vid not in self._alerted):
                            self._alerted.add(vid)
                            self._handle_violation(frame, info, "DROWSY_DRIVER", timestamp)
                            self.ear_counters[vid] = 0
                    else:
                        self.ear_counters[vid] = max(0, self.ear_counters[vid] - 1)

                    # Visualise eye contours
                    for pt in left_eye + right_eye:
                        cv2.circle(frame, pt, 2, (0, 255, 255), -1)

        return frame

    def _handle_violation(self, frame, info, vtype, timestamp):
        print(f"[VIOLATION] {vtype} detected.")
        evidence_path = self.logger.save_evidence(frame, vtype, "UNKNOWN", timestamp)
        self.logger.log_violation(
            violation_type=vtype,
            license_plate="UNKNOWN",
            speed_kmh=None,
            timestamp=timestamp,
            evidence_path=evidence_path
        )
        self.alert_system.send_alert(vtype, "UNKNOWN", None, timestamp)
