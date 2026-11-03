# Hybrid Multi-Camera Architecture – Stage 1

## Goal
Add multi-camera capture and behaviour-analysis foundations without changing the existing single-camera execution path. The current main.py remains the default entry point.

## Hybrid deployment model
- Camera/edge workers independently capture streams and maintain bounded latest-frame queues. A future edge process can host YOLO inference for one or more nearby cameras.
- Central analytics receives timestamped observations (camera ID, camera-local track ID, lane ID, indicator probabilities and risk measurements), correlates events and stores evidence.
- Track IDs are camera-local. Never equate ID 12 from two cameras. Cross-camera identity matching is a later feature requiring synchronized clocks, calibrated geometry and validated appearance/plate evidence.

## Included in Stage 1
- CameraConfig, CameraStream and CameraManager.
- Bounded queues drop stale frames to control latency.
- UTC timestamps and monotonically increasing per-camera sequence numbers.
- Reconnect support and camera health status.
- Testable trajectory, lane-change, indicator aggregation and risk-triage primitives.
- Fake-capture tests; no webcam or model weights required.

## Later stages
1. Refactor TrafficEnforcementSystem to expose process_frame while keeping its current start wrapper. Instantiate a separate VehicleTracker and detector-state bundle per camera.
2. Add a central event queue and cross-camera correlation. Do not merge identities without validated re-identification evidence.
3. Train and validate an indicator visual model. The Stage 1 IndicatorDetector is only a temporal aggregator: a vision model must provide left/right amber probabilities and visibility/occlusion. UNKNOWN is mandatory when the lamp cannot be observed.
4. Add cutting-in and overtaking analysis only after camera calibration and reliable relative-motion estimates.

## Behaviour safeguards
- One lane change is not automatically reckless.
- Repeated lane transitions are review candidates, not legal conclusions.
- Indicator non-use may be considered only when the relevant lamp is clearly visible throughout the pre-manoeuvre interval.
- TTC and proximity require calibrated geometry and reliable motion estimates.
- All events are suspected events requiring human review; they must not directly issue challans.

## Example configuration
Copy config/cameras.example.json to a deployment-specific file and set each source. Integer sources are local camera indices; RTSP URLs may be strings. Do not commit credentials or camera passwords.

## Tests
Run: pytest -q tests/test_multicamera_foundation.py

## Current limitation
This stage does not yet run multiple YOLO inference pipelines from main.py, provide cross-camera re-identification, or include a trained indicator-recognition model. Those require subsequent integration, data collection and real-road validation.
