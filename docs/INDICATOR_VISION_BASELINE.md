# Turn-indicator visual baseline

## What is implemented

`detectors/indicator_vision.py` adds an OpenCV HSV-based visual baseline for
rear-facing vehicle crops. It examines calibrated left/right regions in the
lower portion of each vehicle bounding box, estimates amber-pixel activity,
and returns the callback contract consumed by the existing temporal
`IndicatorDetector`.

The multi-camera pipeline uses one classifier and one temporal history per
camera/track. It is disabled unless the camera is explicitly marked as a rear
view and its `calibration.indicator_detection.enabled` setting is true.

## Example camera configuration

```json
{
  "camera_id": "CAM_REAR",
  "source": 1,
  "role": "rear",
  "calibration": {
    "indicator_detection": {
      "enabled": true,
      "active_ratio": 0.035,
      "min_samples": 5,
      "history_size": 12
    }
  }
}
```

Tune lamp-region geometry and thresholds against the actual camera view and
labelled examples. The current baseline assumes the rear of the vehicle is
visible and the vehicle bounding box is reasonably tight.

## Important limitations

This is a colour/geometry heuristic, **not a trained deep-learning model**.
Amber reflections, hazard lights, brake lamps, unusual lamp colours, image
compression, small distant vehicles, occlusion, rain and night exposure can
cause errors. The current visibility heuristic is not a semantic proof that
both lamps are visible. Therefore its outputs are experimental review signals
only. Do not use them to issue challans or assert an offence.

A production classifier needs a labelled dataset with left, right, both,
inactive, not-visible and uncertain/occluded states; vehicle-level lamp
localization; training/validation split by camera/site; temporal blink
evaluation; confidence calibration; and field testing across vehicle types,
lighting and weather. Record precision, recall and false-positive rate before
operational use.

## Temporal interpretation

The existing `IndicatorDetector` aggregates per-frame probabilities. The
classifier returns `visible=false` when the crop is invalid or too small, so
the aggregator returns UNKNOWN rather than treating missing observations as
OFF. Temporal sample count and probability thresholds are configurable per
camera.
