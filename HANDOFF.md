# H7 Crowd Density Prototype - Handoff

This document records the `dockerize-app` branch at `02aee31`, before integration
with `remove-invalid-stats`. Its setup paths and pending tasks describe that
snapshot. For the merged application, use the [current setup and deployment
instructions](README.md) and [recorded replay and stream measurements](benchmarks/README.md).

## 1. Purpose

This repository contains a Django/Channels crowd-density prototype for Code Fuzion 2026 H7.

The prototype supports:

- Django REST APIs for feeds, uploads, calibration and incidents.
- Django Channels WebSocket dashboard snapshots and events.
- Browser playback for uploaded MP4 videos.
- Ultralytics YOLO person detection.
- Supervision and tracking utilities.
- A Docker web, PostgreSQL, Redis and vision container topology.
- A single-origin Django-hosted frontend.
- Automatic processing jobs for uploaded MP4 files.
- Looping replay processing for uploaded videos.
- 30-minute metric staleness.

This is a prototype, not a certified crowd-safety system.

Do not claim count accuracy, density accuracy, risk prediction accuracy or 5+ FPS performance
unless a labeled ground-truth run or benchmark is attached.

## 2. Current Repository

Primary repository:

```text
C:\Users\aarti\OneDrive\Desktop\qbit\Hackathon-Sem-1
```

Isolated UI/replay worktree:

```text
C:\Users\aarti\OneDrive\Desktop\h7-docker-work
```

The Docker work did not modify `main` or the frontend branch.

## 3. Branch State

### `dockerize-app`

Purpose:

- PostgreSQL, Redis, Django web and YOLO vision containers.
- Automatic vision jobs for uploaded videos.
- Docker Compose startup.

Latest verified commit before isolated follow-up work:

```text
f231d3e feat: dockerize web and automatic vision supervision
```

### `remove-invalid-stats`

Purpose:

- Hide invalid/stale measurements in the UI.
- Restore unvalidated people counts with explicit labels.
- Show every backend-returned metric that is available.
- Loop uploaded replay videos.
- Apply a 30-minute frontend and backend staleness threshold.

Latest commit:

```text
60a5f8e feat: loop replay and use 30-minute staleness
```

This branch is represented by the isolated worktree at
`C:\Users\aarti\OneDrive\Desktop\h7-docker-work`.

The isolated worktree should not be merged into `dockerize-app` or `main`
without reviewing the exact UI and replay differences.

## 4. Verified Working Behavior

The following behavior was verified during the session:

- Docker Desktop and WSL2 were installed and Ubuntu was created.
- Docker Engine was started successfully.
- Docker Compose started:
  - PostgreSQL
  - Redis
  - Django/Daphne web container
  - Vision container
- Django health endpoint returned `200`.
- Frontend returned `200` at `http://127.0.0.1:8000/`.
- Dashboard REST returned `200`.
- Dashboard WebSocket returned a `dashboard.snapshot`.
- MP4 upload returned a feed and preview URL.
- Uploaded MP4 was served from `/media/feeds/`.
- Upload created a persisted `VisionJob`.
- Vision container loaded a shared YOLO runtime.
- A real MP4 produced persisted people-count telemetry.
- Real inference produced observed FPS in roughly the 16–25 FPS range in development runs.
- Uncalibrated real detections were persisted with:
  - people count
  - measured FPS
  - timestamp
  - `is_valid=false`
  - `calibration_invalid`
- Replay processing was changed to loop uploaded MP4 files.
- Replay staleness was changed to 1800 seconds/30 minutes.
- Automated test suite reached 33 passing tests after the replay/stale changes.

These are implementation and runtime observations, not performance guarantees.

## 5. Not Verified

The following items must not be reported as achieved:

- People-count accuracy under 20% error.
- People/m² density accuracy.
- Risk-prediction accuracy.
- Official 5+ processed FPS requirement on a labeled two-feed benchmark.
- Two simultaneous real MP4 feeds.
- Counting error from manual ground truth.
- A strong model fine-tuned for the campus crowd dataset.
- Incident sustained-recovery validation against real footage.
- Public deployment readiness.

No H7 target should be described as passed without saved benchmark evidence.

## 6. Architecture

```text
Browser
  -> Django templates/static frontend
  -> Django REST/WebSocket
  -> PostgreSQL
  -> Redis Channels

Uploaded MP4
  -> Media volume
  -> VisionJob
  -> Vision container
  -> Shared YOLO runtime
  -> OpenCV + Supervision processing
  -> TelemetryPublisher
  -> Worker ingest API
  -> Django telemetry/risk services
  -> Dashboard REST/WebSocket
```

The backend owns:

- Feed state.
- Calibration state.
- Metric ingestion.
- Severity and incident lifecycle.
- Persistent incident acknowledgement/recovery policy.
- Event sequence and snapshot truth.

The frontend only renders backend state.

## 7. Important Models

Backend application:

```text
backend/monitoring/models.py
```

Core models:

- `Feed`
- `Zone`
- `Calibration`
- `FeedMetric`
- `CriticalIncident`
- `EventLogEntry`
- `VisionJob`

`VisionJob` stores:

- pending/running/completed/error state
- source media path
- worker ID
- start/completion/heartbeat timestamps
- error message
- configuration version

## 8. Vision Runtime

Primary files:

```text
vision/detector.py
vision/sources.py
vision/scheduler.py
vision/tracking.py
vision/zones.py
vision/calibration.py
vision/metrics.py
vision/publisher.py
backend/monitoring/management/commands/run_vision.py
```

The supervisor loads one shared YOLO runtime, polls for feed jobs and processes uploaded MP4 sources.

Current replay behavior:

- MP4 capture restarts at EOF.
- Replay jobs remain active while looping.
- Metrics continue publishing.
- Stale status is controlled by metric age.

Current replay changes exist in `remove-invalid-stats`/isolated worktree,
not yet merged into `dockerize-app`.

## 9. Start Docker

Run from the repository:

```powershell
cd C:\Users\aarti\OneDrive\Desktop\qbit\Hackathon-Sem-1
git switch dockerize-app
git pull origin dockerize-app
docker compose -f deploy/docker-compose.yml up --build -d
```

Open:

```text
http://127.0.0.1:8000/
```

Verify:

```powershell
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs --tail=100 vision
docker compose -f deploy/docker-compose.yml logs --tail=100 web
```

Health endpoint:

```text
http://127.0.0.1:8000/health/
```

Dashboard endpoint:

```text
http://127.0.0.1:8000/api/dashboard/
```

WebSocket:

```text
ws://127.0.0.1:8000/ws/dashboard/
```

Stop:

```powershell
docker compose -f deploy/docker-compose.yml down
```

Remove data only if explicitly requested:

```powershell
docker compose -f deploy/docker-compose.yml down -v
```

## 10. Run the Isolated Replay/UI Branch

Build it from the separate worktree:

```powershell
cd C:\Users\aarti\OneDrive\Desktop\h7-docker-work
git switch remove-invalid-stats
git pull origin remove-invalid-stats
docker compose -f deploy/docker-compose.yml up --build -d
```

Do not build from the isolated worktree unless the UI/replay branch is intended
to replace the current Docker prototype. The worktree contains live-loop and
full-metric UI changes not yet merged into `dockerize-app`.

## 11. Docker Engine Recovery

If Docker cannot connect:

```powershell
& "C:\Program Files\Docker\Docker\DockerCli.exe" -SwitchLinuxEngine
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
docker info
docker ps
```

If WSL is missing or stopped:

```powershell
wsl --status
wsl --update
wsl --shutdown
wsl -l -v
```

WSL feature activation may require elevated Windows setup and a reboot.

## 12. Database

PostgreSQL database:

```text
crowd_fuzion
```

Docker volume:

```text
deploy_postgres_data
```

Media Docker volume:

```text
deploy_media_data
```

Open PostgreSQL shell:

```powershell
docker compose -f deploy/docker-compose.yml exec db psql -U crowd_fuzion -d crowd_fuzion
```

Useful table queries:

```sql
\dt
SELECT * FROM monitoring_feed;
SELECT * FROM monitoring_visionjob;
SELECT * FROM monitoring_feedmetric ORDER BY received_at DESC LIMIT 20;
```

Actual table names should be confirmed with `\dt`.

## 13. Upload and Vision Test

Upload through the frontend:

1. Open `http://127.0.0.1:8000/`.
2. Select Add Feed.
3. Choose Video File.
4. Upload an MP4.
5. Wait for the vision supervisor.
6. Verify that people, FPS and latest-sample fields update.

Do not confuse browser preview with inference.

The UI should present:

- Real person estimate.
- `Unvalidated` for uncalibrated measurements.
- FPS as measured processing FPS.
- Latest sample timestamp.
- Density as unavailable until calibration.

## 14. Incident Policy

Acknowledgement:

- Silences the alarm.
- Releases navigation restrictions if no other critical incidents remain unacknowledged.
- Does not resolve, unpin or downgrade an incident.

Resolution:

- Only backend-confirmed sustained recovery may resolve an incident.
- Offline/stale/invalid/uncalibrated telemetry is not recovery.

## 15. Next Steps

Priority order:

1. Merge the isolated replay/UI branch only after review.
2. Replace current calibration UI assumptions with a tested camera calibration workflow.
3. Persist and expose valid density measurements.
4. Collect and label campus-style MP4 footage.
5. Fine-tune a stronger YOLO person model.
6. Add or harden tracking across overlapping and occluded people.
7. Perform manual ground-truth counting.
8. Measure:
   - count mean absolute error
   - percentage count error
   - processed FPS
   - inference latency
   - simultaneous two-feed throughput
9. Benchmark several resolutions and confidence thresholds.
10. Add replay-loop, stale and WebSocket integration tests.
11. Add PostgreSQL/Redis production settings and secrets management.
12. Add TLS/reverse proxy deployment if public access is required.
13. Add real alert thresholds and sustained-recovery validation.
14. Add calibration and benchmark results to documentation.

## 16. Accuracy Narrative

Safe presentation language:

> The prototype demonstrates real YOLO inference on video and reports live person detections. Accuracy has not yet been validated against labeled ground truth, density is not claimed until calibration is complete, and count/FPS targets remain to be benchmarked.

Do not say:

- The model is accurate.
- The count is confirmed.
- The crowd is safely below/above a threshold.
- 5+ FPS has passed unless a saved benchmark proves it.
- People/m² is valid for an uncalibrated feed.

## 17. Tests

Run locally:

```powershell
cd C:\Users\aarti\OneDrive\Desktop\qbit\Hackathon-Sem-1
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest
```

Docker:

```powershell
docker compose -f deploy/docker-compose.yml config
docker compose -f deploy/docker-compose.yml up --build -d
docker compose -f deploy/docker-compose.yml ps
```

No benchmark result should be replaced with mocked success.

## 18. Outstanding Risks

- Accuracy is low-confidence and unbenchmarked.
- Density is not valid without calibration.
- Replay loop behavior is implemented in the isolated branch only until merged.
- YOLO memory/load behavior for two feeds is unmeasured.
- No public HTTPS/TLS deployment is configured.
- Docker engine availability depends on Windows WSL2/virtualization support.
- The database currently reflects development data and Docker volumes.
- The media and database volumes contain prototype state.
- Frontend and branch ownership must be reconciled before merge.

## 19. Final Handoff Statement

The next agent should prioritize:

1. Merge and test `remove-invalid-stats` only after UI review.
2. Confirm replay-loop behavior in the PostgreSQL/Docker database.
3. Add calibration-backed density to the live page.
4. Create labeled benchmark footage.
5. Measure and document accuracy/FPS.
6. Replace prototype thresholds and claims with measured evidence.
