"""
Helper script to download required model files.
Run once before starting the system.
"""

import os
import bz2
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent


def download_dlib_landmarks():
    """Download the 68-point facial landmark predictor from dlib.net."""
    dat_path = MODELS_DIR / "shape_predictor_68_face_landmarks.dat"
    bz2_path = MODELS_DIR / "shape_predictor_68_face_landmarks.dat.bz2"

    if dat_path.exists():
        print(f"[OK] {dat_path.name} already present.")
        return

    url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
    print(f"[DOWNLOAD] Fetching {url} ...")
    urllib.request.urlretrieve(url, bz2_path, reporthook=_progress)
    print("\n[EXTRACT] Decompressing...")
    with bz2.open(bz2_path, "rb") as src, open(dat_path, "wb") as dst:
        dst.write(src.read())
    bz2_path.unlink()
    print(f"[OK] Saved to {dat_path}")


def download_yolo():
    """YOLOv8n is downloaded automatically by ultralytics on first use."""
    print("[INFO] YOLOv8n will be auto-downloaded by ultralytics on first run.")


def _progress(count, block_size, total_size):
    pct = int(count * block_size * 100 / total_size)
    print(f"\r  {pct}% ", end="", flush=True)


if __name__ == "__main__":
    print("=== Downloading model files ===")
    download_dlib_landmarks()
    download_yolo()
    print("=== Done ===")
