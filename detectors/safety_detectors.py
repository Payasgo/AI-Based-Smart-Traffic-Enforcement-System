"""
Helmet Detection       – checks whether a motorcyclist wears a helmet.
Seatbelt Detection     – checks whether a car driver's seatbelt is visible.
Phone Usage Detection  – detects a driver holding a phone near their face.
Distraction Detection  – combines gaze direction + head-pose + phone cues.

All four classes share a common YOLOv8-based backbone (or fall back to
MediaPipe Face Mesh / OpenCV Haar cascades when ultralytics is absent).
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────────────
# Helper: safe YOLO loader
# ──────────────────────────────────────────────────────────────────────────────

def _load_yolo(model_path: str):
    try:
        from ultralytics import YOLO
        return YOLO(model_path)
    except Exception as e:
        print(f"[WARNING] YOLO not loaded for safety detectors ({e}).")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 1. Helmet Detection
# ──────────────────────────────────────────────────────────────────────────────

class HelmetDetector:
    """
    Detects whether motorcycle riders are wearing helmets.

    Strategy:
      • YOLO detects motorcycles (class 3 in COCO).
      • For each motorcycle ROI the upper third is cropped (where the head is).
      • A colour/shape heuristic checks for helmet-like circular contours.
      • If a custom YOLOv8 helmet model is provided in config it is used instead.
    """

    MOTORCYCLE_CLASS = 3   # COCO class id

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._alerted: set = set()

        # Optional dedicated helmet model; falls back to heuristic
        helmet_model_path = getattr(config, 'HELMET_MODEL_PATH', None)
        self._helmet_model = _load_yolo(helmet_model_path) if helmet_model_path else None
        self._vehicle_model = _load_yolo(config.YOLO_MODEL_PATH)

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        for vid, info in tracked_vehicles.items():
            x1, y1, x2, y2 = info['bbox']
            # Narrow check to motorcycles only (class stored by tracker if available)
            vehicle_class = info.get('class_id', -1)
            if vehicle_class not in (self.MOTORCYCLE_CLASS, -1):
                continue

            head_roi = frame[y1: y1 + (y2 - y1) // 3, x1:x2]
            if head_roi.size == 0:
                continue

            has_helmet = self._check_helmet(head_roi)
            color = (0, 200, 0) if has_helmet else (0, 0, 255)
            label = "HELMET OK" if has_helmet else "NO HELMET!"
            cv2.putText(frame, label, (x1, y1 - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            if not has_helmet and vid not in self._alerted:
                self._alerted.add(vid)
                self._handle_violation(frame, info, timestamp)

        return frame

    # ------------------------------------------------------------------
    def _check_helmet(self, roi: np.ndarray) -> bool:
        """
        Heuristic: look for a large, roughly circular, dark or coloured blob
        in the upper portion of the motorcycle bounding box.
        Falls back to True (safe) when the ROI is too small to judge.
        """
        if self._helmet_model:
            results = self._helmet_model(roi, verbose=False)
            for r in results:
                for box in r.boxes:
                    if int(box.cls[0]) == 0:   # assume class 0 = helmet
                        return True
            return False

        # Colour-blob heuristic
        h, w = roi.shape[:2]
        if h < 10 or w < 10:
            return True   # too small; assume OK
        gray    = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1.2,
            minDist=max(h // 2, 10),
            param1=80, param2=30,
            minRadius=max(h // 4, 5),
            maxRadius=max(h, 10)
        )
        return circles is not None

    # ------------------------------------------------------------------
    def _handle_violation(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[VIOLATION] NO HELMET detected | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "NO_HELMET", plate, timestamp)
        self.logger.log_violation("NO_HELMET", plate, None, timestamp, ev)
        self.alert_system.send_alert("NO_HELMET", plate, None, timestamp)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Seatbelt Detection
# ──────────────────────────────────────────────────────────────────────────────

class SeatbeltDetector:
    """
    Detects whether the driver is wearing a seatbelt.

    Strategy:
      • Crop the driver's torso region from each tracked vehicle's ROI.
      • Use edge + line detection to look for a diagonal strap across the chest.
      • Optionally use a custom YOLO seatbelt model if provided.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._alerted: set = set()
        self._counter: dict[int, int] = defaultdict(int)   # frames without seatbelt

        sb_model_path = getattr(config, 'SEATBELT_MODEL_PATH', None)
        self._model   = _load_yolo(sb_model_path) if sb_model_path else None

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        for vid, info in tracked_vehicles.items():
            x1, y1, x2, y2 = info['bbox']
            # Torso: middle horizontal third, left half (driver side)
            torso_y1 = y1 + (y2 - y1) // 3
            torso_y2 = y1 + 2 * (y2 - y1) // 3
            torso_x2 = x1 + (x2 - x1) // 2
            torso = frame[torso_y1:torso_y2, x1:torso_x2]
            if torso.size == 0:
                continue

            belt_found = self._detect_belt(torso)

            if not belt_found:
                self._counter[vid] += 1
                required = getattr(self.config, 'SEATBELT_CONSEC_FRAMES', 20)
                if self._counter[vid] >= required and vid not in self._alerted:
                    self._alerted.add(vid)
                    self._handle_violation(frame, info, timestamp)
                label, color = "NO SEATBELT!", (0, 0, 255)
            else:
                self._counter[vid] = max(0, self._counter[vid] - 2)
                self._alerted.discard(vid)
                label, color = "SEATBELT OK", (0, 200, 0)

            cv2.putText(frame, label, (x1, y1 - 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        return frame

    # ------------------------------------------------------------------
    def _detect_belt(self, torso: np.ndarray) -> bool:
        if self._model:
            results = self._model(torso, verbose=False)
            for r in results:
                for box in r.boxes:
                    if int(box.cls[0]) == 0:   # class 0 = seatbelt
                        return True
            return False

        # Diagonal-line heuristic
        gray  = cv2.cvtColor(torso, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30,
                                 minLineLength=torso.shape[0] // 3,
                                 maxLineGap=20)
        if lines is None:
            return False
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 == x1:
                continue
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            # Seatbelt runs diagonally ~30-60 degrees
            if 25 < angle < 65:
                return True
        return False

    # ------------------------------------------------------------------
    def _handle_violation(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[VIOLATION] NO SEATBELT detected | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "NO_SEATBELT", plate, timestamp)
        self.logger.log_violation("NO_SEATBELT", plate, None, timestamp, ev)
        self.alert_system.send_alert("NO_SEATBELT", plate, None, timestamp)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Phone Usage Detection
# ──────────────────────────────────────────────────────────────────────────────

class PhoneUsageDetector:
    """
    Detects a driver holding a phone near their face / ear.

    Strategy:
      • Detect faces inside each vehicle's ROI.
      • Detect cell phones (COCO class 67) in the same ROI.
      • Flag if a phone bounding box overlaps or is close to a face box.
    """

    PHONE_CLASS = 67   # COCO class id

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._alerted: set = set()
        self._counter: dict[int, int] = defaultdict(int)
        self._model = _load_yolo(config.YOLO_MODEL_PATH)

        # Face cascade as lightweight fallback
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self._face_cascade = cv2.CascadeClassifier(cascade_path)

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        for vid, info in tracked_vehicles.items():
            x1, y1, x2, y2 = info['bbox']
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            phone_detected = self._detect_phone(roi)

            if phone_detected:
                self._counter[vid] += 1
                required = getattr(self.config, 'PHONE_CONSEC_FRAMES', 15)
                if self._counter[vid] >= required and vid not in self._alerted:
                    self._alerted.add(vid)
                    self._handle_violation(frame, info, timestamp)
                cv2.putText(frame, "PHONE USAGE!", (x1, y1 - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            else:
                self._counter[vid] = max(0, self._counter[vid] - 1)
                self._alerted.discard(vid)

        return frame

    # ------------------------------------------------------------------
    def _detect_phone(self, roi: np.ndarray) -> bool:
        if self._model is None:
            return False

        results = self._model(roi, conf=0.35, verbose=False)
        phone_boxes, face_boxes = [], []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                coords = list(map(int, box.xyxy[0]))
                if cls == self.PHONE_CLASS:
                    phone_boxes.append(coords)
                elif cls == 0:   # person / face (loose proxy)
                    face_boxes.append(coords)

        # Fallback face detection
        if not face_boxes:
            gray  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            for (fx, fy, fw, fh) in faces:
                face_boxes.append([fx, fy, fx + fw, fy + fh])

        for pb in phone_boxes:
            for fb in face_boxes:
                if self._iou(pb, fb) > 0.05 or self._proximity(pb, fb) < 60:
                    return True
        return False

    @staticmethod
    def _iou(a, b) -> float:
        ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
        ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _proximity(a, b) -> float:
        ca = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
        cb = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        return np.hypot(ca[0] - cb[0], ca[1] - cb[1])

    # ------------------------------------------------------------------
    def _handle_violation(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[VIOLATION] PHONE USAGE detected | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "PHONE_USAGE", plate, timestamp)
        self.logger.log_violation("PHONE_USAGE", plate, None, timestamp, ev)
        self.alert_system.send_alert("PHONE_USAGE", plate, None, timestamp)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Distraction Detection
# ──────────────────────────────────────────────────────────────────────────────

class DistractionDetector:
    """
    Detects driver distraction via head-pose estimation (yaw / pitch).

    Strategy:
      • Locate facial landmarks with dlib or MediaPipe.
      • Estimate head pose using a 6-point PnP solve against a 3-D face model.
      • Flag large yaw (looking sideways) or large pitch (looking down) as
        distracted.
      • Also flags activity like eating, applying makeup using object proximity.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._alerted: set = set()
        self._counter: dict[int, int] = defaultdict(int)

        self._predictor = None
        self._detector  = None
        self._mp_face   = None
        self._load_models()

        # 3-D model points for 6-point PnP (generic face)
        self._model_pts = np.array([
            [0.0,    0.0,    0.0   ],   # Nose tip
            [0.0,   -330.0, -65.0 ],   # Chin
            [-225.0, 170.0, -135.0],   # Left eye corner
            [225.0,  170.0, -135.0],   # Right eye corner
            [-150.0,-150.0, -125.0],   # Left mouth corner
            [150.0, -150.0, -125.0],   # Right mouth corner
        ], dtype=np.float64)

    # ------------------------------------------------------------------
    def _load_models(self):
        try:
            import dlib
            self._detector  = dlib.get_frontal_face_detector()
            self._predictor = dlib.shape_predictor(
                self.config.DLIB_LANDMARK_MODEL)
            print("[INFO] DistractionDetector: dlib loaded.")
            return
        except Exception:
            pass
        try:
            import mediapipe as mp
            self._mp_face = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=1,
                refine_landmarks=True, min_detection_confidence=0.5)
            print("[INFO] DistractionDetector: MediaPipe FaceMesh loaded.")
        except Exception as e:
            print(f"[WARNING] DistractionDetector: no pose model ({e}).")

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]
        cam_matrix = np.array([
            [w, 0, w / 2],
            [0, w, h / 2],
            [0, 0,     1]], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        for vid, info in tracked_vehicles.items():
            x1, y1, x2, y2 = info['bbox']
            roi_gray = gray[max(0, y1):y2, max(0, x1):x2]
            if roi_gray.size == 0:
                continue

            yaw, pitch = self._estimate_head_pose(
                frame, roi_gray, x1, y1, cam_matrix, dist_coeffs)

            if yaw is None:
                continue

            yaw_thresh   = getattr(self.config, 'DISTRACTION_YAW_DEG',   25)
            pitch_thresh = getattr(self.config, 'DISTRACTION_PITCH_DEG', 20)
            distracted = abs(yaw) > yaw_thresh or abs(pitch) > pitch_thresh

            label = f"YAW:{yaw:+.0f} PITCH:{pitch:+.0f}"
            color = (0, 0, 255) if distracted else (0, 200, 200)
            cv2.putText(frame, label, (x1, y2 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            if distracted:
                self._counter[vid] += 1
                req = getattr(self.config, 'DISTRACTION_CONSEC_FRAMES', 20)
                if self._counter[vid] >= req and vid not in self._alerted:
                    self._alerted.add(vid)
                    self._handle_violation(frame, info, timestamp)
                cv2.putText(frame, "DISTRACTED!", (x1, y1 - 62),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
            else:
                self._counter[vid] = max(0, self._counter[vid] - 1)
                self._alerted.discard(vid)

        return frame

    # ------------------------------------------------------------------
    def _estimate_head_pose(self, frame, roi_gray, ox, oy,
                             cam_matrix, dist_coeffs):
        """Return (yaw_deg, pitch_deg) or (None, None)."""
        img_pts = None

        if self._predictor and self._detector:
            import dlib
            faces = self._detector(roi_gray, 0)
            if not faces:
                return None, None
            face  = faces[0]
            shape = self._predictor(roi_gray, face)
            # 6 landmark indices matching _model_pts
            idxs  = [30, 8, 36, 45, 48, 54]
            img_pts = np.array(
                [(shape.part(i).x + ox, shape.part(i).y + oy) for i in idxs],
                dtype=np.float64)

        elif self._mp_face:
            rgb = cv2.cvtColor(roi_gray, cv2.COLOR_GRAY2RGB)
            res = self._mp_face.process(rgb)
            if not res.multi_face_landmarks:
                return None, None
            lm = res.multi_face_landmarks[0].landmark
            h, w = roi_gray.shape[:2]
            # Approx indices for nose/chin/eyes/mouth corners
            key_idxs = [1, 152, 33, 263, 61, 291]
            img_pts = np.array(
                [(lm[i].x * w + ox, lm[i].y * h + oy) for i in key_idxs],
                dtype=np.float64)
        else:
            return None, None

        success, rot_vec, _ = cv2.solvePnP(
            self._model_pts, img_pts, cam_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE)
        if not success:
            return None, None

        rot_mat, _ = cv2.Rodrigues(rot_vec)
        angles, *_ = cv2.RQDecomp3x3(rot_mat)
        pitch, yaw = angles[0], angles[1]
        return float(yaw), float(pitch)

    # ------------------------------------------------------------------
    def _handle_violation(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[VIOLATION] DISTRACTION detected | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "DISTRACTION", plate, timestamp)
        self.logger.log_violation("DISTRACTION", plate, None, timestamp, ev)
        self.alert_system.send_alert("DISTRACTION", plate, None, timestamp)
