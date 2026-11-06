# Multi-camera benchmarking and operator evidence review

## Stage 4 — Benchmark the target PC

Run from the project root after installing the Windows requirements:

```powershell
.venv\Scripts\python scripts\benchmark_multicamera.py --config config/cameras.example.json --warmup-seconds 30 --duration-seconds 300 --output benchmark-results\windows-multicamera.json
```

Edit the camera JSON to use real camera sources and site-specific settings. Keep the planned resolution, camera count and full detection pipeline. Use `--no-detection-pipeline` only for a capture/tracking baseline.

The report records per-camera consumer FPS, result-age percentiles, worker errors, CPU and peak RSS when psutil is installed. These are measurements on the host that ran the command, not guaranteed capacity. Repeat 5–15 minute trials under representative load and retain the reports privately because they can expose machine details.

## Stage 5 — Evidence review workflow

- `GET /api/review?status=PENDING_REVIEW&limit=100`
- `POST /api/review/<event_id>` with JSON `{"status":"APPROVED","note":"..."}`
- Allowed decisions: `APPROVED`, `REJECTED`, `NEEDS_MORE_EVIDENCE`.
- `GET /api/review?status=ALL` lists events with their latest review decision.

Camera events are append-only in `logs/violations.csv`. Operator decisions are appended separately to `logs/evidence_reviews.csv`; the latest decision per event is joined when the queue is read. The two files form one logical audit record and must be backed up and restored together. Do not edit either file while the application is running.

The dashboard authenticates using HTTP Basic credentials. A reviewer's identity is taken from the authenticated account, not from a caller-supplied reviewer field. Keep the dashboard bound to localhost unless credentials are configured, and use HTTPS through a trusted reverse proxy before remote operational use.

Approval is an operator workflow state. It does not issue a challan, prove legal admissibility, or submit to a government portal. Human verification of plate, timestamp, camera/site, calibration, image integrity and applicable law remains mandatory.
