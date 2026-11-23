from datetime import timedelta

import pytest
from django.utils import timezone

from backend.monitoring.enums import IncidentState, Severity, StreamState
from backend.monitoring.models import Calibration, CriticalIncident, Feed, Zone
from backend.monitoring.services.incidents import CriticalIncidentEngine
from backend.monitoring.services.risk import RiskPolicy
from backend.monitoring.services.telemetry import ObservationValidationError, TelemetryProcessor


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, event_type, payload, feed_id=None):
        event = {"type": event_type, "payload": payload, "feed_id": feed_id}
        self.events.append(event)
        return event


def make_feed(name="Gate A"):
    return Feed.objects.create(
        name=name,
        location="North gate",
        source_type="webcam",
        stream_state=StreamState.LIVE,
    )


def make_calibrated_feed(name="Gate A"):
    feed = make_feed(name)
    zone = Zone.objects.create(feed=feed, name="Entrance", polygon_image=[[0, 0]])
    Calibration.objects.create(
        zone=zone,
        version=1,
        source_frame_size={"width": 100, "height": 100},
        image_reference_points=[[0, 0]],
        ground_reference_points_m=[[0, 0]],
        homography=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        polygon_ground_m=[[0, 0], [10, 0], [10, 10], [0, 10]],
        area_m2=100.0,
        calibrated=True,
    )
    return feed, zone


def payload(feed, zone, sequence, captured_at, density, sample_id="demo"):
    return {
        "feed_id": str(feed.id),
        "zone_id": str(zone.id),
        "sample_id": sample_id,
        "sequence": sequence,
        "captured_at": captured_at.isoformat(),
        "processed_at": captured_at.isoformat(),
        "people_count": int(density * 100),
        "density_people_per_m2": density,
        "calibration_version": 1,
        "measured_fps": 6.0,
        "quality_flags": [],
    }


@pytest.mark.django_db
def test_critical_create_acknowledge_and_duplicate_telemetry(django_capture_on_commit_callbacks):
    feed, zone = make_calibrated_feed()
    publisher = RecordingPublisher()
    policy = RiskPolicy(stale_seconds=300, recovery_seconds=30)
    processor = TelemetryProcessor(publisher=publisher, policy=policy)
    now = timezone.now()

    with django_capture_on_commit_callbacks(execute=True):
        first = processor.accept(payload(feed, zone, 1, now - timedelta(seconds=5), 2.2))
        duplicate = processor.accept(payload(feed, zone, 1, now - timedelta(seconds=5), 2.2))

    assert not first["duplicate"]
    assert duplicate["duplicate"]
    incident = CriticalIncident.objects.get(feed=feed, state=IncidentState.ACTIVE)
    assert incident.acknowledged is False
    assert sum(e["type"] == "incident.created" for e in publisher.events) == 1

    engine = CriticalIncidentEngine(publisher=publisher, policy=policy)
    with django_capture_on_commit_callbacks(execute=True):
        acknowledged = engine.acknowledge(str(incident.incident_id), actor="operator-a")
        repeated = engine.acknowledge(str(incident.incident_id), actor="operator-b")
    assert acknowledged.acknowledged is True
    assert acknowledged.acknowledged_by == "operator-a"
    assert repeated.acknowledged_at == acknowledged.acknowledged_at
    assert acknowledged.state == IncidentState.ACTIVE
    assert acknowledged.severity == Severity.CRITICAL
    assert sum(e["type"] == "incident.acknowledged" for e in publisher.events) == 1
    assert engine.can_navigate() is True


@pytest.mark.django_db
def test_recovery_requires_sustained_valid_observations_and_new_episode(django_capture_on_commit_callbacks):
    feed, zone = make_calibrated_feed()
    publisher = RecordingPublisher()
    policy = RiskPolicy(stale_seconds=300, recovery_seconds=30)
    processor = TelemetryProcessor(publisher=publisher, policy=policy)
    now = timezone.now()

    with django_capture_on_commit_callbacks(execute=True):
        processor.accept(payload(feed, zone, 1, now - timedelta(seconds=60), 2.2))
    incident = CriticalIncident.objects.get(feed=feed, state=IncidentState.ACTIVE)
    engine = processor.incidents

    first_safe = processor.accept(payload(feed, zone, 2, now - timedelta(seconds=30), 1.0, "safe-1"))
    assert not first_safe["lifecycle"]["resolved"]
    incident.refresh_from_db()
    assert incident.recovery_started_at is not None

    one_low = processor.accept(payload(feed, zone, 3, now - timedelta(seconds=20), 1.0, "safe-2"))
    assert not one_low["lifecycle"]["resolved"]

    recovered = processor.accept(payload(feed, zone, 4, now, 1.0, "safe-3"))
    assert recovered["lifecycle"]["resolved"]
    incident.refresh_from_db()
    assert incident.state == IncidentState.RESOLVED
    assert incident.resolved_at is not None
    assert incident.acknowledged is False

    old_id = incident.incident_id
    with django_capture_on_commit_callbacks(execute=True):
        new_episode = processor.accept(payload(feed, zone, 5, now + timedelta(seconds=5), 10.0, "critical-2"))
    assert new_episode["lifecycle"]["created"] is True
    incident = CriticalIncident.objects.get(feed=feed, state=IncidentState.ACTIVE)
    assert incident.incident_id != old_id
    assert sum(e["type"] == "incident.created" for e in publisher.events) == 2


@pytest.mark.django_db
def test_offline_stale_and_uncalibrated_cannot_resolve():
    feed, zone = make_calibrated_feed()
    policy = RiskPolicy(stale_seconds=15, recovery_seconds=30)
    processor = TelemetryProcessor(policy=policy)
    now = timezone.now()
    processor.accept(payload(feed, zone, 1, now - timedelta(seconds=5), 2.2))
    incident = CriticalIncident.objects.get(feed=feed, state=IncidentState.ACTIVE)

    feed.stream_state = StreamState.OFFLINE
    feed.save(update_fields=["stream_state"])
    with pytest.raises(ObservationValidationError):
        processor.accept(payload(feed, zone, 2, now, 1.0))
    incident.refresh_from_db()
    assert incident.state == IncidentState.ACTIVE
    assert incident.resolved_at is None

    feed.stream_state = StreamState.LIVE
    feed.save(update_fields=["stream_state"])
    Calibration.objects.filter(zone=zone).update(calibrated=False)
    with pytest.raises(ObservationValidationError):
        processor.accept(payload(feed, zone, 3, now, 1.0))
    incident.refresh_from_db()
    assert incident.state == IncidentState.ACTIVE


@pytest.mark.django_db
def test_multiple_active_incidents_are_independent():
    feed_a, zone_a = make_calibrated_feed("Gate A")
    feed_b, zone_b = make_calibrated_feed("Gate B")
    policy = RiskPolicy(stale_seconds=300)
    processor = TelemetryProcessor(policy=policy)
    now = timezone.now()

    processor.accept(payload(feed_a, zone_a, 1, now, 2.2))
    processor.accept(payload(feed_b, zone_b, 1, now, 2.4))

    active = CriticalIncident.objects.filter(state=IncidentState.ACTIVE)
    assert active.count() == 2
