"""
Multi-camera 3D triangulation utility.
Given matched 2D keypoints from two calibrated cameras,
computes the real-world 3D position of a point.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


def triangulate_point(
    pt1: tuple,
    pt2: tuple,
    proj_matrix1: np.ndarray,
    proj_matrix2: np.ndarray
) -> np.ndarray:
    """
    Triangulate a 3D point from two 2D observations and camera projection matrices.

    Args:
        pt1: (u, v) pixel coords in camera 1
        pt2: (u, v) pixel coords in camera 2
        proj_matrix1: 3x4 projection matrix for camera 1 (K @ [R|t])
        proj_matrix2: 3x4 projection matrix for camera 2 (K @ [R|t])

    Returns:
        3D point as (X, Y, Z) numpy array in world coordinates.
    """
    A = np.array([
        pt1[0] * proj_matrix1[2] - proj_matrix1[0],
        pt1[1] * proj_matrix1[2] - proj_matrix1[1],
        pt2[0] * proj_matrix2[2] - proj_matrix2[0],
        pt2[1] * proj_matrix2[2] - proj_matrix2[1],
    ])
    _, _, Vt = np.linalg.svd(A)
    X = Vt[-1]
    return (X[:3] / X[3]).astype(np.float64)


def compute_3d_speed(
    pos1: np.ndarray,
    pos2: np.ndarray,
    delta_seconds: float
) -> float:
    """
    Compute speed in km/h from two 3D world positions and elapsed time.
    """
    dist_meters = np.linalg.norm(pos2 - pos1)
    speed_ms = dist_meters / delta_seconds if delta_seconds > 0 else 0.0
    return speed_ms * 3.6


def build_projection_matrix(K: np.ndarray, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Build a 3x4 projection matrix P = K @ [R | t]."""
    Rt = np.hstack([R, t.reshape(3, 1)])
    return K @ Rt


# ---------------------------------------------------------------------------
# Example calibration (replace with your real camera parameters)
# ---------------------------------------------------------------------------
def example_dual_camera_setup():
    """
    Returns two example projection matrices for testing.
    In production, obtain these via cv2.calibrateCamera() and cv2.stereoCalibrate().
    """
    fx, fy, cx, cy = 800, 800, 640, 360
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)

    R1 = np.eye(3)
    t1 = np.zeros(3)

    # Camera 2 is 2 meters to the right of camera 1
    R2 = np.eye(3)
    t2 = np.array([-2.0, 0, 0])

    P1 = build_projection_matrix(K, R1, t1)
    P2 = build_projection_matrix(K, R2, t2)
    return P1, P2
