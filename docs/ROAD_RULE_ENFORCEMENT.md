# Camera road-rule enforcement configuration

The live pipeline now combines the existing vehicle tracker, speed detector,
wrong-way detector, lane scene analysis, traffic-light classifier and pedestrian
detector with a configurable road-rule layer.

## Configure each camera before enforcement

Coordinates are normalized fractions of frame width/height (0.0 to 1.0).
Survey the camera view and configure polygons for no-parking areas, bus stops,
junction keep-clear areas and zebra crossings. A zone can use a different dwell
threshold for each rule:

```python
ROAD_RULE_ZONES = [
    {
        "name": "BUS_STOP_A",
        "polygon": [[0.10, 0.60], [0.32, 0.60], [0.35, 0.92], [0.08, 0.92]],
        "violation_type": "BUS_STOP_PARKING",
        "dwell_seconds": 10,
    },
    {
        "name": "ZEBRA_CROSSING_A",
        "polygon": [[0.40, 0.72], [0.70, 0.72], [0.75, 0.88], [0.38, 0.88]],
        "violation_type": "CROSSWALK_BLOCKING",
        "dwell_seconds": 3,
    },
]
```

Configure solid-line or restricted-lane boundaries as line segments:

```python
ROAD_RULE_LINES = [
    {
        "name": "SOLID_WHITE_LINE_A",
        "start": [0.48, 0.55],
        "end": [0.60, 0.95],
        "violation_type": "SOLID_LINE_CROSSING",
        "direction": "either",
    },
]
```

For a directional boundary, use `negative_to_positive` or
`positive_to_negative` instead of `either`. A crossing is based on tracked
vehicle-centroid positions on successive frames.

## Speed and wrong-way configuration

Set `SPEED_LIMIT_KMH`, the two speed measurement line positions, and
`LINE_DISTANCE_METERS` for the specific road segment. Speed enforcement is
only meaningful after the camera geometry and measured line distance have been
surveyed. Configure `WRONG_WAY_DIRECTION_X/Y` for the camera's permitted
image-space direction. The wrong-way detector is a single-view motion check,
not a GPS/map route classifier.

## Camera + live operation

Use a live camera index or RTSP/video source supported by OpenCV. Enable the
existing alert integration with `ENABLE_ALERTS`, an authority-approved
`ALERT_ENDPOINT_URL`, and the `TRAFFIC_API_KEY` environment variable. The
pipeline writes evidence snapshots and violation rows and sends live alert
events through the existing alert adapter.

## Fines and legal workflow

`FINE_SCHEDULE_INR` is intentionally empty by default. Populate it only after
the applicable state/UT rules, offence mapping, effective dates and authorised
fine amounts have been verified. This repository currently creates evidence
and reviewable violation alerts; it does not issue a legally binding challan,
collect payment, or replace an authorised officer's verification. OCR output
may be UNKNOWN or incorrect and must not be used as sole identity evidence.

## Validation before field deployment

- Calibrate speed measurement against a traceable reference instrument.
- Survey and independently validate every polygon, line, stop line and signal ROI.
- Test day/night, rain, glare, occlusion, congestion and camera vibration.
- Measure false-positive/false-negative rates on representative local footage.
- Verify timestamp synchronization, camera identity, evidence retention and
  chain-of-custody controls with the deploying authority.
- Treat the current colour-based traffic-light state as experimental until
  validated against the actual signal head and its mounting geometry.
