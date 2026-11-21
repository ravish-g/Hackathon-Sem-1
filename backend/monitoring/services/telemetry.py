"""Authoritative calibrated timestamped telemetry validation and ingestion."""

from datetime import datetime, timedelta, timezone
import math
import uuid
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone

from backend.monitoring.enums import DensityTrend, Severity, StreamState
from backend.monitoring.models import Calibration, Feed, FeedMetric
from backend.monitoring.services.calibration import validate_calibration
from backend.monitoring.services.incidents import CriticalIncidentEngine
from backend.monitoring.services.risk import RiskAssessor, RiskPolicy


def parse_utc(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be ISO-8601")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass
class ValidatedObservation:
    feed_id: str
    zone_id: str | None
    sample_id: str
    sequence: int
    captured_at: datetime
    processed_at: datetime
    people_count: int | None
    density: float | None
    calibration_version: int | None
    measured_fps: float | None
    inference_ms: float | None
    quality_flags: list
    is_valid: bool

class ObservationValidationError(ValueError):
    pass


class TelemetryProcessor:
    def __init__(self, publisher=None, policy: RiskPolicy | None = None):
        self.publisher = publisher
        self.policy = policy or RiskPolicy.from_settings()
        self.assessor = RiskAssessor(self.policy)
        self.incidents = CriticalIncidentEngine(publisher=publisher, policy=self.policy)

    def _now(self) -> datetime:
        return django_timezone.now()

    def validate(self, payload: dict) -> ValidatedObservation:
        if not isinstance(payload, dict):
            raise ObservationValidationError("payload must be an object")
        feed_id = payload.get("feed_id")
        if not feed_id:
            raise ObservationValidationError("feed_id is required")
        try:
            feed = Feed.objects.select_related().get(pk=feed_id)
        except (Feed.DoesNotExist, ValueError, TypeError):
            raise ObservationValidationError("unknown feed")

        if feed.stream_state in (StreamState.OFFLINE, StreamState.STALE, StreamState.ERROR):
            self.incidents.mark_recovery_unavailable(feed)
            raise ObservationValidationError("feed is offline, stale or in error")

        try:
            sequence = int(payload["sequence"])
        except (KeyError, TypeError, ValueError):
            raise ObservationValidationError("sequence must be a positive integer")
        if sequence < 1:
            raise ObservationValidationError("sequence must be a positive integer")

        try:
            captured_at = parse_utc(payload["captured_at"])
            processed_at = parse_utc(payload.get("processed_at") or payload["captured_at"])
        except (KeyError, ValueError, TypeError, OverflowError):
            raise ObservationValidationError("captured_at and processed_at must be UTC ISO-8601")

        now = self._now()
        if captured_at > now + timedelta(seconds=30):
            self.incidents.mark_recovery_unavailable(feed)
            raise ObservationValidationError("captured_at is too far in the future")
        if (now - captured_at).total_seconds() > self.policy.stale_seconds:
            self.incidents.mark_recovery_unavailable(feed)
            raise ObservationValidationError("observation is stale")

        people_count = payload.get("people_count")
        if people_count is not None:
            if isinstance(people_count, bool):
                raise ObservationValidationError("people_count must be a nonnegative integer")
            try:
                people_count = int(people_count)
            except (TypeError, ValueError):
                raise ObservationValidationError("people_count must be a nonnegative integer")
            if people_count < 0:
                raise ObservationValidationError("people_count must be a nonnegative integer")

        if payload.get("is_valid") is False and payload.get("density_people_per_m2") is None:
            quality_flags = payload.get("quality_flags")
            if quality_flags is None:
                quality_flags = []
            if not isinstance(quality_flags, list):
                raise ObservationValidationError("quality_flags must be a list")
            measured_fps = payload.get("measured_fps")
            if measured_fps is not None:
                try:
                    measured_fps = float(measured_fps)
                except (TypeError, ValueError):
                    raise ObservationValidationError("measured_fps must be numeric")
                if not math.isfinite(measured_fps) or measured_fps < 0:
                    raise ObservationValidationError("measured_fps must be finite and nonnegative")
            inference_ms = payload.get("inference_ms")
            if inference_ms is not None:
                try:
                    inference_ms = float(inference_ms)
                except (TypeError, ValueError):
                    raise ObservationValidationError("inference_ms must be numeric")
                if not math.isfinite(inference_ms) or inference_ms < 0:
                    raise ObservationValidationError("inference_ms must be finite and nonnegative")
            self.incidents.mark_recovery_unavailable(feed)
            return ValidatedObservation(
                str(feed.id), payload.get("zone_id"),
                str(payload.get("sample_id") or uuid.uuid4()),
                sequence, captured_at, processed_at, people_count, None,
                None, measured_fps, inference_ms, quality_flags, False,
            )

        density = payload.get("density_people_per_m2")
        try:
            density = float(density)
        except (TypeError, ValueError):
            raise ObservationValidationError("calibrated density is required")
        if not math.isfinite(density) or density < 0:
            raise ObservationValidationError("density must be finite and nonnegative")

        try:
            calibration_version = int(payload["calibration_version"])
        except (KeyError, TypeError, ValueError):
            raise ObservationValidationError("calibration_version is required")

        zone_id = payload.get("zone_id")
        calibration = None
        if zone_id:
            try:
                calibration = Calibration.objects.get(
                    zone_id=zone_id, zone__feed=feed, version=calibration_version
                )
            except (Calibration.DoesNotExist, ValueError, TypeError):
                raise ObservationValidationError("calibration version is not valid for this feed zone")
        else:
            calibration = (
                Calibration.objects.filter(zone__feed=feed, version=calibration_version)
                .order_by("-created_at").first()
            )
        valid, reason = validate_calibration(calibration)
        if not valid:
            self.incidents.mark_recovery_unavailable(feed)
            raise ObservationValidationError(reason or "uncalibrated observation")

        measured_fps = payload.get("measured_fps")
        if measured_fps is not None:
            try:
                measured_fps = float(measured_fps)
            except (TypeError, ValueError):
                raise ObservationValidationError("measured_fps must be numeric")
            if not math.isfinite(measured_fps) or measured_fps < 0:
                raise ObservationValidationError("measured_fps must be finite and nonnegative")

        inference_ms = payload.get("inference_ms")
        if inference_ms is not None:
            try:
                inference_ms = float(inference_ms)
            except (TypeError, ValueError):
                raise ObservationValidationError("inference_ms must be numeric")
            if not math.isfinite(inference_ms) or inference_ms < 0:
                raise ObservationValidationError("inference_ms must be finite and nonnegative")

        quality_flags = payload.get("quality_flags")
        if quality_flags is None:
            quality_flags = []
        if not isinstance(quality_flags, list):
            raise ObservationValidationError("quality_flags must be a list")

        return ValidatedObservation(
            str(feed.id), str(zone_id) if zone_id else None,
            str(payload.get("sample_id") or uuid.uuid4()),
            sequence, captured_at, processed_at, people_count, density,
            calibration_version, measured_fps, inference_ms, quality_flags, True,
        )

    @transaction.atomic
    def accept(self, payload: dict):
        # Check repeat telemetry before freshness and calibration revalidation:
        # a retransmission is idempotent even if it arrives after a late window.
        try:
            repeat_feed = Feed.objects.get(pk=payload["feed_id"])
            repeat_sequence = int(payload["sequence"])
        except (KeyError, Feed.DoesNotExist, TypeError, ValueError):
            repeat_feed = None
            repeat_sequence = None
        if repeat_feed is not None:
            repeat = FeedMetric.objects.filter(
                feed=repeat_feed, sequence=repeat_sequence
            ).first()
            if repeat:
                supplied_sample_id = payload.get("sample_id")
                if supplied_sample_id is None or repeat.sample_id == str(supplied_sample_id):
                    return {"duplicate": True, "metric": repeat, "risk": None}
        observation = self.validate(payload)
        feed = Feed.objects.select_for_update().get(pk=observation.feed_id)
        existing = FeedMetric.objects.filter(feed=feed, sequence=observation.sequence).first()
        if existing:
            supplied_sample_id = payload.get("sample_id")
            if supplied_sample_id is not None and existing.sample_id != str(supplied_sample_id):
                raise ObservationValidationError("sequence has already been used with another sample")
            return {"duplicate": True, "metric": existing, "risk": None}

        previous = (
            FeedMetric.objects.filter(feed=feed, sequence__lt=observation.sequence)
            .order_by("-sequence").first()
        )
        if previous and previous.sequence > 0:
            elapsed = (observation.captured_at - previous.captured_at).total_seconds()
            if elapsed < 0:
                raise ObservationValidationError("observation is older than the latest metric")
        else:
            elapsed = 0

        prior_density = previous.density_people_per_m2 if previous else None
        prior_time = previous.captured_at if previous else None
        if observation.density is None:
            try:
                metric = FeedMetric.objects.create(
                    feed=feed, zone=None, sample_id=observation.sample_id,
                    sequence=observation.sequence, captured_at=observation.captured_at,
                    processed_at=observation.processed_at,
                    people_count=observation.people_count,
                    density_people_per_m2=None,
                    density_trend=DensityTrend.UNKNOWN.value,
                    growth_rate=0.0,
                    predicted_threshold_time=None,
                    measured_fps=observation.measured_fps,
                    inference_ms=observation.inference_ms,
                    calibration_version=None,
                    quality_flags=observation.quality_flags,
                    is_valid=False,
                )
            except IntegrityError:
                existing = FeedMetric.objects.filter(feed=feed, sequence=observation.sequence).first()
                return {"duplicate": True, "metric": existing, "risk": None}
            feed.severity = Severity.UNKNOWN.value
            feed.risk_score = None
            feed.last_metric_at = observation.captured_at
            feed.stream_state = StreamState.REPLAY if feed.source_type == "upload" else StreamState.LIVE
            feed.state_version += 1
            feed.save(update_fields=[
                "severity", "risk_score", "last_metric_at", "stream_state",
                "state_version", "updated_at",
            ])
            return {"duplicate": False, "metric": metric, "risk": None, "lifecycle": None}
        risk = self.assessor.assess(
            observation.density, observation.captured_at,
            prior_density, prior_time, feed.severity,
        )

        zone = None
        if observation.zone_id:
            zone = feed.zones.filter(pk=observation.zone_id).first()

        try:
            metric = FeedMetric.objects.create(
                feed=feed, zone=zone, sample_id=observation.sample_id,
                sequence=observation.sequence, captured_at=observation.captured_at,
                processed_at=observation.processed_at,
                people_count=observation.people_count,
                density_people_per_m2=observation.density,
                density_trend=risk.density_trend.value,
                growth_rate=risk.growth_rate,
                predicted_threshold_time=risk.predicted_threshold_time,
                measured_fps=observation.measured_fps,
                inference_ms=observation.inference_ms,
                calibration_version=observation.calibration_version,
                quality_flags=observation.quality_flags,
                is_valid=True,
            )
        except IntegrityError:
            existing = FeedMetric.objects.filter(feed=feed, sequence=observation.sequence).first()
            return {"duplicate": True, "metric": existing, "risk": None}

        feed.severity = risk.severity.value
        feed.risk_score = risk.risk_score
        feed.last_metric_at = observation.captured_at
        feed.stream_state = StreamState.REPLAY if feed.source_type == "upload" else StreamState.LIVE
        feed.state_version += 1
        feed.save(update_fields=[
            "severity", "risk_score", "last_metric_at", "stream_state",
            "state_version", "updated_at",
        ])

        lifecycle = self.incidents.process_observation(
            feed=feed,
            zone=zone,
            captured_at=observation.captured_at,
            risk=risk,
            people_count=observation.people_count,
            sequence=observation.sequence,
        )
        return {"duplicate": False, "metric": metric, "risk": risk, "lifecycle": lifecycle}


def validate_telemetry_payload(payload: dict, publisher=None, policy: RiskPolicy | None = None):
    return TelemetryProcessor(publisher=publisher, policy=policy).validate(payload)
