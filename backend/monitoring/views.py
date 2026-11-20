import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .enums import IncidentState, SourceType
from .models import Calibration, CriticalIncident, EventLogEntry, Feed, Zone
from .selectors import active_incidents_queryset, event_cursor, feed_queryset
from .serializers import CalibrationSerializer, EventSerializer, FeedSerializer, IncidentSerializer, TelemetrySerializer


AUTH = [SessionAuthentication, BasicAuthentication]


def error(code, message, fields=None, http_status=400):
    payload = {"error": {"code": code, "message": message}}
    if fields:
        payload["error"]["fields"] = fields
    return Response(payload, status=http_status)


def authenticated(view):
    view.cls.authentication_classes = AUTH
    view.cls.permission_classes = [IsAuthenticated]
    return view


def feed_data(feed):
    return FeedSerializer(feed).data


@authenticated
@api_view(["GET"])
def dashboard(request):
    return Response({
        "server_time": timezone.now().isoformat().replace("+00:00", "Z"),
        "event_cursor": event_cursor(),
        "feeds": [feed_data(feed) for feed in feed_queryset()],
        "active_incidents": IncidentSerializer(active_incidents_queryset(), many=True).data,
    })


@authenticated
@api_view(["GET", "POST"])
def feeds(request):
    if request.method == "GET":
        return Response({"results": [feed_data(feed) for feed in feed_queryset()]})
    serializer = FeedSerializer(data=request.data)
    if not serializer.is_valid():
        return error("VALIDATION_ERROR", "Feed data is invalid.", serializer.errors)
    feed = serializer.save()
    return Response(feed_data(feed), status=status.HTTP_201_CREATED)


@authenticated
@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def feed_upload(request):
    upload = request.FILES.get("file")
    if upload is None:
        return error("UPLOAD_INVALID", "A video file is required.")
    max_bytes = int(getattr(settings, "MAX_UPLOAD_BYTES", 100 * 1024 * 1024))
    if upload.size > max_bytes:
        return error("UPLOAD_TOO_LARGE", "The uploaded file exceeds the configured limit.", http_status=413)
    allowed = {".mp4", ".mov", ".avi", ".mkv"}
    extension = Path(upload.name).suffix.lower()
    if extension not in allowed or upload.content_type not in {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"}:
        return error("UPLOAD_UNSUPPORTED", "Only supported video files are accepted.", http_status=415)
    header = upload.read(12)
    upload.seek(0)
    signatures = {
        ".mp4": lambda value: len(value) >= 8 and value[4:8] == b"ftyp",
        ".mov": lambda value: len(value) >= 8 and value[4:8] == b"ftyp",
        ".avi": lambda value: value[:4] == b"RIFF" and value[8:12] == b"AVI ",
        ".mkv": lambda value: value[:4] == b"\x1a\x45\xdf\xa3",
    }
    if not signatures[extension](header):
        return error("UPLOAD_INVALID", "The file signature does not match a supported video.", http_status=415)
    media_root = Path(settings.MEDIA_ROOT).resolve()
    upload_dir = media_root / "feeds"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{extension}"
    destination = (upload_dir / stored_name).resolve()
    if media_root not in destination.parents:
        return error("UPLOAD_INVALID", "Unsafe upload path.")
    with destination.open("wb") as target:
        for chunk in upload.chunks():
            target.write(chunk)
    data = {"name": request.data.get("name") or Path(upload.name).stem, "location": request.data.get("location", ""), "source_type": SourceType.UPLOAD.value}
    feed = Feed.objects.create(**data, source_config={"stored_name": stored_name})
    return Response(feed_data(feed), status=status.HTTP_201_CREATED)


@authenticated
@api_view(["GET", "PATCH", "DELETE"])
def feed_detail(request, feed_id):
    try:
        feed = feed_queryset().get(id=feed_id)
    except Feed.DoesNotExist:
        return error("NOT_FOUND", "Feed was not found.", http_status=404)
    if request.method == "GET":
        return Response(feed_data(feed))
    if request.method == "PATCH":
        serializer = FeedSerializer(feed, data=request.data, partial=True)
        if not serializer.is_valid():
            return error("VALIDATION_ERROR", "Feed data is invalid.", serializer.errors)
        serializer.save(configuration_version=feed.configuration_version + 1)
        return Response(feed_data(feed))
    if active_incidents_queryset().filter(feed=feed).exists():
        return error("ACTIVE_INCIDENT", "A feed with an active incident cannot be deleted.", http_status=409)
    if CriticalIncident.objects.filter(feed=feed).exists():
        return error("INCIDENT_HISTORY", "A feed with incident history cannot be deleted.", http_status=409)
    feed.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@authenticated
@api_view(["PUT"])
def feed_calibration(request, feed_id):
    try:
        feed = Feed.objects.get(id=feed_id)
    except Feed.DoesNotExist:
        return error("NOT_FOUND", "Feed was not found.", http_status=404)
    serializer = CalibrationSerializer(data=request.data)
    if not serializer.is_valid():
        return error("CALIBRATION_INVALID", "Calibration data is invalid.", serializer.errors, 422)
    data = serializer.validated_data
    expected = data.get("expected_configuration_version")
    if expected is not None and expected != feed.configuration_version:
        return error("VERSION_CONFLICT", "Feed configuration has changed.", http_status=409)
    try:
        zone = feed.zones.get(id=data["zone_id"])
    except Zone.DoesNotExist:
        return error("ZONE_NOT_FOUND", "Zone does not belong to this feed.", http_status=404)
    version = (Calibration.objects.filter(zone=zone).order_by("-version").values_list("version", flat=True).first() or 0) + 1
    calibration = Calibration.objects.create(
        zone=zone, version=version, source_frame_size=data["source_frame_size"],
        image_reference_points=data["image_reference_points"],
        ground_reference_points_m=data["ground_reference_points_m"],
        homography=[], polygon_ground_m=data["ground_reference_points_m"],
        area_m2=data["area_m2"], calibrated=True,
    )
    feed.configuration_version += 1
    feed.analysis_state = "active"
    feed.save(update_fields=["configuration_version", "analysis_state", "updated_at"])
    return Response({
        "calibrated": calibration.calibrated, "area_m2": calibration.area_m2,
        "calibration_version": calibration.version, "zone_id": str(zone.id),
        "configuration_version": feed.configuration_version, "warnings": [],
    })


@authenticated
@api_view(["GET"])
def events(request):
    queryset = EventLogEntry.objects.select_related("feed").all()
    cursor = request.query_params.get("cursor")
    if cursor:
        try:
            queryset = queryset.filter(sequence__lt=int(cursor))
        except ValueError:
            return error("INVALID_CURSOR", "Cursor must be an integer.")
    if request.query_params.get("feed_id"):
        queryset = queryset.filter(feed_id=request.query_params["feed_id"])
    if request.query_params.get("severity"):
        queryset = queryset.filter(severity=request.query_params["severity"])
    if request.query_params.get("category"):
        queryset = queryset.filter(category=request.query_params["category"])
    try:
        limit = min(max(int(request.query_params.get("limit", 50)), 1), 100)
    except ValueError:
        return error("INVALID_LIMIT", "Limit must be an integer.")
    rows = list(queryset[:limit])
    return Response({"results": EventSerializer(rows, many=True).data, "next_cursor": rows[-1].sequence if rows else None})


@authenticated
@api_view(["GET"])
def active_incidents(request):
    return Response({"results": IncidentSerializer(active_incidents_queryset(), many=True).data})


@authenticated
@api_view(["GET"])
def incident_detail(request, incident_id):
    try:
        incident = CriticalIncident.objects.select_related("feed", "zone").get(incident_id=incident_id)
    except CriticalIncident.DoesNotExist:
        return error("NOT_FOUND", "Incident was not found.", http_status=404)
    return Response(IncidentSerializer(incident).data)


@authenticated
@api_view(["POST"])
def acknowledge_incident(request, incident_id):
    try:
        incident = CriticalIncident.objects.select_related("feed").get(incident_id=incident_id)
    except CriticalIncident.DoesNotExist:
        return error("NOT_FOUND", "Incident was not found.", http_status=404)
    if not incident.acknowledged:
        incident.acknowledged = True
        incident.acknowledged_at = timezone.now()
        incident.acknowledged_by = request.user.get_username() or str(request.user.pk)
        incident.save(update_fields=["acknowledged", "acknowledged_at", "acknowledged_by", "last_updated_at"])
    return Response(IncidentSerializer(incident).data)

