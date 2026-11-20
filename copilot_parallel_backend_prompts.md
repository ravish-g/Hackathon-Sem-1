# Code Fuzion 2026 H7 — Parallel Copilot Backend Development

**Version:** 1.1 · **Platform:** VS Code on Windows 11 · **Coordination:** GitHub Copilot Agents window, four isolated local worktrees

## Responsibility and branch naming

**Your scope is backend only.** You own the Django project, APIs, database, video-processing worker, risk/incident services, WebSocket server, backend tests and backend deployment. A separate teammate owns all frontend HTML/CSS/JavaScript, layout, visual design and browser-side alert interactions. `front_end.md` is **read-only reference material** for the shared REST/WebSocket contract and incident behavior; these sessions must not implement, edit or deploy the frontend. If the frontend specification demands a backend endpoint/event, implement the server-side contract or flag the gap.

**Branch naming rule:** every feature branch starts with an **imperative verb**, uses lowercase kebab-case and describes the work—not the person or Copilot session. Never use `agent`, a letter designation, a developer name, or a session ID in a branch name. `main` remains the permanent integration branch.

| Workstream | Branch name | Owned backend work |
|---|---|---|
| Foundation | `establish-foundation` | Django scaffold, canonical models and contracts |
| REST and persistence | `build-apis` | HTTP endpoints, serializers, database operations, worker ingestion |
| Vision processing | `process-feeds` | YOLO, Supervision, calibration, dual-stream processing, benchmarks |
| Risk and incidents | `predict-risk` | Density trends, early warnings, acknowledgement/recovery state machine |
| Real-time communication | `stream-events` | Django Channels, WebSocket events, contract tests |
| Final integration (optional) | `integrate-backend` | Merge fixes, end-to-end backend tests, deployment readiness |

Commit the foundation first and merge it into `main`. Create all four parallel worktrees from that exact foundation commit.

## Read first

This document contains **ready-to-paste prompts exclusively for backend development**. It coordinates engineering work for H7 — Crowd Density Alert for Campus Fests. The authoritative backend source is `back_end.md` (v1.0). Consult `front_end.md` (v1.2) only to honor agreed API/WS contracts, and `Code_Fuzion_2026_Problem_Statements.pdf` for official H7 judging requirements. The spec files must exist **inside the repository and be committed** before parallel work starts. These specifications describe proposed interfaces, not existing implementations. If there is a conflict, report it explicitly instead of silently rewriting the agreements.

**Official H7 targets:** simultaneous person counting on **two** video feeds on a laptop CPU or free GPU; perspective-calibrated people/m²; trend-based early warnings; **under 20% count error at 5+ FPS**. Hidden judge inputs and an hour-12 new requirement require modular and testable code. Do not claim a metric without measuring it.

**Non-negotiable critical-alert behavior:** A critical feed must cause server events/state that enable the frontend to pin the feed and play an audible browser alarm where permitted. The backend must expose whether any critical incident remains unacknowledged, so the frontend can block unrelated navigation until acknowledgement. Acknowledgement **changes the incident's alarm flag to silenced only**; it never unpins, downgrades or resolves the incident. The backend must keep unresolved critical incidents present in initial snapshots and reconnect events so the frontend can preserve pinning across routes and refreshes. Offline/stale feeds cannot automatically resolve. Only backend-confirmed **sustained valid recovery** resolves an incident and signals the frontend to unpin. All critical incidents have stable IDs and server-owned state.

## Workflow — do this in order

1. Create/open the `crowd-fuzion` Git repo in VS Code. Add and commit `back_end.md`, `front_end.md` and, if available, the official PDF. Ensure `.env`, model weights, raw video, `venv`, database, credentials are gitignored.
2. Start one **foundation** Copilot session on branch `establish-foundation` and paste **Prompt 0**. Review its changes and run checks. Commit and merge `establish-foundation` into `main` before starting parallel workers.
3. Open **Chat: Open Agents window** using Ctrl+Shift+P. Select **New Session**, **This Computer**, the same repository, the **Copilot** harness, and **New Worktree**. Create **four** sessions using **Prompts A–D**, each based on the foundation commit, with branch names `build-apis`, `process-feeds`, `predict-risk`, and `stream-events`, not each other's unfinished branches. If you have already created worktrees using the PowerShell commands below, open those worktree folders instead of creating duplicate worktrees. Use separate session isolation, never four chats that edit the same checkout.
4. Periodically inspect each session's code changes and approvals. Allow intended dependency installation and tests only after reviewing commands. Do not indiscriminately approve secrets, destructive commands or service deployment.
5. Require each agent to finish its own tests, commit to its worktree branch, and report commits, touched files, tests and blockers. **Do not let agents directly merge into main.**
6. Integrate the four branches **sequentially** into `main`, resolve conflicts carefully, and rerun the combined backend test suite and real two-feed benchmark. Fix integration gaps in a separate backend integration pass. Deploy the Django backend and run the vision worker; record actual performance and limitations. Leave all frontend implementation and frontend deployment to the designated frontend developer.

---

## Prompt 0 — Establish backend foundation (`establish-foundation`; run first)

```text
You are the technical lead establishing the common baseline for Code Fuzion 2026 H7, Crowd Density Alert for Campus Fests. This is a first-iteration backend; do not invent completed features. Read back_end.md entirely and consult front_end.md, especially API routes, WebSocket event names and critical incident behavior, before editing. If the official problem-statement PDF is in the repo, consult its H7 requirements too.

Mission: create a minimal, clean, COMMITTED backend foundation on branch `establish-foundation` from which four isolated Copilot worktrees can implement backend modules independently. Do NOT implement the entire product in this phase. No frontend files may be edited.

Stack: Python 3.11+, Django, Django REST Framework where useful, Django Channels/Daphne, OpenCV, Ultralytics YOLO, Roboflow supervision, NumPy, and trackers where compatible. Pin realistic dependencies from installable official versions; prefer measured compatibility to assumptions. Keep the vision-worker process separate from request handlers.

Create the suggested directory skeleton: backend/config, backend/monitoring, backend/monitoring/services, backend/monitoring/tests, backend/worker_api, vision, vision/tests, benchmarks, fixtures and scripts. Establish the Django project, ASGI application, routing stubs, settings/environment example, .gitignore, README quickstart, test runner and a health endpoint. Create minimal domain model classes and migrations for Feed, Zone, Calibration, latest metrics/observations, CriticalIncident and EventLogEntry based on back_end.md. Establish canonical severity and incident state enums and a stable JSON/event contract module that agents can import, with named interfaces for risk, incidents and broadcasting. Ensure the models can express acknowledgement and resolution as separate fields and support stable incident IDs. Establish public endpoint path declarations and TODO/stub handlers only where essential, not dishonest successful mocks. Generate an API_CONTRACT.md with exact JSON examples and ownership rules; preserve the endpoints specified in both handoff documents.

Define firm ownership boundaries for all next workstreams:
`build-apis`: backend/monitoring REST layer, serializers, query selectors, feed/config/calibration endpoints, backend/worker_api ingestion; existing models may be extended ONLY by this workstream after coordination.
`process-feeds`: vision/** and benchmarks/** only; no Django schema or API edits.
`predict-risk`: backend/monitoring/services/risk.py, incidents.py, telemetry.py and their dedicated tests only; no schema migrations.
`stream-events`: backend/monitoring/consumers.py, backend/config/routing.py, backend/monitoring/services/publisher.py and realtime/contract tests only; no database migrations.

Prevent circular imports by defining service interfaces and event schemas now. For each shared model field needed by the other workstreams, put it in the baseline models and API_CONTRACT.md; do not make those agents invent their own incompatible versions. Establish a clearly documented strategy for injecting a publisher and calling the incident engine after telemetry ingestion. If exact API schema ambiguities remain, document one explicit decision in API_CONTRACT.md and flag it for team review.

Run dependency installation, django checks, migrations and baseline tests in your workspace. Do not claim passing tests if a command failed. Return a concise summary: files created, commands run and results, base commit hash, decisions made, and the exact foundation commit the four worktrees should use. Do not start the four feature sessions or merge their future work yourself. The human integrator will merge `establish-foundation` to `main` first.
```

---

## Prompt A — Build Django APIs (`build-apis`)

```text
You are the backend API engineer working on branch `build-apis`, implementing the Django data/API layer for Code Fuzion 2026 H7. Read back_end.md, front_end.md and API_CONTRACT.md from this checkout. Use the existing foundation models and paths; don't rewrite architecture or invent incompatible schemas.

YOUR EXCLUSIVE FILE OWNERSHIP: backend/monitoring/views.py, serializers.py, urls.py, selectors.py, models.py if carefully necessary, its migrations and tests for REST/persistence; backend/worker_api/**. Do NOT modify vision/**, services/risk.py, services/incidents.py, monitoring/consumers.py, config/routing.py or the frontend. Avoid editing root requirements without a strong reason; report needed dependencies instead. If another workstream's interface does not exist, use clear imports/stubs and state the integration dependency rather than silently implementing its logic.

Implement validated, authenticated APIs matching the spec:
GET /api/dashboard/ including feeds, latest metrics, all active critical incidents, event cursor and server time; GET/POST /api/feeds/; POST /api/feeds/upload/; GET/PATCH/DELETE /api/feeds/{id}/ with incident-safe deletion; PUT /api/feeds/{id}/calibration/; GET /api/events/?cursor=...; GET /api/incidents/active/; GET /api/incidents/{id}/; POST /api/incidents/{id}/acknowledge/ (calls the authoritative incident service; does NOT resolve); POST /internal/telemetry/ and POST /internal/worker-heartbeat/ with worker-only credentials.

Use UTC timestamps, safe upload validation, explicit error responses, authorization, stable IDs, and read-model performance suitable for rapid dashboards. Never expose RTSP credentials, worker keys or private local file paths to browser responses. Session/CSRF can protect operator routes; worker credential must never appear in JS. The telemetry ingestion endpoint should call the risk/incident service interface defined by the foundation/`predict-risk` rather than duplicate risk decisions. Publish events via `stream-events` service interface after successful persistence. Do not invent detector measurements in production.

Write focused API and model tests including refresh restoring pinned incidents, idempotent acknowledgement, deletion blocked for active incidents, invalid calibration, worker auth rejection, replayed telemetry sequence and safe upload handling. Run tests and system checks. Commit only your owned files on this worktree branch and report commit hash, endpoints implemented, tests/results, unresolved integration points. Do not merge.
```

---

## Prompt B — Process video feeds (`process-feeds`)

```text
You are the computer-vision engineer working on branch `process-feeds`, implementing the Python computer-vision worker for Code Fuzion 2026 H7. Read back_end.md, front_end.md and API_CONTRACT.md. The worker must process real video, not synthetic counters. Match the published internal telemetry schema exactly.

YOUR EXCLUSIVE FILE OWNERSHIP: vision/**, benchmarks/**, fixtures/README.md and tests within vision. Do not edit Django models, REST, Channels or frontend files. Report dependency requirements rather than unexpectedly changing shared root files.

Build independent two-source video processing using bounded frame buffers, timestamped OpenCV capture, fair inference scheduling/worker isolation, clear end-of-video/reconnect handling, actual YOLO person detection, Roboflow supervision Detections and zone utilities, and optional supported tracking (check current trackers API; do not assume obsolete sv.ByteTrack). Keep per-camera trackers and zones independent. Implement a transparent frame-to-ground homography using known real-world four-point correspondence, meaningful zone area in m², foot-point zone membership, per-zone count, density, measured processed FPS, confidence/freshness and a telemetry publisher with retries/backoff and no unbounded queue growth. Count a person consistently and avoid counting the same tracked person multiple times within a single zone. Make calibration required before reporting calibrated density; uncalibrated readings must be marked invalid rather than guessed.

Supply a CLI to process two distinct MP4s (and configured supported camera sources if practical) on laptop CPU, with flags for model, resolution, frame pacing and telemetry URL. Provide a local demo path without live cloud dependencies. Include offline benchmark logic: read manual per-frame ground truth, report absolute percentage count errors on nonzero counts, explicit handling of zero-count frames, per-feed FPS and combined performance. Record actual results only after execution on real clips; if real clips are unavailable, keep the benchmark runnable and clearly say unmeasured. Provide unit tests for homography, zone membership and invalid calibration plus smoke tests with a mocked detector, but do not confuse mock tests with the hackathon accuracy result.

Run tests, commit your owned worktree files and report reproducible commands, actual FPS/errors if measured, limitations on overlapping crowds and required integration changes. Do not merge.
```

---

## Prompt C — Predict risk and manage incidents (`predict-risk`)

```text
You are the crowd-intelligence engineer working on branch `predict-risk`, implementing backend crowd-intelligence domain services for Code Fuzion 2026 H7. Read back_end.md and API_CONTRACT.md; consult front_end.md only for API/WS contracts. Do not create or edit frontend code. Critical incident semantics take priority over UI convenience. You must not alter database models/migrations, API routes, Channels consumers or vision code; use the foundation's declared model and publisher interfaces and report any missing fields explicitly.

YOUR EXCLUSIVE FILE OWNERSHIP: backend/monitoring/services/risk.py, incidents.py, telemetry.py, calibration.py as appropriate, and focused service tests owned by you. Do not modify the publisher service owned by `stream-events` or Django endpoints/models owned by `build-apis`.

Implement authoritative validation and processing for calibrated timestamped observations, density people/m², smoothed trends from actual elapsed time, prediction horizon and configured severity thresholds. Use explicitly configurable demonstration thresholds—not ungrounded public-safety standards. Add hysteresis to avoid severity flapping, stable risk ordering and debounced warnings. Ensure stale or uncalibrated measurements never imply safety. Use transactional incident state changes: CREATED/ACTIVE UNACKNOWLEDGED -> ACTIVE ACKNOWLEDGED -> backend-confirmed RESOLVED; allow valid recovery directly from unacknowledged if policy permits. No acknowledgement action may resolve, downgrade or unpin. Never resolve while offline/stale. Require a sustained sequence/window of calibrated safe observations to resolve; record actor/time for ack, state versions and reason/metrics for event audit. Support multiple simultaneous incidents by stable incident ID, one active episode per feed as proposed in the spec. Repeat telemetry must not create duplicate incidents; acknowledgement must be idempotent; a subsequent critical episode after resolution must get a new ID. Persist the state before broadcasting via a publisher interface and transaction.on_commit where suitable.

Service contract should make incident.created, incident.acknowledged, incident.updated, incident.resolved observable to the realtime layer and initial dashboard snapshot. Tests are essential: create critical; acknowledge only silences alarm; still pinned after ack/reload; cannot navigate with other unacknowledged incidents; recovery below exit threshold sustained; one safe frame not sufficient; offline/stale cannot resolve; multiple concurrent incidents; duplicate telemetry; reconciliation after missed WebSocket events. Implement without storing browser UI flags as backend business truth.

Run tests, commit only owned worktree files, report entry points, tests/results, policy defaults, migration assumptions and integration blockers. Do not merge.
```

---

## Prompt D — Stream backend events (`stream-events`)

```text
You are the real-time backend engineer working on branch `stream-events`, implementing realtime delivery and schema conformance for Code Fuzion 2026 H7. Read back_end.md and API_CONTRACT.md; consult front_end.md only for API/WS contracts. Do not create or edit frontend code. Work from the committed foundation interfaces; don't independently reinvent API paths or incident states.

YOUR EXCLUSIVE FILE OWNERSHIP: backend/monitoring/consumers.py, backend/config/routing.py (and ASGI connection only if required and coordinated), backend/monitoring/services/publisher.py, dedicated websocket/contract tests, and an integration-verification checklist under docs/. Do not edit Django models/migrations, `build-apis` REST layer, `predict-risk` risk/incident services, vision/** or frontend/**.

Implement authenticated, authorized /ws/dashboard/ using Django Channels. Use a common envelope {type,event_id,sequence,timestamp,feed_id,payload}; support dashboard.snapshot/feed.added/feed.removed/feed.status_changed/feed.metrics_updated/feed.calibration_changed/alert.created/alert.updated/incident.created/incident.acknowledged/incident.updated/incident.resolved/system.heartbeat as documented. Support stable ordering/monotonic sequence or a clearly documented event cursor, subscription lifecycle and reconnect/snapshot rehydration. Never silently drop incident lifecycle events while throttling/coalescing routine metric updates. Limit frame-level broadcasts so the dashboard doesn't flood. On reconnect the source of truth must come from durable DB-backed REST snapshot, not an in-memory WebSocket cache. For deployment, keep in-memory channel layers limited to the single-process local demo; document Redis if separate ASGI processes require it.

Write integration contract tests that connect as an authorized browser, reject unauthorized connections, receive correct event structures, preserve acknowledgement versus resolution, restore active incidents after refresh/reconnect, handle multiple active incidents, and validate event schemas against fixtures/contract. No hard-coded sample critical metrics in production. If provider services from other worktrees are not yet merged, use clean dependency injection or contract test doubles rather than changing their files.

Run tests, commit only owned worktree files, report exact test command, event formats, remaining integration assumptions and commit hash. Do not merge.
```

---

## Prompt E — Integrate the backend (after reviewing and merging all four workstreams)

```text
You are the H7 backend integration reviewer. This is the backend integration branch or `main` after four separate worktree branches have been reviewed and merged. Read back_end.md, front_end.md and API_CONTRACT.md. Do not rewrite the entire architecture or hide errors with mocks. Audit actual endpoints/serializers/models; validate that the independent computer-vision worker can send authenticated telemetry and the Django backend processes it via authoritative density/trend/incident services and emits ordered Channels events. Check that the backend REST/WS contracts agree with the read-only `front_end.md` handoff and provide a concrete contract discrepancy report. Do NOT implement or modify frontend code.

Run migrations/checks, Django/pytest unit and integration tests, websocket contract tests, and a true simultaneous two-feed test with real video if available. Verify invalid/unavailable video fails honestly, per-feed FPS is measured, calibrated people/m² comes from real-world camera calibration, warnings derive from time trends, and count accuracy compares against manually annotated ground truth. Do not claim H7 targets met without measurement. Verify server-side snapshot and events continue to mark a critical incident as pinned after acknowledgement and reconnection, and only indicate unpin eligibility after sustained valid recovery. The browser pinning/navigation UI itself belongs to the frontend developer. Loss of video must not auto-resolve it. Evaluate security of worker credentials, uploads, operator auth and accidental secret exposure; verify README lists actual startup and deployment commands.

Fix only necessary integration defects. Provide commands, measured metrics or explicit 'not measured', full checklist with pass/fail, technical risk list for judges' hidden tests, and concise viva explanation for each core service. No simulated production metrics or silent fake demos.
```

---

## Create and name worktrees (Windows PowerShell)

You can create these worktrees explicitly before opening Copilot sessions in them. Run commands in the repository's root folder **after** `establish-foundation` is committed and merged into `main`, with a clean working tree.

```powershell
# Foundation branch, before the foundation prompt
git switch -c establish-foundation
# Run Prompt 0, inspect changes, then commit
git add .
git commit -m "build: establish shared backend foundation"
git switch main
git merge --no-ff establish-foundation

# Four isolated worktrees for concurrent Copilot sessions
git worktree add -b build-apis ..\crowd-fuzion-build-apis main
git worktree add -b process-feeds ..\crowd-fuzion-process-feeds main
git worktree add -b predict-risk ..\crowd-fuzion-predict-risk main
git worktree add -b stream-events ..\crowd-fuzion-stream-events main

git worktree list
```

Open each worktree folder in its own VS Code Copilot session. Alternatively, if the VS Code Agents window creates and names the worktrees automatically, rename **each worktree's checked-out branch inside that worktree's own terminal** using `git branch -m build-apis` (or its corresponding name) before prompting. Never create two worktrees on the same branch or rename `main`.

## Integration commands (PowerShell; exact approved branch names)

```powershell
# Verify main is clean and inspect available branches
 git status
 git branch --all

# Integrate one reviewed branch at a time
 git switch main
 git merge --no-ff build-apis
 git merge --no-ff predict-risk
 git merge --no-ff stream-events
 git merge --no-ff process-feeds

# Run comprehensive checks from the correct Python environment
 python -m pip install -r requirements.txt
 python backend/manage.py check
 python backend/manage.py migrate
 python -m pytest
```

Keep these names consistent with the worktrees and prompts. If VS Code created other branch names, rename them inside their worktrees before merging. If there is a conflict, do not blindly run `git checkout --ours .` or discard changes; inspect each file and reconcile the contract. Keep `main` deployable and use feature branches/PRs when convenient. Run required pre-commit checks explicitly; VS Code's auto-commit may bypass hooks.

## Critical finish line

- [ ] Two genuinely concurrent video feeds, with separately measured processed FPS
- [ ] YOLO/Roboflow Supervision processing with actual predictions, not mocked in demo
- [ ] Valid calibration and real-world per-zone people/m²
- [ ] Valid time-series forecasting and configurable risk policy
- [ ] Critical incident persists after acknowledgement, browser refresh and backend reconnect
- [ ] Offline/stale data never auto-resolves an active incident
- [ ] Only sustained valid recovery resolves and unpins it
- [ ] REST and WebSocket schemas match frontend docs
- [ ] Held-out counting-error benchmark and genuine FPS results (or transparent failure/unknown)
- [ ] Deployed Django backend and reproducible vision-worker setup; no hard-coded private credentials
- [ ] All four backend workstreams are reviewed, tested and integrated before submission

## Official workflow references

- VS Code Agents window: https://code.visualstudio.com/docs/agents/run/agents-window
- Parallel agent sessions/worktrees: https://code.visualstudio.com/docs/agents/concepts/sessions
- Git worktrees in VS Code: https://code.visualstudio.com/docs/sourcecontrol/branches-worktrees
- VS Code subagents: https://code.visualstudio.com/docs/agents/run/subagents
