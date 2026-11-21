import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class HomographyCalibration:
    image_points: np.ndarray
    ground_points_m: np.ndarray
    version: int = 1

    def __post_init__(self) -> None:
        if self.image_points.shape != (4, 2):
            raise ValueError("calibration requires exactly 4 image points")
        if self.ground_points_m.shape != (4, 2):
            raise ValueError("calibration requires exactly 4 ground points")
        if not np.isfinite(self.image_points).all() or not np.isfinite(self.ground_points_m).all():
            raise ValueError("calibration points must be finite")

    def homography(self) -> np.ndarray:
        h, mask = cv2.findHomography(
            np.asarray(self.image_points, dtype=np.float32),
            np.asarray(self.ground_points_m, dtype=np.float32),
            method=0,
        )
        if h is None:
            raise ValueError("invalid calibration: homography could not be computed")
        if abs(float(np.linalg.det(h))) < 1e-9:
            raise ValueError("invalid calibration: singular homography")
        return h

    def image_to_ground(self, image_points: np.ndarray) -> np.ndarray:
        h = self.homography()
        points = np.asarray(image_points, dtype=np.float32).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(points, h).reshape(-1, 2)

    @property
    def valid(self) -> bool:
        try:
            h = self.homography()
            return bool(np.isfinite(h).all())
        except (cv2.error, ValueError):
            return False


def polygon_area_m2(points_m: np.ndarray) -> float:
    points = np.asarray(points_m, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
        raise ValueError("zone polygon requires at least 3 two-dimensional points")
    if not np.isfinite(points).all():
        raise ValueError("zone polygon points must be finite")
    x = points[:, 0]
    y = points[:, 1]
    area = abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2.0
    if area <= 0.0:
        raise ValueError("zone polygon area must be positive")
    return area
