import csv
import threading
from utils.evidence_file_lock import evidence_file_lock
from utils.evidence_logger import EvidenceLogger
from utils.evidence_review import EvidenceReviewStore


def test_review_update_and_logger_append_share_cross_instance_lock(tmp_path):
    log_dir = tmp_path / "logs"
    evidence = tmp_path / "evidence"
    logger = EvidenceLogger(log_dir, evidence)
    csv_path = log_dir / "violations.csv"
    review = EvidenceReviewStore(csv_path)

    logger.log_violation("SPEED", "UNKNOWN", 65.0, None, "", camera_id="CAM1")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        event_id = next(csv.DictReader(handle))["event_id"]

    failures = []
    def append_events():
        try:
            for _ in range(30):
                logger.log_violation("TEST", "UNKNOWN", None, None, "", camera_id="CAM1")
        except Exception as exc:
            failures.append(exc)
    def review_event():
        try:
            for _ in range(10):
                review.update_status(event_id, "APPROVED", "operator-1", "checked")
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=append_events), threading.Thread(target=review_event)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()

    assert not failures
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 31
    assert rows[0]["review_status"] == "APPROVED"
    assert rows[0]["reviewed_by"] == "operator-1"
    assert rows[0]["review_note"] == "checked"
