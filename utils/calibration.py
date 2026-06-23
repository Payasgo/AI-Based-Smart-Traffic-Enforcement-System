"""
Camera calibration helper.
Run this script with a chessboard image/video to compute intrinsic parameters
that go into config/settings.py (CAMERA_MATRIX, DIST_COEFFS).
"""

import cv2
import numpy as np
import argparse
from pathlib import Path


def calibrate_camera(image_dir: str, board_size=(9, 6), square_size_mm=25.0):
    """
    Calibrate from a folder of chessboard images.
    Returns camera_matrix, dist_coeffs.
    """
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
    objp *= square_size_mm

    obj_points, img_points = [], []

    images = list(Path(image_dir).glob("*.jpg")) + list(Path(image_dir).glob("*.png"))
    print(f"[CALIB] Found {len(images)} calibration images.")

    for img_path in images:
        img  = cv2.imread(str(img_path))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, board_size, None)
        if ret:
            obj_points.append(objp)
            refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            img_points.append(refined)
            print(f"  ✓ {img_path.name}")
        else:
            print(f"  ✗ {img_path.name} (corners not found)")

    if not obj_points:
        print("[CALIB] No usable images found.")
        return None, None

    h, w = cv2.imread(str(images[0])).shape[:2]
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, (w, h), None, None
    )
    print(f"\n[CALIB] RMS error: {ret:.4f}")
    print(f"Camera matrix:\n{mtx}")
    print(f"Distortion coefficients:\n{dist.ravel()}")
    return mtx, dist


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camera calibration utility")
    parser.add_argument("--images", required=True, help="Directory with chessboard images")
    parser.add_argument("--cols",   type=int, default=9, help="Chessboard inner columns")
    parser.add_argument("--rows",   type=int, default=6, help="Chessboard inner rows")
    parser.add_argument("--square", type=float, default=25.0, help="Square size in mm")
    args = parser.parse_args()

    calibrate_camera(args.images, (args.cols, args.rows), args.square)
