from dataclasses import dataclass

import cv2
import numpy as np

from .calibration import HomographyCalibration, polygon_area_m2


@dataclass(frozen=True)
class Zone:
    zone_id: str
    ground_polygon_m: np.ndarray
    image_polygon: np.ndarray | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ground_polygon_m", np.asarray(self.ground_polygon_m, dtype=np.float32))
        if self.image_polygon is not None:
            object.__setattr__(self, "image_polygon", np.asarray(self.image_polygon, dtype=np.float32))

    @property
    def area_m2(self) -> float:
        return polygon_area_m2(self.ground_polygon_m)

    def contains_ground_point(self, point_m: np.ndarray) -> bool:
        polygon = np.asarray(self.ground_polygon_m, dtype=np.float32)
        point = np.asarray(point_m, dtype=np.float32)
        return bool(cv2.pointPolygonTest(polygon, (float(point[0]), float(point[1])), False) >= 0)

    def contains_image_point(self, point_xy: np.ndarray) -> bool:
        if self.image_polygon is None:
            return False
        point = np.asarray(point_xy, dtype=np.float32)
        return bool(cv2.pointPolygonTest(
            np.asarray(self.image_polygon, dtype=np.float32),
            (float(point[0]), float(point[1])),
            False,
        ) >= 0)


def foot_points(boxes: np.ndarray) -> np.ndarray:
    boxes = np.asarray(boxes, dtype=np.float32)
    if boxes.size == 0:
        return np.empty((0, 2), dtype=np.float32)
    return np.column_stack(((boxes[:, 0] + boxes[:, 2]) / 2.0, boxes[:, 3]))


def count_zone_occupants(
    calibration: HomographyCalibration | None,
    zone: Zone,
    boxes: np.ndarray,
    tracker_ids: np.ndarray | None = None,
) -> tuple[int, float | None, list[str]]:
    if calibration is None or not calibration.valid:
        return 0, None, ["calibration_invalid"]

    points = foot_points(boxes)
    if len(points) == 0:
        return 0, 0.0, []

    ground_points = calibration.image_to_ground(points)
    unique_ids: set[int | str] = set()
    in_zone_count = 0
    for index, ground_point in enumerate(ground_points):
        if not zone.contains_ground_point(ground_point):
            continue
        track_id = tracker_ids[index] if tracker_ids is not None and index < len(tracker_ids) else None
        identity = int(track_id) if track_id is not None and track_id >= 0 else f"box-{index}"
        if identity not in unique_ids:
            unique_ids.add(identity)
            in_zone_count += 1

    density = in_zone_count / zone.area_m2
    return in_zone_count, density, []
