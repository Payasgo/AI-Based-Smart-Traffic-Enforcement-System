import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.dashboard import create_app


def test_dashboard_requires_basic_auth_when_credentials_configured(tmp_path):
    app, cache = create_app(tmp_path / "violations.csv", username="operator", password="strong-test-password")
    client = app.test_client()
    try:
        response = client.get("/api/stats")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert client.get("/api/stats", auth=("operator", "wrong")).status_code == 401
        assert client.get("/api/stats", auth=("operator", "strong-test-password")).status_code == 200
    finally:
        cache.stop()


def test_dashboard_rejects_partial_credentials(tmp_path):
    import pytest
    with pytest.raises(RuntimeError, match="Set both"):
        create_app(tmp_path / "violations.csv", username="operator", password=None)


def test_dashboard_recent_table_uses_text_content_not_csv_html_injection():
    source = (Path(__file__).resolve().parents[1] / "utils" / "dashboard.py").read_text(encoding="utf-8")
    assert "td.textContent = String(value ?? '')" in source
    assert "tr.innerHTML = `<td>${r.timestamp}" not in source
