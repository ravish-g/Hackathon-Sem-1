# Docker Rewrite and Production Handoff

## Status

- Handoff branch: `dockerize-app`
- Source branch: `host-backend`
- Source commit at branch creation: `db3099a`
- Docker is not currently installed or available in this execution environment.
- Docker files must be validated on a machine with Docker Engine/Desktop before public deployment.
- Do not claim Docker, two-feed inference, FPS or count accuracy is production-ready until startup and benchmark tests are run.

## Goal

Replace manual local startup and split frontend/backend operation with a single reproducible Docker deployment.

The target application will provide:

- A Django/Channels application on one HTTP origin.
- Django templates and static assets served by Django.
- PostgreSQL for persistent application data.
- Redis for Channels and future cross-process coordination.
- A bounded vision supervisor that starts and tracks configured feeds.
- Uploaded MP4 playback and automatic analysis scheduling.
- REST compatibility endpoints and WebSocket dashboard events.
- One-command startup for local development.
- Separate web and vision containers in production-oriented Compose topology.

## Current State

The existing implementation includes:

- Django foundation and integrated REST APIs.
- Django Channels WebSocket dashboard.
- Feed, zone, calibration, metric and incident models.
- YOLO person detection and Supervision utilities.
- Two-source vision CLI.
- Frontend assets copied into `frontend/dist/`.
- A combined Django-origin prototype on `host-backend`.

Known problems:

- Upload registration does not automatically start vision.
- The vision CLI requires an exact manual command and exact feed IDs.
- Source files and calibration are not managed as a complete persisted job.
- YOLO may consume too much memory for two processes or devices.
- Local SQLite and the in-memory channel layer are not production topology.
- Current settings do not provide PostgreSQL or Redis dependencies.
- The frontend bundle still contains demo fixture code even though startup is live-only.
- There is no container health policy or graceful worker lifecycle.
- Existing architecture is the result of multiple workstreams and can contain duplicate compatibility logic.

## Target Architecture

```text
Browser
  |
  | HTTP / WebSocket
  v
Django + Daphne
  |-- templates and static assets
  |-- REST compatibility API
  |-- session authentication
  |-- upload and calibration
  |-- dashboard snapshot
  |-- Django Channels
  |
  +--> PostgreSQL
  +--> Redis
  |
  +--> shared media volume
             ^
             |
Vision Supervisor
  |-- persistent feed scan
  |-- bounded source readers
  |-- shared YOLO runtime
  |-- tracking and zones
  |-- density/risk telemetry
  +--> Django ingest endpoint
```

## Container Topology

### `db`

- PostgreSQL 16.
- Persistent named volume.
- Django database settings from environment variables.

### `redis`

- Redis 7.
- Persistent Channels layer for the web service.
- No Redis requirement for the application database.

### `web`

- Django migrations.
- Daphne/ASGI.
- Django templates and static assets.
- Uploaded media mounted or served through persistent storage.
- Must become healthy through `/health/`.

### `vision`

- Python/YOLO worker.
- Shared media volume read access.
- Starts with the Django ingest URL and worker credential.
- Queries feed configuration from Django or receives durable jobs.
- Must be unprivileged, bounded and observable.

### `nginx` (optional for later)

- Static/media proxy.
- TLS termination.
- Not required for the first Docker Compose prototype.

## Recommended Django Layout

Use conventional Django applications rather than distributing UI code in a worktree:

```text
backend/
  manage.py
  config/
    settings/base.py
    settings/local.py
    settings/docker.py
    urls.py
    asgi.py
    wsgi.py
    routing.py
  monitoring/
    templates/monitoring/
    static/monitoring/
    forms.py
    models.py
    views.py
    urls.py
    consumers.py
    selectors.py
    services/
  worker_api/
  vision/
deploy/
  Dockerfile.web
  Dockerfile.vision
  docker-compose.yml
  docker-compose.test.yml
  .dockerignore
.env.example
```

The existing `backend/` and `vision/` code is mostly reusable. Consolidate rather than rewrite correct domain logic.

## Required Reuse

Reuse existing implementations after hardening:

- `Feed`, `Zone`, `Calibration`, `FeedMetric`, `CriticalIncident`, `EventLogEntry`.
- Camera homography and area calculation.
- `TelemetryProcessor`.
- `RiskAssessor`.
- `CriticalIncidentEngine`.
- `ChannelsEventPublisher`.
- `YoloPersonDetector`.
- `SourceReader`.
- `count_zone_occupants`.
- Existing WebSocket envelope and feed snapshot shape.

Do not duplicate feed or incident state in templates or JavaScript.

## Required Reductions

Remove or gate:

- Frontend demo fixture snapshot.
- Demo incident and recovery controls.
- Separate frontend server as normal startup.
- Per-feed YOLO model instantiation.
- Manual `--feed` invocation for uploaded feeds.
- Browser-origin CORS compatibility middleware after one-origin hosting.
- SQLite and in-memory Channels defaults from Docker settings.
- Worker token in browser JavaScript or public responses.

## Data Model Changes

Add a durable vision job model or equivalent state machine.

Minimum fields:

- `feed`
- `source_type`
- `source_path`
- `requested_state`
- `runtime_state`
- `worker_id`
- `started_at`
- `last_heartbeat_at`
- `last_frame_at`
- `error_message`
- `configuration_version`
- `sequence`

Use states:

```text
pending
starting
running
paused
stale
offline
error
completed
```

Uploaded MP4 replay jobs become `completed` at end of file.
Live network/webcam jobs restart according to policy.
Offline or stale state must never resolve an incident.

## Vision Supervisor Requirements

- Load one YOLO runtime per vision container.
- Create one capture processor per feed.
- Maintain bounded queues.
- Drop stale frames under CPU overload.
- Limit concurrent feeds to the measured model/device capacity.
- Recover source readers with bounded backoff.
- Publish heartbeat and metrics to Django.
- Mark replay end explicitly.
- Never invent people counts.
- Expose graceful stop handling.
- Never hold a YOLO model in each Django process.

## Django Startup Requirements

Create management commands:

- `python manage.py migrate`
- `python manage.py collectstatic --noinput`
- `python manage.py run_h7` for local orchestration
- `python manage.py vision_supervisor` for vision container

The Docker web command should:

1. Wait for PostgreSQL.
2. Run migrations.
3. Collect static assets.
4. Start Daphne.

The Docker vision command should:

1. Wait for Django health.
2. Authenticate with an internal worker secret.
3. Start configured feed jobs.
4. Heartbeat and reconnect.

## Environment Variables

Required:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DATABASE_URL
REDIS_URL
WORKER_INGEST_TOKEN
CRITICAL_RECOVERY_SECONDS
METRIC_STALE_SECONDS
MEDIA_ROOT
VISION_MODEL
VISION_DEVICE
VISION_CONFIDENCE
VISION_MAX_FEEDS
```

Use Docker secrets or environment injection for deployment credentials.
Never commit `.env`, worker credentials or private source URLs.

## Compose Contract

Initial implementation:

```text
docker compose up --build
docker compose ps
docker compose logs -f web
docker compose logs -f vision
docker compose down
```

Target URL:

```text
http://localhost:8000/
```

No port `5173` frontend service is needed.

## Upload and Vision Integration

On successful `FeedUploadView`:

1. Store the file in the media volume.
2. Create or update the `Feed`.
3. Set `source_type=upload`.
4. Set `preview_url` to `/media/feeds/<name>`.
5. Set `stream_state=replay`.
6. Create `pending` vision job.
7. Publish a feed event.

The vision supervisor:

1. Reads pending jobs.
2. Resolves the media file.
3. Updates job to `starting`, then `running`.
4. Processes frames.
5. Publishes metrics.
6. Updates replay completion.
7. Never starts automatically from browser JavaScript.

## Web Template Contract

Django views must own:

- Dashboard page.
- Feed list.
- Feed detail.
- Upload form.
- Calibration form.
- Incident acknowledgement.
- Event log.
- Health/status diagnostics.

Templates:

```text
monitoring/templates/monitoring/base.html
monitoring/templates/monitoring/dashboard.html
monitoring/templates/monitoring/feed_detail.html
monitoring/templates/monitoring/feed_form.html
monitoring/templates/monitoring/calibration_form.html
monitoring/templates/monitoring/incidents.html
monitoring/templates/monitoring/partials/feed_card.html
monitoring/templates/monitoring/partials/activity_log.html
```

Keep JavaScript small and use WebSocket events only for realtime updates.
Do not send worker credentials from template or JavaScript code.

## Testing and Acceptance

Minimum automated tests:

- Django system check.
- Migration check.
- `/health/` returns expected JSON.
- Upload accepts valid MP4 and creates a feed/job.
- Invalid file and MIME type are rejected.
- Calibration creates homography and area.
- Duplicate telemetry is idempotent.
- Acknowledgement does not resolve an incident.
- Sustained recovery resolves only after policy window.
- Offline/stale data does not resolve incidents.
- WebSocket reconnect restores dashboard snapshot.
- Vision supervisor can start and stop two sources.
- Docker web, Redis, Postgre and vision containers become healthy.

Benchmark evidence:

- Report processed FPS, not browser playback FPS.
- Report actual count error on labeled footage.
- Report mean and peak inference latency.
- Report concurrent feed configuration.
- Report device, model and resolution.
- Mark no-video/labeled-footage gaps as unmeasured.

## Deployment Constraints

- Keep secrets out of source control.
- Add PostgreSQL and Redis before public deployment.
- Use persistent volumes for PostgreSQL and media.
- Add TLS and private worker-ingest authorization.
- Use a reverse proxy for production static/media handling.
- Do not expose worker-ingest endpoints publicly without authentication and network policy.
- Do not claim public safety certification.

## Implementation Order

1. Add Docker and Compose baseline.
2. Move settings to environment-based PostgreSQL/Redis configuration.
3. Add healthchecks and migration startup.
4. Add Django templates and live-only views.
5. Add persisted vision jobs.
6. Add vision supervisor command/container.
7. Bind upload success to pending jobs.
8. Replace in-process demo behavior completely.
9. Add container integration tests.
10. Run and measure real two-feed MP4 processing.

## Known Blocker

Docker could not be invoked in this execution environment because Docker CLI was unavailable. After code changes, validation must occur on a host with Docker Engine or Docker Desktop.

## Handoff Checklist

- [ ] Docker branch exists and is pushed.
- [ ] Handoff document is in the repository.
- [ ] `.env.example` contains Docker variables.
- [ ] Dockerfiles and Compose file are present.
- [ ] Web container passes `/health/`.
- [ ] Database migrations run automatically.
- [ ] Redis Channels layer works.
- [ ] Uploaded MP4 creates a vision job.
- [ ] Vision container starts configured jobs.
- [ ] Shared YOLO model is loaded once.
- [ ] Dashboard receives real metrics.
- [ ] Incident acknowledgement remains unresolved.
- [ ] Sustained recovery policy is tested.
- [ ] Real benchmark data is reported separately.
