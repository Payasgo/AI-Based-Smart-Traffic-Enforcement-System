# Hybrid multi-camera Stage 3: full visual detector pipeline

The multi-camera runner can now attach an independent visual detector suite to
each camera. Each camera owns its YOLO tracker and all stateful visual
detectors (speed, wrong-way, road rules, lane, traffic-light, road-scene and
driver-safety detectors). The existing single-camera `python main.py --source 0`
path is unchanged.

## Run

```bash
python main.py --multi-camera-config config/cameras.example.json
```

For a headless run:

```bash
python main.py --multi-camera-config config/cameras.example.json --no-display
```

The CLI's JSON-based runner enables the detector suite by default. Code that
constructs `MultiCameraRunner` directly keeps the lightweight inference-only
default; pass `enable_detection_pipeline=True` to enable the full suite.

## Isolation and shared services

- Tracker/model and temporal detector objects are per camera.
- Evidence logging and alert delivery are shared sinks.
- Audio/honk capture and lesson/voice coaching remain central services and
  are not started once per camera.
- Camera frame processing occurs in that camera's inference worker before its
  latest-result queue is published, so the UI receives the processed frame.

## Camera-specific calibration

The current JSON camera schema provides source, role, dimensions and stream
settings. Road-rule polygons/lines, speed measurement geometry, traffic-light
stop lines and permitted travel direction still need explicit per-camera
configuration support and field calibration. Until then, the suite uses
`config/settings.py` defaults. Do not treat default geometry as deployment
calibration.

## Safety and limitations

This stage wires existing visual detectors into each camera; it does not
validate their accuracy. Speed estimation requires measured camera geometry,
road-rule zones/lines must be surveyed, and traffic-light state needs local
validation. Driver-safety models may be unavailable or heuristic. Alerts are
candidate events for human review, not legal determinations or automatic
challans. Indicator-state aggregation remains separate from a trained lamp
classifier; unobservable lamps must remain UNKNOWN.