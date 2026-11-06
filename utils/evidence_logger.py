"""Thread-safe, append-only evidence event persistence with integrity metadata."""
import csv
import hashlib
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
from utils.evidence_file_lock import evidence_file_lock

FIELDNAMES = [
    "event_id", "timestamp", "camera_id", "site_id", "calibration_version",
    "model_version", "detector_version", "track_id", "frame_sequence",
    "violation_type", "license_plate", "speed_kmh", "evidence_image",
    "evidence_sha256", "location", "review_status", "reviewed_by", "review_note",
]


class EvidenceLogger:
    def __init__(self, log_dir="logs", evidence_dir="evidence"):
        self.log_dir, self.evidence_dir = Path(log_dir), Path(evidence_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.log_dir / "violations.csv"
        self._lock = threading.RLock()
        self._init_csv()

    def _init_csv(self):
        with self._lock, evidence_file_lock(self.csv_path):
            if not self.csv_path.exists() or self.csv_path.stat().st_size == 0:
                with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
                    csv.DictWriter(handle, fieldnames=FIELDNAMES).writeheader()
                return
            with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                existing = reader.fieldnames or []
                if all(name in existing for name in FIELDNAMES):
                    return
                rows = list(reader)
            tmp = self.csv_path.with_suffix(".csv.tmp")
            with tmp.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                for old in rows:
                    row = {name: old.get(name, "") for name in FIELDNAMES}
                    row["event_id"] = row["event_id"] or uuid.uuid4().hex
                    row["review_status"] = row["review_status"] or "PENDING_REVIEW"
                    writer.writerow(row)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.csv_path)

    @staticmethod
    def _timestamp(value):
        value = value or datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def save_evidence(self, frame, violation_type, plate, timestamp, camera_id=None):
        safe = lambda value: "".join(c if c.isalnum() or c in "-_" else "_" for c in str(value or "unknown"))
        path = self.evidence_dir / (
            f"{safe(camera_id or 'single')}_{safe(violation_type)}_{safe(plate)}_{uuid.uuid4().hex}.jpg"
        )
        with self._lock, evidence_file_lock(self.csv_path):
            if not cv2.imwrite(str(path), frame):
                raise OSError(f"Could not write evidence image: {path}")
        return str(path)

    def log_violation(
        self, violation_type, license_plate, speed_kmh, timestamp, evidence_path,
        location="N/A", *, camera_id="", site_id="", calibration_version="",
        model_version="", detector_version="", track_id="", frame_sequence="",
        event_id=None, review_status="PENDING_REVIEW",
    ):
        digest = ""
        if evidence_path and Path(evidence_path).is_file():
            hasher = hashlib.sha256()
            with Path(evidence_path).open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
        row = {
            "event_id": event_id or uuid.uuid4().hex,
            "timestamp": self._timestamp(timestamp),
            "camera_id": camera_id or "", "site_id": site_id or "",
            "calibration_version": calibration_version or "",
            "model_version": model_version or "", "detector_version": detector_version or "",
            "track_id": track_id if track_id is not None else "",
            "frame_sequence": frame_sequence if frame_sequence is not None else "",
            "violation_type": violation_type, "license_plate": license_plate or "",
            "speed_kmh": f"{speed_kmh:.1f}" if isinstance(speed_kmh, (int, float)) else "",
            "evidence_image": evidence_path or "", "evidence_sha256": digest,
            "location": location or "N/A", "review_status": review_status,
            "reviewed_by": "", "review_note": "",
        }
        with self._lock, evidence_file_lock(self.csv_path):
            self._init_csv()
            with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=FIELDNAMES).writerow(row)
                handle.flush()
                os.fsync(handle.fileno())
        return row["event_id"]
