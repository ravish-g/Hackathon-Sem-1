import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from backend.monitoring.enums import IncidentState, Severity
from backend.monitoring.models import CriticalIncident, Feed, FeedMetric, Zone
from backend.monitoring.views import set_incident_dependencies
from backend.worker_api.views import set_telemetry_processor


class TelemetryDouble:
    def __init__(self):
        self.payloads = []

    def accept(self, payload):
        self.payloads.append(payload)


class IncidentEngineDouble:
    def __init__(self):
        self.calls = []

    def acknowledge(self, incident_id, actor):
        self.calls.append((incident_id, actor))
        incident = CriticalIncident.objects.get(incident_id=incident_id)
        incident.acknowledged = True
        incident.acknowledged_at = timezone.now()
        incident.acknowledged_by = actor
        incident.save(update_fields=["acknowledged", "acknowledged_at", "acknowledged_by", "last_updated_at"])
        return incident


class PublisherDouble:
    def __init__(self):
        self.events = []

    def publish(self, event_type, payload, feed_id=None):
        self.events.append((event_type, payload, feed_id))


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_user(username="operator", password="secret")


@pytest.fixture
def api(operator):
    client = APIClient()
    client.force_authenticate(operator)
    return client


@pytest.fixture
def feed():
    return Feed.objects.create(name="North Gate", location="Entry", source_type="upload")


@pytest.fixture(autouse=True)
def integration_doubles():
    telemetry = TelemetryDouble()
    engine = IncidentEngineDouble()
    publisher = PublisherDouble()
    set_telemetry_processor(telemetry)
    set_incident_dependencies(engine, publisher)
    yield {"telemetry": telemetry, "engine": engine, "publisher": publisher}
    set_telemetry_processor(None)
    set_incident_dependencies(None, None)


@pytest.mark.django_db
def test_dashboard_restores_active_incident_after_refresh(api, feed):
    incident = CriticalIncident.objects.create(feed=feed, severity=Severity.CRITICAL.value, reason="density")
    response = api.get("/api/dashboard/")
    assert response.status_code == 200
    assert str(incident.incident_id) == response.json()["active_incidents"][0]["incident_id"]


@pytest.mark.django_db
def test_dashboard_returns_json_to_browser_accept_header(api):
    response = api.get("/api/dashboard/", HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    assert "feeds" in response.json()


@pytest.mark.django_db
def test_acknowledgement_is_idempotent_and_does_not_resolve(api, feed, operator, integration_doubles):
    incident = CriticalIncident.objects.create(feed=feed, severity=Severity.CRITICAL.value, reason="density")
    first = api.post(f"/api/incidents/{incident.incident_id}/acknowledge/", {})
    second = api.post(f"/api/incidents/{incident.incident_id}/acknowledge/", {})
    assert first.status_code == second.status_code == 200
    incident.refresh_from_db()
    assert incident.acknowledged is True
    assert incident.state == IncidentState.ACTIVE.value
    assert incident.acknowledged_by == operator.username
    assert incident.acknowledged_at.isoformat().replace("+00:00", "Z") == second.json()["acknowledged_at"]
    assert len(integration_doubles["engine"].calls) == 1
    assert len(integration_doubles["publisher"].events) == 1


@pytest.mark.django_db
def test_delete_is_blocked_for_active_incident(api, feed):
    CriticalIncident.objects.create(feed=feed, severity=Severity.CRITICAL.value, reason="density")
    response = api.delete(f"/api/feeds/{feed.id}/")
    assert response.status_code == 409
    assert Feed.objects.filter(id=feed.id).exists()


@pytest.mark.django_db
def test_invalid_calibration_is_rejected(api, feed):
    zone = Zone.objects.create(feed=feed, name="Queue")
    response = api.put(f"/api/feeds/{feed.id}/calibration/", {
        "zone_id": str(zone.id),
        "source_frame_size": {"width": 1280, "height": 720},
        "image_reference_points": [[0, 0], [1, 1], [2, 2], [3, 3]],
        "ground_reference_points_m": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "zone_polygon_image": [[0, 0], [1, 1], [2, 2], [3, 3]],
    }, format="json")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CALIBRATION_INVALID"


@pytest.mark.django_db
def test_calibration_computes_homography_and_area(api, feed):
    zone = Zone.objects.create(feed=feed, name="Queue")
    response = api.put(f"/api/feeds/{feed.id}/calibration/", {
        "zone_id": str(zone.id),
        "source_frame_size": {"width": 1280, "height": 720},
        "image_reference_points": [[0, 0], [2, 0], [2, 2], [0, 2]],
        "ground_reference_points_m": [[0, 0], [4, 0], [4, 2], [0, 2]],
        "zone_polygon_image": [[0, 0], [2, 0], [2, 2], [0, 2]],
        "area_m2": 999999,
    }, format="json")
    assert response.status_code == 200
    assert response.json()["area_m2"] == 8
    calibration = zone.calibrations.get()
    assert calibration.homography != []
    assert calibration.polygon_ground_m == [[0.0, 0.0], [4.0, 0.0], [4.0, 2.0], [0.0, 2.0]]


@pytest.mark.django_db
def test_worker_auth_and_replayed_telemetry(api, feed, settings, integration_doubles):
    payload = {
        "feed_id": str(feed.id), "sample_id": "sample-1", "sequence": 1,
        "captured_at": "2026-11-20T16:00:00Z", "processed_at": "2026-11-20T16:00:01Z",
        "people_count": 4, "is_valid": True,
    }
    settings.WORKER_INGEST_TOKEN = "worker-secret"
    unauthenticated = APIClient().post("/internal/telemetry/", payload, format="json")
    assert unauthenticated.status_code == 401
    first = APIClient().post("/internal/telemetry/", payload, format="json", HTTP_X_WORKER_TOKEN="worker-secret")
    replay = APIClient().post("/internal/telemetry/", payload, format="json", HTTP_X_WORKER_TOKEN="worker-secret")
    assert first.status_code == 201
    assert replay.status_code == 409
    assert FeedMetric.objects.filter(feed=feed, sequence=1).count() == 1
    assert len(integration_doubles["telemetry"].payloads) == 1
    heartbeat = APIClient().post(
        "/internal/worker-heartbeat/", {"worker_id": "worker-1"},
        format="json", HTTP_X_WORKER_TOKEN="worker-secret",
    )
    assert heartbeat.status_code == 200
    assert "worker-secret" not in heartbeat.content.decode()


@pytest.mark.django_db
def test_missing_authoritative_providers_fail_explicitly(api, feed, settings):
    settings.WORKER_INGEST_TOKEN = "worker-secret"
    set_telemetry_processor(None)
    telemetry_response = APIClient().post("/internal/telemetry/", {
        "feed_id": str(feed.id), "sample_id": "sample-1", "sequence": 1,
        "captured_at": "2026-11-20T16:00:00Z", "processed_at": "2026-11-20T16:00:01Z",
        "people_count": 4, "is_valid": True,
    }, format="json", HTTP_X_WORKER_TOKEN="worker-secret")
    assert telemetry_response.status_code == 503
    incident = CriticalIncident.objects.create(feed=feed, severity=Severity.CRITICAL.value, reason="density")
    set_incident_dependencies(None, None)
    acknowledgement_response = api.post(f"/api/incidents/{incident.incident_id}/acknowledge/", {})
    assert acknowledgement_response.status_code == 503
    incident.refresh_from_db()
    assert incident.acknowledged is False


@pytest.mark.django_db
@override_settings(MAX_UPLOAD_BYTES=20, MEDIA_ROOT="/tmp/crowd-fuzion-test-media")
def test_upload_validation_rejects_unsafe_and_too_large_files(api):
    unsafe = SimpleUploadedFile("payload.exe", b"MZ", content_type="application/octet-stream")
    assert api.post("/api/feeds/upload/", {"file": unsafe}, format="multipart").status_code == 415
    oversized = SimpleUploadedFile("clip.mp4", b"\x00" * 21, content_type="video/mp4")
    assert api.post("/api/feeds/upload/", {"file": oversized}, format="multipart").status_code == 413
