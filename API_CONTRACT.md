# Backend API and event contract

Status: foundation contract. Feature workstreams must preserve these names and invariants.

## Ownership

| Area | Owner branch | Owned paths |
|---|---|---|
| REST, serializers, persistence and worker ingestion | `build-apis` | `backend/monitoring/views.py`, `serializers.py`, `selectors.py`, `urls.py`, `backend/worker_api/**` |
| Vision worker and benchmarks | `process-feeds` | `vision/**`, `benchmarks/**` |
| Risk, telemetry and incident lifecycle | `predict-risk` | `backend/monitoring/services/risk.py`, `incidents.py`, `telemetry.py`, `calibration.py` |
| Channels and event publishing | `stream-events` | `backend/monitoring/consumers.py`, `backend/config/routing.py`, `backend/monitoring/services/publisher.py` |

Models and this contract are shared foundations. Changes require coordination and a migration.

## REST paths

The public paths are `/api/dashboard/`, `/api/feeds/`, `/api/feeds/upload/`,
`/api/feeds/{feed_id}/`, `/api/feeds/{feed_id}/calibration/`,
`/api/events/?cursor=...`, `/api/incidents/active/`,
`/api/incidents/{incident_id}/`, and
`/api/incidents/{incident_id}/acknowledge/`.

Private worker paths are `/internal/telemetry/` and
`/internal/worker-heartbeat/`; they require a worker-only credential and never
return that credential.

The foundation exposes only `/health/` and honest `501 NOT_IMPLEMENTED` API
stubs. It does not claim feature endpoints are implemented.

## Incident invariant

`acknowledged` and `state` are independent. Acknowledgement silences an
incident alarm only; it never changes `state`, severity, pin eligibility or
monitoring. Only a backend-confirmed sustained recovery may set
`state=resolved` and `resolved_at`. Offline, stale, invalid or uncalibrated
telemetry cannot count as recovery. Active incidents must be included in the
dashboard and active-incident snapshots after refresh and reconnect.

## Dashboard response shape

```json
{
  "server_time": "UTC ISO-8601",
  "event_cursor": 0,
  "feeds": [],
  "active_incidents": []
}
```

Feed and incident fields are defined by the canonical models and the
frontend-facing specification. Illustrative metrics are never production
defaults.

## WebSocket envelope

Endpoint: `/ws/dashboard/`.

Every event uses:

```json
{
  "type": "incident.created",
  "event_id": "stable-id",
  "sequence": 1,
  "timestamp": "UTC ISO-8601",
  "feed_id": "stable-feed-id-or-null",
  "payload": {}
}
```

Allowed event types are declared in `backend/monitoring/contracts.py`.
Incident lifecycle events must not be dropped when routine metric events are
coalesced. Reconnects restore truth from durable REST/database state.

