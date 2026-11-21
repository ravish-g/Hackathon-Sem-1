import numpy as np
import pytest

from vision.calibration import HomographyCalibration, polygon_area_m2
from vision.zones import Zone, count_zone_occupants, foot_points


def test_homography_identity_mapping():
    image = np.array([[0, 0], [4, 0], [4, 3], [0, 3]], dtype=np.float32)
    ground = np.array([[0, 0], [4, 0], [4, 3], [0, 3]], dtype=np.float32)
    calibration = HomographyCalibration(image, ground)

    mapped = calibration.image_to_ground(np.array([[2, 1]], dtype=np.float32))

    assert calibration.valid
    np.testing.assert_allclose(mapped[0], [2, 1], atol=1e-4)


def test_ground_zone_area_and_foot_point_count():
    image = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
    ground = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
    calibration = HomographyCalibration(image, ground)
    zone = Zone("entrance", np.array([[0, 0], [4, 0], [4, 4], [0, 4]], dtype=np.float32))
    boxes = np.array([[1, 1, 2, 3], [8, 8, 9, 9]], dtype=np.float32)

    count, density, quality = count_zone_occupants(calibration, zone, boxes)

    assert count == 1
    assert zone.area_m2 == pytest.approx(16.0)
    assert density == pytest.approx(1.0 / 16.0)
    assert quality == []


def test_duplicate_track_id_is_counted_once():
    image = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
    calibration = HomographyCalibration(image, image.copy())
    zone = Zone("zone-a", np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32))
    boxes = np.array([[1, 1, 2, 3], [4, 4, 5, 6]], dtype=np.float32)

    count, _, _ = count_zone_occupants(
        calibration, zone, boxes, np.array([7, 7], dtype=np.int32)
    )

    assert count == 1


def test_invalid_calibration_returns_invalid_density():
    zone = Zone("zone-a", np.array([[0, 0], [2, 0], [2, 2], [0, 2]], dtype=np.float32))
    boxes = np.array([[0, 0, 1, 1]], dtype=np.float32)

    count, density, quality = count_zone_occupants(None, zone, boxes)

    assert count == 0
    assert density is None
    assert "calibration_invalid" in quality


def test_invalid_polygon_area_rejected():
    with pytest.raises(ValueError):
        polygon_area_m2(np.array([[0, 0], [1, 1], [1, 1]], dtype=np.float32))

def test_untracked_people_do_not_share_an_identity():
    polygon = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
    calibration = HomographyCalibration(polygon, polygon.copy())
    boxes = np.array([[1, 1, 2, 2], [3, 1, 4, 2], [5, 1, 6, 2]], dtype=np.float32)
    count, _, _ = count_zone_occupants(calibration, Zone("floor", polygon), boxes, [2, -1, -1])
    assert count == 3
