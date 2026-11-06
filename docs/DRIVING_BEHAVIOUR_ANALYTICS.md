# Driving-behaviour analytics integration

The multi-camera visual pipeline now invokes the trajectory, lane-change,
indicator aggregation and reckless-driving analytics independently for each
camera. Track histories and indicator histories are not shared between cameras.

## Lane geometry is required

Lane transitions are inferred only when a camera has surveyed, normalized lane
polygons. Add them under that camera's `calibration` object:

```json
{
  "camera_id": "north-road",
  "source": 0,
  "calibration": {
    "lane_polygons": [
      {"lane_id": "lane-left", "polygon": [[0.05,0.30],[0.45,0.30],[0.48,0.98],[0.02,0.98]]},
      {"lane_id": "lane-right", "polygon": [[0.55,0.30],[0.95,0.30],[0.98,0.98],[0.52,0.98]]}
    ]
  }
}
```

Replace the example geometry with polygons surveyed for the actual camera. The
vehicle centroid must fall unambiguously inside exactly one polygon; otherwise
its lane is UNKNOWN. Repeated transitions inside the configured time window
produce a suspected weaving review event. These polygons are image-space
regions and must be checked after camera movement or zoom changes.

## Indicator vision and TTC

`IndicatorDetector` is now called for every tracked vehicle and aggregates
observations over time. Without an injected `indicator_classifier`, every
observation is UNKNOWN. A classifier can be injected when constructing
`CameraDetectionPipeline`; it must accept
`(frame, bbox, track_id, timestamp)` and return
`left_probability`, `right_probability`, and `visible`. It must be trained
and validated on the target camera views before use. Classifier errors and
occluded lamps remain UNKNOWN, never OFF.

An optional `ttc_estimator` can be injected with
`(track_id, track_info, all_tracks, timestamp)`. No TTC is fabricated when
there is no estimator. Do not treat raw pixel distances as seconds.

## Output and limitations

Lane-change and unsafe-driving outputs are review-only events with plate
UNKNOWN, no speed value and `legal_violation_confirmed=false` in the analytics
result. The existing event logger/alert adapter receives these as candidate
events for operator review. Repeated lane changes alone are not proof of
reckless driving. This integration does not claim to train an indicator model
or provide enforcement-grade TTC.
