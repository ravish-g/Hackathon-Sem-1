import os
import socket
import time
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from backend.monitoring.models import Calibration, Feed, VisionJob
from vision.calibration import HomographyCalibration
from vision.detector import YoloPersonDetector
from vision.publisher import TelemetryPublisher
from vision.scheduler import SourceProcessor
from vision.sources import SourceReader
from vision.zones import Zone


class Command(BaseCommand):
    help = "Runs pending uploaded-feed vision jobs with one shared YOLO runtime"

    def add_arguments(self, parser):
        parser.add_argument("--max-feeds", type=int, default=int(os.getenv("VISION_MAX_FEEDS", "2")))

    def handle(self, *args, **options):
        max_feeds = max(1, options["max_feeds"])
        detector = YoloPersonDetector(
            model_path=os.getenv("VISION_MODEL", "yolo11n.pt"),
            confidence=float(os.getenv("VISION_CONFIDENCE", "0.25")),
            device=os.getenv("VISION_DEVICE", "cpu"),
        )
        telemetry_url = os.getenv("VISION_TELEMETRY_URL", "http://web:8000/internal/telemetry/")
        worker_token = os.getenv("WORKER_INGEST_TOKEN", "")
        publisher = TelemetryPublisher(telemetry_url, worker_token)
        publisher.start()
        active: dict[str, tuple[SourceReader, SourceProcessor]] = {}
        worker_id = os.getenv("VISION_WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"

        try:
            self.stdout.write(self.style.SUCCESS("Vision supervisor started"))
            while True:
                self._heartbeat(active, worker_id)
                for job in VisionJob.objects.select_related("feed").filter(
                    state__in=[
                        VisionJob.STATE_PENDING,
                        VisionJob.STATE_RUNNING,
                        VisionJob.STATE_COMPLETED,
                    ]
                ).order_by("created_at"):
                    if len(active) >= max_feeds:
                        break
                    if str(job.feed_id) in active:
                        continue
                    if job.feed.source_type != "upload":
                        continue
                    if not job.source_path:
                        self._mark_error(job, "Upload source path is missing")
                        continue
                    source = (Path(settings.MEDIA_ROOT) / job.source_path).resolve()
                    if not source.is_file():
                        self._mark_error(job, f"Upload source was not found: {job.source_path}")
                        continue
                    try:
                        capture = cv2.VideoCapture(str(source))
                        if not capture.isOpened():
                            capture.release()
                            self._mark_error(job, "OpenCV could not open the uploaded MP4")
                            continue
                        ok, frame = capture.read()
                        capture.release()
                        if not ok:
                            self._mark_error(job, "Uploaded MP4 contains no readable frame")
                            continue
                        calibration, zones = self._load_calibration(job.feed, frame.shape[1], frame.shape[0])
                        reader = SourceReader(str(job.feed_id), str(source), None, loop=True)
                        processor = SourceProcessor(
                            str(job.feed_id),
                            detector,
                            zones,
                            calibration,
                            publisher,
                            tracking=True,
                        )
                        reader.frames = processor.frames
                        reader.start()
                        processor.start()
                        active[str(job.feed_id)] = (reader, processor)
                        job.state = VisionJob.STATE_RUNNING
                        job.worker_id = worker_id
                        job.started_at = timezone.now()
                        job.last_heartbeat_at = timezone.now()
                        job.error_message = ""
                        job.save(update_fields=["state", "worker_id", "started_at", "last_heartbeat_at", "error_message", "updated_at"])
                        job.feed.analysis_state = "active"
                        job.feed.stream_state = "replay"
                        job.feed.save(update_fields=["analysis_state", "stream_state", "updated_at"])
                        self.stdout.write(self.style.SUCCESS(f"Started {job.feed.name}: {source.name}"))
                    except Exception as exc:
                        self._mark_error(job, str(exc))

                completed = []
                for feed_id, (reader, processor) in active.items():
                    job = VisionJob.objects.filter(feed_id=feed_id).first()
                    if reader.ended:
                        reader.stop()
                        processor.stop()
                        if job:
                            job.state = VisionJob.STATE_COMPLETED
                            job.completed_at = timezone.now()
                            job.last_heartbeat_at = timezone.now()
                            job.save(update_fields=["state", "completed_at", "last_heartbeat_at", "updated_at"])
                            job.feed.analysis_state = "paused"
                            job.feed.save(update_fields=["analysis_state", "updated_at"])
                        completed.append(feed_id)
                for feed_id in completed:
                    active.pop(feed_id, None)

                time.sleep(float(os.getenv("VISION_POLL_SECONDS", "5")))
        finally:
            for reader, processor in active.values():
                reader.stop()
                processor.stop()
            publisher.stop()

    def _heartbeat(self, active, worker_id):
        feed_ids = [feed_id for feed_id in active]
        if feed_ids:
            VisionJob.objects.filter(feed_id__in=feed_ids).update(
                worker_id=worker_id,
                last_heartbeat_at=timezone.now(),
            )

    def _mark_error(self, job, message):
        job.state = VisionJob.STATE_ERROR
        job.error_message = message[:1000]
        job.completed_at = timezone.now()
        job.save(update_fields=["state", "error_message", "completed_at", "updated_at"])
        job.feed.analysis_state = "failed"
        job.feed.save(update_fields=["analysis_state", "updated_at"])
        self.stderr.write(self.style.ERROR(f"{job.feed.name}: {message}"))

    def _load_calibration(self, feed: Feed, width: int, height: int):
        for zone in feed.zones.filter(is_active=True).prefetch_related("calibrations"):
            calibration = zone.calibrations.order_by("-version").filter(calibrated=True).first()
            if calibration:
                image_points = np.asarray(calibration.image_reference_points, dtype=np.float32)
                if calibration.source_frame_size.get("width") == 1:
                    image_points = image_points * np.asarray([width, height], dtype=np.float32)
                homography = HomographyCalibration(
                    image_points=image_points,
                    ground_points_m=np.asarray(calibration.ground_reference_points_m, dtype=np.float32),
                    version=calibration.version,
                )
                zones = [
                    Zone(
                        zone_id=str(zone.id),
                        ground_polygon_m=np.asarray(calibration.polygon_ground_m, dtype=np.float32),
                        image_polygon=np.asarray(zone.polygon_image, dtype=np.float32),
                    )
                ]
                return homography, zones
        return None, []
