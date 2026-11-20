from typing import Protocol

import numpy as np

from .types import Detections


class PersonDetector(Protocol):
    def detect(self, frame: np.ndarray) -> Detections: ...


class YoloPersonDetector:
    def __init__(self, model_path: str = "yolo11n.pt", confidence: float = 0.25, device: str = "cpu"):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is required for real detection. Install 'ultralytics>=8.3' "
                "and provide a YOLO checkpoint."
            ) from exc

        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device

    def detect(self, frame: np.ndarray) -> Detections:
        results = self.model.predict(
            frame,
            conf=self.confidence,
            classes=[0],
            device=self.device,
            verbose=False,
        )
        try:
            import supervision as sv
            detections = sv.Detections.from_ultralytics(results[0])
            person_mask = np.asarray(detections.class_id) == 0
            return Detections(
                xyxy=np.asarray(detections.xyxy[person_mask], dtype=np.float32),
                confidence=np.asarray(detections.confidence[person_mask], dtype=np.float32),
                class_id=np.asarray(detections.class_id[person_mask], dtype=np.int32),
            )
        except ImportError as exc:
            raise RuntimeError(
                "Supervision is required to normalize YOLO detections. "
                "Install 'supervision>=0.27'."
            ) from exc
