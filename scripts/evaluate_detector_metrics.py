"""Compute class-wise precision, recall and F1 from labelled predictions.

Input JSONL rows require task, camera_id, ground_truth and prediction. UNKNOWN
is a first-class label. This evaluates predictions; it does not train a model.
"""
import argparse
import json
from collections import Counter, defaultdict


def evaluate(rows):
    labels = sorted({str(row[key]) for row in rows for key in ("ground_truth", "prediction")})
    matrix = {label: Counter() for label in labels}
    for row in rows:
        matrix[str(row["ground_truth"])][str(row["prediction"])] += 1
    report = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in labels if other != label)
        fn = sum(matrix[label][other] for other in labels if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[label].values())}
    total = len(rows)
    accuracy = sum(matrix[label][label] for label in labels) / total if total else 0.0
    return {"samples": total, "accuracy": accuracy, "per_class": report,
            "confusion_matrix": {label: dict(matrix[label]) for label in labels}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", help="JSONL prediction file from a camera-disjoint test set")
    args = parser.parse_args()
    with open(args.predictions, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    required = {"ground_truth", "prediction", "camera_id"}
    for i, row in enumerate(rows, 1):
        if not required.issubset(row):
            raise SystemExit(f"line {i}: required fields are {sorted(required)}")
    print(json.dumps(evaluate(rows), indent=2))


if __name__ == "__main__":
    main()
