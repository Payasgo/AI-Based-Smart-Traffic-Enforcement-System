"""Validate a JSONL traffic-vision annotation manifest.

Each line: {"image":"relative/path.jpg","camera_id":"CAM01","split":"train",
"task":"indicator|traffic_signal","label":"..."}
Indicator labels: LEFT, RIGHT, BOTH, OFF, NOT_VISIBLE, UNKNOWN.
Traffic signal labels: RED, AMBER, GREEN, UNKNOWN.
"""
import argparse
import json
from pathlib import Path

LABELS = {
    "indicator": {"LEFT", "RIGHT", "BOTH", "OFF", "NOT_VISIBLE", "UNKNOWN"},
    "traffic_signal": {"RED", "AMBER", "GREEN", "UNKNOWN"},
}
SPLITS = {"train", "validation", "test"}


def validate_manifest(path, check_files=True):
    path = Path(path)
    errors, seen = [], set()
    counts = {}
    camera_splits = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: invalid JSON: {exc}")
                continue
            required = ("image", "camera_id", "split", "task", "label")
            missing = [key for key in required if not item.get(key)]
            if missing:
                errors.append(f"line {line_no}: missing {', '.join(missing)}")
                continue
            task, label, split = item["task"], item["label"], item["split"]
            if task not in LABELS:
                errors.append(f"line {line_no}: unsupported task {task}")
                continue
            if label not in LABELS[task]:
                errors.append(f"line {line_no}: invalid {task} label {label}")
            if split not in SPLITS:
                errors.append(f"line {line_no}: split must be train, validation or test")
            image = (path.parent / item["image"]).resolve()
            if check_files and not image.is_file():
                errors.append(f"line {line_no}: image not found: {image}")
            identity = (item["camera_id"], str(image))
            if identity in seen:
                errors.append(f"line {line_no}: duplicate image annotation")
            seen.add(identity)
            camera_splits.setdefault(item["camera_id"], set()).add(split)
            key = f"{task}:{split}:{label}"
            counts[key] = counts.get(key, 0) + 1
    for camera, splits in camera_splits.items():
        if len(splits) > 1:
            errors.append(f"camera {camera} appears in multiple splits; use camera-disjoint evaluation")
    return {"valid": not errors, "annotations": len(seen), "counts": counts, "errors": errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", help="JSONL annotation manifest")
    parser.add_argument("--skip-file-check", action="store_true")
    args = parser.parse_args()
    report = validate_manifest(args.manifest, not args.skip_file_check)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
