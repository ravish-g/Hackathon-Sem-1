  # BACK-END ARCHITECTURE & INTEGRATION BRIEF
## Code Fuzion 2026 · H7 — Crowd Density Alert for Campus Fests

**Document type:** First-iteration backend engineering specification and agent handoff  
**Version:** 1.0 · 20 November 2026  
**Status:** Proposed design — not a claim that any endpoint, model, worker, or deployment already exists  
**Intended handoff:** Backend developer / Django and computer-vision coding agent  
**Primary stack:** Python · Django · Django Channels · OpenCV · YOLO · Roboflow Supervision · NumPy  
**Companion specification:** `front_end.md` (v1.2) — UI behavior, hover statistics, full-page feed routes, persistent critical dock, right-side logs  
**Source of requirements:** `Code_Fuzion_2026_Problem_Statements.pdf`, H7, plus team decisions in `front_end.md`

---

## 0. Read this first — project context and engineering mandate

### What are we building?

The team is competing in **Code Fuzion 2026**, a **24-hour college hackathon** organized by Student Organisation Vizion Forge at Lovely Professional University. Our active project is **H7 — Crowd Density Alert for Campus Fests** (Hard category).

**Problem:** Gates, food courts, entrances, narrow corridors and event queues can become overcrowded. Volunteers may realize congestion is dangerous only after a bottleneck has developed. We need a monitoring system that processes several video sources, counts visible people in defined zones, converts counts into calibrated **people per square metre**, recognizes worsening trends and alerts operators *before* configured risk criteria are breached.

Here, **crowd traffic** refers to people moving through monitored event spaces, **not vehicle traffic**. The system is a prototype **decision-support interface for volunteers and organizers**, not a certified public-safety controller.

The browser frontend shows a **risk-sorted video grid** (worst risk first) with restrained **red/orange/yellow/green card glows**, hovering reveals current feed statistics, clicking a feed opens its **full-page monitor**, and a vertical activity log stays on the right on desktop. Critical incidents produce a persistent pinned feed. **Acknowledgement only silences warning sound and removes that incident's navigation restriction; it never unpins or resolves the incident.** See `front_end.md` for exact visual requirements.

### Official hackathon acceptance criteria

Treat these as **measured engineering targets**, not marketing claims:

| H7 requirement | Backend ownership | Evidence to produce |
|---|---|---|
| **At least 2 simultaneous video feeds** on a laptop CPU or free GPU | Source readers, independent per-feed inference/tracking, scheduling | Two genuinely concurrent video inputs; per-feed processed FPS |
| **Crowd count** for each feed/zone | Detector, tracking and zone membership | Count snapshots; manual ground-truth comparison |
| **People per m²** using a **camera-calibration step** | Image-to-ground homography, calibrated zone geometry, area | Four-point calibration, known dimensions, computed area, validity flag |
| **Early warning from a trend, not just present count** | Trend analysis, prediction, configurable risk policy | Density history, growth estimate, projected crossing, alert audit trail |
| **Count error under 20% at 5+ frames per second** | Benchmark, data validation, optimization | Timed test runs, actual frame counts, ground-truth table and error calculation |

The event also uses **unseen judge-provided inputs**. All Hard problems receive an additional requirement around hour 12. Keep the pipeline, risk policy and API modular; do **not** hardcode a specific video, crowd count, zone, threshold or filename. Overall judging heavily favors hidden-test performance and code comprehension over superficial appearance.

### Team technology decisions (proposed, not implemented)

- **Django** for feeds, users, calibrations, metrics retrieval, incidents, logs and admin operations.
- **Django Channels** for WebSocket dashboard events; **Redis** channel layer when running separate worker/web processes or multiple ASGI instances.
- **YOLO** for person detection; start with a lightweight pretrained person detector and benchmark on the actual laptop. Training a new model from scratch is *not* the default hackathon plan.
- **Roboflow Supervision** for `Detections` conversion, polygon-zone utilities, annotations and counting support. It is **not a detector**.
- **Roboflow `trackers`**, e.g. `ByteTrackTracker`, for persistent track IDs if tracking improves count stability. Current Supervision versions have removed the older `sv.ByteTrack`; do not copy obsolete tutorials.
- **OpenCV and NumPy** for frame capture, perspective calibration, geometry and measurements.
- **Frontend:** browser JavaScript calling REST + WebSocket APIs, with optional browser-friendly media preview transport.
- **Deployment:** small hosted Django/ASGI application with a separate computer-vision worker on a capable laptop or hosted compute. A public dashboard URL alone does *not* imply inference is cloud-hosted.

### Non-negotiable product invariants

1. **The backend is authoritative** for calibrated density, trend, severity, incident creation, acknowledgement, resolution and all timestamps. The frontend renders these facts; it does not independently decide when a dangerous crowd is safe.
2. **Active critical** and **acknowledged critical** are still **unresolved critical**. They remain **red and globally pinned** in every frontend route.
3. **Acknowledging** a specific incident records `acknowledged_by`/`acknowledged_at`, silences that incident's browser alarm, and releases navigation restrictions only when **every active critical incident has been acknowledged**. The backend must **never** resolve or unpin as a side effect of acknowledgement.
4. **Only backend-confirmed recovery** transitions an incident to `resolved` and causes the frontend to unpin it. Recovery must be observed over sustained, valid measurements, not a single low frame.
5. **Offline, stale, corrupted, missing or uncalibrated data are never “crowd managed.”** A monitoring failure cannot automatically resolve a critical incident.
6. **Multiple simultaneous incidents are independent.** An incident must have a stable ID; frequent incoming frames cannot create a new incident on every update or repeatedly restart an acknowledged siren.
7. No fake numbers, silent sample fixtures in production state, unsupported claims of accuracy or promises that browser audio will always play.

---

## 1. System boundaries and architecture

### Responsibilities by service

| Component | Owns | Must not do |
|---|---|---|
| `vision_worker` (independent Python process) | Read input, timestamp frames, infer, track, count, calibrate, compute raw metrics, optionally annotate preview | Render web UI; directly acknowledge incidents; rely on browser route state |
| `analysis/risk` (backend domain service) | Validate observations, trend estimates, severity, hysteresis, incident lifecycle | Treat dropped frames/offline as recovered; derive density from pixel fill alone |
| `Django REST API` | Register sources, expose snapshot/history, accept calibration, authenticate operators, acknowledge incidents | Perform sustained video inference inside an HTTP request |
| `Django Channels` | Fan out recent metrics, feed status, alerts and incident events to authorized browsers | Serve as permanent incident database or make resolution decisions in WebSocket client code |
| `Database` | Persist feed definitions, zones, latest metrics, incidents, acknowledgements, event logs, calibration versions | Store every raw frame or unbounded high-frequency detections by default |
| `Media/preview adapter` | Serve a supported browser-compatible preview where enabled | Assume browsers can natively play arbitrary `rtsp://` cameras |
| Frontend | Show feeds and status, handle alert audio and navigation restrictions, create/acknowledge through API | Mark incident resolved/unpin because operator clicked an X |

### Conceptual data-flow

```text
[Uploaded MP4 / webcam / supported network camera]
                         │
                         ▼
                SOURCE INGESTION
              timestamp + validation
                         │
                         ▼
              FRAME SCHEDULER/QUEUE
           bounded queue, drop stale frames
                         │
                         ▼
           YOLO PERSON DETECTION (class=person)
                         │
                         ▼
           SUPERVISION Detections + TRACKER
                         │
                         ▼
           CALIBRATED ZONE COUNTING
          homography → ground points → zones
                         │
                         ▼
         DENSITY + TEMPORAL METRIC HISTORY
                         │
                         ▼
        TREND / FORECAST + RISK STATE MACHINE
                         │
                ┌────────┴─────────┐
                ▼                  ▼
        DATABASE + AUDIT       EVENT PUBLISHER
                │                  │
                ▼                  ▼
           DJANGO API       CHANNELS / REDIS
                └────────┬─────────┘
                         ▼
       DASHBOARD / FULL-PAGE FEED / EVENT LOG
            PERSISTENT CRITICAL MINI-DOCK
```

**Deployment modes:**

- **MVP, one laptop:** Django + vision worker running as two separate local processes, with a local browser; easiest to debug and demonstrate without Internet.
- **Hybrid hackathon deployment:** hosted Django + database + Redis (if needed) and a laptop vision worker pushing validated metrics over HTTPS. Public viewers open the hosted dashboard. If the laptop goes offline, **feed state becomes stale/offline** and unresolved incidents remain open.
- **Later production:** separate managed inference services, secured media gateways and dedicated event buses. **Do not overbuild this in 24 hours.**

**Important implementation decision:** The computer-vision process is *not* a Django view, an ASGI consumer loop, or a request handler. Keep detector/model loading inside a long-lived worker to avoid reloading heavy weights for each browser request.

---

## 2. MVP scope, deliberate deferrals, and acceptance boundaries

### P0 — required for a credible H7 submission

- Register, remove and inspect **at least two** feed sources.
- Analyze at least two feed inputs concurrently, using an actual detector, with independent cameras/zones/trackers.
- Validate source availability and report connecting/live/replay/stale/offline/error separately from inference state.
- Calibrate at least one polygon area per feed against known real-world geometry; return count and density when valid.
- Compute trends from timed density observations, not guessed display counters.
- Maintain backend risk severity and durable, single-incident lifecycle.
- Expose the exact endpoints and event formats needed by `front_end.md`.
- Persist active critical incidents across app refresh/reconnect and silence warnings by per-incident acknowledgement.
- Resolve/unpin only after a **configurable sustained recovery window** with valid monitoring.
- Supply a live dashboard snapshot and chronologically paginated event log.
- Produce measured **two-feed FPS** and **count-error** results on a held-out manually counted test set.
- Launch a usable browser dashboard and provide reproducible local/hybrid demo instructions.

### P1 — valuable if the core works

- Browser-ready live preview transport (lightweight MJPEG or another supported mechanism).
- Multiple calibrated subzones per feed, optional detection overlays and calibration editor.
- Basic user roles and event supervision tools.
- Upload progress and replay playback with processing-time metrics clearly labeled.
- Metric history endpoint for the feed-detail trend chart.
- Notification delivery and exportable test results.

### P2 — explicitly defer unless judges require it

- Real RTSP gateway/transcoding for arbitrary hardware cameras; WebRTC ingest with signaling/TURN.
- Complex multi-camera re-identification, cross-camera unique-person totals, face recognition.
- Cloud GPU autoscaling, Kafka, Kubernetes, microservices, custom detector training from scratch.
- SMS/phone-call dispatch, official evacuation advice, safety certification.

### Hard boundaries of the first iteration

- A browser-selected webcam captured with `getUserMedia()` exists **in the browser**, not automatically on the Django server. Supporting this as a backend vision input needs an **explicit frame/media upload or WebRTC ingest protocol**. Do not advertise browser webcam analysis as working until that transport exists.
- An OpenCV worker may read supported local video files, USB webcams, or network streams; an RTSP camera can require backend-native handling and cannot be plugged directly into an ordinary HTML video tag.
- An **uploaded recorded video** must remain labeled `replay` / `file` in the API and UI, even while its frames are analyzed in real time.
- If all you have is one feed or a mock metrics generator, the core H7 technical requirement is **not satisfied**.

---

## 3. Proposed repository and application organization

Use one repository with clear service boundaries. Suggested layout, not mandatory filenames:

```text
crowd-fuzion/
├── backend/
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── routing.py
│   ├── monitoring/
│   │   ├── models.py          # feeds, zones, observations, incidents, events
│   │   ├── serializers.py     # input/output contracts and validation
│   │   ├── views.py           # REST endpoints
│   │   ├── urls.py
│   │   ├── consumers.py       # dashboard WebSocket
│   │   ├── permissions.py
│   │   ├── selectors.py       # dashboard snapshot/read queries
│   │   ├── services/
│   │   │   ├── risk.py
│   │   │   ├── incidents.py
│   │   │   ├── telemetry.py
│   │   │   ├── calibration.py
│   │   │   └── publisher.py
│   │   └── tests/
│   └── worker_api/
│       ├── views.py           # authenticated worker ingest endpoint
│       └── permissions.py
├── vision/
│   ├── main.py                # long-running entrypoint
│   ├── sources.py             # source reader and reconnection
│   ├── scheduler.py           # bounded queues, fair scheduling
│   ├── detector.py            # YOLO adapter
│   ├── tracking.py            # external trackers / supervision integration
│   ├── zones.py               # zone membership
│   ├── calibration.py         # image → ground-plane geometry
│   ├── metrics.py             # counts, confidence, FPS, timestamps
│   ├── publisher.py           # authenticated metrics POST
│   └── tests/
├── frontend/                  # managed by frontend team
├── fixtures/
│   └── README.md              # labeled samples, no fabricated final metrics
├── benchmarks/
│   ├── annotations.csv        # manual counts on held-out frames
│   ├── run_benchmark.py
│   └── results/               # measured output
├── scripts/
├── .env.example
├── requirements.txt / pyproject.toml
├── README.md
├── front_end.md
└── back_end.md
```

Keep the domain policy (`risk.py`, `incidents.py`) testable **without a live detector**, and keep frame inference testable **without an HTTP server**. An agent should not hide all logic in one untestable `views.py`.

---

## 4. Data entities and persistence contract

Use Django models with migrations. Model names below are **proposed**. Prefer UUIDs or other stable opaque IDs for public API identifiers, proper foreign keys and UTC timestamps.

### `Feed` — one source, not one incident

| Field | Type / constraint | Why it exists |
|---|---|---|
| `id` / public `feed_id` | Stable UUID/string; unique | Links cards, routes, WebSocket events and logs |
| `name`, `location` | Nonempty strings | Feed title and venue/zone label |
| `source_type` | Enum: `upload`, `webcam`, `network` | Correct source semantics |
| `source_config` | Protected server-side config | File ID, device ID or source URL; don't expose private RTSP credentials |
| `stream_state` | `connecting`, `live`, `replay`, `stale`, `offline`, `error` | Media availability/replay state |
| `analysis_state` | `pending`, `active`, `calibrating`, `paused`, `failed` | Inference health, separate from transport |
| `severity` | `critical`, `high`, `elevated`, `normal`, `unknown` | Current backend-assessed status |
| `risk_score` | Nullable number, documented scale | Ranked feed grid; higher means more urgent |
| `last_metric_at`, `last_frame_at` | Nullable UTC datetimes | Freshness/staleness |
| `preview_url`, `preview_transport` | Optional browser-safe signed URL + `mjpeg`, `hls`, `webrtc`, `file`, `image` | Frontend preview adapter; never return raw private source URL |
| `configuration_version`, `state_version` | Monotonic integer | Reject out-of-order source settings and telemetry |
| `created_at`, `updated_at` | UTC datetimes | Audit/setup |

A feed may have **multiple zones** and **multiple historical incidents**, but `state=active` critical incidents must be deduplicated according to the chosen per-feed/per-zone policy.

### `Zone` and `Calibration`

| Field | Type / constraint | Why it exists |
|---|---|---|
| `zone_id`, `feed_id` | Stable ID + FK | Define monitored region within feed |
| `name` | String | “Entry corridor”, “Gate queue”, etc. |
| `polygon_image` | ≥3 image points in an agreed source-frame coordinate space | Pixel-space region of interest |
| `polygon_ground_m` | Calibrated ground-plane polygon in metres | Used for true floor area / crowd density |
| `calibration_id`, `version` | Stable ID, increasing version | Identify which calibration produced a metric |
| `image_reference_points` | Four validated pixel coordinates | Input correspondences for homography |
| `ground_reference_points_m` | Four corresponding metre coordinates | Known measured rectangle or quadrilateral |
| `homography` | Valid finite 3×3 transform | Image-to-ground mapping; derived, not blindly trusted |
| `area_m2` | Positive finite float | Density denominator |
| `calibrated` | Boolean | Only show valid people/m² when true |
| `is_active` | Boolean | Zone monitoring enabled |

Calibration may be stored as a dedicated versioned entity or together with a zone if migrations and updates are simpler. Always tie observations to a **calibration version**; invalidating calibration must remove derived-density validity for future samples. Existing incident history remains intact.

### `Observation` / latest `FeedMetrics`

Keep a small persistent metrics history at a controlled interval (e.g. 1 sample/second per feed or zone) and a latest snapshot for fast dashboard load. Do **not** write every frame at full camera FPS into the main database by default.

| Field | Type | Note |
|---|---|---|
| `feed_id`, optional `zone_id` | Stable IDs | Source, monitored area |
| `sample_id`, `sequence` | Unique per feed; monotonic | Idempotent ingest and stale rejection |
| `captured_at`, `processed_at`, `received_at` | UTC datetimes | Distinguish camera/worker/server timing |
| `people_count` | Nonnegative int / null | Current visible count, not unique event attendees |
| `density_people_per_m2` | Nullable nonnegative float | `null` when uncalibrated/invalid |
| `density_trend` | `rising`, `stable`, `falling`, `unknown` | UI indication |
| `growth_rate` | Float with explicit units `people/m²/min` | Rate for trend/prediction |
| `predicted_threshold_time` | Nullable UTC timestamp | Forecast, not safety guarantee |
| `measured_fps` | Nullable float + measurement window | Actual processed inference throughput |
| `inference_ms` | Nullable float | Performance diagnosis |
| `calibration_version` | Nullable int | Audit reliability |
| `quality_flags` | Array/list | Low confidence, dropped frames, occlusion, calibration invalid, etc. |
| `is_valid` | Boolean | Risk model should distinguish valid vs missing telemetry |

Avoid saving per-person track IDs long-term without a concrete requirement. All counts are **estimated visible occupancy**, not biometric identities.

### `CriticalIncident` — the authoritative pin/ack/resolution record

| Field | Type / constraint | Meaning |
|---|---|---|
| `incident_id` | Unique stable ID | Never reuse across separate critical episodes |
| `feed_id`, optional `zone_id` | FKs | Identify location and pinned feed |
| `state` | `active` / `resolved` | **Only `resolved` allows unpin** |
| `severity` | `critical` while active | UI remains red even if acknowledged |
| `acknowledged` | Boolean, default false | Silences this incident's audio after server confirmation |
| `acknowledged_at`, `acknowledged_by` | Nullable UTC / user FK | Auditable operator action |
| `started_at`, `last_updated_at` | UTC | Incident timing and heartbeat |
| `resolved_at` | Nullable UTC | Set only by recovery policy |
| `reason` | Short summary + optional structured trigger code | Explain why flagged |
| `latest_metrics` | Nullable snapshot/reference | Support stale last-known information |
| `recovery_started_at` | Nullable UTC | Tracks continuous good-measurement recovery window |
| `policy_version` | String/int | Identify risk rules applied |

**Critical:** `acknowledged` must never imply `state=resolved`. Do not implement a user-facing `close`, `dismiss`, `unpin`, or manually `resolve` endpoint in v1.

**Deduplication rule:** On a critical transition, search within a transaction for the relevant **existing active incident**. If present, update it, preserving its acknowledgement. If absent, create one new incident and publish **one** `incident.created`. Consider a conditional database uniqueness constraint on active incidents per feed/zone to guard race conditions. If risk varies by subzone, define whether incidents are keyed by `(feed, zone)` or `(feed)` and keep it consistent; UI pinning is ultimately by feed.

### `EventLogEntry` — right-side operational log

| Field | Type | Explanation |
|---|---|---|
| `event_id` | Stable unique ID | Idempotent UI log item |
| `timestamp` | UTC | Show localized in browser |
| `feed_id`, `feed_name` | ID + snapshot label | Stable display even after source renamed |
| `category` | `crowd`, `prediction`, `system`, `calibration` | UI filter |
| `severity` | `critical`, `high`, `elevated`, `info` | Timeline marker |
| `event_type` | Domain-coded string | e.g. `density_rising`, `threshold_crossed`, `feed_disconnected`, `returned_to_normal` |
| `message` | Plain text | No untrusted HTML injection |
| `delta_percent`, `density_people_per_m2`, `people_count` | Optional numbers | Contextual details |
| `incident_id`, `state` | Optional | Correlate incident updates |
| `sequence` | Monotonic event cursor | Reliable resume/gap detection |

Generate logs **on meaningful changes**, not every video frame. A repeated “density rising” event may be emitted after a distinct time/percentage milestone or cooldown, not every 200 ms.

### Optional `Alert` vs `CriticalIncident`

Use transient `Alert` records for high/elevated trend notices if useful; keep them **distinct** from the durable critical-incident lifecycle. A high-warning threshold crossing must not inadvertently acquire the special critical pin/ack semantics. The event names `alert.created`/`alert.updated` may describe these informational warnings.

### Operator identity and worker credentials

Use Django users/sessions for human operators, and a **separate scoped worker credential** for vision telemetry upload. A browser must never see the worker token or private camera passwords. Avoid storing secrets in plain-text source config returned by a `GET /api/feeds/` serializer.

---

## 5. Video ingestion and multi-feed execution

### Supported sources and their semantics

| Input | MVP feasibility | Processing approach | Frontend label |
|---|---|---|---|
| Uploaded MP4 (common codec) | **P0** | Validate + store safely, worker opens with OpenCV/FFmpeg-capable backend | **Replay / File**, not Live |
| USB/local webcam | **P0 if available** | Worker opens assigned `cv2.VideoCapture(index)` or equivalent | Live Camera |
| Network/IP camera | P1 | Worker reads a supported URI with timeouts/reconnect | Live Network |
| Browser `getUserMedia()` source | P2 unless browser-to-worker transport is implemented | Requires WebRTC ingest or authenticated frame/media streaming | Browser Camera — only when real ingest works |

**Never** allow a submitted URL to instruct the backend to fetch arbitrary private network/metadata services. If network URLs are permitted, validate scheme, destination and deployment policy to reduce SSRF exposure; keep credentials server-side.

### Concurrency strategy

- Maintain **one source-reader context per active feed**, with independent timestamps, connection state, tracker and zone state.
- Use bounded per-feed frame queues (e.g. latest-frame queue size 1–2) so a slow model does not accumulate old footage or generate delayed “live” warnings.
- Run two feeds concurrently using capture threads/processes plus a fair inference scheduler, or separate long-lived worker processes if the machine can support it.
- If the model/inference accelerator is shared, schedule both feeds fairly; two cameras must **both** achieve target processed FPS if the test interprets the 5 FPS requirement per feed.
- **Inference FPS** = number of frames actually analyzed divided by elapsed monotonic time per feed in a clearly reported window. Captured FPS and rendered browser FPS are separate metrics.
- On restarts, rebuild tracking state per feed. Track IDs may reset; incident IDs and acknowledgements must not.
- A duplicate uploaded file can be replayed as a second source for plumbing tests, but evaluate accuracy on **distinct footage and judge inputs**; do not misrepresent a cloned demo as a two-camera field deployment.

### Fault handling

- Missing video, invalid codec, device busy, end-of-file, disconnected network, inference exception, timeout → publish feed state and event with meaningful error detail.
- For a replay video, **end of file** should change to completed/ended as an explicit state (or an API-mapped `offline` with a reason), not trigger a fabricated recovery event.
- Reconnection should be bounded and backoff-based; do not spin a CPU core on repeated failure.
- On missing observations, flag the feed `stale` after a configurable timeout, then `offline` if appropriate. The last confirmed incident remains active and pinned.
- Make source lifecycle idempotent: deleting/pausing a feed cannot silently delete an active critical incident or create the impression it was resolved. Guard removal of a feed with unresolved critical incidents or retain a clear orphaned incident record and pinned placeholder until an authorized resolution workflow is explicitly designed.

---

## 6. Person detection, Roboflow Supervision and tracking

### Canonical processing sequence

1. Load a fixed, **recorded model name and checkpoint version** at worker startup.
2. Decode and timestamp a frame (record frame number and source dimensions).
3. Run person detection (COCO person class where applicable) with a configurable confidence threshold.
4. Convert predictions to `supervision.Detections`, retaining boxes, class/confidence and source frame coordinates.
5. Optionally pass detections through a separate `ByteTrackTracker` **unique to this feed**.
6. Calculate the ground-contact/footpoint estimate (commonly bottom-center of box) or another documented position convention.
7. Map footpoints to calibrated ground plane for each relevant zone and count occupants **once per frame** (do not accumulate track IDs as a permanent crowd count).
8. Compute count/density/quality metrics and publish timestamped observations.
9. Optionally render annotated previews as separate media outputs for operator inspection.

### Supervision-specific direction

- Use `sv.Detections.from_ultralytics(...)` as the model-to-utility adapter when predictions come from Ultralytics.
- Use `sv.PolygonZone` for image-space region occupancy and annotations **when its geometry semantics match the chosen method**. Its `current_count` represents current in-zone detections, not a unique cumulative event attendance total.
- For current external tracking support, use `from trackers import ByteTrackTracker` and `tracker.update(detections)`. **Do not use removed `sv.ByteTrack` APIs.**
- Maintain a separate tracker instance per camera; globally shared tracker IDs would mix people across unrelated feeds.
- A tracker may stabilize IDs, but it does **not** discover persons missed by the detection model. Validate the combination on dense/occluded footage; track-based extrapolation must not fabricate crowd counts.
- Choose one output overlay strategy per source: **annotated stream from worker**, or **raw preview + frame-timestamped detection overlay sent to browser**. Do not render boxes twice or claim precise synchronization when frame timestamps do not align.

### Dense-crowd limitations and improvements

Pretrained person detectors can undercount heavily occluded crowds. Include test clips with overlap, distant individuals, motion blur, poor lighting and high contrast. Tune image resolution, detection threshold, non-max suppression and processing stride **against evaluation data**, not by appearance alone. Optional density-estimation methods are a fallback experiment, not a reason to fake compliance with the count-error target.

No facial identification, recognition, or persistent person identity is needed for H7.

---

## 7. Camera calibration and meaningful people/m²

### Required operator workflow

The frontend should let an operator open feed details and **calibrate a zone**. The backend validates and stores:

1. Original source-frame width and height.
2. Four image points corresponding to four **known floor-plane points**, in a consistent order.
3. Their physical ground coordinates in **metres** — e.g. a measured rectangular region with verified width and height, not an invented area.
4. One or more editable polygons designating the monitored ground region.
5. A versioned calibration and computed area.

**Proposed math:** estimate a homography `H` between the image plane and ground plane using four non-collinear correspondences (e.g. OpenCV `getPerspectiveTransform` for exactly four pairs). Transform people footpoints from image coordinates into ground coordinates. Check whether points lie inside the **ground-plane polygon**; calculate that polygon's area (shoelace formula). Then:

```text
zone_people_count = count(valid detected people whose ground-contact point is in zone)
zone_area_m2 = measured/calculated ground polygon area in square metres
zone_density_people_per_m2 = zone_people_count / zone_area_m2
```

Do **not** divide by the number of pixels inside a polygon and label the result `people/m²`.

### Calibration validation and errors

- Verify distinct, correctly ordered points, bounds, finite numbers, positive physical dimensions, and a nondegenerate transform.
- Verify floor-plane assumptions. An elevated camera angle and occluded feet cause density error; document confidence limits.
- Reject negative/zero/non-finite area and extreme, implausible transformations.
- Tie calculated metrics to `calibration_version`, and invalidate affected samples if geometry is updated.
- Return `calibrated=false` and `density_people_per_m2=null` until geometry passes checks. A raw person count may still be shown without claiming verified density.
- If the camera is moved, zoomed or refocused enough to invalidate the mapping, operators must recalibrate.
- If overlapping feeds show the same people, do not sum their counts and call them **unique attendees**. A dashboard sum needs explicit overlap caveats or a true deduplication algorithm.

### H7 compliance demonstration

Show the calibration points over a sample frame, the entered physical dimensions, area in m², and the resulting live density. A judge should be able to change the calibration geometry and see the density update correctly without changing the raw detected people count.

---

## 8. Temporal analysis, severity and early warning

### Inputs must include real time

Use a bounded time series of **valid** observations (`captured_at`/`processed_at`) for each relevant zone. Smooth noise with a small rolling median/mean or robust regression, but keep **raw counts and computed values** available for diagnostics. Calculate density growth in documented units, preferably **people/m² per minute**.

A simple first-order forecast is acceptable **if it is measured and clearly labeled as an estimate**:

```text
estimated_density_at_t_plus_h = current_smoothed_density + growth_rate * horizon_minutes
predicted_threshold_time ≈ now + (threshold - density) / positive_growth_rate
```

Do not produce a time-to-threshold when the rate is near zero, negative, history is insufficient or telemetry is stale. Report `null` instead.

### Proposed risk levels — configurable policy, not universal safety limits

| `severity` | Interpretation | Color/priority |
|---|---|---|
| `critical` | Backend's critical policy crossed; active incident required | Red; pinned |
| `high` | Serious increase / nearing critical under current policy | Orange |
| `elevated` | Rising or approaching warning region | Yellow |
| `normal` | Valid calibrated measurements below configured concern criteria | Green |
| `unknown` | Insufficient/stale/uncalibrated or invalid data | Grey, not green |

**Do not invent universally safe people/m² numbers.** The system needs clearly named **venue-configurable thresholds**, versioned defaults for demos and explanatory notes that they are provisional operator thresholds, not certified evacuation guidance. Critical creation may be triggered by a current threshold or a sufficiently urgent forecast, but the policy must say which occurred.

### Avoid alert spam with hysteresis and stateful logic

- Evaluate risk on valid, fresh metric windows, not one random frame.
- Add separate **enter-critical** and **exit-critical** conditions plus a sustained **recovery window**. This avoids flapping between red and green.
- A newly critical zone creates an incident **once**. Subsequent metric updates refresh the same incident.
- A sudden density drop lasting one frame must **not** resolve it.
- No telemetry / an offline feed must **freeze automatic recovery progress**; never advance recovery while blind.
- A new critical episode after an actually resolved previous incident receives a **new incident ID** and requires fresh acknowledgement.
- Store the policy version and reason codes for evaluation and viva.

### Feed-level sorting and risk score

The frontend sorts **critical > high > elevated > normal**, then by the backend's descending `risk_score`. Risk should incorporate zone density relative to the selected threshold and trend/urgency, **not raw headcount alone**. A compact gate with 35 people can be more dangerous than a courtyard with 90 people.

Set `risk_score=null` when not assessed; separate unknown/unavailable feeds last. Maintain stable score semantics across sources. The frontend may re-sort every few seconds, but backend event cadence should remain independent of UI animation.

### Manual override: not part of v1

The product requirement says the dock should unpin only when the crowd has been managed. In this prototype, **“managed” means the backend has observed sustained valid recovery according to the configured policy**. Do not provide an `is_managed=true` browser input or an “operator resolve” button that lets a client bypass this check. Real operations would eventually need documented human escalation and exceptional override procedures; those require separate authorization and audit design, not a hackathon shortcut.

---

## 9. Critical-incident state machine — implement without compromise

### Explicit states and transitions

```text
NO ACTIVE CRITICAL INCIDENT
        │
        │ valid calibrated observations meet critical entry policy
        ▼
ACTIVE + UNACKNOWLEDGED
  - red feed
  - immediately in global critical dock
  - warning sound requested in browser (subject to autoplay permission)
  - unrelated in-app navigation blocked
        │
        │ POST /api/incidents/{id}/acknowledge/
        ▼
ACTIVE + ACKNOWLEDGED
  - browser stops this incident's sound
  - still red, still pinned across every route and refresh
  - unrestricted in-app navigation only if ALL other active incidents acked
        │
        │ sustained, valid, backend-measured recovery confirmed
        ▼
RESOLVED
  - server timestamps and persists resolution
  - incident.resolved broadcast
  - frontend automatically unpins this incident
```

Either active stage may transition to `resolved` **only** by the recovery rule. Acknowledgement is **not a prerequisite for actual recovery**, but an acknowledgement action must never itself induce recovery.

### Invariants to encode as tests

```text
ACKNOWLEDGED does not mean RESOLVED.
ACTIVE critical incidents stay pinned, acknowledged or not.
A critical feed going offline cannot auto-resolve.
A refresh/reconnect never clears a persisted active incident.
Acknowledgement is keyed by incident_id and is idempotent.
A new critical incident is distinct from an earlier resolved one.
One feed may have a new incident only after prior episode resolution.
All active unacknowledged incidents must be handled before unrelated in-app navigation unlocks.
No client request can directly set incident.state = resolved.
```

### Multiple simultaneous incidents

- Acknowledge each individually; include actor/time on each persisted record.
- Every unresolved incident is included in `GET /api/incidents/active/` and the initial dashboard snapshot.
- Event payloads reference **both `incident_id` and `feed_id`** so the dock can display all active incidents and navigate to the correct feed.
- Prefer **one audible alert controller in the frontend** that alerts for any still-unacknowledged critical incident, rather than overlapping sirens; backend still sends independent incident states.
- If two zones on the same feed become critical, choose and document a consistent policy: distinct zone incidents but one pinned video tile with multiple incident badges, or one aggregated feed incident. This v1 recommends **one active incident per feed** for UI simplicity, with a list of contributing critical zones in `reason`/metadata. This aggregation is a *proposed implementation decision*; align it with the frontend team.

### Recovery algorithm (illustrative policy, not official safety threshold)

```text
IF active incident exists:
  IF sample is invalid/stale/offline:
      keep incident active; reset/pause recovery timer
  ELSE IF all contributing critical zones satisfy configured exit policy:
      start/continue sustained recovery timer
      IF valid recovery window completed:
          atomically mark incident resolved; emit exactly one incident.resolved
  ELSE:
      reset recovery timer; keep incident active
```

The **exit policy** may require density below a lower exit threshold and absence of immediate re-escalation predictions; its values must be configurable, documented and tested. Do not resolve solely because recent count has decreased—verify that the risk condition is actually clear.

### Transaction and event consistency

Use a database transaction when creating, acknowledging or resolving an incident. Persist the change **before** publishing the corresponding WebSocket event (`transaction.on_commit` is a sensible pattern). For greater durability, add a small outbox table so a crash between database commit and broadcast can be replayed. A reconnecting client must always recover truth from `GET /api/dashboard/` / `GET /api/incidents/active/` even if it missed an event.

---

## 10. REST API — match `front_end.md` v1.2

**All paths below are proposed integration contracts, not implemented endpoints.** Avoid renaming them in the backend agent's output without updating `front_end.md` and the frontend client. Use JSON for metadata and multipart uploads for files. Apply proper authentication, CSRF and permission checks.

### Frontend-facing operations

| Method + path | Required behavior | Critical considerations |
|---|---|---|
| `GET /api/dashboard/` | Snapshot of all feeds, latest metrics/zones, `active_incidents`, server time, event cursor | **Must restore active pinned incidents on refresh** |
| `GET /api/feeds/` | Paginated or complete list of configured feeds and latest status | Never expose raw private source credentials |
| `POST /api/feeds/` | Create validated feed from supported source metadata; return ID and lifecycle | Unsupported source types return clear error, not fake success |
| `POST /api/feeds/upload/` | Multipart video upload and registration; return ID/source status | Size, MIME, file signature, path safety, upload limits |
| `GET /api/feeds/{feed_id}/` | Full feed state, zones, calibrated area, latest stats, preview adapter info | Direct deep-link loads must work |
| `PATCH /api/feeds/{feed_id}/` | Rename or update allowed configuration; version control | Source changes may invalidate calibration |
| `DELETE /api/feeds/{feed_id}/` | Stop/remove only when safe under incident policy | **Do not silently discard an active incident** |
| `PUT /api/feeds/{feed_id}/calibration/` | Validate four correspondences and polygon geometry; persist version | Must return area and calibrated flag, with errors |
| `GET /api/events/?cursor=...` | Paginated event history by feed, severity, category | Stable cursor, newest first, dedupe by event ID |
| `GET /api/incidents/active/` | All unresolved critical incidents and acknowledged flags | **Pin-source-of-truth API** |
| `POST /api/incidents/{incident_id}/acknowledge/` | Authenticated, idempotent per-incident acknowledgement | **Never resolves, clears, unpins or downgrades** |
| `GET /api/incidents/{incident_id}/` | Historical/active incident detail | Read-only incident lifecycle |

### Backend-worker operations (private)

| Method + path | Purpose | Access |
|---|---|---|
| `POST /internal/telemetry/` | Validated latest counts, density inputs, timestamps, FPS, feed sequence and status from worker | Scoped worker credential, not browser |
| `POST /internal/worker-heartbeat/` | Liveness, assigned feed IDs, worker/model version | Worker credential |
| `GET /internal/worker-config/` *(optional)* | Feed sources and current calibration versions | Worker credential, redact secrets in logs |

`/internal/*` should be restricted by credentials and ideally network policy. Never ship worker ingestion keys in JavaScript. A narrower implementation can run analysis and risk together in one worker that calls a protected Django ingest endpoint; choose one **authoritative location** for incident decisions and document it.

### Suggested response: initial dashboard

```json
{
  "server_time": "2026-11-20T16:10:00Z",
  "event_cursor": 143,
  "feeds": [
    {
      "feed_id": "gate-a",
      "name": "North Gate",
      "location": "Festival entry",
      "source_type": "upload",
      "stream_state": "replay",
      "analysis_state": "active",
      "severity": "critical",
      "risk_score": 93.2,
      "people_count": 83,
      "density_people_per_m2": 1.9,
      "density_trend": "rising",
      "growth_rate": 0.14,
      "growth_rate_unit": "people_per_m2_per_minute",
      "predicted_threshold_time": "2026-11-20T16:12:00Z",
      "zone_area_m2": 43.7,
      "calibrated": true,
      "measured_fps": 7.4,
      "metric_timestamp": "2026-11-20T16:09:59Z",
      "preview_url": null,
      "preview_transport": null,
      "version": 88
    }
  ],
  "active_incidents": [
    {
      "incident_id": "inc-gate-a-01",
      "feed_id": "gate-a",
      "state": "active",
      "severity": "critical",
      "acknowledged": false,
      "acknowledged_at": null,
      "acknowledged_by": null,
      "started_at": "2026-11-20T16:00:00Z",
      "last_updated_at": "2026-11-20T16:09:59Z",
      "resolved_at": null,
      "reason": "Calibrated density exceeded configured critical policy"
    }
  ]
}
```

**The numbers above are illustrative API fixtures** for contract discussion. They are not detected values or recommended safety thresholds. Do not use them as an undifferentiated real dashboard feed.

### Suggested acknowledgement behavior

```http
POST /api/incidents/inc-gate-a-01/acknowledge/
Content-Type: application/json
X-CSRFToken: <browser-session-csrf-token>

{}
```

Successful `200 OK` (or `204 No Content` plus authoritative follow-up) must confirm stable incident identity and `acknowledged=true`, with `state=active` if unresolved. Repeated acknowledgements return the same persistent state without emitting duplicate meaningful events.

**Race case:** If a legitimate recovery resolves the incident just before an acknowledge request arrives, return the already-resolved record or an explicit nonfatal conflict with current state. Never recreate or reopen it just to satisfy the ack request.

### Suggested calibration request

```json
{
  "zone_id": "north-queue",
  "source_frame_size": {"width": 1280, "height": 720},
  "image_reference_points": [[100,120],[880,120],[1060,600],[65,600]],
  "ground_reference_points_m": [[0,0],[8,0],[8,5],[0,5]],
  "zone_polygon_image": [[100,120],[880,120],[1060,600],[65,600]],
  "expected_configuration_version": 3
}
```

Return `calibrated`, `area_m2`, `calibration_version`, validation warnings and any corrected normalized coordinates. An agent must implement actual geometry validation, **not accept arbitrary positive `area_m2` from the browser as proof**.

### Errors, concurrency and pagination

- Use consistent HTTP semantics: `400` malformed, `401` unauthenticated, `403` unauthorized, `404` missing, `409` version conflict/unsafe deletion, `413` too large, `415` unsupported format, `422` invalid geometry/semantic input where supported, `429` rate limit, `5xx` service failure.
- Choose a consistent JSON error envelope, e.g. `{ "error": {"code":"CALIBRATION_INVALID","message":"...","fields":{...}}}`.
- `GET /api/events/` should allow `limit`, `cursor`, `feed_id`, `severity`, and `category`, use stable ordering, and return `next_cursor`.
- Store all durable timestamps in UTC ISO 8601. The frontend renders local times; do not hardcode IST strings into the API.
- Use optimistic version numbers for settings, sequence IDs for worker telemetry and server-owned event cursors for WebSocket recovery.

---

## 11. Real-time WebSocket contract — match `front_end.md`

**Endpoint:** `wss://<backend-host>/ws/dashboard/` or equivalent same-origin `/ws/dashboard/` with Django Channels/ASGI.

### Event envelope

Every event should include:

```json
{
  "type": "feed.metrics_updated",
  "event_id": "evt-144",
  "sequence": 144,
  "timestamp": "2026-11-20T16:10:01Z",
  "feed_id": "gate-a",
  "payload": {
    "people_count": 84,
    "density_people_per_m2": 1.92,
    "severity": "critical",
    "risk_score": 93.4,
    "measured_fps": 7.5,
    "metric_timestamp": "2026-11-20T16:10:00.8Z",
    "version": 89
  }
}
```

### Events to publish

| Event type | When to emit | Essential payload |
|---|---|---|
| `dashboard.snapshot` | On initial WebSocket connect if supported | Same truth as `GET /api/dashboard/`, cursor included |
| `feed.added` | Source registered | Full feed state |
| `feed.removed` | Source safely removed | Feed ID and reason |
| `feed.status_changed` | Connected, replay, offline, stale, analysis error | Feed state + timestamps |
| `feed.metrics_updated` | Periodic sample/coalesced batch | Latest metrics, version and freshness |
| `feed.calibration_changed` | Valid calibration modified | Zone ID, new version, area, validity |
| `alert.created` / `alert.updated` | Informational/early-warning transitions | Alert/zone info, not incident resolution |
| `incident.created` | **One new critical episode** | Complete incident snapshot |
| `incident.acknowledged` | Ack persisted | `incident_id`, `feed_id`, `acknowledged=true`, actor/time |
| `incident.updated` | Active incident cause/severity context changes | Incident ID, metrics and version; preserves ack |
| `incident.resolved` | Backend confirmed sustained recovery | `incident_id`, `feed_id`, `state=resolved`, `resolved_at` |
| `system.heartbeat` | Periodic connection health | Server time, optional sequence |

**Incident events are priority messages.** Don't rate-limit them together with high-frequency count frames. A backlog may coalesce routine metrics by feed; it must not swallow incident creation/acknowledgement/resolution.

### Canonical incident events

```json
{
  "type": "incident.created",
  "event_id": "evt-101",
  "sequence": 101,
  "timestamp": "2026-11-20T16:00:00Z",
  "feed_id": "gate-a",
  "incident": {
    "incident_id": "inc-gate-a-01",
    "feed_id": "gate-a",
    "state": "active",
    "severity": "critical",
    "acknowledged": false
  }
}
```

```json
{
  "type": "incident.acknowledged",
  "event_id": "evt-102",
  "sequence": 102,
  "timestamp": "2026-11-20T16:01:00Z",
  "incident_id": "inc-gate-a-01",
  "feed_id": "gate-a",
  "acknowledged": true,
  "acknowledged_at": "2026-11-20T16:01:00Z",
  "acknowledged_by": "operator-1"
}
```

```json
{
  "type": "incident.resolved",
  "event_id": "evt-103",
  "sequence": 103,
  "timestamp": "2026-11-20T16:06:00Z",
  "incident_id": "inc-gate-a-01",
  "feed_id": "gate-a",
  "state": "resolved",
  "resolved_at": "2026-11-20T16:06:00Z"
}
```

These examples deliberately reproduce the key field names in `front_end.md`. The frontend must treat `incident.resolved` **or a newer authoritative snapshot** as the only basis for removing a pinned critical feed.

### Ordering, reconnection, persistence

- Server event sequences should be monotonic for a given event stream; use DB sequence IDs or similar. Global sequence continuity may have gaps if some event types aren't broadcast; document rules for what constitutes a gap.
- On connection, return a snapshot **including every active critical incident and ack flag**. Client can then apply newer events.
- Reconnect with exponential backoff; after disconnect, clients should re-fetch `GET /api/dashboard/` and `GET /api/incidents/active/`. Never rely on WebSocket memory as the only history.
- Dedupe repeated events by `event_id`/`sequence`, and ignore older feed `version` updates.
- Use authenticated, origin-validated WebSocket handshakes; don't permit anonymous external observers of private footage or incident state unless intentionally configured.
- Server heartbeats must not be misinterpreted as fresh camera measurements.

### Broadcast cadence

- Routine dashboard metrics can be emitted around **1–2 times per second per feed**, with every inference frame still measured inside the worker.
- Preserve **all** state transitions and critical events, independent of telemetry throttling.
- Avoid sending full-resolution encoded frames over JSON WebSocket messages. Media preview should use a separate transport.

---

## 12. Media previews and per-feed full-page monitoring

The frontend requires many simultaneous tiles, hover stats, a full-page route on click and a **globally persistent mini-preview** for every unresolved critical incident. Backend responsibilities:

1. Return a stable `feed_id` and display metadata, plus `preview_url` and `preview_transport` **only when preview is actually available**.
2. Support a raw or annotated preview strategy. If overlay detections are client-rendered, include correct frame timestamps/dimensions and explicit coordinate convention.
3. Keep long-lived preview stream access separate from the metrics WebSocket so adding tiles does not duplicate YOLO inference per viewer.
4. A globally pinned feed should **subscribe to the same underlying preview source**, not spawn a brand-new independent detection pipeline for each route/card/dock.
5. Generate a lower-bitrate/fps thumbnail preview for grid/dock and higher-quality preview for the full-page route where feasible. Inference FPS is independent from preview delivery FPS.
6. For a prerecorded input, distinguish replay/looping from an actual live camera and preserve truthful timestamps.
7. If preview goes offline while an incident is active, show a stale last frame or placeholder with the incident remaining active; never unpin.

**MVP choice:** A short-interval JPEG thumbnail URL or a carefully implemented MJPEG stream may suffice for a LAN/local prototype. Browser clients can display MJPEG via an image element, but it is not the same as an `HTMLVideoElement` stream; the frontend adapter must choose correctly. For a public deployment, consider bandwidth, authentication and browser compatibility. Do not promise HLS/WebRTC/RTSP handling if unimplemented.

**Security:** do not expose private campus feeds, live RTSP credentials or uploaded sensitive footage to the open Internet by default. Require authentication, restrict origins and document any intentionally public demo sources.

---

## 13. Feed health, observability and operational resilience

### Status must be multidimensional

A feed can be `stream_state=live` and `analysis_state=failed`; a replay can be `replay` and `analysis_state=active`. Its `severity` can be `critical` even if observations go stale, because an unresolved incident exists. Avoid a single misleading `status` string.

Recommended health signals: last captured frame, last successful inference, last accepted telemetry sample, worker heartbeat, queue-drop count, inference error count, measured FPS window, calibration validity and viewer preview status (where measured).

### Freshness semantics

- Define configurable thresholds for `fresh`, `stale` and `offline`, per source type or worker environment.
- Compute freshness server-side from timestamp age and accepted heartbeats; use timezone-aware UTC comparisons.
- Keep last-known metrics annotated with `metric_timestamp`; mark them stale rather than leaving a green card looking live.
- If an active critical incident's feed becomes stale/offline, **retain red incident record and pinned feed** and publish a distinct system event warning that monitoring visibility is degraded.
- If monitoring resumes, a sustained-valid-measurement recovery window may begin anew, subject to policy; offline time does **not** count as recovery.

### Logging and diagnostics

Provide structured logs containing `feed_id`, `zone_id`, `incident_id`, worker ID, calibration version, error code and timestamp where relevant. Avoid raw URLs with embedded credentials, user video data or full auth tokens in application logs.

Useful diagnostic counters include per-feed inference FPS, accepted telemetry per minute, queue drops, detector latency percentile, active critical incidents, unacknowledged incidents, reconnect attempts and time since last successful source frame.

### Optional alert sound coordination

**Backend does not play the siren.** It persists acknowledgement and sends events. Browser audio is subject to autoplay restrictions. The frontend should have a visible “Enable sound alerts” action, and repeated `feed.metrics_updated` events must not restart sound for an already acknowledged incident.

---

## 14. Security, privacy and responsible operation

- Protect human endpoints with Django authentication. For a hackathon, a small operator-login system or intentionally isolated demo account is preferable to unauthenticated public control over live feeds.
- Same-origin session authentication + CSRF tokens is a reasonable default for browser mutating API requests; configure CORS/CSRF trusted origins appropriately for split frontend deployment.
- Require permission checks for adding/removing feeds, changing calibration, viewing camera previews and acknowledging incidents.
- Use **different credentials** for workers posting telemetry; rotate/revoke them through environment configuration, not committed secrets.
- Apply upload caps, safe filenames, content checks, controlled storage paths and malware/codec error handling. Reject unexpected executable extensions and oversize videos.
- Validate network camera URLs to mitigate SSRF; whitelist schemes/protocols and, when possible, camera hosts. Never reflect connection credentials in API responses.
- Authenticate WebSockets, enforce allowed origins and apply per-connection/event limits.
- Use HTTPS/WSS in hosted deployment; set production `DEBUG=False`, `ALLOWED_HOSTS`, secure secrets and appropriate cookie flags.
- Avoid storing raw video permanently unless specifically needed for replay; document a minimal retention period and cleanup mechanism. Do not add facial recognition or identity inference.
- Use anonymized or consented demonstration footage where practical. Keep logs and UI honest about what is observed vs inferred.
- A critical alert is a **decision-support warning**, not a guarantee that a crowd is physically unsafe or safe.

---

## 15. Deployment and environment strategy

### Local demo (must work without external services where practical)

Run Django/ASGI and vision worker as separate processes; configure SQLite for fast local iteration if appropriate and a local Redis instance if real Channels cross-process messaging is used. If Redis is unavailable during the very first proof of concept, a single-process/in-memory channel layer can only be used for a single-process local demo; **it must not be treated as reliable cross-process event transport**.

### Hybrid hosted deployment

- Host Django/ASGI + frontend + database at a reachable HTTPS origin.
- Use production-supported Redis channel layer for Channels message broadcast across processes/services.
- Run the actual multi-feed vision worker on the hackathon laptop or on a machine with adequate compute.
- Worker submits bounded, authenticated telemetry over HTTPS to the hosted server; preferably include idempotent sequence and receive validation errors.
- Deploy media previews separately/securely if needed; remote viewers may not be able to see local USB/RTSP cameras unless the worker **publishes** a browser-playable preview.
- Expose a visible worker-offline diagnostic state; keep unresolved critical incidents server-side regardless of laptop connectivity.
- Check the hackathon's deployment requirement with organizers if necessary: a reachable dashboard alone and local-only detection might be viewed differently from a fully hosted inference demo. Be precise in the README/demo.

### Example environment variable categories (names can be chosen by implementer)

```dotenv
DJANGO_SECRET_KEY=<generated-secret>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<hostnames>
DATABASE_URL=<postgres-connection-string>
REDIS_URL=<redis-connection-string>
WORKER_INGEST_TOKEN=<separate-scoped-token>
MEDIA_STORAGE_PATH=<controlled-location>
MODEL_CHECKPOINT=<explicit-model-file>
MODEL_DEVICE=cpu
METRIC_STALE_SECONDS=<configurable>
CRITICAL_RECOVERY_SECONDS=<configurable>
RISK_POLICY_PATH=<versioned-config-file>
```

Never commit actual `.env` values. The example above lists **configuration categories**, not runnable secrets or recommended safety thresholds.

### Deliverables for demonstrable deployment

- README with one-command or minimal-step startup for backend, worker and frontend.
- Versioned dependency file and reproducible setup instructions for Windows 11 laptop and deployment host.
- Public repo with meaningful commit history and no secrets or large private test footage accidentally committed.
- Reachable frontend URL and working authenticated APIs; video source/processing setup documented honestly.
- Demo/backup walkthrough as allowed by event rules, clearly distinguishing replay and live feed modes.

---

## 16. Testing, evaluation and hidden-test readiness

### A. Unit tests — domain logic

- Valid geometry produces expected area; reversed/invalid calibration yields safe error.
- Count=0 gives density=0 **only when calibration is valid**; when uncalibrated, density is `null`.
- Trend detector handles increasing, decreasing, flat, missing and irregularly spaced samples.
- Risk policy uses real density + growth, without reading arbitrary frontend display state.
- Severity hysteresis avoids oscillating between levels on noisy thresholds.
- An active critical incident is created **once** per distinct episode.
- Acknowledgement persists, is idempotent and does not resolve/unpin.
- Recovery requires a full sequence of valid observations; brief drops, source loss and stale data do not resolve.
- Multiple incidents acknowledge and resolve independently.

### B. API and WebSocket contract tests

- Verify every path in Section 10 and its response fields match `front_end.md`.
- Snapshot returns all active incidents and acknowledgement flags, including after server restart.
- Unauthenticated/unauthorized write actions fail.
- Upload/type/size validation and calibration validation return useful error structures.
- Two duplicate worker telemetry POSTs with same `feed_id` + sequence do not duplicate observations/incident events.
- Older telemetry cannot overwrite newer versions or falsely clear incidents.
- Correct sequence of `incident.created` → `incident.acknowledged` → `incident.resolved` survives reconnect.
- On WebSocket failure, the frontend can rebuild correct state from REST snapshot and log cursor.

### C. Integration tests — live computer vision

- Two video sources genuinely process in parallel without tracker-state mixing.
- New source registration eventually produces valid measurements or a clear failure state.
- Changing calibration updates zone area/density, not the underlying detector raw counts.
- A high-density clip creates a durable incident; acknowledgement stops a specific siren in frontend without removing pin.
- A valid recovery clip permits resolution only after configured confirmation; a disconnected camera does not.
- A full-page feed view, hover stats, event log and global dock all reference **the same backend state**.

### D. Count-accuracy benchmark — do not fake the percentage

Judges require **under 20% count error** at **5+ processed frames/second**. Publish the **exact metric calculation and aggregation method** you used. A clear starting point is per-frame absolute percentage error for frames with nonzero ground-truth count:

```text
absolute_count_error = |predicted_count - manually_counted_ground_truth|
relative_count_error = absolute_count_error / max(ground_truth, 1)
```

**Caution:** Using `max(ground_truth, 1)` is a defensible zero-count convention for a development metric, not an official judging formula. Also report absolute error on empty frames, aggregate mean/median/p90 error, and the count of evaluated frames. The judges may use another metric; be able to explain discrepancies.

Benchmark at least:

- A moderately crowded entry; a high-occlusion crowd; a sparse/empty area.
- Two feeds **simultaneously** on the actual hardware, including end-to-end throughput and latency.
- Unseen clips not used to tune the detector/confidence/model.
- Frames with overlap, side views and partial people where detections often undercount.

Record ground-truth frame ID/timestamp, predicted count, source dimensions, model checkpoint, threshold, device, measured processed FPS, and errors. Clearly separate **inference FPS per feed**, **total inference FPS**, **preview FPS** and **video capture FPS**.

### E. Failure injection tests

- Force close a webcam or kill the worker during an active critical incident: the incident remains pinned and no auto-resolution event occurs.
- Restore network and WebSocket after ack: ack remains true; siren does not restart for the same incident.
- Create two critical feeds: acknowledging one does not release the other's navigation lock.
- Simulate a sharp one-frame count dip: no resolution.
- Simulate a return to truly low risk over the full recovery window: a single authoritative resolved event; pin disappears.
- Reload the dashboard during an active critical incident: correct pin/lock recreated from REST/WS snapshot.
- Try invalid calibration dimensions, malformed input and unsafe upload/source URLs.

### F. Viva-ready engineering explanation

Every teammate should be able to explain: person detector vs tracker vs Supervision, calibrated homography and floor area, why density is better than raw count, how a trend warning is computed, why ack ≠ resolve, stale-feed behavior, measured FPS and count error, and how the worker publishes live metrics to Django.

---

## 17. Implementation phases for a 24-hour hackathon

This is a **priority order**, not a prediction of how long every engineer needs.

| Phase | Target | Exit condition |
|---|---|---|
| **1. Contracts and skeleton** | Repo, Django models, test fixture, initial `/api/dashboard/` and `/ws/dashboard/` | Frontend can load a clearly labeled fixture snapshot |
| **2. Real inference** | Two video readers, YOLO + Supervision/trackers, live count/FPS | Both sources produce actual, timestamped counts |
| **3. Calibration and density** | Four-point calibration + world-ground zones | Valid zone area and people/m²; invalid stays unknown |
| **4. Risk/incident state machine** | Trend, forecast, risk levels, incident create/ack/recover | Automated tests for pinned/ack/resolution invariants pass |
| **5. Real-time UI integration** | Event publisher, REST snapshot, frontend card/log/dock/detail integration | Refresh/reconnect preserves active acknowledged critical incident |
| **6. Testing + deploy** | Hidden-input-style clips, two-feed benchmark, hosted/local setup | Live demo works, measured FPS/error evidence ready |
| **7. Hour-12 surprise accommodation** | Modular enhancement as announced | New requirement integrated without breaking core tests |

### Suggested four-person team ownership

- **Backend owner:** Django REST, models, authentication, persistence, worker ingest and API contracts.
- **Vision owner:** source readers, YOLO, Supervision, tracking, performance benchmark.
- **Analysis owner:** calibration geometry, time series, severity and incident state machine, tests.
- **Frontend/integration owner:** risk-ranked dashboard, activity log, hover/detail and persistent critical dock; coordinate API/WS contract.

All four should review incident logic, test results and the actual code ahead of viva. AI-tool assistance must be disclosed as required by the hackathon rules.

---

## 18. Definition of done: acceptance checklist for backend agent

**Source and measurement**

- [ ] Actual person detections run on **two simultaneous video feeds** on the target laptop/free GPU.
- [ ] Independent source readers, tracker instances, sample timestamps and per-feed performance metrics exist.
- [ ] `supervision.Detections`/zone functions and optional external tracker integration match installed versions.
- [ ] Camera calibration uses **known real-world ground coordinates** and computes positive area in m².
- [ ] Uncalibrated/stale data are never represented as verified healthy density.
- [ ] Density trend and predicted risk are derived from measured time-series data.
- [ ] Count-error/FPS benchmark produces reproducible, truthful results against manually labeled frames.

**Backend and API**

- [ ] `GET /api/dashboard/` returns feeds + **every active incident**, including ack status.
- [ ] Feed creation/upload/detail/update/calibration and log APIs follow the proposed frontend contract.
- [ ] WebSocket broadcasts metric updates and exact critical incident events; clients can resync after missed messages.
- [ ] Unknown, offline, stale, replay and calibration statuses remain distinct.
- [ ] Worker ingestion is authenticated, validated and idempotent; secrets are not exposed to the frontend.
- [ ] Preview URLs are only returned when playback is genuinely supported and properly access-controlled.

**Critical incident guarantees**

- [ ] A critical transition emits **one stable incident ID** and one `incident.created` event.
- [ ] Acknowledgement records actor/time, silences this incident's alarm through an event, but **does not change `state=active` or severity**.
- [ ] Multiple unacknowledged critical incidents independently keep navigation locked.
- [ ] All unresolved critical incidents remain discoverable for a persistent pinned dock, across refresh/routes/reconnect.
- [ ] Offlining a feed, stopping a worker, transient count dip or deleting frontend UI **cannot resolve an incident**.
- [ ] The only automatic unpin path is **server-confirmed, sustained crowd recovery** → `incident.resolved`.
- [ ] Duplicate/out-of-order metrics and restarts do not duplicate incidents or erase ack state.

**Hackathon delivery**

- [ ] Local or hybrid deployment starts reliably, with a working demo URL/clear access instructions.
- [ ] README explains architecture, actual deployment boundaries, source types and all measured benchmarks.
- [ ] No hardcoded judge inputs, fake camera counts, fabricated count accuracy, private footage or secrets committed.
- [ ] Git commits are meaningful and AI-tool contributions are declared; all teammates can defend the implementation.

---

## 19. Open decisions to settle with the frontend and vision teams

Resolve these **before building incompatible interfaces**. Suggested defaults follow; they are **decisions to agree on, not statements of existing support**.

| Decision | Suggested v1 choice | Why |
|---|---|---|
| Does one feed have multiple zones? | Yes in schema; at least one operational zone/feed for MVP | Meets density requirement, extensible |
| What is one critical incident keyed to? | **Feed-level active incident**, with contributing zone details | One pinned preview per feed and simple ack flow |
| Can operators manually resolve critical? | **No** | Matches persistent pin / automatic sustained recovery requirement |
| How is acknowledgement shared? | **Global incident acknowledgement**, persisted and broadcast to all operator sessions | Matches frontend's single `acknowledged` boolean; audit actor |
| Who makes risk decisions? | **One backend domain service**, never both worker and browser | Avoid conflicting severity and resolution |
| What's the preview technology? | Browser-compatible JPEG/MJPEG for demo, if feasible; otherwise null + honest placeholder | Keeps inference independent of playback |
| How does worker authenticate? | Scoped token in server/worker environment | No secret in browser JS |
| What's the first two-feed input? | Two locally available MP4 files or a webcam + MP4 | Reliable test repeatability; label replay correctly |
| How are default safety thresholds decided? | Configurable, documented demonstration policy; no universal safety claim | Prevent misleading safety guidance |
| What constitutes recovery? | Valid, sustained below-exit-policy observations, with hysteresis and no monitoring gaps | Prevents accidental unpin |
| How much metric history to save? | Latest + bounded/sampled history, events persistent for demo | Avoid large write volume |
| When is browser webcam supported? | Only after a real browser→worker media transport exists | `getUserMedia()` alone is local-only |

---

## 20. API and architecture reference sources

The following are **implementation references**, not claims that a library alone fulfills H7:

- **Official problem statement:** `Code_Fuzion_2026_Problem_Statements.pdf`, H7 and judging/submission sections.
- **Companion frontend requirements:** `front_end.md`, v1.2, especially sections 3B, 8–10 and 12.
- **Roboflow Supervision:** https://github.com/roboflow/supervision and https://supervision.roboflow.com/latest/
- **PolygonZone:** https://supervision.roboflow.com/latest/detection/tools/polygon_zone/
- **Roboflow trackers:** https://github.com/roboflow/trackers (current `ByteTrackTracker` approach)
- **Ultralytics Python inference:** https://docs.ultralytics.com/usage/python/
- **OpenCV homography:** https://docs.opencv.org/4.x/d7/dff/tutorial_feature_homography.html
- **Django:** https://docs.djangoproject.com/
- **Django Channels:** https://channels.readthedocs.io/en/latest/
- **Django CSRF/security:** https://docs.djangoproject.com/en/5.2/ref/csrf/

**Final backend directive:** Build a *real, measurable two-feed computer-vision pipeline*, calibrated zone density and trend-based predictions, and a **Django-owned authoritative incident state machine**. The client may acknowledge a critical incident and stop its sound, but **the feed must remain red and pinned until sustained, valid crowd recovery is confirmed by the backend and `incident.resolved` is emitted**. Every API response, event and system failure state must preserve this distinction.
