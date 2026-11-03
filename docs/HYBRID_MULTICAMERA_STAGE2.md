# Hybrid multi-camera Stage 2: independent YOLO workers

Stage 2 adds a separate inference worker for each configured camera. Each worker receives timestamped frames from its camera stream and owns a distinct VehicleTracker instance, including its own YOLO model instance and centroid tracker state. Track IDs are therefore camera-local.

## Run

The current CLI remains backward compatible. Stage 2 can be launched through the multi-camera runner entry point after the CLI integration in the next incremental change. Configure camera sources in config/cameras.example.json; camera indices 0/1/2 are examples only and must be checked on the target PC.

## Resource considerations

A separate YOLO model per camera increases RAM and CPU/GPU load. Start with 640x480 or 720p capture and a reduced inference rate. If CPU is saturated, use one inference process per edge computer and reduce camera count per node; do not share mutable tracker state. Model batching or a shared inference server can be introduced later while keeping independent trackers.

## Behaviour

This stage performs vehicle detection and camera-local tracking. It does not yet run every existing violation detector on every stream. The existing single-camera application remains the complete detector pipeline and default mode. The next integration step will adapt the detector suite into a per-camera frame processor, while keeping audio capture and user-facing lesson services shared at site level.

## Safety

Vehicle tracks and alerts are observations, not proof of an offence. No automatic challan generation or submission is performed. Validate on consented/local traffic footage, measure false positives and missed detections, and require authorized human review.
