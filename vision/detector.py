from threading import Lock
from typing import Protocol

import cv2
import numpy as np

from .types import Detections


class PersonDetector(Protocol):
    def detect(self, frame: np.ndarray) -> Detections: ...


def tile_starts(length: int, size: int) -> list[int]:
    if length <= size:
        return [0]
    # Distribute the overlap evenly, including at the far edge.
    intervals = int(np.ceil((length - size) / (size * 0.8)))
    return np.linspace(0, length - size, intervals + 1, dtype=int).tolist()


class YoloPersonDetector:
    def __init__(self, model_path: str = "yolo11n.pt", confidence: float = 0.25,
                 device: str = "cpu", tile_size: int = 640):
        from ultralytics import YOLO

        if tile_size < 0:
            raise ValueError("tile_size must be nonnegative")
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device
        self.tile_size = tile_size
        self.lock = Lock()

    def _boxes(self, frame):
        with self.lock:
            result = self.model.predict(frame, conf=self.confidence, classes=[0],
                                        device=self.device, verbose=False, max_det=2000)[0]
            return result.boxes.data.cpu().numpy().copy()

    def detect(self, frame: np.ndarray) -> Detections:
        height, width = frame.shape[:2]
        size = self.tile_size
        boxes = self._boxes(frame)
        if size and max(width, height) > size:
            candidates = [boxes]
            for y in tile_starts(height, size):
                for x in tile_starts(width, size):
                    crop = frame[y:y + size, x:x + size]
                    local = self._boxes(crop)
                    # Discard boxes clipped by an interior seam. The overlapping
                    # neighbor or the whole-frame pass sees the complete person.
                    h, w = crop.shape[:2]
                    clipped = (((x > 0) & (local[:, 0] < 2)) |
                               ((y > 0) & (local[:, 1] < 2)) |
                               ((x + w < width) & (local[:, 2] > w - 2)) |
                               ((y + h < height) & (local[:, 3] > h - 2)))
                    local = local[~clipped]
                    local[:, :4] += [x, y, x, y]
                    candidates.append(local)
            boxes = np.concatenate(candidates)
            if len(boxes):
                xywh = boxes[:, :4].copy()
                xywh[:, 2:] -= xywh[:, :2]
                keep = cv2.dnn.NMSBoxes(xywh.tolist(), boxes[:, 4].tolist(), 0.0, 0.55)
                boxes = boxes[np.asarray(keep, dtype=int).reshape(-1)]
        return Detections(boxes[:, :4], boxes[:, 4], boxes[:, 5].astype(np.int32))
