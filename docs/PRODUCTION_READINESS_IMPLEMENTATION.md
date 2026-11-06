# Staged production-readiness implementation notes

This change set improves software foundations; it does not certify the system for enforcement.

## Evidence reliability
- Event CSV remains append-only; review decisions are stored in a separate append-only journal.
- Review journal reads and writes share a cross-process lock.
- Event rows can carry camera/site/calibration, model/detector version, track ID and source frame sequence.
- Run `python scripts/reconcile_evidence.py --log logs/violations.csv --evidence-dir evidence` to report missing images, SHA-256 mismatches and orphan images.
- Add `--quarantine-orphans` to move orphan files into `evidence/orphaned`; it does not delete them.
- Back up `violations.csv`, `evidence_reviews.csv` and evidence images together.

## Speed calibration
`utils/road_plane_calibration.py` provides a homography projector from at least four paired normalized image points and surveyed ground-plane coordinates in metres. It is a calibration primitive, not an automatic calibration workflow. Collect more than four well-distributed points, reserve independent check points, report reprojection error, and compare speed against a traceable reference. Do not set the camera speed calibration verified flag until an authorized site validation is complete.

## Indicator and traffic-signal datasets
Use JSONL manifests with camera-disjoint train/validation/test splits. Validate a manifest:
`python scripts/validate_vision_manifest.py dataset/annotations.jsonl`.
Supported labels:
- Indicators: LEFT, RIGHT, BOTH, OFF, NOT_VISIBLE, UNKNOWN.
- Traffic signal: RED, AMBER, GREEN, UNKNOWN.

Evaluate held-out predictions:
`python scripts/evaluate_detector_metrics.py dataset/test_predictions.jsonl`.
The evaluation reports class precision, recall, F1 and confusion matrix. No trained weights or labelled footage are included in this repository. Do not claim a detector is trained or validated until a reproducible dataset, training run, camera-disjoint test and field report exist.

## Multi-camera health
Inference workers now expose last frame time and result-queue drops. Benchmark on the target PC with actual cameras; a worker thread being alive does not prove the camera is fresh or accurate.

## Dashboard access
Review actions require authenticated request intent, use the authenticated username as reviewer when Basic auth is enabled, and can be disabled for the configured read-only role via `DASHBOARD_ROLE=readonly`. This remains a single-role deployment setting, not full multi-account RBAC. Put remote deployments behind HTTPS and an identity-aware reverse proxy; complete an independent security review before exposing the dashboard.

## Explicitly not completed by source changes
- Physical camera survey, road-plane measurement and speed instrument validation.
- Trained Indian plate, indicator or traffic-signal models and their measured accuracy.
- Target-PC multi-camera capacity, thermal, reconnect and 24-hour soak tests.
- Authority approvals, privacy/retention policy sign-off and government challan integration.
