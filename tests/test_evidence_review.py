import csv
from utils.evidence_review import EvidenceReviewStore


def test_review_store_lists_pending_and_updates_status(tmp_path):
    path = tmp_path / "violations.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "violation_type", "review_status"])
        writer.writeheader()
        writer.writerow({"event_id": "evt-1", "violation_type": "SPEED", "review_status": "PENDING_REVIEW"})
        writer.writerow({"event_id": "evt-2", "violation_type": "RED_LIGHT", "review_status": "REJECTED"})

    store = EvidenceReviewStore(path)
    assert [row["event_id"] for row in store.list_events()] == ["evt-1"]
    updated = store.update_status("evt-1", "APPROVED", "operator-1", "Evidence checked")
    assert updated["review_status"] == "APPROVED"
    assert updated["reviewed_by"] == "operator-1"
    assert updated["review_note"] == "Evidence checked"
    assert store.list_events(status="APPROVED")[0]["event_id"] == "evt-1"


def test_review_store_rejects_unknown_status_and_missing_event(tmp_path):
    path = tmp_path / "violations.csv"
    path.write_text("event_id,review_status\n", encoding="utf-8")
    store = EvidenceReviewStore(path)
    try:
        store.update_status("evt", "ISSUE_CHALLAN", "operator")
        assert False, "unsupported status should fail"
    except ValueError:
        pass
    try:
        store.update_status("missing", "APPROVED", "operator")
        assert False, "missing event should fail"
    except KeyError:
        pass
