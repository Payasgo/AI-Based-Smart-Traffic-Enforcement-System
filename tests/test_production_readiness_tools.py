import csv
import json
from pathlib import Path

import pytest

from scripts.evaluate_detector_metrics import evaluate
from scripts.validate_vision_manifest import validate_manifest
from utils.evidence_review import EvidenceReviewStore
from utils.road_plane_calibration import RoadPlaneProjector


def test_review_summary_joins_append_only_journal(tmp_path):
    path = tmp_path / "violations.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "review_status"])
        writer.writeheader()
        writer.writerow({"event_id": "a", "review_status": "PENDING_REVIEW"})
        writer.writerow({"event_id": "b", "review_status": "PENDING_REVIEW"})
    store = EvidenceReviewStore(path)
    store.update_status("a", "APPROVED", "reviewer")
    assert store.review_summary()["APPROVED"] == 1
    assert store.review_summary()["PENDING_REVIEW"] == 1


def test_road_plane_projector_recovers_metric_distance():
    image = [[0, 0], [1, 0], [1, 1], [0, 1], [0.5, 0.5]]
    ground = [[0, 0], [10, 0], [10, 20], [0, 20], [5, 10]]
    projector = RoadPlaneProjector(image, ground)
    assert projector.project((0.5, 0.5)) == pytest.approx((5.0, 10.0))
    assert projector.speed_kmh((0.1, 0.5), 1.0, (0.2, 0.5), 2.0) == pytest.approx(3.6)


def test_manifest_rejects_camera_leakage_and_invalid_labels(tmp_path):
    manifest = tmp_path / "annotations.jsonl"
    manifest.write_text(
        json.dumps({"image": "one.jpg", "camera_id": "cam1", "split": "train", "task": "indicator", "label": "LEFT"}) + "\n" +
        json.dumps({"image": "two.jpg", "camera_id": "cam1", "split": "test", "task": "indicator", "label": "BLINK"}) + "\n",
        encoding="utf-8",
    )
    result = validate_manifest(manifest, check_files=False)
    assert not result["valid"]
    assert any("multiple splits" in error for error in result["errors"])
    assert any("invalid indicator label" in error for error in result["errors"])


def test_detector_metrics_reports_false_positives_and_false_negatives():
    result = evaluate([
        {"ground_truth": "RED", "prediction": "RED"},
        {"ground_truth": "RED", "prediction": "UNKNOWN"},
        {"ground_truth": "GREEN", "prediction": "RED"},
    ])
    assert result["samples"] == 3
    assert result["per_class"]["RED"]["precision"] == pytest.approx(0.5)
    assert result["per_class"]["RED"]["recall"] == pytest.approx(0.5)
