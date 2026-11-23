import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from backend.config.asgi import application
from backend.monitoring.contracts import EVENT_TYPES
from backend.monitoring.models import CriticalIncident, Feed
from backend.monitoring.services.publisher import event_publisher
from backend.monitoring.enums import IncidentState


@pytest.mark.django_db(transaction=True)
def test_authorized_dashboard_receives_snapshot():
    user = get_user_model().objects.create(username="operator")

    async def run():
        communicator = WebsocketCommunicator(application, "/ws/dashboard/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        assert connected
        message = await communicator.receive_json_from()
        assert message["type"] == "dashboard.snapshot"
        assert set(message) == {
            "type", "event_id", "sequence", "timestamp", "feed_id", "payload",
        }
        assert message["payload"]["active_incidents"] == []
        await communicator.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
def test_anonymous_dashboard_connection_is_rejected():
    from django.contrib.auth.models import AnonymousUser

    async def run():
        communicator = WebsocketCommunicator(application, "/ws/dashboard/")
        communicator.scope["user"] = AnonymousUser()
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4403

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
def test_incident_lifecycle_survives_metric_coalescing_and_reconnect():
    user = get_user_model().objects.create(username="incident-operator")
    feed = Feed.objects.create(
        name="Gate",
        location="Main gate",
        source_type="network",
    )
    incident = CriticalIncident.objects.create(
        feed=feed,
        state=IncidentState.ACTIVE,
        severity="critical",
        acknowledged=False,
        reason="Test incident",
    )

    async def run():
        communicator = WebsocketCommunicator(application, "/ws/dashboard/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        assert connected
        snapshot = await communicator.receive_json_from()
        assert len(snapshot["payload"]["active_incidents"]) == 1

        await sync_to_async(event_publisher.publish)(
            "feed.metrics_updated",
            {"people_count": 100},
            str(feed.id),
        )
        lifecycle = await sync_to_async(event_publisher.publish)(
            "incident.acknowledged",
            {
                "incident_id": str(incident.incident_id),
                "acknowledged": True,
                "state": "active",
                "severity": "critical",
            },
            str(feed.id),
        )
        acknowledged = await communicator.receive_json_from()
        if acknowledged["type"] == "feed.metrics_updated":
            acknowledged = await communicator.receive_json_from()
        assert acknowledged["type"] == "incident.acknowledged"
        assert acknowledged["sequence"] == lifecycle["sequence"]
        assert acknowledged["payload"]["state"] == "active"
        assert acknowledged["payload"]["acknowledged"] is True

        await communicator.send_json_to({"type": "snapshot"})
        restored = await communicator.receive_json_from()
        assert restored["type"] == "dashboard.snapshot"
        assert restored["payload"]["event_cursor"] >= lifecycle["sequence"]
        await communicator.disconnect()

    async_to_sync(run)()


def test_contract_types_include_lifecycle():
    assert "dashboard.snapshot" in EVENT_TYPES
    assert "incident.acknowledged" in EVENT_TYPES
    assert "incident.resolved" in EVENT_TYPES
