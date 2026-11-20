import time

import numpy as np

from vision.metrics import TelemetrySample
from vision.scheduler import SourceProcessor
from vision.types import Detections, FramePacket
from vision.zones import Zone


class MockDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return Detections(
            xyxy=np.array([[1, 1, 3, 4]], dtype=np.float32),
            confidence=np.array([0.9], dtype=np.float32),
            class_id=np.array([0], dtype=np.int32),
        )


class RecordingPublisher:
    def __init__(self):
        self.samples = []

    def publish(self, sample):
        self.samples.append(sample)
        return True


def test_mock_detector_smoke_uncalibrated():
    processor = SourceProcessor(
        feed_id="feed-a",
        detector=MockDetector(),
        zones=[Zone("zone-a", np.array([[0, 0], [5, 0], [5, 5], [0, 5]], dtype=np.float32))],
        calibration=None,
        publisher=RecordingPublisher(),
        tracking=False,
    )
    processor.start()
    processor.enqueue(FramePacket(
        feed_id="feed-a",
        source_id="mock.mp4",
        frame_number=1,
        captured_at="2026-11-20T00:00:00+00:00",
        frame=np.zeros((10, 10, 3), dtype=np.uint8),
        source_width=10,
        source_height=10,
    ))
    for _ in range(20):
        if processor.publisher.samples:
            break
        time.sleep(0.01)

    processor.stop()
    assert len(processor.publisher.samples) == 1
    sample = processor.publisher.samples[0]
    assert sample.people_count == 0
    assert sample.density_people_per_m2 is None
    assert sample.is_valid is False
