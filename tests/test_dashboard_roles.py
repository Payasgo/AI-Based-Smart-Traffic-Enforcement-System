import csv
import json

from utils.dashboard import create_app
from utils.evidence_logger import EvidenceLogger


def test_dashboard_review_uses_authenticated_user_and_role(tmp_path, monkeypatch):
    logger = EvidenceLogger(tmp_path / "logs", tmp_path / "evidence")
    logger.log_violation("TEST", "UNKNOWN", None, None, "")
    with logger.csv_path.open(newline="", encoding="utf-8") as handle:
        event_id = next(csv.DictReader(handle))["event_id"]
    monkeypatch.setenv("DASHBOARD_USERS_JSON", json.dumps({
        "reviewer-a": {"password": "secret-a", "role": "reviewer"},
        "auditor": {"password": "secret-b", "role": "readonly"},
    }))
    app, cache = create_app(logger.csv_path)
    client = app.test_client()
    try:
        url = f"/api/review/{event_id}"
        headers = {"X-Requested-With": "XMLHttpRequest"}
        denied = client.post(url, json={"status": "APPROVED"}, headers=headers,
                             auth=("auditor", "secret-b"))
        assert denied.status_code == 403
        accepted = client.post(url, json={"status": "APPROVED", "reviewer": "spoofed"},
                               headers=headers, auth=("reviewer-a", "secret-a"))
        assert accepted.status_code == 200
        assert accepted.get_json()["reviewed_by"] == "reviewer-a"
    finally:
        cache.stop()


def test_dashboard_review_rejects_cross_origin_and_missing_intent(tmp_path):
    logger = EvidenceLogger(tmp_path / "logs", tmp_path / "evidence")
    logger.log_violation("TEST", "UNKNOWN", None, None, "")
    with logger.csv_path.open(newline="", encoding="utf-8") as handle:
        event_id = next(csv.DictReader(handle))["event_id"]
    app, cache = create_app(logger.csv_path, username="operator", password="secret")
    client = app.test_client()
    try:
        url = f"/api/review/{event_id}"
        assert client.post(url, json={"status": "APPROVED"}, auth=("operator", "secret")).status_code == 403
        response = client.post(url, json={"status": "APPROVED"},
                               headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example"},
                               auth=("operator", "secret"))
        assert response.status_code == 403
    finally:
        cache.stop()
