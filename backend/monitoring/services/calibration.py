"""Authoritative calibration validation."""

import math
from typing import Iterable


def _finite_number(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def validate_calibration(calibration) -> tuple[bool, str | None]:
    """Validate a calibration object or mapping without changing the model."""
    if calibration is None:
        return False, "missing calibration"

    def get(name, default=None):
        if isinstance(calibration, dict):
            return calibration.get(name, default)
        return getattr(calibration, name, default)

    if not bool(get("calibrated", False)):
        return False, "uncalibrated"

    area = get("area_m2")
    if area is None or not _finite_number(area) or float(area) <= 0:
        return False, "invalid calibration area"

    homography = get("homography", [])
    if homography is not None and not isinstance(homography, (list, tuple)):
        return False, "invalid homography"

    polygon = get("polygon_ground_m", [])
    if polygon is not None and not isinstance(polygon, (list, tuple)):
        return False, "invalid ground polygon"

    return True, None


def calibration_for_version(feed, version) -> tuple[object | None, str | None]:
    """Return the latest matching calibration for a feed and zone-aware version."""
    if version is None:
        return None, "missing calibration version"

    zones = list(feed.zones.all())
    candidates = []
    for zone in zones:
        candidates.extend(
            zone.calibrations.filter(version=int(version)).order_by("-created_at")
        )
    if not candidates:
        return None, "calibration version not found"

    calibration = candidates[0]
    valid, reason = validate_calibration(calibration)
    return (calibration if valid else None), reason
