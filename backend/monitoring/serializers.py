from rest_framework import serializers

from .enums import SourceType, StreamState
from .models import Calibration, CriticalIncident, EventLogEntry, Feed, FeedMetric, Zone


def iso(value):
    return value.isoformat().replace("+00:00", "Z") if value else None


class FeedMetricSerializer(serializers.ModelSerializer):
    metric_timestamp = serializers.DateTimeField(source="captured_at", read_only=True)

    class Meta:
        model = FeedMetric
        fields = (
            "people_count", "density_people_per_m2", "density_trend", "growth_rate",
            "predicted_threshold_time", "measured_fps", "inference_ms",
            "calibration_version", "quality_flags", "is_valid", "metric_timestamp",
            "sequence",
        )


class ZoneSerializer(serializers.ModelSerializer):
    area_m2 = serializers.SerializerMethodField()
    calibrated = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = ("id", "name", "polygon_image", "is_active", "area_m2", "calibrated")

    def get_area_m2(self, obj):
        calibration = obj.calibrations.order_by("-version").first()
        return calibration.area_m2 if calibration else None

    def get_calibrated(self, obj):
        calibration = obj.calibrations.order_by("-version").first()
        return bool(calibration and calibration.calibrated)


class FeedSerializer(serializers.ModelSerializer):
    feed_id = serializers.UUIDField(source="id", read_only=True)
    latest_metric = serializers.SerializerMethodField()
    zones = ZoneSerializer(many=True, read_only=True)
    source_config = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Feed
        fields = (
            "feed_id", "name", "location", "source_type", "source_config",
            "stream_state", "analysis_state", "severity", "risk_score",
            "last_metric_at", "last_frame_at", "preview_url", "preview_transport",
            "configuration_version", "state_version", "created_at", "updated_at",
            "latest_metric", "zones",
        )
        read_only_fields = (
            "stream_state", "analysis_state", "severity", "risk_score", "last_metric_at",
            "last_frame_at", "preview_url", "preview_transport", "configuration_version",
            "state_version", "created_at", "updated_at",
        )

    def validate_source_type(self, value):
        if value not in {item.value for item in SourceType}:
            raise serializers.ValidationError("Unsupported source type.")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("name"):
            raise serializers.ValidationError({"name": "This field is required."})
        if attrs.get("source_type") == SourceType.NETWORK.value:
            config = attrs.get("source_config", {})
            if not isinstance(config, dict) or not config.get("url"):
                raise serializers.ValidationError({"source_config": "A network source requires a URL."})
        return attrs

    def get_latest_metric(self, obj):
        metric = obj.metrics.order_by("-sequence").first()
        return FeedMetricSerializer(metric).data if metric else None


class CalibrationSerializer(serializers.Serializer):
    zone_id = serializers.UUIDField()
    source_frame_size = serializers.DictField()
    image_reference_points = serializers.ListField()
    ground_reference_points_m = serializers.ListField()
    zone_polygon_image = serializers.ListField()
    expected_configuration_version = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        size = attrs["source_frame_size"]
        if set(size) != {"width", "height"} or any(
            not isinstance(size[key], (int, float)) or size[key] <= 0 for key in ("width", "height")
        ):
            raise serializers.ValidationError({"source_frame_size": "Width and height must be positive."})
        for field in ("image_reference_points", "ground_reference_points_m", "zone_polygon_image"):
            points = attrs[field]
            if len(points) != 4 or any(not isinstance(point, (list, tuple)) or len(point) != 2 for point in points):
                raise serializers.ValidationError({field: "Exactly four 2D points are required."})
            if len({tuple(point) for point in points}) != 4:
                raise serializers.ValidationError({field: "Points must be distinct."})
            if any(not all(isinstance(value, (int, float)) for value in point) for point in points):
                raise serializers.ValidationError({field: "Points must contain numeric coordinates."})
        def polygon_area(points):
            return abs(sum(
                points[index][0] * points[(index + 1) % 4][1] -
                points[(index + 1) % 4][0] * points[index][1]
                for index in range(4)
            )) / 2

        area = polygon_area(attrs["ground_reference_points_m"])
        if area <= 0:
            raise serializers.ValidationError({"ground_reference_points_m": "Points must enclose a positive area."})
        for field in ("image_reference_points", "zone_polygon_image"):
            if polygon_area(attrs[field]) <= 0:
                raise serializers.ValidationError({field: "Points must enclose a positive area."})
        attrs["area_m2"] = area
        return attrs


class IncidentSerializer(serializers.ModelSerializer):
    incident_id = serializers.UUIDField(read_only=True)
    feed_id = serializers.UUIDField(source="feed.id", read_only=True)
    zone_id = serializers.UUIDField(source="zone.id", read_only=True, allow_null=True)

    class Meta:
        model = CriticalIncident
        fields = (
            "incident_id", "feed_id", "zone_id", "state", "severity", "acknowledged",
            "acknowledged_at", "acknowledged_by", "started_at", "last_updated_at",
            "resolved_at", "reason", "latest_metrics", "recovery_started_at", "policy_version",
        )


class EventSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField(read_only=True)
    feed_id = serializers.UUIDField(source="feed.id", read_only=True, allow_null=True)

    class Meta:
        model = EventLogEntry
        fields = (
            "event_id", "timestamp", "feed_id", "feed_name", "category", "severity",
            "event_type", "message", "delta_percent", "density_people_per_m2",
            "people_count", "incident_id", "state", "sequence",
        )


class TelemetrySerializer(serializers.Serializer):
    feed_id = serializers.UUIDField()
    sample_id = serializers.CharField(max_length=120)
    sequence = serializers.IntegerField(min_value=0)
    captured_at = serializers.DateTimeField()
    processed_at = serializers.DateTimeField()
    people_count = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    density_people_per_m2 = serializers.FloatField(required=False, min_value=0, allow_null=True)
    density_trend = serializers.CharField(required=False, max_length=20)
    growth_rate = serializers.FloatField(required=False, allow_null=True)
    predicted_threshold_time = serializers.DateTimeField(required=False, allow_null=True)
    measured_fps = serializers.FloatField(required=False, min_value=0, allow_null=True)
    inference_ms = serializers.FloatField(required=False, min_value=0, allow_null=True)
    calibration_version = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    quality_flags = serializers.ListField(required=False, child=serializers.CharField())
    is_valid = serializers.BooleanField()
    stream_state = serializers.ChoiceField(choices=[item.value for item in StreamState], required=False)

