# WebSocket integration checklist

## Contract

- [ ] Session-authenticated browser connects to `wss://<host>/ws/dashboard/`.
- [ ] Anonymous or unauthenticated connections are closed with `4403`.
- [ ] Every message is one of the documented event envelopes:
  `dashboard.snapshot`, `feed.added`, `feed.removed`, `feed.status_changed`,
  `feed.metrics_updated`, `feed.calibration_changed`, `alert.created`,
  `alert.updated`, `incident.created`, `incident.acknowledged`,
  `incident.updated`, `incident.resolved`, or `system.heartbeat`.
- [ ] Envelope fields are `type`, `event_id`, `sequence`, `timestamp`,
  `feed_id`, and `payload`.
- [ ] `sequence` is a positive monotonic database-backed cursor.
- [ ] A client reconnect sends `snapshot` or `resync` and deduplicates by
  `event_id`/`sequence`.

## Incident truth

- [ ] Refresh/reconnect restores every active incident from `CriticalIncident`,
  including `acknowledged=true`, state, severity and feed ID.
- [ ] `incident.acknowledged` never changes `state` or `severity`.
- [ ] Only `incident.resolved` removes an incident from the active snapshot.
- [ ] Metric coalescing does not reorder or discard incident lifecycle events.

## Deployment

- [ ] Production sets `ALLOWED_HOSTS` and uses HTTPS/WSS.
- [ ] Operator authentication is enforced by Django session middleware.
- [ ] The in-memory Channels layer is used only for one ASGI process.
- [ ] Separate or horizontally scaled ASGI processes use the Redis channel layer
  with the same `dashboard` group and a shared database.
- [ ] Health/heartbeat clients tolerate missed heartbeats and do not infer
  incident recovery from a disconnect.
