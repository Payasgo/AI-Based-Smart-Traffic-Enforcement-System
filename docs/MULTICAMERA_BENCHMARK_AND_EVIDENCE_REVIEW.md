# Multi-camera benchmarking and operator evidence review

## Stage 4 — Benchmark the target PC

Run from the project root after installing the Windows requirements:

```powershell
.venv\Scripts\python scripts\benchmark_multicamera.py --config config/cameras.example.json --warmup-seconds 30 --duration-seconds 300 --output benchmark-results\windows-multicamera.json
```

Before running, edit the camera JSON to use the real camera sources and actual per-camera settings. Keep the same resolution, camera count and detection pipeline planned for deployment. The default benchmark enables the full per-camera detector pipeline. Use `--no-detection-pipeline` only to establish a capture/YOLO tracking baseline.

The JSON report records platform, processor, logical CPU count, Python version, per-camera processed frames/FPS, p50/p95 frame-to-result latency, worker errors, and (when `psutil` is installed) process CPU and peak resident memory. The script does not invent capacity estimates. Run repeated 5–15 minute trials under representative load and retain the reports to compare hardware/configuration changes.

Benchmark output may contain machine details; keep it out of public commits unless you intend to publish them. The script writes to `benchmark-results/` by default only when that output path is selected.

## Stage 5 — Evidence review workflow

The dashboard adds a pending evidence review queue and review API:
- `GET /api/review?status=PENDING_REVIEW&limit=100`
- `POST /api/review/<event_id>` with JSON `{"status":"APPROVED","reviewer":"operator-id","note":"..."}`
- Allowed decisions: `APPROVED`, `REJECTED`, `NEEDS_MORE_EVIDENCE`.
- `GET /api/review?status=ALL` lists all records.

Review decisions are written back to the evidence CSV with reviewer and note fields. The existing dashboard authentication rules also protect these routes. Keep the dashboard bound to localhost unless both `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` are configured. Use a trusted network and HTTPS/reverse proxy before remote operational use.

Approval means an operator marked evidence for further handling; it does not issue a challan, prove legal admissibility, or submit to a government portal. Human verification of plate, timestamp, camera/site, calibration, image integrity and applicable local law remains required.
