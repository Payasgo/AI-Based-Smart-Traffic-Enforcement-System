"""Measure real multi-camera throughput on the machine running the cameras.

Example (Windows PowerShell):
  .venv\\Scripts\\python scripts\\benchmark_multicamera.py --config config/cameras.example.json --duration-seconds 300 --output benchmark-results\\windows.json

Use actual camera sources and calibrated site settings. Results are measurements, not guarantees.
"""
import argparse
import json
import os
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from camera.multi_camera_runner import MultiCameraRunner


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 2)


def run_benchmark(config, duration_seconds=60, warmup_seconds=10, enable_detection_pipeline=True):
    if duration_seconds <= 0 or warmup_seconds < 0:
        raise ValueError("duration_seconds must be positive and warmup_seconds cannot be negative")
    runner = MultiCameraRunner.from_json(config, enable_detection_pipeline=enable_detection_pipeline)
    counts = defaultdict(int)
    latencies_ms = defaultdict(list)
    health_samples = defaultdict(list)
    process = None
    try:
        try:
            import psutil
            process = psutil.Process(os.getpid())
            process.cpu_percent(None)
        except ImportError:
            process = None
        runner.start()
        start = time.monotonic()
        measurement_start = start + warmup_seconds
        end = measurement_start + duration_seconds
        while time.monotonic() < end:
            results = runner.read_results(timeout=0.02)
            now = datetime.now(timezone.utc)
            for camera_id, result in results.items():
                if time.monotonic() >= measurement_start:
                    counts[camera_id] += 1
                    timestamp = getattr(result, "timestamp", None)
                    if timestamp is not None:
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        latencies_ms[camera_id].append(max(0.0, (now - timestamp.astimezone(timezone.utc)).total_seconds() * 1000))
            if process and time.monotonic() >= measurement_start:
                snapshot = process.memory_info()
                health_samples["_process"].append({
                    "cpu_percent": process.cpu_percent(None),
                    "rss_mb": snapshot.rss / (1024 * 1024),
                })
    finally:
        runner.stop()

    health = runner.health()
    actual_seconds = duration_seconds
    cameras = {}
    for camera_id in sorted(runner.workers):
        values = latencies_ms[camera_id]
        cameras[camera_id] = {
            "frames_processed": counts[camera_id],
            "measured_fps": round(counts[camera_id] / actual_seconds, 3),
            "latency_ms_p50": percentile(values, 0.50),
            "latency_ms_p95": percentile(values, 0.95),
            "worker_processed_frames_total": health[camera_id].get("processed_frames"),
            "worker_error_count": health[camera_id].get("inference_error_count"),
            "last_inference_error": health[camera_id].get("inference_error"),
            "last_successful_inference_at": health[camera_id].get("last_successful_inference_at"),
        }
    samples = health_samples["_process"]
    return {
        "schema_version": 1,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "psutil_available": process is not None,
            "avg_process_cpu_percent": round(statistics.mean(s["cpu_percent"] for s in samples), 2) if samples else None,
            "peak_process_rss_mb": round(max((s["rss_mb"] for s in samples), default=0), 2) if samples else None,
        },
        "settings": {
            "camera_config": str(config),
            "warmup_seconds": warmup_seconds,
            "measurement_seconds": duration_seconds,
            "full_detection_pipeline": enable_detection_pipeline,
        },
        "cameras": cameras,
        "notes": [
            "Run on the target Windows PC with the real cameras connected.",
            "Use the full detection pipeline for deployment-capacity measurements.",
            "Repeat for at least 5 minutes and during realistic traffic; compare p95 latency, FPS, CPU, RAM and worker errors.",
            "A zero worker error count does not establish detector accuracy.",
            "CPU and RAM metrics are omitted when psutil is unavailable.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark configured multi-camera inference on this PC")
    parser.add_argument("--config", required=True, help="Path to multi-camera JSON configuration")
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--warmup-seconds", type=int, default=10)
    parser.add_argument("--output", default="benchmark-results/multicamera.json")
    parser.add_argument("--no-detection-pipeline", action="store_true", help="Benchmark capture + YOLO tracking only")
    args = parser.parse_args()
    report = run_benchmark(args.config, args.duration_seconds, args.warmup_seconds, not args.no_detection_pipeline)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nBenchmark report saved to: {output}")


if __name__ == "__main__":
    main()
