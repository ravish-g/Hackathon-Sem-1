"""Shared, versioned names and envelope helpers for all backend workstreams."""

from datetime import datetime, timezone
from uuid import uuid4

EVENT_TYPES = (
    "dashboard.snapshot",
    "feed.added",
    "feed.removed",
    "feed.status_changed",
    "feed.metrics_updated",
    "feed.calibration_changed",
    "alert.created",
    "alert.updated",
    "incident.created",
    "incident.acknowledged",
    "incident.updated",
    "incident.resolved",
    "system.heartbeat",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def event_envelope(event_type, sequence, payload, feed_id=None, event_id=None):
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")
    envelope = {
        "type": event_type,
        "event_id": event_id or str(uuid4()),
        "sequence": sequence,
        "timestamp": utc_now_iso(),
        "feed_id": feed_id,
        "payload": payload,
    }
    return envelope

