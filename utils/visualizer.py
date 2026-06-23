"""
Violation dashboard: reads the violations CSV and shows a summary plot.
Usage: python utils/visualizer.py --log logs/violations.csv
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path


def load_logs(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    return df


def plot_dashboard(df: pd.DataFrame, output_path: str = None):
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Traffic Violation Dashboard", fontsize=16, fontweight="bold")

    # ── 1. Violations by type ─────────────────────────────────────
    ax1 = axes[0, 0]
    counts = df["violation_type"].value_counts()
    ax1.bar(counts.index, counts.values, color=["#e74c3c", "#e67e22", "#3498db"])
    ax1.set_title("Violations by Type")
    ax1.set_ylabel("Count")
    ax1.tick_params(axis="x", rotation=20)

    # ── 2. Speed distribution ─────────────────────────────────────
    ax2 = axes[0, 1]
    speed_df = df[df["speed_kmh"].notna() & (df["violation_type"] == "SPEED")]
    if not speed_df.empty:
        speed_df["speed_kmh"].astype(float).hist(bins=20, ax=ax2, color="#e74c3c", edgecolor="white")
    ax2.set_title("Speed Violation Distribution")
    ax2.set_xlabel("km/h")
    ax2.set_ylabel("Frequency")

    # ── 3. Violations over time ───────────────────────────────────
    ax3 = axes[1, 0]
    if not df.empty:
        df.set_index("timestamp").resample("1H")["violation_type"].count().plot(
            ax=ax3, color="#2ecc71", linewidth=2
        )
    ax3.set_title("Violations per Hour")
    ax3.set_ylabel("Count")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax3.tick_params(axis="x", rotation=30)

    # ── 4. Top plates ─────────────────────────────────────────────
    ax4 = axes[1, 1]
    top_plates = df["license_plate"].value_counts().head(10)
    ax4.barh(top_plates.index, top_plates.values, color="#9b59b6")
    ax4.set_title("Top Repeat Offenders (Plates)")
    ax4.set_xlabel("Violations")

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[VIZ] Dashboard saved → {output_path}")
    else:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traffic Violation Dashboard")
    parser.add_argument("--log",    default="logs/violations.csv", help="Path to violations CSV")
    parser.add_argument("--output", default=None, help="Save plot to file instead of showing")
    args = parser.parse_args()

    df = load_logs(args.log)
    print(f"[VIZ] Loaded {len(df)} violation records.")
    plot_dashboard(df, args.output)
