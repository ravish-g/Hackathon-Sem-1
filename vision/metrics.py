from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Iterable

import numpy as np


@dataclass
class TelemetrySample:
    feed_id: str
    zone_id: str | None
    sample_id: str
    sequence: int
    captured_at: str
    processed_at: str
    received_at: str | None
    people_count: int | None
    density_people_per_m2: float | None
    density_trend: str
    growth_rate: float
    predicted_threshold_time: str | None
    measured_fps: float | None
    inference_ms: float | None
    calibration_version: int | None
    quality_flags: list[str]
    is_valid: bool

    def to_dict(self) -> dict:
        return {
            "feed_id": self.feed_id,
            "zone_id": self.zone_id,
            "sample_id": self.sample_id,
            "sequence": self.sequence,
            "captured_at": self.captured_at,
            "processed_at": self.processed_at,
            "received_at": self.received_at,
            "people_count": self.people_count,
            "density_people_per_m2": self.density_people_per_m2,
            "density_trend": self.density_trend,
            "growth_rate": self.growth_rate,
            "predicted_threshold_time": self.predicted_threshold_time,
            "measured_fps": self.measured_fps,
            "inference_ms": self.inference_ms,
            "calibration_version": self.calibration_version,
            "quality_flags": list(self.quality_flags),
            "is_valid": self.is_valid,
        }


class FpsMeter:
    def __init__(self, window_seconds: float = 5.0):
        self.window_seconds = window_seconds
        self._times: deque[float] = deque()

    def add(self) -> None:
        now = time.monotonic()
        self._times.append(now)
        cutoff = now - self.window_seconds
        while self._times and self._times[0] < cutoff:
            self._times.popleft()

    def fps(self) -> float:
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def density_trend(densities: Iterable[float]) -> str:
    values = [float(value) for value in densities]
    if len(values) < 2:
        return "unknown"
    delta = values[-1] - values[-2]
    if delta > 0.05:
        return "rising"
    if delta < -0.05:
        return "falling"
    return "stable"
