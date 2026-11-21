import numpy as np

from .types import Detections


class PerSourceTracker:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._tracker = None
        if enabled:
            try:
                from trackers import ByteTrackTracker
                self._tracker = ByteTrackTracker()
            except ImportError:
                self._tracker = None

    def update(self, detections: Detections) -> Detections:
        if not self.enabled or self._tracker is None:
            detections.tracker_id = None
            return detections

        try:
            import supervision as sv
            sv_detections = sv.Detections(
                xyxy=detections.xyxy,
                confidence=detections.confidence,
                class_id=detections.class_id,
            )
            tracked = self._tracker.update(sv_detections)
            # Trackers can return a filtered or reordered subset. Only attach
            # IDs when they refer to the exact detector rows used for counting.
            if np.array_equal(tracked.xyxy, detections.xyxy):
                detections.tracker_id = getattr(tracked, "tracker_id", None)
        except ImportError:
            detections.tracker_id = None
        return detections
