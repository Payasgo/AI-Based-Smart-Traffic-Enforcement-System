"""Road-plane homography helpers for surveyed camera calibration.

Coordinates are normalized image points paired with surveyed ground-plane
coordinates in metres. A minimum of four non-collinear correspondences is
required. Calibration must be verified on independent check points before use.
"""
import cv2
import numpy as np


class RoadPlaneProjector:
    def __init__(self, image_points, ground_points_m):
        image = np.asarray(image_points, dtype=np.float64)
        ground = np.asarray(ground_points_m, dtype=np.float64)
        if image.ndim != 2 or ground.ndim != 2 or image.shape[1:] != (2,) or ground.shape[1:] != (2,):
            raise ValueError("image_points and ground_points_m must be Nx2 arrays")
        if len(image) < 4 or len(image) != len(ground):
            raise ValueError("at least four paired calibration points are required")
        if not np.isfinite(image).all() or not np.isfinite(ground).all():
            raise ValueError("calibration points must be finite")
        matrix, mask = cv2.findHomography(image, ground, method=0)
        if matrix is None or mask is None or int(mask.sum()) < 4:
            raise ValueError("could not estimate road-plane homography")
        self.matrix = matrix

    def project(self, normalized_image_point):
        point = np.asarray([[normalized_image_point]], dtype=np.float64)
        projected = cv2.perspectiveTransform(point, self.matrix)[0, 0]
        if not np.isfinite(projected).all():
            raise ValueError("projected point is not finite")
        return float(projected[0]), float(projected[1])

    def speed_kmh(self, first_point, first_timestamp, second_point, second_timestamp):
        elapsed = float(second_timestamp - first_timestamp)
        if elapsed <= 0:
            raise ValueError("timestamps must be strictly increasing")
        x1, y1 = self.project(first_point)
        x2, y2 = self.project(second_point)
        distance = float(np.hypot(x2 - x1, y2 - y1))
        return distance / elapsed * 3.6
