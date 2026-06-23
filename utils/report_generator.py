"""
Generates summary reports from the violations CSV.
"""

import os
import csv
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas/matplotlib not installed. Report charts disabled.")


def generate_text_report(csv_path: str, output_path: str = "evidence/report.txt"):
    """Generate a plain-text summary from violations CSV."""
    if not os.path.exists(csv_path):
        logger.error(f"CSV not found: {csv_path}")
        return

    counts = defaultdict(int)
    total = 0
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[row["violation_type"]] += 1
            total += 1

    lines = [
        "=" * 50,
        "  TRAFFIC ENFORCEMENT SYSTEM — VIOLATION REPORT",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 50,
        f"  Total Violations: {total}",
        "",
        "  By Type:",
    ]
    for vtype, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"    {vtype:<20} {cnt:>5} violations")
    lines += ["", "=" * 50]

    report = "\n".join(lines)
    print(report)
    with open(output_path, "w") as f:
        f.write(report)
    logger.info(f"Report saved: {output_path}")


def generate_chart_report(csv_path: str, output_dir: str = "evidence"):
    """Generate bar chart of violations by type using pandas + matplotlib."""
    if not PANDAS_AVAILABLE:
        logger.warning("pandas/matplotlib unavailable. Skipping chart.")
        return
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        logger.info("No violations to chart.")
        return

    # Violations by type
    counts = df["violation_type"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 5))
    counts.plot(kind="bar", ax=ax, color=["#e74c3c", "#e67e22", "#2980b9"])
    ax.set_title("Traffic Violations by Type", fontsize=14, fontweight="bold")
    ax.set_xlabel("Violation Type")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=0)
    plt.tight_layout()
    out = os.path.join(output_dir, "violations_chart.png")
    plt.savefig(out, dpi=120)
    plt.close()
    logger.info(f"Chart saved: {out}")


if __name__ == "__main__":
    generate_text_report("evidence/violations.csv")
    generate_chart_report("evidence/violations.csv")
