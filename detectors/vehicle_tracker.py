"""
Vehicle detection and tracking using YOLOv8 + gated global centroid assignment.

This keeps the existing public API so main.py and downstream detectors do not
need to change. It is a safer lightweight tracker, not a replacement for
appearance-based trackers such as ByteTrack/DeepSORT.
"""

from collections import OrderedDict

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


class CentroidTracker:
    """Track detections with globally optimal, distance-gated assignment."""

    def __init__(self, max_disappeared=40, max_distance=120.0):
        self.next_id = 0
        self.objects = OrderedDict()       # id -> (cx, cy)
        self.bboxes = OrderedDict()        # id -> (x1, y1, x2, y2)
        self.disappeared = OrderedDict()   # id -> missed frames
        self.max_disappeared = int(max_disappeared)
        self.max_distance = float(max_distance)

        if self.max_disappeared < 0:
            raise ValueError("max_disappeared must be >= 0")
        if self.max_distance <= 0:
            raise ValueError("max_distance must be > 0")

    @staticmethod
    def _normalize_bbox(bbox):
        x1, y1, x2, y2 = map(int, bbox)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Invalid bounding box: {bbox}")
        return (x1, y1, x2, y2)

    @staticmethod
    def _centroid(bbox):
        x1, y1, x2, y2 = bbox
        # Keep floating-point coordinates to avoid unnecessary rounding noise.
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def register(self, centroid, bbox):
        self.objects[self.next_id] = tuple(centroid)
        self.bboxes[self.next_id] = tuple(bbox)
        self.disappeared[self.next_id] = 0
        self.next_id += 1

    def deregister(self, obj_id):
        self.objects.pop(obj_id, None)
        self.bboxes.pop(obj_id, None)
        self.disappeared.pop(obj_id, None)

    def _mark_missed(self, obj_id):
        self.disappeared[obj_id] += 1
        if self.disappeared[obj_id] > self.max_disappeared:
            self.deregister(obj_id)

    def update(self, detections):
        """
        Args:
            detections: iterable of (x1, y1, x2, y2) boxes.

        Returns:
            {track_id: {'centroid': (cx, cy), 'bbox': (x1, y1, x2, y2)}}
        """
        normalized = [self._normalize_bbox(box) for box in detections]
        input_centroids = [self._centroid(box) for box in normalized]

        if not normalized:
            for obj_id in list(self.disappeared.keys()):
                self._mark_missed(obj_id)
            return self._as_dict()

        if not self.objects:
            for centroid, bbox in zip(input_centroids, normalized):
                self.register(centroid, bbox)
            return self._as_dict()

        object_ids = list(self.objects.keys())
        object_centroids = np.asarray(
            [self.objects[obj_id] for obj_id in object_ids], dtype=np.float64
        )
        detection_centroids = np.asarray(input_centroids, dtype=np.float64)

        distances = np.linalg.norm(
            object_centroids[:, np.newaxis, :] -
            detection_centroids[np.newaxis, :, :],
            axis=2,
        )

        # Hungarian assignment avoids the order-dependent greedy matching bug.
        rows, cols = linear_sum_assignment(distances)
        matched_rows, matched_cols = set(), set()

        for row, col in zip(rows, cols):
            # Reject implausible jumps rather than attaching a track to a
            # distant detection. Both sides remain available for miss/register.
            if distances[row, col] > self.max_distance:
                continue

            obj_id = object_ids[row]
            self.objects[obj_id] = input_centroids[col]
            self.bboxes[obj_id] = normalized[col]
            self.disappeared[obj_id] = 0
            matched_rows.add(row)
            matched_cols.add(col)

        for row, obj_id in enumerate(object_ids):
            if row not in matched_rows and obj_id in self.disappeared:
                self._mark_missed(obj_id)

        for col, (centroid, bbox) in enumerate(zip(input_centroids, normalized)):
            if col not in matched_cols:
                self.register(centroid, bbox)

        return self._as_dict()

    def _as_dict(self):
        return {
            obj_id: {
                "centroid": centroid,
                "bbox": self.bboxes[obj_id],
            }
            for obj_id, centroid in self.objects.items()
        }


class VehicleTracker:
    """YOLO-based vehicle detector with a lightweight centroid tracker."""

    def __init__(self, config):
        self.config = config
        self.tracker = CentroidTracker(
            max_disappeared=getattr(config, "TRACKER_MAX_DISAPPEARED", 40),
            max_distance=getattr(config, "TRACKER_MAX_DISTANCE", 120.0),
        )
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.config.YOLO_MODEL_PATH)
            print(f"[INFO] YOLO model loaded: {self.config.YOLO_MODEL_PATH}")
        except Exception as exc:
            # Do not silently pretend that detections are being produced.
            self.model = None
            print(f"[ERROR] YOLO model unavailable: {exc}")

    def update(self, frame, timestamp):
        """Detect vehicles and update tracks. Timestamp retained for API compatibility."""
        detections = self._detect(frame)
        tracked = self.tracker.update(detections)

        for obj_id, info in tracked.items():
            x1, y1, x2, y2 = info["bbox"]
            cx, cy = info["centroid"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 255), 2)
            cv2.putText(
                frame, f"V{obj_id}", (x1, max(15, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1,
            )
            cv2.circle(frame, (int(cx), int(cy)), 4, (0, 255, 0), -1)

        return tracked

    def _detect(self, frame):
        """Run YOLO inference and return valid vehicle bounding boxes."""
        if self.model is None:
            return []

        results = self.model(
            frame,
            conf=self.config.YOLO_CONF_THRESHOLD,
            iou=self.config.YOLO_IOU_THRESHOLD,
            verbose=False,
        )
        boxes = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls = int(box.cls[0])
                if cls not in self.config.VEHICLE_CLASS_IDS:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                if x2 > x1 and y2 > y1:
                    boxes.append((x1, y1, x2, y2))
        return boxes
