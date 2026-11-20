import threading
import time
import uuid
from datetime import datetime, timezone
from queue import Empty, Full, Queue

import numpy as np

from .calibration import HomographyCalibration
from .metrics import FpsMeter, TelemetrySample, density_trend, utc_now
from .publisher import TelemetryPublisher
from .tracking import PerSourceTracker
from .types import Detections, FramePacket
from .zones import Zone, count_zone_occupants


class SourceProcessor:
    def __init__(
        self,
        feed_id: str,
        detector,
        zones: list[Zone],
        calibration: HomographyCalibration | None,
        publisher: TelemetryPublisher,
        queue_size: int = 4,
        tracking: bool = True,
        frame_pacing_seconds: float = 0.0,
    ):
        self.feed_id = feed_id
        self.detector = detector
        self.zones = zones
        self.calibration = calibration
        self.publisher = publisher
        self.frames: Queue[FramePacket] = Queue(maxsize=queue_size)
        self.tracker = PerSourceTracker(enabled=tracking)
        self.frame_pacing_seconds = frame_pacing_seconds
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.fps_meter = FpsMeter()
        self.sequence = 0
        self._density_history: dict[str, list[float]] = {zone.zone_id: [] for zone in zones}

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"inference-{self.feed_id}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3.0)

    def enqueue(self, packet: FramePacket) -> bool:
        try:
            self.frames.put_nowait(packet)
            return True
        except Full:
            try:
                self.frames.get_nowait()
            except Empty:
                pass
            try:
                self.frames.put_nowait(packet)
                return True
            except Full:
                return False

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                packet = self.frames.get(timeout=0.1)
            except Empty:
                continue
            started = time.monotonic()
            try:
                detections: Detections = self.detector.detect(packet.frame)
                detections = self.tracker.update(detections)
                tracker_ids = detections.tracker_id
                self.fps_meter.add()
                processed_at = utc_now()
                inference_ms = (time.monotonic() - started) * 1000.0

                if not self.zones:
                    flags = ["calibration_invalid"]
                    if detections.confidence is not None and len(detections.confidence):
                        if float(np.mean(detections.confidence)) < 0.5:
                            flags.append("low_confidence")
                    self.sequence += 1
                    sample = TelemetrySample(
                        feed_id=self.feed_id,
                        zone_id=None,
                        sample_id=str(uuid.uuid4()),
                        sequence=self.sequence,
                        captured_at=packet.captured_at,
                        processed_at=processed_at,
                        received_at=None,
                        people_count=len(detections.xyxy),
                        density_people_per_m2=None,
                        density_trend="unknown",
                        growth_rate=0.0,
                        predicted_threshold_time=None,
                        measured_fps=self.fps_meter.fps(),
                        inference_ms=inference_ms,
                        calibration_version=None,
                        quality_flags=flags,
                        is_valid=False,
                    )
                    self.publisher.publish(sample)
                else:
                    for zone in self.zones:
                        count, density, quality = count_zone_occupants(
                            self.calibration,
                            zone,
                            detections.xyxy,
                            tracker_ids,
                        )
                        if density is None:
                            history = []
                            trend = "unknown"
                            valid = False
                            density_for_history = None
                        else:
                            history = self._density_history[zone.zone_id]
                            history.append(density)
                            if len(history) > 30:
                                del history[:-30]
                            trend = density_trend(history)
                            valid = True
                            density_for_history = density
                        if detections.confidence is not None and len(detections.confidence):
                            if float(np.mean(detections.confidence)) < 0.5:
                                quality.append("low_confidence")
                        self.sequence += 1
                        sample = TelemetrySample(
                            feed_id=self.feed_id,
                            zone_id=zone.zone_id,
                            sample_id=str(uuid.uuid4()),
                            sequence=self.sequence,
                            captured_at=packet.captured_at,
                            processed_at=processed_at,
                            received_at=None,
                            people_count=count,
                            density_people_per_m2=density,
                            density_trend=trend,
                            growth_rate=0.0,
                            predicted_threshold_time=None,
                            measured_fps=self.fps_meter.fps(),
                            inference_ms=inference_ms,
                            calibration_version=self.calibration.version if self.calibration and self.calibration.valid else None,
                            quality_flags=quality,
                            is_valid=valid,
                        )
                        self.publisher.publish(sample)
            except Exception as exc:
                self.sequence += 1
                sample = TelemetrySample(
                    feed_id=self.feed_id,
                    zone_id=None,
                    sample_id=str(uuid.uuid4()),
                    sequence=self.sequence,
                    captured_at=packet.captured_at,
                    processed_at=utc_now(),
                    received_at=None,
                    people_count=None,
                    density_people_per_m2=None,
                    density_trend="unknown",
                    growth_rate=0.0,
                    predicted_threshold_time=None,
                    measured_fps=self.fps_meter.fps(),
                    inference_ms=(time.monotonic() - started) * 1000.0,
                    calibration_version=self.calibration.version if self.calibration and self.calibration.valid else None,
                    quality_flags=["inference_error"],
                    is_valid=False,
                )
                self.publisher.publish(sample)
            if self.frame_pacing_seconds:
                time.sleep(self.frame_pacing_seconds)
