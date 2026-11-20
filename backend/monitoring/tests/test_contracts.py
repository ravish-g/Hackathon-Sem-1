import pytest

from backend.monitoring.contracts import EVENT_TYPES, event_envelope


def test_event_envelope_has_shared_fields():
    event = event_envelope("system.heartbeat", 1, {"healthy": True})
    assert set(event) == {"type", "event_id", "sequence", "timestamp", "feed_id", "payload"}
    assert event["feed_id"] is None


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValueError):
        event_envelope("unknown.event", 1, {})


def test_required_event_types_are_declared():
    assert "incident.acknowledged" in EVENT_TYPES
    assert "incident.resolved" in EVENT_TYPES

