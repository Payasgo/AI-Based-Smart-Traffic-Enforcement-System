"""Audit evidence CSV rows against image files and SHA-256 hashes."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


def audit(csv_path, evidence_dir):
    csv_path, evidence_dir = Path(csv_path), Path(evidence_dir)
    referenced, missing, mismatched = set(), [], []
    if csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                name = row.get("evidence_image", "")
                if not name:
                    continue
                path = Path(name)
                if not path.is_absolute():
                    path = Path.cwd() / path
                referenced.add(path.resolve())
                if not path.is_file():
                    missing.append({"event_id": row.get("event_id"), "path": str(path)})
                    continue
                expected = row.get("evidence_sha256", "")
                if expected:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    if digest.lower() != expected.lower():
                        mismatched.append({"event_id": row.get("event_id"), "path": str(path)})
    images = [p for p in evidence_dir.rglob("*") if p.is_file() and "orphaned" not in p.parts]
    orphans = [p for p in images if p.resolve() not in referenced]
    return {
        "event_log": str(csv_path), "evidence_directory": str(evidence_dir),
        "referenced_images": len(referenced), "missing_images": missing,
        "hash_mismatches": mismatched, "orphan_images": [str(p) for p in orphans],
        "counts": {"missing": len(missing), "hash_mismatches": len(mismatched), "orphans": len(orphans)},
    }


def main():
    parser = argparse.ArgumentParser(description="Audit evidence image references and hashes")
    parser.add_argument("--log", default="logs/violations.csv")
    parser.add_argument("--evidence-dir", default="evidence")
    parser.add_argument("--output", default="")
    parser.add_argument("--quarantine-orphans", action="store_true",
                        help="Move orphan images to evidence/orphaned; never deletes them")
    args = parser.parse_args()
    report = audit(args.log, args.evidence_dir)
    if args.quarantine_orphans:
        target = Path(args.evidence_dir) / "orphaned"
        moved = []
        for item in report["orphan_images"]:
            source = Path(item)
            target.mkdir(parents=True, exist_ok=True)
            destination = target / source.name
            if destination.exists():
                destination = target / f"{source.stem}_{source.stat().st_mtime_ns}{source.suffix}"
            shutil.move(str(source), str(destination))
            moved.append(str(destination))
        report["quarantined_orphans"] = moved
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
