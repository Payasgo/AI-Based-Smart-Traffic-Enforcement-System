"""Experimental plate localization, OCR confidence and temporal consensus.

This OpenCV contour proposal + Tesseract OCR implementation is a review aid,
not a trained ANPR model. It returns UNKNOWN when localization/recognition is
weak and never fabricates a plate.
"""
from collections import Counter, defaultdict, deque
import re

import cv2
import numpy as np


class PlateRecognition:
    def __init__(self, min_confidence=55.0, history_size=8, min_votes=3):
        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be in 0..100")
        if history_size < min_votes or min_votes < 1:
            raise ValueError("history_size must be >= min_votes >= 1")
        self.min_confidence = float(min_confidence)
        self.history_size = int(history_size)
        self.min_votes = int(min_votes)
        self._votes = defaultdict(lambda: deque(maxlen=self.history_size))

    @staticmethod
    def normalize(text):
        return re.sub(r"[^A-Z0-9]", "", (text or "").upper())

    @staticmethod
    def _candidate_rois(vehicle_roi):
        h, w = vehicle_roi.shape[:2]
        if h < 24 or w < 48:
            return []
        gray = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        edges = cv2.Canny(gray, 60, 180)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
            x, y, cw, ch = cv2.boundingRect(contour)
            ratio = cw / max(ch, 1)
            area_ratio = (cw * ch) / float(w * h)
            if 2.0 <= ratio <= 6.5 and 0.002 <= area_ratio <= 0.20:
                pad_x, pad_y = int(cw * 0.06), int(ch * 0.12)
                x1, y1 = max(0, x-pad_x), max(0, y-pad_y)
                x2, y2 = min(w, x+cw+pad_x), min(h, y+ch+pad_y)
                candidates.append(vehicle_roi[y1:y2, x1:x2])
        return candidates[:8]

    def recognize(self, frame, bbox, track_id="unknown"):
        try:
            import pytesseract
            x1, y1, x2, y2 = map(int, bbox)
            h, w = frame.shape[:2]
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                return {"plate": "UNKNOWN", "confidence": 0.0, "status": "UNKNOWN"}
            vehicle = frame[y1:y2, x1:x2]
            # Plate is usually in the lower half; preserve a generous crop.
            lower = vehicle[int(vehicle.shape[0] * 0.45):]
            candidates = self._candidate_rois(lower)
            if not candidates:
                candidates = [lower] if lower.size else []
            best_text, best_conf = "", 0.0
            for roi in candidates:
                if roi.size == 0:
                    continue
                enlarged = cv2.resize(roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
                processed = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                  cv2.THRESH_BINARY, 31, 11)
                data = pytesseract.image_to_data(
                    processed, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                    output_type=pytesseract.Output.DICT)
                tokens, scores = [], []
                for raw, score in zip(data.get("text", []), data.get("conf", [])):
                    token = self.normalize(raw)
                    try: score = float(score)
                    except (TypeError, ValueError): continue
                    if token and score >= 0:
                        tokens.append(token); scores.append(score)
                text = "".join(tokens)
                confidence = sum(scores) / len(scores) if scores else 0.0
                if confidence > best_conf:
                    best_text, best_conf = text, confidence
            if not best_text or best_conf < self.min_confidence:
                return {"plate": "UNKNOWN", "confidence": best_conf, "status": "LOW_CONFIDENCE"}
            history = self._votes[str(track_id)]
            history.append(best_text)
            counts = Counter(history)
            plate, votes = counts.most_common(1)[0]
            if votes < self.min_votes:
                return {"plate": "UNKNOWN", "candidate": plate, "confidence": best_conf,
                        "status": "PENDING_CONSENSUS"}
            return {"plate": plate, "confidence": best_conf, "status": "REVIEW_REQUIRED"}
        except Exception:
            return {"plate": "UNKNOWN", "confidence": 0.0, "status": "UNAVAILABLE"}
