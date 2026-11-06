# Speed calibration, ANPR and signal validation

## Speed calibration

The two-line estimator still requires a physically measured distance between
the two crossing lines on the road plane. The per-camera configuration must
include distinct normalized line positions, a positive measured distance, a
calibration version and an explicit verification flag before a speed event
can be raised. Never use the example values as surveyed measurements. Verify
against a traceable speed reference over several speeds and lanes. This
implementation does not infer metres from pixels or replace site survey.

## ANPR

`detectors/anpr_detector.py` proposes plate-shaped contours inside the lower
vehicle crop, runs Tesseract OCR with confidence scoring, and uses per-track
multi-frame voting. Weak or inconsistent reads return UNKNOWN / pending
consensus. This is an experimental classical-CV pipeline, not a trained plate
localizer or a validated Indian registration parser. It needs camera-specific
plate data, night/rain/angle tests and measured exact-match performance.

## Traffic signal confidence

The signal detector now examines a configurable normalized signal ROI,
compares colour-component evidence, and requires a stable temporal consensus.
A low-confidence, conflicting or insufficient observation returns UNKNOWN.
The road-rule detector receives RED only after that confirmation; UNKNOWN
must never be interpreted as RED. Calibrate ROI per camera and test glare,
LED flicker, dusk, rain and occlusion.

## Evidence and legal limits

All detections remain review candidates. Do not issue challans based solely
on OCR or computer-vision estimates. Retain original evidence and human review.
