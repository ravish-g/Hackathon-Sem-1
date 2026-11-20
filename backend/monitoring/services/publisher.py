"""Durable event sequence and Channels publisher for dashboard events."""

from __future__ import annotations

import threading
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Max

from backend.monitoring.contracts import event_envelope
from backend.monitoring.interfaces import EventPublisher
from backend.monitoring.models import EventLogEntry, Feed


DASHBOARD_GROUP = "dashboard"
ROUTINE_METRIC_TYPES = frozenset({
    "feed.metrics_updated",
})
INCIDENT_TYPES = frozenset({
    "incident.created",
    "incident.acknowledged",
    "incident.updated",
    "incident.resolved",
})


class ChannelsEventPublisher:
    """Persists and broadcasts envelopes with monotonic, gap-visible sequences."""

    def __init__(self, coalesce_seconds: float = 0.5) -> None:
        self.coalesce_seconds = coalesce_seconds
        self._lock = threading.RLock()
        self._pending_metrics: dict[str, dict[str, Any]] = {}
        self._timer: threading.Timer | None = None

    def next_sequence(self) -> int:
        with transaction.atomic():
            maximum = EventLogEntry.objects.aggregate(value=Max("sequence"))["value"]
            return (maximum or 0) + 1

    def publish(
        self,
        event_type: str,
        payload: dict,
        feed_id: str | None = None,
    ) -> dict:
        if event_type in ROUTINE_METRIC_TYPES:
            key = feed_id or "__dashboard__"
            with self._lock:
                self._pending_metrics[key] = {
                    "event_type": event_type,
                    "payload": payload,
                    "feed_id": feed_id,
                }
                if self._timer is None:
                    self._timer = threading.Timer(
                        self.coalesce_seconds,
                        self._flush_metrics,
                    )
                    self._timer.daemon = True
                    self._timer.start()
            # A coalesced metric has no envelope until the coalesce window expires.
            return {"coalesced": True}

        return self._publish_now(event_type, payload, feed_id)

    def flush(self) -> None:
        """Publish pending routine metrics immediately (tests and controlled shutdown)."""
        self._flush_metrics()

    def _flush_metrics(self) -> None:
        with self._lock:
            pending = list(self._pending_metrics.values())
            self._pending_metrics.clear()
            if self._timer is not None:
                self._timer.cancel()
            self._timer = None

        for item in pending:
            self._publish_now(
                item["event_type"],
                item["payload"],
                item["feed_id"],
            )

    def _publish_now(
        self,
        event_type: str,
        payload: dict,
        feed_id: str | None = None,
    ) -> dict:
        # Incident lifecycle events flush routine updates first and are never
        # replaced or discarded by the metric coalescer.
        if event_type in INCIDENT_TYPES:
            self._flush_metrics()

        with self._lock:
            sequence = self.next_sequence()
            event_id = self._persist_event(
                event_type,
                payload,
                feed_id,
                sequence,
            )
            envelope = event_envelope(
                event_type,
                sequence,
                payload,
                feed_id=feed_id,
                event_id=event_id,
            )
            channel_layer = get_channel_layer()
            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(
                    DASHBOARD_GROUP,
                    {"type": "dashboard.event", "event": envelope},
                )
            return envelope

    def _persist_event(
        self,
        event_type: str,
        payload: dict,
        feed_id: str | None,
        sequence: int,
    ) -> str:
        feed = None
        if feed_id:
            feed = Feed.objects.filter(pk=feed_id).first()

        incident_id = payload.get("incident_id")
        severity = payload.get("severity")
        if severity is None:
            severity = "critical" if event_type in INCIDENT_TYPES else "unknown"
        category = "incident" if event_type in INCIDENT_TYPES else "system"
        if event_type.startswith("alert"):
            category = "alert"
        elif event_type.startswith("feed"):
            category = "feed"

        event_log = EventLogEntry(
            feed=feed,
            feed_name=feed.name if feed else "",
            category=category,
            severity=str(severity),
            event_type=event_type,
            message=str(payload.get("message", event_type)),
            delta_percent=payload.get("delta_percent"),
            density_people_per_m2=payload.get("density_people_per_m2"),
            people_count=payload.get("people_count"),
            incident_id=incident_id,
            state=payload.get("state"),
            sequence=sequence,
        )
        event_log.save(force_insert=True)
        return str(event_log.event_id)


event_publisher = ChannelsEventPublisher()


def get_event_publisher() -> ChannelsEventPublisher:
    return event_publisher


__all__ = [
    "EventPublisher",
    "ChannelsEventPublisher",
    "DASHBOARD_GROUP",
    "event_publisher",
    "get_event_publisher",
]

