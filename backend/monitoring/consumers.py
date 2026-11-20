"""Authorized dashboard WebSocket consumer."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.db.models import Max

from backend.monitoring.contracts import event_envelope
from backend.monitoring.models import CriticalIncident, EventLogEntry, Feed
from backend.monitoring.serializers import FeedSerializer
from backend.monitoring.services.publisher import DASHBOARD_GROUP, get_event_publisher


def _utc(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    heartbeat_task = None

    async def connect(self):
        user = self.scope.get("user")
        local_demo = settings.DEBUG and getattr(settings, "ALLOW_LOCAL_ANONYMOUS", False)
        if (user is None or not getattr(user, "is_authenticated", False)) and not local_demo:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(DASHBOARD_GROUP, self.channel_name)
        await self.accept()
        await self.send_json(await self._snapshot())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, code):
        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
        await self.channel_layer.group_discard(DASHBOARD_GROUP, self.channel_name)

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(30)
                await database_sync_to_async(
                    get_event_publisher().publish
                )(
                    "system.heartbeat",
                    {"healthy": True},
                )
        except asyncio.CancelledError:
            return

    async def receive_json(self, content, **kwargs):
        message_type = content.get("type")
        if message_type in ("snapshot", "resync", "reconnect"):
            await self.send_json(await self._snapshot())
            return
        if message_type == "ping":
            cursor = await self._event_cursor()
            await self.send_json(
                event_envelope(
                    "system.heartbeat",
                    cursor,
                    {"healthy": True},
                )
            )
            return
        if message_type == "subscribe":
            await self.send_json(await self._snapshot())
            return
        if message_type == "cursor":
            cursor = await self._event_cursor()
            client_cursor = content.get("cursor")
            if isinstance(client_cursor, int) and client_cursor < cursor:
                await self.send_json(await self._snapshot())

    async def dashboard_event(self, event):
        await self.send_json(event["event"])

    @database_sync_to_async
    def _event_cursor(self) -> int:
        return EventLogEntry.objects.aggregate(value=Max("sequence"))["value"] or 0

    @database_sync_to_async
    def _snapshot(self) -> dict:
        cursor = EventLogEntry.objects.aggregate(value=Max("sequence"))["value"] or 0
        feeds = []
        for feed in Feed.objects.all().prefetch_related("metrics"):
            feed_data = FeedSerializer(feed).data
            feed_data["latest_metrics"] = feed_data.get("latest_metric")
            feeds.append(feed_data)

        active = []
        for incident in CriticalIncident.objects.filter(state="active").select_related(
            "feed",
            "zone",
        ):
            active.append({
                "incident_id": str(incident.incident_id),
                "feed_id": str(incident.feed_id),
                "zone_id": str(incident.zone_id) if incident.zone_id else None,
                "state": incident.state,
                "severity": incident.severity,
                "acknowledged": incident.acknowledged,
                "acknowledged_at": _utc(incident.acknowledged_at),
                "acknowledged_by": incident.acknowledged_by,
                "started_at": _utc(incident.started_at),
                "last_updated_at": _utc(incident.last_updated_at),
                "resolved_at": _utc(incident.resolved_at),
                "reason": incident.reason,
                "latest_metrics": incident.latest_metrics,
                "recovery_started_at": _utc(incident.recovery_started_at),
                "policy_version": incident.policy_version,
            })

        payload = {
            "server_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event_cursor": cursor,
            "feeds": feeds,
            "active_incidents": active,
        }
        return event_envelope(
            "dashboard.snapshot",
            cursor,
            payload,
        )
