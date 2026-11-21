import os
import socket
import time
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import F

from backend.monitoring.models import Calibration, Feed, FeedMetric, VisionJob
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
            tile_size=int(os.getenv("VISION_TILE_SIZE", "640")),
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
                jobs = VisionJob.objects.select_related("feed").filter(
                    state__in=[
                        VisionJob.STATE_PENDING,
                        VisionJob.STATE_RUNNING,
                        VisionJob.STATE_COMPLETED,
                    ]
                ).order_by(F("started_at").asc(nulls_first=True), "created_at")
                waiting = jobs.exclude(feed_id__in=active)
                if len(active) >= max_feeds and waiting.exists():
                    oldest = jobs.filter(feed_id__in=active).first()
                    if oldest and (timezone.now() - oldest.started_at).total_seconds() >= 20:
                        reader, processor = active.pop(str(oldest.feed_id))
                        reader.stop()
                        processor.stop()
                        oldest.feed.analysis_state = "paused"
                        oldest.feed.save(update_fields=["analysis_state"])
                for job in jobs:
                    if len(active) >= max_feeds:
                        break
                    if str(job.feed_id) in active:
                        continue
                    replay = job.feed.source_type == "upload"
                    if replay:
                        source = str(Path(settings.MEDIA_ROOT) / job.source_path)
                    elif job.feed.source_type == "webcam":
                        source = job.feed.source_config.get("device_index", 0)
                    else:
                        source = job.feed.source_config.get("url")
                    if source is None or (replay and not Path(source).is_file()):
                        self._mark_error(job, "Video source unavailable")
                        continue
                    try:
                        capture = SourceReader.open_capture(source)
                        try:
                            ok, frame = capture.read()
                        finally:
                            capture.release()
                        if not ok:
                            self._mark_error(job, "Could not read a frame from this source")
                            continue
                        calibration, zones = self._load_calibration(job.feed, frame.shape[1], frame.shape[0])
                        reader = SourceReader(str(job.feed_id), source, None, loop=replay)
                        if not replay:
                            preview = Path(settings.MEDIA_ROOT) / "previews" / f"{job.feed_id}.jpg"
                            preview.parent.mkdir(exist_ok=True)
                            cv2.imwrite(str(preview), frame)
                            reader.preview_path = preview
                            job.feed.preview_url = f"{settings.MEDIA_URL}previews/{preview.name}"
                            job.feed.preview_transport = "image"
                        processor = SourceProcessor(
                            str(job.feed_id),
                            detector,
                            zones,
                            calibration,
                            publisher,
                            tracking=True,
                        )
                        processor.sequence = (FeedMetric.objects.filter(feed_id=job.feed_id)
                                              .order_by("-sequence").values_list("sequence", flat=True)
                                              .first() or 0)
                        reader.frames = processor.frames
                        reader.start()
                        processor.start()
                        active[str(job.feed_id)] = (reader, processor)
                        job.configuration_version = job.feed.configuration_version
                        job.state = VisionJob.STATE_RUNNING
                        job.worker_id = worker_id
                        job.started_at = timezone.now()
                        job.last_heartbeat_at = timezone.now()
                        job.error_message = ""
                        job.save(update_fields=["state", "configuration_version", "worker_id", "started_at", "last_heartbeat_at", "error_message", "updated_at"])
                        job.feed.analysis_state = "active"
                        job.feed.stream_state = "replay" if replay else "live"
                        job.feed.save(update_fields=["analysis_state", "stream_state", "preview_url", "preview_transport", "updated_at"])
                        self.stdout.write(self.style.SUCCESS(f"Started {job.feed.name}: {job.feed.source_type}"))
                    except Exception as exc:
                        self._mark_error(job, str(exc))

                completed = []
                for feed_id, (reader, processor) in active.items():
                    job = VisionJob.objects.filter(feed_id=feed_id).first()
                    if reader.ended or job is None or job.configuration_version != job.feed.configuration_version:
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
