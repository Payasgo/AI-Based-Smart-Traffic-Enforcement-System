"""Append-only operator review journal for evidence CSV events."""
import csv
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from utils.evidence_file_lock import evidence_file_lock

REVIEW_STATUSES = {"PENDING_REVIEW", "APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE"}
REVIEW_FIELDS = ["review_id", "event_id", "review_status", "reviewed_by", "review_note", "reviewed_at_utc"]


class EvidenceReviewStore:
    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)
        self.journal_path = self.csv_path.with_name("evidence_reviews.csv")
        self._lock = threading.RLock()

    def _latest_decisions_unlocked(self):
        if not self.journal_path.exists():
            return {}
        latest = {}
        with self.journal_path.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                event_id = row.get("event_id", "")
                if event_id:
                    latest[event_id] = row
        return latest

    def latest_decisions(self):
        # Journal readers and writers use the same OS-level lock. A reader can
        # never observe a partially appended CSV record.
        with self._lock, evidence_file_lock(self.journal_path):
            return self._latest_decisions_unlocked()

    def review_summary(self):
        counts = {status: 0 for status in REVIEW_STATUSES}
        with self._lock, evidence_file_lock(self.csv_path), evidence_file_lock(self.journal_path):
            if not self.csv_path.exists():
                return counts
            with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                events = list(csv.DictReader(handle))
            decisions = self._latest_decisions_unlocked()
        for event in events:
            decision = decisions.get(event.get("event_id", ""))
            status = decision.get("review_status") if decision else event.get("review_status")
            status = status or "PENDING_REVIEW"
            if status in counts:
                counts[status] += 1
        return counts

    def list_events(self, status="PENDING_REVIEW", limit=100):
        if status not in REVIEW_STATUSES and status != "ALL":
            raise ValueError("Unsupported review status")
        limit = max(1, min(int(limit), 500))
        # Stable lock order prevents deadlocks: event log, then review journal.
        with self._lock, evidence_file_lock(self.csv_path), evidence_file_lock(self.journal_path):
            if not self.csv_path.exists():
                return []
            with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            decisions = self._latest_decisions_unlocked()
        merged = []
        for row in rows:
            decision = decisions.get(row.get("event_id", ""))
            if decision:
                row.update({
                    "review_status": decision.get("review_status", "PENDING_REVIEW"),
                    "reviewed_by": decision.get("reviewed_by", ""),
                    "review_note": decision.get("review_note", ""),
                    "reviewed_at_utc": decision.get("reviewed_at_utc", ""),
                })
            else:
                row.setdefault("review_status", "PENDING_REVIEW")
                row.setdefault("reviewed_by", "")
                row.setdefault("review_note", "")
            if status == "ALL" or row.get("review_status") == status:
                merged.append(row)
        return list(reversed(merged[-limit:]))

    def update_status(self, event_id, status, reviewer, note=""):
        if not event_id or len(str(event_id)) > 128:
            raise ValueError("A valid event_id is required")
        if status not in REVIEW_STATUSES - {"PENDING_REVIEW"}:
            raise ValueError("Review status must be APPROVED, REJECTED or NEEDS_MORE_EVIDENCE")
        reviewer = str(reviewer or "").strip()[:128]
        note = str(note or "").strip()[:1000]
        if not reviewer:
            raise ValueError("reviewer is required")
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, evidence_file_lock(self.csv_path), evidence_file_lock(self.journal_path):
            if not self.csv_path.exists():
                raise KeyError("Evidence event not found")
            with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if "event_id" not in (reader.fieldnames or []):
                    raise RuntimeError("Evidence CSV has no event_id column; migrate it with EvidenceLogger first")
                found = any(row.get("event_id") == str(event_id) for row in reader)
            if not found:
                raise KeyError("Evidence event not found")
            journal_exists = self.journal_path.exists() and self.journal_path.stat().st_size > 0
            decision = {
                "review_id": os.urandom(16).hex(),
                "event_id": str(event_id),
                "review_status": status,
                "reviewed_by": reviewer,
                "review_note": note,
                "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            with self.journal_path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
                if not journal_exists:
                    writer.writeheader()
                writer.writerow(decision)
                handle.flush()
                os.fsync(handle.fileno())
            return decision
