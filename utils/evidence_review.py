"""Operator review workflow for evidence CSV records.

This is an internal review queue, not a government challan submission service.
"""
import csv
import os
import threading
from pathlib import Path

REVIEW_STATUSES = {"PENDING_REVIEW", "APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE"}


class EvidenceReviewStore:
    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)
        self._lock = threading.RLock()

    def list_events(self, status="PENDING_REVIEW", limit=100):
        if status not in REVIEW_STATUSES and status != "ALL":
            raise ValueError("Unsupported review status")
        limit = max(1, min(int(limit), 500))
        with self._lock:
            if not self.csv_path.exists():
                return []
            with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
        if status != "ALL":
            rows = [row for row in rows if (row.get("review_status") or "PENDING_REVIEW") == status]
        return list(reversed(rows[-limit:]))

    def update_status(self, event_id, status, reviewer, note=""):
        if not event_id or len(str(event_id)) > 128:
            raise ValueError("A valid event_id is required")
        if status not in REVIEW_STATUSES - {"PENDING_REVIEW"}:
            raise ValueError("Review status must be APPROVED, REJECTED or NEEDS_MORE_EVIDENCE")
        reviewer = str(reviewer or "").strip()[:128]
        note = str(note or "").strip()[:1000]
        if not reviewer:
            raise ValueError("reviewer is required")
        with self._lock:
            if not self.csv_path.exists():
                raise KeyError("Evidence event not found")
            with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                fields = list(reader.fieldnames or [])
                rows = list(reader)
            if "event_id" not in fields:
                raise RuntimeError("Evidence CSV has no event_id column; migrate it with EvidenceLogger first")
            if "review_status" not in fields:
                fields.append("review_status")
            if "reviewed_by" not in fields:
                fields.append("reviewed_by")
            if "review_note" not in fields:
                fields.append("review_note")
            match = None
            for row in rows:
                if row.get("event_id") == str(event_id):
                    match = row
                    break
            if match is None:
                raise KeyError("Evidence event not found")
            match["review_status"] = status
            match["reviewed_by"] = reviewer
            match["review_note"] = note
            temporary = self.csv_path.with_name(self.csv_path.name + ".review.tmp")
            try:
                with temporary.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(rows)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.csv_path)
            finally:
                if temporary.exists():
                    temporary.unlink()
            return dict(match)
