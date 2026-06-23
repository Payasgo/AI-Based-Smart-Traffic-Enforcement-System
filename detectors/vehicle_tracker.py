"""
Vehicle detection and tracking using YOLOv8 + simple centroid tracker.
"""

import cv2
import numpy as np
from datetime import datetime
from collections import OrderedDict


class CentroidTracker:
    """Simple centroid-based tracker with unique IDs per vehicle."""

    def __init__(self, max_disappeared=40):
        self.next_id = 0
        self.objects = OrderedDict()      # id -> centroid
        self.bboxes  = OrderedDict()      # id -> (x,y,w,h)
        self.disappeared = OrderedDict()  # id -> frames since last seen
        self.max_disappeared = max_disappeared

    def register(self, centroid, bbox):
        self.objects[self.next_id] = centroid
        self.bboxes[self.next_id]  = bbox
        self.disappeared[self.next_id] = 0
        self.next_id += 1

    def deregister(self, obj_id):
        del self.objects[obj_id]
        del self.bboxes[obj_id]
        del self.disappeared[obj_id]

    def update(self, detections):
        """
        detections: list of (x1, y1, x2, y2) bounding boxes
        Returns dict: {id: {'centroid': (cx,cy), 'bbox': (x1,y1,x2,y2)}}
        """
        if not detections:
            for obj_id in list(self.disappeared):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)
            return self._as_dict()

        input_centroids = []
        input_bboxes    = []
        for (x1, y1, x2, y2) in detections:
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            input_centroids.append((cx, cy))
            input_bboxes.append((x1, y1, x2, y2))

        if not self.objects:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i], input_bboxes[i])
        else:
            obj_ids   = list(self.objects.keys())
            obj_cents = list(self.objects.values())

            D = np.linalg.norm(
                np.array(obj_cents)[:, np.newaxis] - np.array(input_centroids),
                axis=2
            )
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows, used_cols = set(), set()
            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                obj_id = obj_ids[row]
                self.objects[obj_id]     = input_centroids[col]
                self.bboxes[obj_id]      = input_bboxes[col]
                self.disappeared[obj_id] = 0
                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(D.shape[0])) - used_rows
            unused_cols = set(range(D.shape[1])) - used_cols

            for row in unused_rows:
                obj_id = obj_ids[row]
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)

            for col in unused_cols:
                self.register(input_centroids[col], input_bboxes[col])

        return self._as_dict()

    def _as_dict(self):
        result = {}
        for obj_id, centroid in self.objects.items():
            result[obj_id] = {
                'centroid': centroid,
                'bbox': self.bboxes[obj_id]
            }
        return result


class VehicleTracker:
    """YOLO-based vehicle detector with centroid tracking."""

    def __init__(self, config):
        self.config  = config
        self.tracker = CentroidTracker(max_disappeared=40)
        self.model   = None
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.config.YOLO_MODEL_PATH)
            print(f"[INFO] YOLOv8 model loaded: {self.config.YOLO_MODEL_PATH}")
        except Exception as e:
            print(f"[WARNING] YOLO model not loaded ({e}). Using mock detections.")

    def update(self, frame, timestamp):
        """Detect vehicles and update tracker. Returns tracked vehicle dict."""
        detections = self._detect(frame)
        tracked    = self.tracker.update(detections)

        # Draw bounding boxes
        for obj_id, info in tracked.items():
            x1, y1, x2, y2 = info['bbox']
            cx, cy = info['centroid']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 255), 2)
            cv2.putText(frame, f"V{obj_id}", (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
            cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

        return tracked

    def _detect(self, frame):
        """Run YOLO inference; fall back to empty list if model unavailable."""
        if self.model is None:
            return []
        results = self.model(
            frame,
            conf=self.config.YOLO_CONF_THRESHOLD,
            iou=self.config.YOLO_IOU_THRESHOLD,
            verbose=False
        )
        boxes = []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                if cls in self.config.VEHICLE_CLASS_IDS:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    boxes.append((x1, y1, x2, y2))
        return boxes
