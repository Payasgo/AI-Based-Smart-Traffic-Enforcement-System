"""
Evidence logging: saves violation images and appends records to a CSV file.
"""

import os
import csv
import cv2
from datetime import datetime
from pathlib import Path


FIELDNAMES = [
    "timestamp", "violation_type", "license_plate",
    "speed_kmh", "evidence_image", "location"
]


class EvidenceLogger:
    """Persists violation data to CSV and disk images."""

    def __init__(self, log_dir="logs", evidence_dir="evidence"):
        self.log_dir      = Path(log_dir)
        self.evidence_dir = Path(evidence_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        self.csv_path = self.log_dir / "violations.csv"
        self._init_csv()

    def _init_csv(self):
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()

    def save_evidence(self, frame, violation_type, plate, timestamp):
        """Save a JPEG snapshot as evidence. Returns file path string."""
        ts_str   = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{violation_type}_{plate}_{ts_str}.jpg"
        filepath = self.evidence_dir / filename
        cv2.imwrite(str(filepath), frame)
        return str(filepath)

    def log_violation(self, violation_type, license_plate, speed_kmh,
                      timestamp, evidence_path, location="N/A"):
        """Append one row to the violations CSV."""
        row = {
            "timestamp":      timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "violation_type": violation_type,
            "license_plate":  license_plate,
            "speed_kmh":      f"{speed_kmh:.1f}" if speed_kmh else "",
            "evidence_image": evidence_path or "",
            "location":       location,
        }
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)
        print(f"[LOG] Violation logged → {self.csv_path}")
