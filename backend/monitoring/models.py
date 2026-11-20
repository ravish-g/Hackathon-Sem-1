import uuid

from django.db import models

from .enums import (
    AnalysisState,
    DensityTrend,
    IncidentState,
    Severity,
    SourceType,
    StreamState,
)


class Feed(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=[(x.value, x.value) for x in SourceType])
    source_config = models.JSONField(default=dict)
    stream_state = models.CharField(max_length=20, choices=[(x.value, x.value) for x in StreamState], default=StreamState.CONNECTING)
    analysis_state = models.CharField(max_length=20, choices=[(x.value, x.value) for x in AnalysisState], default=AnalysisState.PENDING)
    severity = models.CharField(max_length=20, choices=[(x.value, x.value) for x in Severity], default=Severity.UNKNOWN)
    risk_score = models.FloatField(null=True, blank=True)
    last_metric_at = models.DateTimeField(null=True, blank=True)
    last_frame_at = models.DateTimeField(null=True, blank=True)
    preview_url = models.URLField(null=True, blank=True)
    preview_transport = models.CharField(max_length=20, null=True, blank=True)
    configuration_version = models.PositiveIntegerField(default=1)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]


class Zone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=120)
    polygon_image = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)


class Calibration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="calibrations")
    version = models.PositiveIntegerField()
    source_frame_size = models.JSONField(default=dict)
    image_reference_points = models.JSONField(default=list)
    ground_reference_points_m = models.JSONField(default=list)
    homography = models.JSONField(default=list)
    polygon_ground_m = models.JSONField(default=list)
    area_m2 = models.FloatField(null=True, blank=True)
    calibrated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["zone", "version"], name="unique_zone_calibration_version"),
        ]


class FeedMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="metrics")
    zone = models.ForeignKey(Zone, null=True, blank=True, on_delete=models.CASCADE, related_name="metrics")
    sample_id = models.CharField(max_length=120)
    sequence = models.PositiveBigIntegerField()
    captured_at = models.DateTimeField()
    processed_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    people_count = models.PositiveIntegerField(null=True, blank=True)
    density_people_per_m2 = models.FloatField(null=True, blank=True)
    density_trend = models.CharField(max_length=20, choices=[(x.value, x.value) for x in DensityTrend], default=DensityTrend.UNKNOWN)
    growth_rate = models.FloatField(null=True, blank=True)
    predicted_threshold_time = models.DateTimeField(null=True, blank=True)
    measured_fps = models.FloatField(null=True, blank=True)
    inference_ms = models.FloatField(null=True, blank=True)
    calibration_version = models.PositiveIntegerField(null=True, blank=True)
    quality_flags = models.JSONField(default=list)
    is_valid = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["feed", "sequence"], name="unique_feed_metric_sequence"),
        ]
        indexes = [models.Index(fields=["feed", "-sequence"])]


class CriticalIncident(models.Model):
    incident_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feed = models.ForeignKey(Feed, on_delete=models.PROTECT, related_name="incidents")
    zone = models.ForeignKey(Zone, null=True, blank=True, on_delete=models.PROTECT, related_name="incidents")
    state = models.CharField(max_length=20, choices=[(x.value, x.value) for x in IncidentState], default=IncidentState.ACTIVE)
    severity = models.CharField(max_length=20, choices=[(x.value, x.value) for x in Severity], default=Severity.CRITICAL)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.CharField(max_length=150, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=500)
    latest_metrics = models.JSONField(null=True, blank=True)
    recovery_started_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=50, default="v1")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["feed", "zone"],
                condition=models.Q(state=IncidentState.ACTIVE.value),
                name="one_active_incident_per_feed_zone",
            ),
        ]
        indexes = [models.Index(fields=["state", "feed"])]


class EventLogEntry(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    feed = models.ForeignKey(Feed, null=True, blank=True, on_delete=models.SET_NULL, related_name="event_logs")
    feed_name = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=30)
    severity = models.CharField(max_length=20)
    event_type = models.CharField(max_length=80)
    message = models.CharField(max_length=500)
    delta_percent = models.FloatField(null=True, blank=True)
    density_people_per_m2 = models.FloatField(null=True, blank=True)
    people_count = models.PositiveIntegerField(null=True, blank=True)
    incident_id = models.UUIDField(null=True, blank=True)
    state = models.CharField(max_length=20, null=True, blank=True)
    sequence = models.PositiveBigIntegerField(unique=True)

    class Meta:
        ordering = ["-sequence"]

