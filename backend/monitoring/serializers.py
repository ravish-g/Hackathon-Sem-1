from urllib.parse import urlsplit

from rest_framework import serializers
import numpy as np

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
    history = serializers.SerializerMethodField()
    people_count = serializers.SerializerMethodField()
    density_people_per_m2 = serializers.SerializerMethodField()
    density_trend = serializers.SerializerMethodField()
    growth_rate = serializers.SerializerMethodField()
    predicted_threshold_time = serializers.SerializerMethodField()
    measured_fps = serializers.SerializerMethodField()
    metric_timestamp = serializers.SerializerMethodField()
    zone_area_m2 = serializers.SerializerMethodField()
    calibrated = serializers.SerializerMethodField()
    zones = ZoneSerializer(many=True, read_only=True)
    source_config = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Feed
        fields = (
            "feed_id", "name", "location", "source_type", "source_config",
            "stream_state", "analysis_state", "severity", "risk_score",
            "last_metric_at", "last_frame_at", "preview_url", "preview_transport",
            "configuration_version", "state_version", "created_at", "updated_at",
            "latest_metric", "history", "people_count", "density_people_per_m2", "density_trend",
            "growth_rate", "predicted_threshold_time", "measured_fps", "metric_timestamp",
            "zone_area_m2", "calibrated", "zones",
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
        source_type = attrs.get("source_type", getattr(self.instance, "source_type", None))
        config = attrs.get("source_config", getattr(self.instance, "source_config", {}))
        if source_type == SourceType.NETWORK.value:
            if not isinstance(config, dict) or not config.get("url"):
                raise serializers.ValidationError({"source_config": "A network source requires a URL."})
            try:
                address = urlsplit(config["url"])
                if (address.scheme not in {"http", "https", "rtsp"} or not address.hostname
                        or address.username or address.password):
                    raise ValueError
                address.port
            except (ValueError, TypeError, AttributeError):
                raise serializers.ValidationError({"source_config": "Enter an HTTP, HTTPS or RTSP stream URL without credentials."})
        if source_type == SourceType.WEBCAM.value:
            index = config.get("device_index", 0)
            if type(index) is not int or index < 0:
                raise serializers.ValidationError({"source_config": "Enter a nonnegative camera index."})
        return attrs

    def get_history(self, obj):
        latest = self._latest_metric(obj)
        if not latest or not latest.is_valid:
            return []
        densities = obj.metrics.filter(
            zone_id=latest.zone_id, calibration_version=latest.calibration_version,
            is_valid=True, density_people_per_m2__isnull=False,
        ).order_by("-sequence").values_list("density_people_per_m2", flat=True)[:90]
        return list(reversed(list(densities)))

    def get_latest_metric(self, obj):
        metric = self._latest_metric(obj)
        return FeedMetricSerializer(metric).data if metric else None

    def _latest_metric(self, obj):
        if not hasattr(obj, "_serialized_metric"):
            obj._serialized_metric = obj.metrics.order_by("-sequence").first()
        return obj._serialized_metric

    def _latest_calibration(self, obj):
        zone = obj.zones.filter(is_active=True).prefetch_related("calibrations").first()
        return zone.calibrations.order_by("-version").first() if zone else None

    def get_people_count(self, obj):
        metric = self._latest_metric(obj)
        return metric.people_count if metric else None

    def get_density_people_per_m2(self, obj):
        metric = self._latest_metric(obj)
        return metric.density_people_per_m2 if metric else None

    def get_density_trend(self, obj):
        metric = self._latest_metric(obj)
        return metric.density_trend if metric else None

    def get_growth_rate(self, obj):
        metric = self._latest_metric(obj)
        return metric.growth_rate if metric else None

    def get_predicted_threshold_time(self, obj):
        metric = self._latest_metric(obj)
        return iso(metric.predicted_threshold_time) if metric else None

    def get_measured_fps(self, obj):
        metric = self._latest_metric(obj)
        return metric.measured_fps if metric else None

    def get_metric_timestamp(self, obj):
        metric = self._latest_metric(obj)
        return iso(metric.captured_at) if metric else None

    def get_zone_area_m2(self, obj):
        calibration = self._latest_calibration(obj)
        return calibration.area_m2 if calibration else None

    def get_calibrated(self, obj):
        calibration = self._latest_calibration(obj)
        return bool(calibration and calibration.calibrated)


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
            if any(not all(isinstance(value, (int, float)) and np.isfinite(value) for value in point) for point in points):
                raise serializers.ValidationError({field: "Points must contain numeric coordinates."})
            if len({tuple(point) for point in points}) != 4:
                raise serializers.ValidationError({field: "Points must be distinct."})
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
        try:
            homography = _homography(
                attrs["image_reference_points"], attrs["ground_reference_points_m"]
            )
            polygon_ground = _project(homography, attrs["zone_polygon_image"])
            transformed_area = polygon_area(polygon_ground)
        except (np.linalg.LinAlgError, ValueError):
            raise serializers.ValidationError(
                {"image_reference_points": "Correspondences do not define a valid homography."}
            )
        if transformed_area <= 0 or not np.isfinite(transformed_area):
            raise serializers.ValidationError(
                {"zone_polygon_image": "The transformed zone must enclose a positive area."}
            )
        attrs["homography"] = homography
        attrs["polygon_ground_m"] = polygon_ground
        attrs["area_m2"] = transformed_area
        return attrs


def _homography(image_points, ground_points):
    matrix = []
    values = []
    for (x, y), (u, v) in zip(image_points, ground_points):
        matrix.extend([
            [x, y, 1, 0, 0, 0, -u * x, -u * y],
            [0, 0, 0, x, y, 1, -v * x, -v * y],
        ])
        values.extend([u, v])
    solution = np.linalg.solve(np.asarray(matrix, dtype=float), np.asarray(values, dtype=float))
    result = np.append(solution, 1.0).reshape((3, 3))
    if not np.isfinite(result).all():
        raise ValueError("Homography contains non-finite values.")
    return result.tolist()


def _project(homography, points):
    matrix = np.asarray(homography, dtype=float)
    projected = []
    for x, y in points:
        result = matrix @ np.asarray([x, y, 1.0])
        if result[2] == 0:
            raise ValueError("Homography maps a point to infinity.")
        projected.append([float(result[0] / result[2]), float(result[1] / result[2])])
    return projected


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

