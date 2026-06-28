"""
Road-Scene Detectors
====================
• TrafficLightDetector    – detects red / amber / green signal state
• TrafficSignRecognizer   – classifies common road signs
• CollisionWarning        – Time-to-Collision (TTC) estimation
• PedestrianDetector      – pedestrian detection + unsafe proximity alert
• ObstacleDetector        – generic in-path obstacle detection
• BlindSpotDetector       – flags vehicles in adjacent lanes
• ParkingAssistant        – guides parking via rear-view proximity grid
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────────────
# Shared YOLO helper
# ──────────────────────────────────────────────────────────────────────────────

def _load_yolo(path: str):
    try:
        from ultralytics import YOLO
        return YOLO(path)
    except Exception as e:
        print(f"[WARNING] YOLO load failed ({e}).")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 1. Traffic Light Detector
# ──────────────────────────────────────────────────────────────────────────────

class TrafficLightDetector:
    """
    Detects traffic-light state (RED / AMBER / GREEN) using colour segmentation
    in the upper portion of the frame, or a YOLO traffic-light model if provided.

    A red-light violation is flagged when a vehicle crosses a stop line while
    the detected signal is RED.
    """

    # COCO class 9 = traffic light
    TL_CLASS = 9

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._model       = _load_yolo(config.YOLO_MODEL_PATH)
        self._alerted: set = set()
        self._state       = "UNKNOWN"     # RED | AMBER | GREEN | UNKNOWN

        # Stop line Y position (fraction of frame height)
        self._stop_line_y_frac = getattr(config, 'TRAFFIC_STOP_LINE_Y', 0.7)

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        h, w = frame.shape[:2]
        stop_y = int(h * self._stop_line_y_frac)

        # Detect signal state
        self._state = self._detect_state(frame)

        # Draw stop line and state
        color_map = {"RED": (0, 0, 255), "AMBER": (0, 165, 255),
                     "GREEN": (0, 255, 0), "UNKNOWN": (128, 128, 128)}
        line_color = color_map.get(self._state, (128, 128, 128))
        cv2.line(frame, (0, stop_y), (w, stop_y), line_color, 2)
        cv2.putText(frame, f"SIGNAL: {self._state}", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, line_color, 2)

        # Check vehicles crossing stop line on RED
        if self._state == "RED":
            for vid, info in tracked_vehicles.items():
                _, _, _, y2 = info['bbox']
                if y2 > stop_y and vid not in self._alerted:
                    self._alerted.add(vid)
                    self._handle_violation(frame, info, timestamp)
        else:
            self._alerted.clear()

        return frame

    # ------------------------------------------------------------------
    def _detect_state(self, frame: np.ndarray) -> str:
        """Use colour segmentation in top-third of frame."""
        h, w = frame.shape[:2]
        roi  = frame[0:h // 3, w // 4: 3 * w // 4]
        hsv  = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Colour masks
        red1   = cv2.inRange(hsv, (0,  120,  70), (10,  255, 255))
        red2   = cv2.inRange(hsv, (170, 120,  70), (180, 255, 255))
        red    = cv2.bitwise_or(red1, red2)
        amber  = cv2.inRange(hsv, (10,  120,  70), (30,  255, 255))
        green  = cv2.inRange(hsv, (40,   60,  70), (90,  255, 255))

        counts = {
            "RED":   cv2.countNonZero(red),
            "AMBER": cv2.countNonZero(amber),
            "GREEN": cv2.countNonZero(green),
        }
        best = max(counts, key=counts.get)
        return best if counts[best] > 200 else "UNKNOWN"

    # ------------------------------------------------------------------
    def _handle_violation(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[VIOLATION] RED LIGHT crossed | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "RED_LIGHT", plate, timestamp)
        self.logger.log_violation("RED_LIGHT", plate, None, timestamp, ev)
        self.alert_system.send_alert("RED_LIGHT", plate, None, timestamp)

    @property
    def current_state(self) -> str:
        return self._state


# ──────────────────────────────────────────────────────────────────────────────
# 2. Traffic Sign Recognizer
# ──────────────────────────────────────────────────────────────────────────────

class TrafficSignRecognizer:
    """
    Classifies road signs using a colour + shape heuristic pipeline,
    or a dedicated YOLO traffic-sign model when provided.

    Recognised categories (heuristic): STOP, YIELD, SPEED-LIMIT, WARNING, INFO.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        model_path        = getattr(config, 'SIGN_MODEL_PATH', None)
        self._model       = _load_yolo(model_path) if model_path else None
        self._last_sign   = "NONE"

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        signs = self._detect_signs(frame)
        for (x1, y1, x2, y2, label) in signs:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 2)
            self._last_sign = label

        if signs:
            cv2.putText(frame, f"SIGN: {signs[-1][4]}", (10, 105),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)
        return frame

    # ------------------------------------------------------------------
    def _detect_signs(self, frame):
        """Return list of (x1,y1,x2,y2,label)."""
        if self._model:
            return self._yolo_detect(frame)
        return self._heuristic_detect(frame)

    def _yolo_detect(self, frame):
        results = self._model(frame, verbose=False)
        out = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                label = self._model.names.get(cls, f"SIGN_{cls}")
                out.append((x1, y1, x2, y2, label.upper()))
        return out

    def _heuristic_detect(self, frame):
        """Simple colour-based sign detection."""
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        out  = []

        # Red octagonal → STOP
        red1 = cv2.inRange(hsv, (0,  140, 70), (10,  255, 255))
        red2 = cv2.inRange(hsv, (170, 140, 70), (180, 255, 255))
        red  = cv2.bitwise_or(red1, red2)
        out += self._contour_signs(red, "STOP", frame.shape)

        # Yellow triangle → WARNING
        yellow = cv2.inRange(hsv, (20, 100, 100), (35, 255, 255))
        out   += self._contour_signs(yellow, "WARNING", frame.shape)

        # Blue rectangle → INFO
        blue  = cv2.inRange(hsv, (100, 100, 50), (130, 255, 255))
        out  += self._contour_signs(blue, "INFO", frame.shape)

        return out

    @staticmethod
    def _contour_signs(mask, label, shape):
        kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        cnts, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
        signs = []
        h, w  = shape[:2]
        for c in cnts:
            area = cv2.contourArea(c)
            if area < 400 or area > 0.1 * h * w:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            signs.append((x, y, x + bw, y + bh, label))
        return signs


# ──────────────────────────────────────────────────────────────────────────────
# 3. Collision Warning
# ──────────────────────────────────────────────────────────────────────────────

class CollisionWarning:
    """
    Estimates Time-to-Collision (TTC) for each tracked vehicle using
    optical-flow-based looming (expanding bounding box area).

    TTC ≈ bbox_area / d(bbox_area)/dt
    """

    TTC_WARN_SEC  = 3.0   # Warn if TTC < this
    TTC_ALERT_SEC = 1.5   # Critical if TTC < this

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._prev_area: dict[int, float] = {}
        self._prev_ts:   dict[int, float] = {}
        self._alerted: set = set()

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        import time
        now = timestamp.timestamp()

        for vid, info in tracked_vehicles.items():
            x1, y1, x2, y2 = info['bbox']
            area = float((x2 - x1) * (y2 - y1))

            if vid in self._prev_area and vid in self._prev_ts:
                dt      = now - self._prev_ts[vid]
                da      = area - self._prev_area[vid]
                if dt > 0 and da > 0:
                    ttc = area / (da / dt)
                    ttc = min(ttc, 999.9)
                    label_color = (0, 255, 0)
                    if ttc < self.TTC_WARN_SEC:
                        label_color = (0, 165, 255)
                    if ttc < self.TTC_ALERT_SEC:
                        label_color = (0, 0, 255)
                        if vid not in self._alerted:
                            self._alerted.add(vid)
                            self._handle_warning(frame, info, ttc, timestamp)
                    else:
                        self._alerted.discard(vid)

                    cv2.putText(frame, f"TTC:{ttc:.1f}s", (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, label_color, 1)

            self._prev_area[vid] = area
            self._prev_ts[vid]   = now

        return frame

    # ------------------------------------------------------------------
    def _handle_warning(self, frame, info, ttc, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[WARNING] COLLISION IMMINENT TTC={ttc:.1f}s | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "COLLISION_WARNING", plate, timestamp)
        self.logger.log_violation("COLLISION_WARNING", plate, None, timestamp, ev)
        self.alert_system.send_alert("COLLISION_WARNING", plate, None, timestamp)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Pedestrian Detector
# ──────────────────────────────────────────────────────────────────────────────

class PedestrianDetector:
    """
    Detects pedestrians (COCO class 0) and warns if a vehicle is
    approaching them too closely.
    """

    PERSON_CLASS = 0

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._model       = _load_yolo(config.YOLO_MODEL_PATH)
        self._alerted: set = set()
        # HOG fallback
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        pedestrians = self._detect_pedestrians(frame)

        for (px1, py1, px2, py2) in pedestrians:
            cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 0, 255), 2)
            cv2.putText(frame, "PEDESTRIAN", (px1, py1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 1)

        # Check proximity between pedestrians and vehicle bboxes
        prox_thresh = getattr(self.config, 'PED_PROXIMITY_PIXELS', 80)
        for vid, info in tracked_vehicles.items():
            vx1, vy1, vx2, vy2 = info['bbox']
            for (px1, py1, px2, py2) in pedestrians:
                dist = self._bbox_distance(
                    (vx1, vy1, vx2, vy2), (px1, py1, px2, py2))
                if dist < prox_thresh:
                    cv2.putText(frame, "PED ALERT!", (vx1, vy1 - 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                    key = (vid, px1, py1)
                    if key not in self._alerted:
                        self._alerted.add(key)
                        self._handle_alert(frame, info, timestamp)

        return frame

    # ------------------------------------------------------------------
    def _detect_pedestrians(self, frame):
        if self._model:
            results = self._model(frame, conf=0.40, verbose=False)
            boxes = []
            for r in results:
                for box in r.boxes:
                    if int(box.cls[0]) == self.PERSON_CLASS:
                        boxes.append(tuple(map(int, box.xyxy[0])))
            return boxes

        # HOG fallback
        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rects, _ = self._hog.detectMultiScale(
            gray, winStride=(8, 8), padding=(4, 4), scale=1.05)
        return [(x, y, x + w, y + h) for (x, y, w, h) in rects]

    @staticmethod
    def _bbox_distance(a, b) -> float:
        """Minimum edge distance between two bboxes."""
        dx = max(0, max(a[0], b[0]) - min(a[2], b[2]))
        dy = max(0, max(a[1], b[1]) - min(a[3], b[3]))
        return np.hypot(dx, dy)

    # ------------------------------------------------------------------
    def _handle_alert(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[WARNING] PEDESTRIAN PROXIMITY | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "PED_PROXIMITY", plate, timestamp)
        self.logger.log_violation("PED_PROXIMITY", plate, None, timestamp, ev)
        self.alert_system.send_alert("PED_PROXIMITY", plate, None, timestamp)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Obstacle Detector
# ──────────────────────────────────────────────────────────────────────────────

class ObstacleDetector:
    """
    Detects stationary or slow-moving obstacles in the vehicle's path
    using background subtraction + connected-component analysis.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._bg_sub      = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=50, detectShadows=False)
        self._alerted: set = set()

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        h, w = frame.shape[:2]
        # Only consider lower-half (road level)
        road_roi = frame[h // 2:, :]
        fg_mask  = self._bg_sub.apply(road_roi)

        kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        fg_mask  = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        fg_mask  = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  kernel)

        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg_mask)
        min_area = getattr(self.config, 'OBSTACLE_MIN_AREA', 1500)

        for i in range(1, n_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            ox = stats[i, cv2.CC_STAT_LEFT]
            oy = stats[i, cv2.CC_STAT_TOP] + h // 2
            ow = stats[i, cv2.CC_STAT_WIDTH]
            oh = stats[i, cv2.CC_STAT_HEIGHT]
            cv2.rectangle(frame, (ox, oy), (ox + ow, oy + oh), (0, 128, 255), 2)
            cv2.putText(frame, "OBSTACLE", (ox, oy - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 128, 255), 1)

            # Warn if any tracked vehicle's centroid is above obstacle and close
            for vid, info in tracked_vehicles.items():
                cx, cy = info['centroid']
                if ox < cx < ox + ow and cy < oy:
                    dist = oy - cy
                    if dist < getattr(self.config, 'OBSTACLE_ALERT_DIST', 120):
                        key = (vid, ox, oy)
                        if key not in self._alerted:
                            self._alerted.add(key)
                            self._handle_alert(frame, info, timestamp)

        return frame

    # ------------------------------------------------------------------
    def _handle_alert(self, frame, info, timestamp):
        plate = info.get('plate', 'UNKNOWN')
        print(f"[WARNING] OBSTACLE IN PATH | Plate: {plate}")
        ev = self.logger.save_evidence(frame, "OBSTACLE", plate, timestamp)
        self.logger.log_violation("OBSTACLE", plate, None, timestamp, ev)
        self.alert_system.send_alert("OBSTACLE", plate, None, timestamp)


# ──────────────────────────────────────────────────────────────────────────────
# 6. Blind Spot Detector
# ──────────────────────────────────────────────────────────────────────────────

class BlindSpotDetector:
    """
    Flags vehicles that enter the side (blind-spot) zones of the ego vehicle.

    The ego vehicle is assumed to be the largest tracked vehicle in the lower
    centre of the frame.  Two rectangular blind-spot zones are defined to its
    left and right at mid-frame height.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._alerted: set = set()

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        h, w = frame.shape[:2]

        ego = self._find_ego(tracked_vehicles, h, w)
        if ego is None:
            return frame

        ego_id, ego_info = ego
        ex1, ey1, ex2, ey2 = ego_info['bbox']

        # Blind-spot zones: flanking rectangles at ego mid-height
        zone_h = (ey2 - ey1)
        zone_w = getattr(self.config, 'BLIND_SPOT_ZONE_W', 120)
        mid_y  = (ey1 + ey2) // 2

        left_zone  = (max(0, ex1 - zone_w), mid_y - zone_h // 2,
                      ex1,                  mid_y + zone_h // 2)
        right_zone = (ex2,                  mid_y - zone_h // 2,
                      min(w, ex2 + zone_w), mid_y + zone_h // 2)

        for side, zone in (("LEFT", left_zone), ("RIGHT", right_zone)):
            cv2.rectangle(frame, zone[:2], zone[2:], (200, 200, 0), 1)
            for vid, info in tracked_vehicles.items():
                if vid == ego_id:
                    continue
                cx, cy = info['centroid']
                if zone[0] < cx < zone[2] and zone[1] < cy < zone[3]:
                    cv2.rectangle(frame, zone[:2], zone[2:], (0, 0, 255), 3)
                    cv2.putText(frame, f"BLIND SPOT {side}!", (zone[0], zone[1] - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    key = (ego_id, vid, side)
                    if key not in self._alerted:
                        self._alerted.add(key)
                        print(f"[WARNING] BLIND SPOT {side} | vid {vid}")

        return frame

    # ------------------------------------------------------------------
    @staticmethod
    def _find_ego(tracked_vehicles, h, w):
        """Heuristic: ego = largest vehicle in lower-centre region."""
        best_id, best_area = None, 0
        for vid, info in tracked_vehicles.items():
            x1, y1, x2, y2 = info['bbox']
            cx, cy = info['centroid']
            # Must be in lower half, roughly centred
            if cy < h * 0.5 or cx < w * 0.2 or cx > w * 0.8:
                continue
            area = (x2 - x1) * (y2 - y1)
            if area > best_area:
                best_area = area
                best_id = vid
        if best_id is None:
            return None
        return best_id, tracked_vehicles[best_id]


# ──────────────────────────────────────────────────────────────────────────────
# 7. Parking Assistant
# ──────────────────────────────────────────────────────────────────────────────

class ParkingAssistant:
    """
    Provides a visual rear-proximity grid overlay to assist parking.

    Uses background subtraction on a rear-view crop to estimate distance to
    the nearest obstacle and overlays a colour-coded proximity grid.
    Emits a beep-rate indication (text) and logs close-obstacle events.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self._bg_sub      = cv2.createBackgroundSubtractorKNN(
            history=200, dist2Threshold=400, detectShadows=False)
        self._warning_issued = False

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray, tracked_vehicles: dict,
                timestamp: datetime) -> np.ndarray:
        """
        In a real deployment this would receive a rear-camera feed.
        Here we use the lower portion of the current frame as proxy.
        """
        h, w = frame.shape[:2]
        rear_roi = frame[int(h * 0.65):, :]

        fg = self._bg_sub.apply(rear_roi)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel)

        # Divide rear ROI into 3 columns × 3 rows grid
        grid_rows, grid_cols = 3, 3
        rh, rw = rear_roi.shape[:2]
        cell_h = rh // grid_rows
        cell_w = rw // grid_cols
        offset_y = int(h * 0.65)

        for r in range(grid_rows):
            for c in range(grid_cols):
                y0, y1_ = r * cell_h, (r + 1) * cell_h
                x0, x1_ = c * cell_w, (c + 1) * cell_w
                cell_fg = fg[y0:y1_, x0:x1_]
                density = cv2.countNonZero(cell_fg) / max(cell_fg.size, 1)

                # Colour by density
                if density > 0.35:
                    color, label = (0, 0, 255), "!!!"
                elif density > 0.15:
                    color, label = (0, 165, 255), " ! "
                else:
                    color, label = (0, 200, 0), "   "

                # Draw on actual frame
                fy0, fy1 = y0 + offset_y, y1_ + offset_y
                cv2.rectangle(frame, (x0, fy0), (x1_, fy1), color, 1)
                cv2.putText(frame, label,
                            (x0 + cell_w // 3, fy0 + cell_h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                # Alert on front row (closest)
                if r == 0 and density > 0.35 and not self._warning_issued:
                    self._warning_issued = True
                    cv2.putText(frame, "STOP – OBSTACLE CLOSE!", (10, h - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
                    print("[PARKING] Obstacle very close – stop!")

        if cv2.countNonZero(fg) / max(fg.size, 1) < 0.05:
            self._warning_issued = False  # clear when all clear

        cv2.putText(frame, "PARKING ASSIST ACTIVE", (10, h - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 200), 1)
        return frame
