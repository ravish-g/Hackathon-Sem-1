# Antropy

A responsive campus-fest control room built with browser-native HTML, CSS and JavaScript. The four default camera views are generated still images with illustrative annotations and sample measurements.

## Run locally

From this directory, run `python -m http.server 8000 --bind 127.0.0.1 --directory dist` and open `http://localhost:8000`. The frontend has no build step or runtime package dependencies.

## Demonstrate the volunteer workflow

1. Open Main Gate to inspect its zone measurements, density history and critical incident.
2. Acknowledge the warning. Visit Food Court to see the estimated threshold crossing. Main Gate stays pinned.
3. Open Diagnostics and select **Simulate recovery** to deliver a demo recovery event. **Simulate incident** starts the next sample incident.
4. Open **Add feed** to preview a local video, webcam, or browser-playable network video. In its monitor, choose **Calibrate zone**, mark a measured ground rectangle in perimeter order, and enter its width and length in metres. Local sources show pending measurements until connected to analysis.

## Connect the processing worker

Open the OP operator menu, select **Live Django backend**, and enter the origin of the team's Django service. This repository contains the frontend and its adapter. The YOLO/OpenCV worker and Django service are external dependencies for live analysis. For session-cookie authentication, serving the frontend on the same origin as the API allows it to forward Django's CSRF token on write operations. A separate HTTPS origin needs matching credentialed CORS, CSRF and media configuration.

- `GET /api/dashboard/` returns `feeds`, `incidents` and `events` arrays, with optional `sequence` and `stale_timeout_seconds`. If the incident list is absent, the adapter fetches `GET /api/incidents/active/`.
- `/ws/dashboard/` carries the event names in the frontend brief. Provide an ordered sequence and stable event IDs. A sequence gap or lost socket triggers reconnection and snapshot reconciliation.
- Feed updates carry the stable `feed_id` and a `metrics` or `feed` object. Supply ground-zone counts, calibrated density, area, trend, growth in people/m²/minute, estimated crossing time, measured inference FPS, ISO timestamps, and optional evaluated `count_error_percent`. The interface accepts annotated image/MJPEG previews and browser-playable video URLs. Transcode RTSP on the worker.
- Feed setup uses `POST /api/feeds/` for network or worker-camera sources and multipart `POST /api/feeds/upload/` for files. Return the newly created feed. A webcam in demo mode uses a browser-local camera. In live mode select a camera index on the processing worker.
- `PUT /api/feeds/{id}/calibration/` accepts four normalized top-left-origin reference points, measured width and length, and ground area. Return a validated feed or confirmation. Supply fresh metrics for the new zone.
- `POST /api/incidents/{id}/acknowledge/` returns confirmed acknowledgement. Active incidents are removed from the dock on a resolved event or reconciliation with an authoritative snapshot. `DELETE /api/feeds/{id}/` removes a feed.

Count error below 20% and throughput of at least 5 processed FPS on two simultaneous feeds require evaluation of the team's vision worker on labeled footage. The demo does not supply benchmark results.
