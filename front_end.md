# FRONT-END DESIGN & INTEGRATION BRIEF
## Code Fuzion 2026 · H7 — Crowd Density Alert for Campus Fests

**Document type:** Design and frontend-behavior specification for a designer/development agent  
**Status:** Proposed interface blueprint · revised project-context and interaction specification (v1.2); not a description of an existing product  
**Intended handoff:** Frontend designer / frontend coding agent  
**Product role:** A live, multi-camera crowd-risk monitoring dashboard used by campus event volunteers and organizers  
**Backend context:** Django + Django Channels; Python video processing with YOLO, OpenCV, and Roboflow Supervision

---

## Project context — essential briefing for the frontend agent

### What project are we building?

This is the interface design brief for **H7 — Crowd Density Alert for Campus Fests**, the team's **current active hackathon project** for **Code Fuzion 2026**, a **24-hour college hackathon** organized by Student Organisation Vizion Forge at Lovely Professional University. H7 is categorized as a **Hard** engineering problem. The official problem statement is the product source of truth; this file translates its intent into a frontend design and integration handoff.

**Problem to solve:** During crowded campus events, people gather around gates, entrances, exits, food courts, and other bottlenecks. Volunteers often notice congestion only after it has already become dangerous. The system is intended to make rising crowd pressure visible early enough for organizers to intervene. In this project, **“traffic” means movement and concentration of people, not road-vehicle traffic**.

**Product concept:** A browser-based **live crowd-monitoring control room** where authorized volunteers can add and monitor camera/video feeds, immediately identify high-risk crowd zones, inspect the evidence behind an alert, acknowledge warnings, and track whether a critical situation has actually recovered. This is an operational interface, **not** a marketing page, a general-purpose CCTV archive, or an AI chatbot.

### Who uses it and what decisions do they make?

- **Primary user — event volunteer or security/control-room operator:** watches multiple crowd zones at once, identifies the riskiest area, opens a feed for closer inspection, acknowledges an alarm, and coordinates an intervention.
- **Secondary user — event organizer/supervisor:** reviews active incidents and chronological logs, understands which zones are becoming more crowded, and verifies that risk has reduced after action is taken.
- **Technical/setup user:** adds feed sources, labels locations (e.g., Main Gate / Food Court), calibrates a camera's monitored ground area, and checks stream/model health.

The interface should support decisions such as **“Which zone needs attention now?”**, **“Is density still rising?”**, **“Has someone acknowledged this?”**, and **“Is the situation truly resolved?”** The interface is decision support; human event staff handle real-world crowd interventions.

### Official H7 requirements and why the layout must expose them

The following are **system-level acceptance requirements from the official Code Fuzion 2026 H7 statement** (not promises that this prototype already meets them):

| Official requirement | Implication for the frontend design |
|---|---|
| Person counting on **at least 2 simultaneous video feeds** using a laptop CPU or free GPU | Design the feed grid and detail pages for concurrent streams, clear camera identifiers, and individual feed-health indicators. |
| Density **per zone in people/m²** using a **camera-calibration step** | Surface calibrated zone names, actual area units, calibration status, and a clear “not calibrated / density unavailable” state. |
| **Early warning from crowd trend**, not only current count | Show direction and rate of change, approaching-threshold warnings, short trend history, and predicted risk without presenting forecasts as fact. |
| **Under 20% count error at 5+ processed frames/second** | Leave space for per-feed measured processing FPS and evaluation/diagnostic indicators. Do not confuse rendered video FPS with inference FPS or claim an accuracy figure without a real test result. |
| Hidden inputs and live measurement during judging | Do not hardcode demo numbers or assume a fixed feed count, video filename, zone geometry, density range, or permanent network connection. |

Code Fuzion's Hard challenges can receive an **additional requirement at hour 12**. Keep the component system modular enough to accommodate one added control, status, or information field. The judging emphasizes hidden-test performance, technical depth, the team's ability to explain the code, usability, and a live demo. Treat visually polished but fabricated metrics as a failure, not a shortcut.

### Chosen technology and where the frontend sits

The team plans to use the following stack. **These are architectural intentions, not claims that all services have already been implemented or deployed.**

| Layer | Planned technology | Responsibility |
|---|---|---|
| Detection | **YOLO** in Python | Detect people in each video frame. |
| Video processing and spatial geometry | **OpenCV / NumPy** | Read feeds, handle frames, and support camera-ground calibration. |
| Detection/tracking utilities | **Roboflow Supervision** (plus an appropriate tracker) | Normalize detections, manage polygons/zones, support tracking and annotations. Supervision is not itself the person-detection model. |
| Metrics and incident logic | **Custom Python services** | Compute counts, zone density, trends, warning severity, alert creation and **backend-confirmed resolution**. |
| Backend | **Django + Django Channels** | Feed registration, authenticated APIs, logs, incident acknowledgement, and real-time data updates. |
| Frontend | **Browser UI with JavaScript** | Arrange and play supported feeds; visualize live measurements, severity, incident state, logs, details, and operator actions. |
| Deployment model (proposed) | **Hosted Django frontend/API + local or hosted vision worker** | Publish a reachable dashboard while allowing compute-heavy video processing to run where hardware is available. |

**Data flow:** `Video sources → Python detector / tracker / calibration / crowd-analysis worker → Django API + WebSocket events → monitoring dashboard`. The frontend does **not** run model inference by default, establish safety thresholds itself, or declare a critical incident resolved on its own. Exact endpoint names, payload schemas, auth, and stream delivery mechanisms appear later in this document as **proposed integration contracts** to agree on with the backend team.

### Central operating scenario (design around this)

1. An operator registers several camera or video sources. The dashboard fills a responsive **risk-ranked grid**; a permanent **right-side activity log** shows events across all sources.
2. Each card has a gentle severity-colored edge (**green, yellow, orange, red**) and a concise live status. **Hovering or keyboard-focusing** reveals detailed current metrics. **Clicking** opens that feed's **full-page** monitoring route.
3. A gate becomes **critical** as its assessed crowd condition crosses configured criteria or a qualifying prediction triggers an incident. That feed becomes most prominent in the grid, appears in a **persistent global side dock**, and starts an audible/visible warning subject to browser audio policy.
4. Until the critical incident is **acknowledged**, the operator cannot navigate to unrelated pages **inside this app**. They can still inspect the danger, review logs, acknowledge it, and access response-critical controls.
5. **Acknowledgement only silences the incident's alarm and releases its navigation restriction** (assuming no other unacknowledged critical incident). It does **not** mark people safe, change the critical badge to green, or hide/unpin the feed.
6. The pinned feed remains visible **across app routes, refreshes, and normal navigation**, even after acknowledgement. It is automatically **unpinned only on authoritative backend-confirmed resolution following actual sustained crowd recovery**. A brief count dip, lost connection, or manual close must not resolve it.
7. If multiple critical zones exist, each has a distinct acknowledged/resolved state. The global critical dock continues representing **every unresolved critical incident**.

### Scope, terminology, and design integrity

- **A feed** is a registered video source. **A zone** is a calibrated region within a feed. A **count** is a model estimate for a feed/zone, not necessarily a unique count of event attendees. Two overlapping feeds may see the same person.
- **Density** is measured as people per square metre of the calibrated ground region, not pixels covered by detection boxes. **Risk/severity** is an assessed status supplied by backend logic, not determined purely by card color or raw headcount.
- **Critical active**, **acknowledged**, and **resolved** are three different concepts. An incident can be **critical + acknowledged + still active**. The interface must visually preserve this distinction.
- **Offline/stale/unknown** is not “normal” or “resolved.” Always show an explicit neutral/error monitoring state, and preserve unresolved incidents despite stream problems.
- This frontend specification concerns **layout, visual hierarchy, user interactions, and integration expectations**. It does **not** instruct the frontend agent to build or train the detection model, invent safe-density thresholds, implement the Django backend, or represent mocked measurements as live facts.
- The product is a **hackathon prototype and decision-support tool**, not a certified emergency-safety system. Avoid UI copy implying that predictions are guaranteed or that an acknowledgement means the crowd has been physically managed.

---

## 0. Assignment and boundaries

Design the **layout, visual treatment, component hierarchy, interactions, responsive states, and frontend integration interfaces** of a real-time crowd monitoring webpage. This document is **not a request to implement the finished system**, a detector, a Django backend, or a machine-learning model. Its purpose is to tell a frontend agent *what the page should look and behave like*, and exactly what browser-side data/API contracts it will eventually need.

Create a confident, information-dense, professional **operations dashboard** rather than a generic admin template, landing page, or flashy sci-fi visualization. The central interface must make it possible to answer in seconds:

1. **Which camera area is most dangerous right now?**
2. **How quickly is its crowd density changing?**
3. **Which other areas need attention?**
4. **What event just happened, and where?**
5. **Is a feed live, stale, offline, still calibrating, or being analyzed?**
6. **Which critical incident must be acknowledged, and which critical feeds must remain visible until recovery?**

### Non-negotiable visual requirements

- Display **any number of user-added video feeds** as responsive cards within a central grid.
- **Rank feeds from highest danger to lowest danger, top-left to bottom-right** by default; the riskiest feed must be the first and most prominent item.
- Surround each video card with a **subtle, controlled colored border/glow** representing its severity: **red → orange → yellow → green** from most to least concerning.
- Keep a **dedicated tall event-log panel on the right side** on desktop, showing chronological events across all feed points (increasing crowds, threshold approach/crossing, connection changes, alerts, recovery).
- Include a visually clear **Add feed** action through which users can provide a video input/source.
- Show **real measurements and provenance states**, not fake guarantees or hardcoded “AI accuracy” claims.
- **Hover or keyboard-focus a feed to reveal its current detailed statistics.** Clicking the card opens a **dedicated full-page feed view**, not a modal.
- If **any critical incident is active and unacknowledged**, block switching to non-critical feeds or unrelated pages **within this web app**, while allowing access to the critical feed, incident log, acknowledgement, and response actions.
- **Acknowledge = silence that incident's warning sound + unlock permitted in-app navigation; it does NOT resolve the incident or remove the persistent critical-feed mini-view.**
- A **persistent side-pinned critical feed** must remain visible across app pages and routes, even after acknowledgement. The system **automatically unpins only after the backend confirms the crowd incident has been managed/resolved**; there is no manual hide/unpin while active.
- Multiple simultaneous critical feeds are separate incidents: each remains represented in the persistent critical-feed dock until its own confirmed resolution.

The actual detection, tracking, density calibration, forecasting, and severity assignment are backend/vision responsibilities. Frontend must present the results accurately, not independently invent crowd-safety conclusions.

---

## 1. Visual identity and design direction

**Visual metaphor:** an event security/control-room workspace with elegant monitoring instrumentation.

- **Default theme:** deep charcoal / near-black, with carefully layered slightly lighter surfaces. Avoid pure-black-on-neon, excessive gradients, glass everywhere, or thick colored outlines.
- **Personality:** precise, calm, serious, glanceable. Critical alerts should command attention without making the whole interface flash.
- **Typography:** use a legible modern sans-serif (e.g., Inter, Geist, or equivalent); use tabular numerals for counters, percentages, density, FPS, and timestamps. Hierarchy should be clear at a glance.
- **Spacing:** consistent 8px spatial rhythm; 12–16px card padding; 16–20px gaps; restrained rounded corners (~12–16px).
- **Depth:** subtle surface contrast, very soft elevation, hairline separators. Prefer visual clarity over decorative gradients.
- **Motion:** understated transitions on hover, live values, and alert emergence. Respect `prefers-reduced-motion`. Do not continuously pulse every red card.
- **Responsiveness:** design desktop-first for control-room use, then elegantly adapt to laptop, tablet, and mobile.

### Suggested UI color tokens (proposals, not hard requirements)

| Token | Suggested color | Usage |
|---|---|---|
| Page background | `#0B1018` | Overall canvas |
| Primary surface | `#121A26` | Video cards, right log panel |
| Raised surface | `#182231` | Toolbar, menus, prominent hover states |
| Border neutral | `#29364A` | Standard boundaries and separators |
| Text primary | `#F1F5F9` | Headlines and key data |
| Text secondary | `#9CAABD` | Labels, supporting context |
| Critical | `#EF4444` | Red: active or imminent critical crowd condition |
| High | `#F97316` | Orange: serious congestion / rapid growth |
| Elevated | `#EAB308` | Yellow: attention required |
| Normal | `#22C55E` | Green: below configured warning criteria |
| Unavailable | `#64748B` | Grey: unknown, offline, uncalibrated, or no data |
| Accent | `#60A5FA` | Primary buttons, links, focused inputs (not danger levels) |

Severity color must be applied **consistently** to video-card perimeter, status badge, alert icon, and relevant log marker. Use a soft outer glow at low opacity, not a harsh halo. Each severity **also needs a text label and icon** so it is distinguishable without color perception.

**Critical semantic distinction:** An **unknown** or **uncalibrated** camera is not green. Show an explicit grey “Not assessed”, “Calibration required”, “Offline”, or “Waiting for data” treatment until a valid condition is available.

---

## 2. Page anatomy / desktop layout

### Overall arrangement

Target initial design at **1440 × 900** and **1920 × 1080**. The page should fill the viewport while allowing contained panels to scroll independently when useful.

```text
┌───────────────────────────────────────────────────────────────────────────────────────┐
│  LOGO / CROWDWATCH         LIVE ●  | Event / Venue | Time   Add Feed   Settings/User  │
├───────────────────────────────────────────────────────────────────────────────────────┤
│  [Active Feeds] [Critical Zones] [Total People*] [Fastest Rising Zone] [System Health]│
├──────────────────────────────────────────────────────────────┬────────────────────────┤
│  FEEDS / LIVE MONITORING                                     │  ACTIVITY & ALERT LOG  │
│  Sort: Highest danger ▾  Filter ▾  Grid density ▾            │  All  Critical  System  │
│                                                              │  ────────────────────  │
│  ┌──────────────────────────┐ ┌──────────────────────────┐    │  20:16  GATE A          │
│  │ ● CRITICAL · GATE A      │ │ ● HIGH · FOOD COURT     │    │  Density rising ...    │
│  │                          │ │                          │    │                        │
│  │       VIDEO FEED         │ │       VIDEO FEED         │    │  20:14  FOOD COURT      │
│  │  subtle RED edge/glow    │ │  subtle ORANGE edge     │    │  High growth ...       │
│  │                          │ │                          │    │                        │
│  │  83 people  1.9/m² ↗    │ │  54 people  1.2/m² ↗    │    │  20:12  GATE C          │
│  └──────────────────────────┘ └──────────────────────────┘    │  Status normal ...     │
│                                                              │                        │
│  ┌──────────────────────────┐ ┌──────────────────────────┐    │  [Scrollable timeline] │
│  │ ● ELEVATED · GATE C      │ │ ● NORMAL · ENTRY B      │    │                        │
│  │       VIDEO FEED         │ │       VIDEO FEED         │    │                        │
│  │  subtle YELLOW edge     │ │  subtle GREEN edge      │    │                        │
│  └──────────────────────────┘ └──────────────────────────┘    │  [Pause auto-scroll]   │
│                                                              │                        │
└──────────────────────────────────────────────────────────────┴────────────────────────┘
```

*Totals must be labeled carefully: adding counts from overlapping camera views may double-count people. If overlap is not resolved by the backend, say “Detections across feeds,” not “unique people.”

### Suggested page regions

1. **Top app bar (about 64–72px):** project mark / concise name on the left; center or right compact real-time connection indicator and currently selected event; right side Add Feed, settings, and optional user controls. Avoid overloading the header.
2. **Overview KPI strip (optional but recommended, about 92–110px):** four or five compact information tiles. At minimum: active feeds, critical zones, fastest-rising zone, and monitoring-system health. Keep these secondary to the feed grid.
3. **Main content area (dominant area):** flexible **video grid occupying about 70–76%** of remaining width at typical laptop/desktop sizes.
4. **Right activity rail (about 320–390px desktop width):** fixed visual column within the main workspace, full available height, internally scrollable chronological event stream.
5. **Global critical-incident dock (conditionally visible):** a persistent mini-feed strip attached to the **application shell**, not to an individual page. It must coexist with the desktop right-hand activity log without covering essential controls. Place it in a reserved edge area (such as a compact dock adjacent to / above the log rail) or use a thoughtfully offset overlay. On all routes, the dock follows the user until verified recovery.
6. **No oversized promotional hero, welcome artwork, or long paragraphs** in the active monitoring view.

At ~1280–1440px, use **two video columns** in the remaining grid width. At very wide desktop sizes (~1700px+), allow **three columns if cards remain comfortably readable**. Avoid shrinking feed cards to fit an arbitrary number. Each video area should generally maintain **16:9** aspect ratio.

---

## 3. Video feed grid: core visual priority

### Grid sorting and placement

- Default sort label: **“Highest danger first”**.
- The first card, at **top-left**, represents the **highest-risk assessed zone**, followed left-to-right and top-to-bottom in descending danger.
- **Do not rank solely by raw person count**: a camera covering a small gate with 35 people may be riskier than a huge courtyard with 90 people. Primary sort by backend-supplied severity/risk score; use forecast urgency, density, and measured count as secondary tie-breakers.
- Recommended severity order: **Critical (red) > High (orange) > Elevated (yellow) > Normal (green)**. Unknown/unassessed feeds should appear in a separate last group with neutral grey, **not** artificially scored as safe.
- New metrics may arrive many times per second. **Do not physically re-order tiles on every update.** Use a short, predictable sort cadence (e.g., every 3–5 seconds), and animate position changes briefly only when they matter.
- A user who is watching a feed in detail should not lose it when rankings change. Allow **pinning/focusing** the selected feed while preserving an always-visible severity label; a pin is a user preference, not a change to the actual risk ranking.
- Provide optional controls for “Highest danger”, “Highest density”, “Fastest rising”, “Name”, and a feed search/filter. Default to danger.

### Anatomy of one feed card

Each card should feel like a dedicated camera-monitoring module with three layers:

**A. Card header (top):**
- Human-friendly feed name and a short location descriptor: e.g., “North Gate”, “Food Court East”.
- Severity indicator: colored dot/icon + **Critical**, **High**, **Elevated**, **Normal**, or **Unknown**.
- Live status text such as **LIVE**, **RECONNECTING**, **OFFLINE**, **PAUSED**, or **FILE REPLAY**. Avoid using “LIVE” for uploaded files under replay.
- Small overflow / expand action. If space is limited, collapse secondary labels into a detail drawer.

**B. Video viewport (central, 16:9):**
- The actual video fills the media area without arbitrary stretching (`contain` or carefully chosen cropping). Camera frames may have different aspect ratios; do not crop away dangerous edges without a choice.
- Optional translucent overlays: bounding boxes around people, zone polygons, count labels, camera timestamp, detection confidence when needed. These overlays should be toggleable to reduce clutter.
- An unobtrusive corner badge showing stream state or input type.
- **Hover or keyboard focus opens a transient statistics overlay** over the feed: current count, calibrated density, trend/growth rate, predicted time to risk threshold (if available), risk level, timestamp/freshness, and processing FPS. Put the stats in a readable translucent panel; avoid blanketing the entire video. On touch, provide a visible **Stats** action and/or first-tap preview. Show “Unavailable / Not calibrated / Stale” instead of invented values.
- Hover also reveals unobtrusive expand, pause-preview and overlay toggles. The feed card remains keyboard-operable. A pause of **local preview** must not silently stop backend monitoring.
- Video loading, stream error, permissions denied, and insufficient frames should have deliberate fallback visuals, not a blank black rectangle.

**C. Card footer (compact telemetry band):**
- **People count** (whole number, recent measurement).
- **Density** in **people/m²**, prominently indicated where calibrated.
- **Trend**: rising, falling, stable, or insufficient history; directional arrow with accessible text.
- Optional small sparkline / 1–5-minute mini-trend if room allows.
- **Last updated** (“2s ago”) and optionally measured **processing FPS** in a compact details/diagnostics region.
- For insufficient calibration, replace density with **“Calibration needed”** rather than displaying an invented 0/m².

### Severity-border treatment

The requested red/orange/yellow/green glowing border should be the signature visual feature:

- **Critical/red:** clear red hairline with a soft red outer bloom; may briefly intensify when a *new* critical state first begins.
- **High/orange:** warm orange hairline with softer glow.
- **Elevated/yellow:** restrained amber edge.
- **Normal/green:** faint green edge, intentionally subtle to keep high-risk items visually dominant.
- **Unknown/offline/uncalibrated:** neutral grey edge, no green visual assertion.
- Keep shadows clipped well outside the video content so they do not obscure footage; maintain usable contrast against the dark page.
- Use a consistent 1–2px border and low-opacity glow. **Never use constant aggressive pulsing** as the main status indicator.

### Feed-card interactions

- **Click / Enter:** navigate to a **dedicated, full-viewport feed page** (suggested app route `/feeds/{feed_id}/monitor`), not a popup or modal. The full-page view emphasizes the video and provides adjacent real-time statistics, risk history, calibration/diagnostic detail, and that feed's recent logs.
- If any critical incident remains unacknowledged, clicking a **different, non-critical feed** or attempting to open an unrelated page must trigger a navigation guard. The guard offers **“View critical feed”** and **“Acknowledge danger”**; do not silently switch views. The operator must still be able to access emergency-response controls.
- When a critical feed is the focused full-page feed, keep it represented by the global pinned dock (a compact docked representation can avoid visual duplication); if the operator visits another permitted page after acknowledging, the critical live mini-feed continues to be visible.
- **Pin:** temporarily keep a feed in a watch position; make pin state visually explicit.
- **Add/Remove feed:** manages a camera source through a deliberate dialog; removal prompts confirmation if this stops active monitoring.
- **Failure:** retain card location with an error state, retry action, last-known good telemetry labeled as stale, and last successful update time.
- **Trend alert:** new danger status should appear as a brief toast *and* a persistent log entry. Avoid repeated toasts for each metric sample.

---

## 3A. Full-page feed monitoring view (mandatory click destination)

**Interaction contract:** hover/focus shows a compact, live statistics preview; **clicking/pressing Enter on the feed card navigates to its own full-page monitoring view.** Do not substitute a lightbox, expandable card, or standard modal for this primary action.

### Layout of the full-page view

- Keep the **global app header** and any active **critical-incident dock** visible, so the operator always retains situational awareness and route navigation rules.
- Use the **largest practical video canvas** (roughly 65–75% of the content width on wide displays), ideally 16:9 with controls over or just below it. Never stretch or crop away peripheral people without a visible fit-mode choice.
- Place an adjacent **live-statistics column** containing a large person count, people/m², current severity, density trend, growth rate with units, predicted limit crossing, last metric timestamp, stream status and actual inference FPS. Use “not available” or “uncalibrated” explicitly when relevant.
- Beneath the video or in collapsible lower panels, show **density history/mini chart, zone map/calibration, camera diagnostics, and feed-specific event history**. Keep the most time-sensitive information above the fold.
- Provide a **Back to all feeds** control that honors the critical-incident navigation guard; if a critical incident is unacknowledged, explain why switching away is restricted and show acknowledgement controls.
- On small screens, video first, stats second, logs/history below; the critical dock remains fixed and accessible without covering the acknowledgement control.
- The full-page view is **live**, not a still-frame details screen. It must work on direct URL loads and after browser refresh by loading authoritative feed and incident state.

### Hover / focus statistics panel

- Reveal a coherent **hover card inside or slightly above the video tile** with the latest verified measurements: **count, density, trend, growth rate, risk/critical state, forecast (if available), FPS, and last update**.
- Appearance: smooth 100–150ms fade/translate (or no motion with reduced-motion), legible dark surface, compact two-column metric arrangement, no excessive blur. Never obscure the feed's critical-status label.
- **Data is live while hovered:** updates reflect the same central feed store as the base card, without an extra HTTP request on every pointer movement. Include staleness age; never show last-known values as current.
- **Mouse, keyboard and touch parity:** `pointerenter`/`pointerleave` or CSS `:hover`, `focusin`/`:focusout`, and a visible **Stats** control for touch. Clicking the card opens the full page; clicking an action inside the hover panel only triggers that action. Support Escape to dismiss an explicitly opened panel.

## 3B. Critical-feed persistence, acknowledgement and navigation lock (mandatory safety behavior)

**Three different concepts — never conflate them:**

1. **Critical active, unacknowledged:** backend has declared a critical incident; frontend shows prominent warning, attempts an audible warning if browser audio is enabled, **pins the feed immediately**, and **guards in-app feed/view switching** until the incident is acknowledged or resolved.
2. **Critical active, acknowledged:** operator acknowledges **that specific incident**. Its warning sound stops and app navigation unlocks **only if no other unacknowledged critical incidents remain**. The persistent critical mini-feed **remains pinned, visually red and visible on every app route**. Acknowledgement is **not** a safety clearance.
3. **Managed/resolved:** backend publishes an **authoritative `incident.resolved`** event after the system's configured recovery criteria are met (such as density remaining below a recovery threshold over a validated observation window). **Only then** does the frontend automatically remove that incident's pinned mini-feed and clear its active critical state. A transient low reading, frontend tab change, browser refresh, or sound mute **must not** unpin it.

### Global critical incident mini-feed dock

- The dock lives in the **persistent root application layout**, outside route-specific page components. It is visible on **dashboard, full-page feed view, settings, log view and any other internal route**.
- For each active critical incident, show a **small continuously updating preview**, feed name/location, red CRITICAL label, count or density (if calibrated), trend, last updated, and incident acknowledgement status. Clicking the mini-feed opens its full-page monitor view. Use compact controls that never offer a normal “close/unpin” action while active.
- On dashboard desktop, **preserve the existing right activity-log panel**. Give the dock its own reserved section/edge position; do not obscure the log, video cards, important tools, or the acknowledgement button. On narrower viewports use a persistent bottom/side dock with sensible max height and a compact stack/scroll for multiple incidents.
- **Multiple active critical feeds:** show every active incident as a mini-card or a compact accessible multi-item dock. A count indicator alone is insufficient to hide an unacknowledged critical feed. Prioritize the most severe/unacknowledged in the visible section, but preserve access to all.
- On refresh/reconnect/route navigation, **rehydrate the dock and acknowledgement state from the Django backend**; local storage can assist UI preferences but **must not decide whether an incident is resolved**.
- If a critical feed becomes **offline or stale**, continue to show its incident in the dock as **Critical — feed unavailable / last measured …**. Do not treat lost measurements as “crowd managed.” Allow acknowledging the still-active incident; keep resolution server-authoritative.

### Navigation guard and warning treatment

- If any active critical incident is **unacknowledged**, intercept **in-app** navigation to other non-critical feeds, dashboard/settings routes, or unrelated sections, including sidebar links and programmatic route changes. Explain the required acknowledgement in a concise high-contrast alert overlay/panel.
- **Never block the operator from seeing critical feed details, opening incident response actions, reading relevant logs or clicking Acknowledge.** Do not create a focus trap that prevents the user from managing the situation. When multiple incidents are critical, acknowledgement is required **for each active unacknowledged incident** before general navigation unlocks.
- Show one clear primary action: **“Acknowledge danger”**. Record the acknowledgement against a stable backend **incident ID**, not a transient frame/count update. The acknowledgement action must work from both the alert panel and the full-page critical-feed view.
- **Acknowledgement silences the audible warning for that incident** (and updates all tabs/routes via authoritative state), but keeps a **persistent visible warning and red pinned feed**. If another unacknowledged critical incident exists, its own audio may continue and switching remains locked.
- The same incident's frequent metric updates must **not restart the siren** after acknowledgement. A genuinely **new incident** with a new ID may issue a new warning. Avoid repeating toast notifications on every video frame.
- Browser audio playback can be blocked until a user gesture. Offer a clear **Enable sound alerts** control and always show an equally clear visual warning. Don't imply that an alarm is guaranteed audible when permission/audio initialization is unavailable.
- Only in-app route/selection changes can be guarded reliably. **Do not promise to block the user from closing a browser tab, changing websites, or using OS navigation.** The app should persist active incident state server-side so it returns on revisit.

### Incident state diagram (UI behavior, not backend implementation)

```text
BACKEND declares CRITICAL incident
       │
       ├──> Pin live mini-feed globally + show red warning
       ├──> Sound warning when browser policy permits
       └──> Guard non-critical in-app navigation
                       │
              User acknowledges incident
                       │
              Mute that incident's sound
              Keep red mini-feed pinned
              Unlock unrelated routes only if
              ALL critical incidents acknowledged
                       │
              Backend confirms crowd MANAGED
                       │
              Incident resolved event arrives
                       │
              Auto-unpin mini-feed, end incident
```

---

## 4. Right-side event log: continuously visible situational context

The right-hand panel should look like a vertically organized **incident/activity timeline**, not a chat interface or a second metrics dashboard.

### Layout

- Panel title: **“Activity & Alerts”** with live event count / unread count as useful.
- Optional filters: **All / Critical / Warnings / System**. Keep filters compact; allow per-feed filtering through a dropdown.
- Each log row has: severity marker; timestamp in local readable time; feed name/location; concise action statement; optional value/delta / current density.
- Example display phrasing: **“North Gate · Density increased 18% in 60s”**, **“Food Court · Predicted threshold crossing in ~2 min”**, **“Entry B · Stream disconnected”**, **“Gate C · Density returned below warning level”**.
- Present **newest first** in a scrollable list, grouped by day if needed; timestamps and feed labels should be consistently aligned.
- Highlight incoming critical events with a brief, unobtrusive entrance animation; older entries remain discoverable.
- Visually distinguish **risk incidents** from **system messages** (reconnect, calibration updated, source removed).
- The log has its **own scroll area**; it must not make the entire dashboard jump as new events arrive.

### Behavior

- When the user is viewing the newest entries, append/prepend incoming events appropriately with consistent anchoring.
- If the user scrolls into history, **do not yank scroll position** when new events arrive; show a compact **“N new events”** control.
- Clicking a log row focuses/highlights the corresponding feed and opens its details without losing the log context.
- Provide empty state: **“No events yet — monitoring activity will appear here.”**
- Provide connection/error state: **“Updates paused — attempting to reconnect”**, with last received time.
- Support keyboard traversal; do not auto-announce every routine update to screen readers. Announce only meaningful alerts.
- **Required Acknowledge** action for active critical incidents; make it available in the log, global critical banner/dock, and critical full-page feed. An acknowledged incident stays visually critical and pinned until an authoritative resolved event. Acknowledged events should record who acknowledged and when (when authentication provides that information).

---

## 5. User input: Add Feed workflow (design only)

The Add Feed action should open a modal or side drawer with clearly separated source options. It does not need to expose underlying computer-vision pipeline details.

**Source options to visually provide:**

1. **Upload video file** — e.g., MP4/WebM and other formats validated by the backend; drag/drop + browse; show filename, size, type, upload progress, and any rejection reason. Uploaded footage should be labeled **Replay / File** and must not masquerade as live CCTV.
2. **Browser webcam** — request user-selected camera access; show permission state and a small local preview. Offer a supported camera selector if multiple devices are available.
3. **Network camera / stream URL** — URL field with name/location. Explicitly mark the format(s) supported by the server. **Browsers do not natively play arbitrary RTSP URLs**; RTSP or other camera protocols require backend media handling / browser-compatible transport.

Common form fields: **Feed name**, **Zone/location label**, **Source type**, and, if applicable, stream address / chosen camera / upload file. Show a clear status after submission: **Validating → Connecting → Calibrating (if needed) → Monitoring** or an actionable error.

**Calibration:** provide a discoverable **“Calibrate zone”** affordance in feed details. The frontend should show the four reference points/polygon handles and the area in m² *if the backend supports that calibration flow*. Do not imply density has been verified until calibration succeeds.

---

## 6. Responsive behavior

| Viewport | Main layout expectation |
|---|---|
| **≥1700px, wide desktop** | 2–3 grid columns depending on card minimum width; right log panel visible ~360–390px |
| **1200–1699px, desktop/laptop** | 2 feed columns; right log visible ~320–360px |
| **900–1199px, smaller laptop/tablet landscape** | Prefer one or two adequately sized feed columns; activity log becomes a narrower dock or accessible toggleable drawer |
| **<900px, tablet/mobile** | Single feed column, KPI strip wraps/scrolls; event log opens as full-height drawer or separate tab |
| **Very narrow phone** | Prioritize emergency feed, status and add-feed access; log tab remains one tap away, not inaccessible |

The highest-danger feed remains first across breakpoints. Ensure a focused/expanded feed can display its key telemetry without horizontal scrolling. When the log collapses, **critical alerts must still surface** through the persistent critical mini-feed dock and acknowledgement panel, not only in a hidden panel.

Use **container-dependent** sizing where practical so the cards adapt to the actual space remaining beside the log, not only the browser width.

---

## 7. States that must be designed, not left to chance

The frontend agent must prepare design states for:

- **No feeds configured**: elegant empty grid, one obvious Add Feed CTA, short guidance.
- **First feed loading**: media skeleton, “Connecting” label; do not show fake telemetry.
- **Monitoring live**: status, last update, severity, metrics and optional overlays.
- **Uploaded video replay**: explicit recorded-media indicator and replay controls.
- **Detection but no calibration**: people count may appear; real-world density displays “Not calibrated”.
- **Metrics delayed/stale**: warning text + elapsed age; do not present old green condition as live.
- **Camera offline / permission denied / invalid URL / unsupported format**: neutral status, reason and retry/settings action.
- **Alert active vs acknowledged vs resolved**: visually separate them; only the server-confirmed resolved state removes the pinned mini-feed.
- **Critical while focused elsewhere**: navigation lock with accessible acknowledgement action, and an immediately pinned mini-feed.
- **Critical acknowledged**: no incident siren, navigation unlocked if no other unacknowledged critical events, but mini-feed remains red and pinned on all routes.
- **Multiple critical incidents**: dock shows all, guards navigation until each is acknowledged, removes them individually on authoritative resolution.
- **Critical camera stale/offline**: pin persists with stale/offline wording; loss of signal must never look like recovery.
- **Direct deep-link/browser refresh**: global dock and lock restored from backend active-incident snapshot.
- **Hover/focus/touch stats**: current statistics panel works across input modes and is dismissed predictably.
- **Full-page camera monitor**: dedicated route, back navigation, live video, larger stats, accessible controls.
- **WebSocket disconnected**: keep existing dashboard visible but label values stale and provide reconnect state.
- **Partial outage**: only affected feeds show error; healthy feeds keep updating.
- **Too many feeds**: preserve fast sorting and rendering through progressive display/lazy-loading rather than shrinking cards indefinitely.

---

## 8. JavaScript & browser API responsibilities

The following table tells the frontend agent which browser-level APIs to plan for. **These are integration requirements / candidate APIs, not claims that anything is already implemented.** The agent may choose a framework (React + TypeScript is a reasonable option), but component boundaries and data contracts should remain framework-independent.

| Browser / JS API | What it is needed for | Important notes |
|---|---|---|
| **`fetch()`** | Retrieve feed list, historical events, zone settings; submit feed creation, calibration data, and acknowledgments | Handle HTTP failures, auth, request cancellation, loading states; do not poll video frames via REST |
| **`WebSocket`** | Receive live metrics, severity and critical-incident lifecycle events, acknowledgements, resolutions and connection health | Use `wss://` on HTTPS; explicit reconnect/backoff, heartbeat/timeout, initial snapshot and gap recovery; acknowledge/resolved must update every active view/dock |
| **`HTMLVideoElement`** | Display playable video in grid, full-page monitor and critical mini-feed; react to load/error/ended states | Reuse a stream adapter or efficient synchronized video source where possible; do not accidentally stop monitoring when moving between routes; no guarantee of native RTSP playback |
| **`navigator.mediaDevices.getUserMedia()`** | Acquire locally selected webcam feed, if browser webcam input is supported | Requires user permission and secure context (typically HTTPS); stop tracks when no longer used |
| **`navigator.mediaDevices.enumerateDevices()`** | Offer camera selection when accessible | Permission and browser restrictions affect device labels/availability |
| **`File` / `FileList`, drag-and-drop, `FormData`** | Video-file upload flow | Validate size/type early, but backend must also validate; display progress via suitable upload implementation |
| **`URL.createObjectURL()` / `URL.revokeObjectURL()`** | Temporary client-side preview for selected video files | Revoke object URLs when previews are discarded to release resources |
| **`CanvasRenderingContext2D` / `<canvas>`** | Optional overlays for bounding boxes, track IDs and calibration polygons | Overlay must align with displayed video and backend coordinate space |
| **`ResizeObserver`** | Keep canvas overlays/polygons aligned as card and video sizes change | Account for letterboxing and device-pixel ratio |
| **`requestAnimationFrame()`** | Smooth visual updates/transitions or overlay presentation | Don't use it as a substitute for actual inference timestamps |
| **`HTMLVideoElement.requestVideoFrameCallback()`** | Optional per-displayed-frame overlay synchronization | Use feature detection/fallback where unsupported; does not guarantee backend detections match that frame |
| **`IntersectionObserver`** | Reduce work on off-screen feed cards / lazy-load previews | Never suspend backend safety monitoring just because a card is off-screen |
| **`AbortController`** | Cancel stale requests when switching filters/feed details | Prevent race conditions and outdated state from overwriting newer data |
| **`Intl.DateTimeFormat` / `Intl.RelativeTimeFormat`** | Format log timestamps and “last updated” UI | Backend timestamps should be absolute UTC ISO 8601; display local zone clearly |
| **`document.visibilityState`** | Adapt rendering when the dashboard tab is hidden | Can reduce visual work; real events still require safe reconnection/resynchronization |
| **Web Audio API / `HTMLAudioElement`** | Audible warning for newly active, unacknowledged critical incidents; silence on acknowledgement | Audio may need an initial user gesture; deduplicate per stable incident ID, prevent unwanted restart, and offer accessible visual fallback. Stop the specific incident's sound when acknowledged or resolved. |
| **Web Notifications API** *(optional)* | Opt-in high-priority system notifications | Requires permission and user controls; don't depend on it as the only warning path |
| **`localStorage`** *(optional)* | Remember UI-only preferences, filters, log width, view style, sound-onboarding preference | **Never** use it as the source of truth for critical acknowledgement, incident resolution or unpinning; server snapshot must win |
| **`BroadcastChannel`** *(optional)* | Coordinate UI audio and incident changes across same-origin tabs | Useful to prevent duplicate alarms; still reconcile with authoritative server events after refresh or reconnection |
| **Router navigation guard** *(framework facility)* | Prevent switching to unrelated app pages/feeds while active critical incidents are unacknowledged | Guard clicks, browser in-app history and programmatic route transitions; never claim control over external browser/OS navigation |
| **Pointer/focus events & CSS `:hover` / `:focus-within`** | Reveal up-to-date hover stats and action controls | Must also provide touch Stats button; use centralized feed data rather than fetching on every hover |
| **`matchMedia('(prefers-reduced-motion: reduce)')`** | Minimize glow/pulse/reordering animations for accessibility | Respect reduced-motion preference without hiding event severity |

For continuously changing metrics, use a **single centralized data state** indexed by `feed_id`, a **separate incident store** indexed by `incident_id`, and **append-only / deduplicated alert history**. Derive `navigationLocked = activeIncidents.some(incident => !incident.acknowledged)` and `pinnedFeeds = activeIncidents.map(...)`; do not derive incident resolution from hover status or a single low-density reading. Avoid separately opening a WebSocket per feed unless there is a compelling backend requirement; **one dashboard events channel** is a simpler default.

---

## 9. Proposed frontend ↔ Django API contract (coordinate with backend team)

**Important:** The paths, fields, and messages below are **proposals**, not existing endpoints. They define what the designer's agent should assume / mock temporarily until the Django team agrees on an exact contract. Keep backend URLs configurable.

### Suggested REST operations

| Action | Proposed method + endpoint | Frontend needs |
|---|---|---|
| Initial dashboard state | `GET /api/dashboard/` | Initial feeds, zones, metric snapshot, server timestamp, active alerts |
| List feeds | `GET /api/feeds/` | IDs, names, locations, sources, current states, display URLs |
| Add feed | `POST /api/feeds/` | Accepts source details and metadata; returns a stable ID and current lifecycle state |
| Upload video | `POST /api/feeds/upload/` | Multipart upload, progress, validation errors, new feed ID |
| Feed detail | `GET /api/feeds/{feed_id}/` | Complete camera state and calibrated zones |
| Update feed settings | `PATCH /api/feeds/{feed_id}/` | Rename, edit user-facing source metadata/settings |
| Remove feed | `DELETE /api/feeds/{feed_id}/` | Stops monitoring / removes configured source, with clear confirmation |
| Zone calibration | `PUT /api/feeds/{feed_id}/calibration/` | Reference points, dimensions/area, backend validation result |
| Alert log | `GET /api/events/?cursor=...` | Historical entries, severity and feed filters, pagination cursor |
| List active incidents | `GET /api/incidents/active/` | Stable critical incident IDs, feed association, acknowledgement state, authoritative active/resolved state; hydrate persistent dock on refresh |
| Acknowledge critical incident **(required)** | `POST /api/incidents/{incident_id}/acknowledge/` | Server confirms who/when acknowledged; silence sound for this incident without clearing critical severity or pin |
| Incident status (optional detail) | `GET /api/incidents/{incident_id}/` | Inspect last update, escalation and confirmed recovery state; resolution is declared by backend, never an unpin button |

Authentication approach should be agreed with Django (session cookie + CSRF for same-origin UI is a reasonable default). The frontend must not embed permanent backend secrets inside public JS bundles.

### Suggested WebSocket channel

- **Endpoint:** `wss://<backend-host>/ws/dashboard/` (or same-origin equivalent).
- **Event types to support:** `dashboard.snapshot`, `feed.added`, `feed.removed`, `feed.status_changed`, `feed.metrics_updated`, `feed.calibration_changed`, `alert.created`, `alert.updated`, `incident.created`, `incident.acknowledged`, `incident.updated`, `incident.resolved`, `system.heartbeat`. Use `incident.*` as the authoritative critical lifecycle, separate from routine metric alerts.
- **Each event should include:** a stable event ID or sequence, `type`, `timestamp` (ISO 8601 UTC), and relevant `feed_id`.
- **On connection or reconnection:** fetch/receive an authoritative snapshot including **all active critical incidents and acknowledgements**, then process ordered incremental updates. Dedupe by event ID or sequence. If a gap is detected, re-fetch the snapshot/history; never silently claim continuity.
- **Rate:** backend may emit many metrics samples, but UI can **coalesce updates** to a manageable visual refresh rate (e.g., roughly 1–2 times/second) while still responding promptly to critical severity changes. Avoid accumulating an unlimited WebSocket message queue.

### Proposed `Feed` entity — fields the UI needs

| Field | Type / possible values | Display or behavior |
|---|---|---|
| `feed_id` | Stable string | Unique component/list key and event join key |
| `name`, `location` | Strings | Camera title/subtitle |
| `source_type` | `upload`, `webcam`, `network` | Correct playback/status language |
| `stream_state` | `connecting`, `live`, `replay`, `stale`, `offline`, `error` | Connection badge and fallback frame |
| `analysis_state` | `pending`, `active`, `calibrating`, `paused`, `failed` | Separate from video transport state |
| `severity` | `critical`, `high`, `elevated`, `normal`, `unknown` | Border color, icon and label |
| `risk_score` | Numeric, backend-defined or null | Default grid order; null is unassessed |
| `people_count` | Nonnegative integer or null | Headcount display |
| `density_people_per_m2` | Number or null | Density display only when calibration valid |
| `density_trend` | `rising`, `falling`, `stable`, `unknown` | Trend arrow and wording |
| `growth_rate` | Number + clearly defined units | Detailed trend / forecast panel |
| `predicted_threshold_time` | ISO timestamp or null | “At this trend, threshold in …” warning if valid |
| `zone_area_m2` / `calibrated` | Number / boolean | Confirm calibration status |
| `measured_fps` | Number or null | Diagnostics and hackathon performance visibility |
| `metric_timestamp` | ISO UTC timestamp | Staleness and last update indicator |
| `preview_url` / `preview_transport` | Optional URL + `hls`, `webrtc`, `mjpeg`, `file`, `image`, etc. | Choose compatible media display adapter |
| `version` / `sequence` | Integer | Prevent out-of-order updates overwriting newer state |

A feed's **analysis status**, **stream state**, **calibration validity**, and **risk severity** are distinct concepts. Do not collapse all of them into one badge.

### Proposed `CriticalIncident` entity — source of truth for alarm, lock and pin

| Field | Type / possible values | Frontend responsibility |
|---|---|---|
| `incident_id` | Stable unique string | Per-incident acknowledgement, alarm deduplication, dock key |
| `feed_id` | Stable string | Associate live mini-feed and full-page monitoring route |
| `state` | `active`, `resolved` | **Only `resolved` from backend triggers automatic unpin** |
| `severity` | `critical` while active | Persistent red alert language (even after acknowledgement) |
| `acknowledged` | Boolean | Silence that incident's alarm and help determine navigation lock |
| `acknowledged_at`, `acknowledged_by` | ISO UTC timestamp / user ID or null | Log/audit context, when available |
| `started_at`, `last_updated_at` | ISO UTC timestamps | Incident age and freshness indicators |
| `resolved_at` | ISO UTC timestamp or null | Remove from dock only after backend-confirmed recovery |
| `reason`, `latest_metrics` | String / optional structured data | Explain incident cause and show live snapshot/stale fallback |

**Suggested frontend state invariants:**

```js
// Conceptual UI selectors, not a complete implementation.
const unresolvedCritical = incidents.filter(i => i.state === 'active');
const navigationLocked = unresolvedCritical.some(i => !i.acknowledged);
const pinnedCritical = unresolvedCritical; // Acknowledgement never filters a pin.
const soundingCritical = unresolvedCritical.filter(i => !i.acknowledged);
// Only receiving authoritative state: 'resolved' removes an incident from the dock.
```

**Example event messages (illustrative contract, not existing backend output):**

```json
{
  "type": "incident.created",
  "event_id": "evt-101",
  "timestamp": "2026-11-20T16:00:00Z",
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
  "timestamp": "2026-11-20T16:01:00Z",
  "incident_id": "inc-gate-a-01",
  "feed_id": "gate-a",
  "acknowledged": true
}
```

```json
{
  "type": "incident.resolved",
  "event_id": "evt-103",
  "timestamp": "2026-11-20T16:06:00Z",
  "incident_id": "inc-gate-a-01",
  "feed_id": "gate-a",
  "state": "resolved"
}
```

### Proposed `EventLogEntry` entity

- `event_id` (stable unique ID)
- `timestamp` (ISO UTC)
- `feed_id`, `feed_name` (source identification)
- `category` (`crowd`, `prediction`, `system`, `calibration`)
- `severity` (`critical`, `high`, `elevated`, `info`)
- `event_type` (e.g., `density_rising`, `threshold_predicted`, `threshold_crossed`, `feed_disconnected`, `returned_to_normal`)
- `message` (short, human-readable; render as text, not raw HTML)
- `delta_percent` / `density_people_per_m2` / `people_count` (optional contextual values)
- `state` (`active`, `acknowledged`, `resolved` when relevant)

### Proposed `DetectionOverlay` payload (only if overlays are client-rendered)

- `feed_id`, `frame_id`/`frame_timestamp`, frame dimensions, and optional `zone_polygon`.
- For each detected/tracked person: optional `track_id`, `confidence`, and normalized bounding box or ground-contact point.
- Use normalized 0–1 coordinates **with an explicitly agreed coordinate convention**; account for video letterboxing/cropping when displaying them.
- If backend already returns annotated video, **do not draw duplicated boxes**. Choose one rendering strategy per feed.
- Do not try to draw timestamp-mismatched detections over unrelated video frames and present them as precise tracking.

---

## 10. Data freshness, severity, and sorting contract

The frontend must **not calculate its own crowd-safety thresholds** unless the backend explicitly delegates that responsibility. The backend must determine the active severity using actual zone density, calibrated area, configured thresholds, growth trend, and any risk forecast.

Frontend sorting policy:

1. Surface **critical** feeds first, then **high**, **elevated**, and **normal**.
2. Within a severity group, order by **descending backend risk score**.
3. Use **most urgent predicted threshold**, then **density**, then **count** as fallbacks when applicable.
4. Put **unknown/not assessed** feeds last in a distinct neutral state; optionally show an Unavailable count in the KPI strip.
5. Keep sorting stable when values are tied to prevent cards jittering between positions.
6. If a user pins or focuses a feed, preserve the focus while making actual danger sorting discoverable.
7. **Critical-feed dock takes precedence over manual pins and grid sort:** every unresolved critical incident remains globally pinned independent of the currently selected route, ranking or hover state. Acknowledgement affects sound/navigation only, not the persistent pin.

A feed is **stale** when no valid new metric has arrived for a backend-agreed timeout. Display the age. A stale feed must **never** keep a “healthy live” visual state solely because its last result was green. Predictions should always be labeled **estimates**, not guarantees; configurable danger levels should not be presented as universally certified safety standards.

---

## 11. Accessibility and operational usability

- Aim for **WCAG 2.2 AA** for text contrast, focus visibility, operability and labeling.
- Text labels must accompany every red/orange/yellow/green indicator; do not rely only on color, motion, or sound.
- All controls (Add Feed, filters, details, pin, log entries, critical alert acknowledge) should be keyboard accessible; hover statistics must also be available on keyboard focus and touch.
- The log should have readable semantic structure, with selective `aria-live` announcements for critical events only, not every count update.
- Use sufficiently large click targets on a laptop/tablet in a fast-moving monitoring environment.
- Use an **audible critical warning** only when browser audio restrictions permit, with clear enable-sound onboarding and a strong visual equivalent. Acknowledgement turns off that incident's warning sound but **does not change its red status or persistent pin**. Avoid aggressive animations and anything that hides the monitored danger behind an unresponsive modal.
- Ensure critical navigation restriction does not block the acknowledgement action, incident detail view or emergency-response controls. Announce why a route switch is restricted and provide a direct path to the required action.
- Distinguish **detection accuracy**, **processing FPS**, **video playback FPS**, and **network freshness**. They are not interchangeable.
- Include visible tooltips or concise help for “Density”, “Prediction”, “Confidence”, and “Calibration”.

---

## 12. Designer-agent deliverables and acceptance checks

**Expected design deliverables** (not backend implementation):

- A page layout covering **desktop, small laptop, tablet and mobile**, including **dedicated full-page feed view, hover/focus/touch statistics panel, and global critical mini-feed dock**.
- Reusable visual components: top bar, KPI tile, feed grid, feed card, severity indicator, add-feed dialog, detail/focus view, activity-log row, filters, empty/error/loading states.
- A clear, constrained theme token set, subtle danger glows, typography, spacing and interaction specifications.
- Defined client state boundaries and adapter interfaces for backend mock data vs real Django API integration.
- Fake/test data may be used **only as explicitly labeled prototype fixtures**; no hard-coded claim of production monitoring.

**Acceptance checklist:**

- [ ] Riskiest *assessed* feed appears at the top-left by default.
- [ ] Any number of feeds can be accommodated without breaking card readability.
- [ ] Card borders/glows visibly distinguish red, orange, yellow, green; unknown is grey.
- [ ] Feed names, crowd counts, density, trend, freshness, and stream status are legible.
- [ ] Activity log remains visible on desktop and accessible on smaller screens.
- [ ] Increasing traffic, predicted crossing, incident, recovery, and offline changes have distinct log treatments.
- [ ] Adding an uploaded file, webcam or supported network feed has a clear workflow.
- [ ] Source type, calibration status, stream status and danger status are not conflated.
- [ ] Frontend can accept arbitrary live feed metrics/events through a well-defined adapter.
- [ ] High-frequency metrics do not cause constant grid reshuffling or full-page re-rendering.
- [ ] Error, empty, stale, uncalibrated, and disconnected states are fully designed.
- [ ] No visible metric is represented as verified unless backed by real processing data.
- [ ] Hover/focus/touch reveals current feed stats without extra calls on every pointer movement; clicking a feed opens a **full-page route**, not a modal.
- [ ] Critical activation **immediately pins** the mini-feed across every in-app route and shows a high-priority warning.
- [ ] Any unacknowledged active critical incident **guards unrelated in-app navigation** but allows viewing/handling critical feeds and acknowledging danger.
- [ ] Acknowledgement **silences that incident's warning sound** and unlocks unrelated navigation only when no other unacknowledged critical incidents remain.
- [ ] Acknowledged critical incidents **stay red and pinned** when user changes pages, refreshes or reconnects.
- [ ] The pinned mini-feed **unpins automatically only when backend declares the incident resolved** after actual crowd recovery; cannot be dismissed manually by a user.
- [ ] Stale/offline camera or temporary density dip **does not count as resolved**; multiple incidents remain independently represented and handled.
- [ ] Browser autoplay/audio restrictions and in-app-only navigation guard limitations are clearly represented rather than promised away.

---

## 13. Project-specific engineering context the designer must respect

The official **Code Fuzion 2026 H7** challenge requires: **at least two simultaneous feeds** on a laptop CPU or free GPU; **camera-calibrated people per square metre**; **early warning from trends**; and **under 20% counting error at 5+ processed frames per second**. These are **system-level requirements**, not tasks for CSS/JavaScript alone. The dashboard should make evidence for these metrics discoverable, especially a diagnostics area for per-feed processed FPS, last update and measured test accuracy when an actual evaluation result exists.

Suggested architecture relationship:

**Video worker (YOLO + Supervision + OpenCV)** → **Django API / Django Channels** → **Frontend live dashboard and event log**.

The JavaScript UI must not pretend browser-side video playback equals backend person detection. A hybrid deployment may show a publicly hosted Django dashboard while processing footage on the hackathon laptop; if the laptop worker stops, the dashboard must visibly show stale/offline status.

### Reference documentation (for API choices, not for visual appearance)

- [WebSocket API — MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [MediaDevices.getUserMedia — MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [File API — MDN](https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications)
- [HTMLVideoElement.requestVideoFrameCallback — MDN](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback)
- [Roboflow Supervision](https://github.com/roboflow/supervision)
- [Django Channels documentation](https://channels.readthedocs.io/)

**Final design directive:** Build the visual architecture around the **danger-ranked camera grid + subtle severity glow + permanent right-side incident log + persistent critical-feed dock**. Feed hover previews current metrics; feed click enters a **full-page monitor**. A critical incident locks unrelated in-app navigation until acknowledged, **acknowledgement only silences that incident's alarm**, and the system **unpins only on backend-confirmed crowd recovery**. Optimize for a volunteer noticing and acting on the next dangerous situation in **one glance**.
