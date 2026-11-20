from importlib import import_module

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from backend.monitoring.models import Feed, FeedMetric
from backend.monitoring.serializers import TelemetrySerializer
from backend.monitoring.views import error

_UNSET = object()
_telemetry_processor = _UNSET


def set_telemetry_processor(processor):
    global _telemetry_processor
    _telemetry_processor = processor


def _load_telemetry_processor():
    if _telemetry_processor is not _UNSET:
        return _telemetry_processor
    try:
        telemetry = import_module("backend.monitoring.services.telemetry")
    except ModuleNotFoundError as exc:
        if not exc.name.startswith("backend.monitoring.services"):
            raise
        return None
    processor = getattr(telemetry, "telemetry_processor", None)
    if processor is None:
        processor_class = getattr(telemetry, "TelemetryProcessor", None)
        processor = processor_class() if processor_class else None
    return processor


def worker_authorized(request):
    token = request.headers.get("X-Worker-Token", "")
    configured = getattr(settings, "WORKER_INGEST_TOKEN", "")
    return bool(configured) and token == configured


@api_view(["POST"])
@parser_classes([JSONParser])
def telemetry(request):
    if not worker_authorized(request):
        return error("WORKER_UNAUTHORIZED", "A valid worker credential is required.", http_status=401)
    serializer = TelemetrySerializer(data=request.data)
    if not serializer.is_valid():
        return error("VALIDATION_ERROR", "Telemetry is invalid.", serializer.errors)
    data = serializer.validated_data
    try:
        feed = Feed.objects.get(id=data["feed_id"])
    except Feed.DoesNotExist:
        return error("NOT_FOUND", "Feed was not found.", http_status=404)
    if FeedMetric.objects.filter(feed=feed, sequence=data["sequence"]).exists():
        return error("REPLAYED_TELEMETRY", "Telemetry sequence was already accepted.", http_status=409)
    processor = _load_telemetry_processor()
    if processor is None:
        return error(
            "TELEMETRY_PROVIDER_UNAVAILABLE",
            "The authoritative telemetry processor is unavailable.",
            http_status=503,
        )
    processor.accept(data)
    fields = {key: value for key, value in data.items() if key not in {"feed_id", "stream_state"}}
    try:
        with transaction.atomic():
            metric = FeedMetric.objects.create(feed=feed, **fields)
            update_fields = ["last_metric_at", "last_frame_at", "updated_at"]
            feed.last_metric_at = metric.processed_at
            feed.last_frame_at = metric.captured_at
            if data.get("stream_state"):
                feed.stream_state = data["stream_state"]
                update_fields.append("stream_state")
            feed.save(update_fields=update_fields)
    except IntegrityError:
        return error("REPLAYED_TELEMETRY", "Telemetry sequence was already accepted.", http_status=409)
    return Response({"accepted": True, "feed_id": str(feed.id), "sequence": metric.sequence}, status=201)


@api_view(["POST"])
@parser_classes([JSONParser])
def worker_heartbeat(request):
    if not worker_authorized(request):
        return error("WORKER_UNAUTHORIZED", "A valid worker credential is required.", http_status=401)
    payload = request.data
    if not isinstance(payload.get("worker_id"), str) or not payload["worker_id"].strip():
        return error("VALIDATION_ERROR", "worker_id is required.", {"worker_id": ["This field is required."]})
    return Response({
        "accepted": True, "worker_id": payload["worker_id"],
        "server_time": timezone.now().isoformat().replace("+00:00", "Z"),
    })
