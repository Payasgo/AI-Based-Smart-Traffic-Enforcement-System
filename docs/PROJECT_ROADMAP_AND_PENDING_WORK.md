# Project Roadmap and Pending Work

Last reviewed: 2026-11-06

This document separates implemented foundations from work that remains necessary
for a dependable, field-tested traffic-monitoring system. A module existing in
the repository is not proof that its model is accurate or suitable for legal
enforcement.

## Current implementation baseline

The repository contains a YOLO-based vehicle detection/tracking path, legacy
single-camera operation, a multi-camera capture/inference foundation, camera-
scoped detection pipelines, speed and wrong-way logic, road-rule detection,
and trajectory/lane-change/indicator/reckless-driving analytics.

The behaviour analytics are **review candidates**, not automatic legal
conclusions. Indicator probabilities require a real, validated image classifier;
without one, the safe result is UNKNOWN. TTC must come from a validated estimator
and must never be inferred from raw pixel distance alone.

The project has Windows USB-camera setup/deployment support and automated tests
for selected components. A passing CI run validates the tested code paths only;
it does not validate detection accuracy on live roads.

## Priority 0 — deployment safety and evidence correctness

These items should be completed before any operational enforcement pilot.

- [ ] Validate evidence capture end to end: every review event must link to the
  correct frame, camera, site, track, timestamp and detector/configuration version.
- [ ] Use timezone-aware UTC event timestamps and preserve the camera's source
  timestamp and sequence number.
- [ ] Make evidence writes atomic and collision-resistant; test concurrent writes
  from multiple camera workers.
- [ ] Add integrity metadata (for example, SHA-256 hashes) and an append-only
  audit trail for evidence creation, review, export and deletion.
- [ ] Ensure worker/detector failures are visible to the operator and cannot
  silently suppress all results from a camera.
- [ ] Keep candidate detections separate from approved violations. Require
  authorized human review before any official enforcement action.
- [ ] Verify dashboard authentication, authorization, secure session settings,
  CSRF protections where applicable, and safe network binding before exposing
  the dashboard beyond localhost.
- [ ] Verify camera/site calibration is present and current before enabling
  speed or geometry-dependent enforcement alerts.

## Priority 1 — measurement and recognition accuracy

### Speed measurement

- [ ] Add per-camera road-plane calibration (homography or a documented
  equivalent) using surveyed reference points.
- [ ] Store calibration version, measured reference distances, camera pose and
  uncertainty with each speed result.
- [ ] Compare measured speeds against a trusted reference instrument over
  multiple distances, lanes, vehicle sizes and speeds.
- [ ] Define a measured error budget and disable enforcement output when the
  calibration is missing, stale or outside tolerance.

### Number-plate recognition

- [ ] Add a dedicated plate detector rather than relying only on vehicle crops.
- [ ] Add plate crop rectification, OCR confidence and multi-frame consensus.
- [ ] Validate Indian registration formats without silently changing uncertain
  characters.
- [ ] Preserve UNKNOWN/low-confidence results and require operator confirmation.
- [ ] Test day/night, motion blur, glare, rain, oblique angles and occlusion.

### Turn indicators

- [ ] Collect and label rear-view vehicle clips with left, right, both,
  not-visible and unknown/occluded labels.
- [ ] Train or integrate a dedicated lamp-localization/classification model.
- [ ] Aggregate blinking evidence over time and distinguish OFF from UNKNOWN.
- [ ] Validate across vehicle types, camera resolutions, day/night, rain, glare
  and partial occlusion.
- [ ] Report precision, recall, false-positive rate and confidence calibration
  before using results for operator review.

### Other detectors

- [ ] Validate traffic-light state using temporal confidence and explicit
  UNKNOWN handling.
- [ ] Validate helmet, seatbelt, phone-use, distraction, pedestrian, collision
  and parking modules against labelled target-domain data.
- [ ] Confirm that drowsiness/driving-impairment outputs are not presented as a
  medical or legal determination.
- [ ] Treat repeated lane changes as a behaviour signal, not proof of reckless
  driving; validate context and false-positive rates.

## Priority 2 — multi-camera reliability and performance

- [ ] Benchmark 1, 2, 4 and 8 camera configurations on documented target hardware.
- [ ] Record per-camera FPS, inference latency, dropped frames, CPU, RAM and
  thermal behaviour.
- [ ] Add configurable resolution, inference cadence and frame skipping.
- [ ] Test disconnect/reconnect, slow streams, malformed frames and camera
  shutdown during inference.
- [ ] Ensure one camera's exception or slow inference cannot block other cameras.
- [ ] Run a 24-hour soak test and verify memory, thread and file-handle stability.
- [ ] Document tested maximum camera count for each supported hardware profile;
  do not promise a camera count/FPS without measurements.

## Priority 3 — operator workflow and security

- [ ] Provide camera health, stale-frame and last-error status in the dashboard.
- [ ] Add review queues with approve, reject and reason/comment actions.
- [ ] Add role-based access for administrators, reviewers and read-only users.
- [ ] Add audit records for user actions and evidence exports.
- [ ] Add filters by date, camera, location, event type and review status.
- [ ] Define encrypted backup, retention, deletion and recovery procedures.
- [ ] Perform a security review before remote/network deployment.

## Priority 4 — validation, jurisdiction and release

- [ ] Build a versioned, consented and legally usable video evaluation dataset.
- [ ] Include normal traffic and controlled scenarios: speeding, wrong-way,
  red-light crossing, lane changes, occlusion, dense traffic, night and rain.
- [ ] Report precision, recall, false-positive rate, event delay, tracking ID
  switches, speed error, OCR exact-match rate and per-camera throughput.
- [ ] Record test hardware, model weights, configuration and dataset version.
- [ ] Verify current Andhra Pradesh and Telangana rules, compounding schedules,
  delegated authority, evidence requirements and privacy/retention obligations
  with competent authorities and qualified counsel.
- [ ] Keep jurisdiction-specific fine schedules disabled until officially
  verified and versioned.
- [ ] Do not integrate official challan submission without written authorization,
  approved APIs and an auditable human-approval process.
- [ ] Test the Windows installer on a clean supported Windows machine and
  document Python/runtime prerequisites and offline limitations.
- [ ] Resolve and test dependency compatibility in a clean Windows environment.
- [ ] Publish a tagged GitHub release only after the release checklist is met.

## Suggested delivery sequence

1. Evidence correctness, visible worker health and dashboard security review.
2. Speed calibration and dedicated ANPR.
3. Turn-indicator model and traffic-light validation.
4. Multi-camera performance/soak tests.
5. Operator review workflow and jurisdictional/legal review.
6. Clean-install verification and a documented versioned release.

## Release gate

A release may be labelled a development/prototype release when its limitations
are explicit. It must not be described as enforcement-grade or production-ready
until the relevant accuracy, security, legal, field and operational checks above
have objective evidence and sign-off.
