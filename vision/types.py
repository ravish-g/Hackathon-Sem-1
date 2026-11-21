from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Detections:
    xyxy: np.ndarray
    confidence: np.ndarray
    class_id: np.ndarray
    tracker_id: np.ndarray | None = None

    @property
    def count(self) -> int:
        return len(self.xyxy)


@dataclass
class FramePacket:
    feed_id: str
    source_id: str
    frame_number: int
    captured_at: str
    frame: Any
    source_width: int
    source_height: int
