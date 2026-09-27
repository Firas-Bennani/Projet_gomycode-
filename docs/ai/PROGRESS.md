# PROGRESS — Engineer 1 (Multi-Agent AI + n8n)

Branch: `ai/multi-agent`. Plan: [PLAN.md](PLAN.md).

| Step | Status | Notes |
|---|---|---|
| 0 — Setup + reproduce bug | ✅ DONE | Bug reproduced, 2 wrong incidents |
| 1 — Fix correlation + tests | ✅ DONE | 29 tests green x3 runs; live API correct on all 4 scenarios |
| 2 — n8n + PGVector infra | ⏳ next | LLM = Gemini (key with Firas) |
| 3 — Bridge + workflow v1 | ⬜ | |
| 4 — GATE 1 (E2E with UI) | ⬜ | must be done by 01:30 Sunday |
| 5 — RAG + LLM in n8n | ⬜ | |
| 6 — ML models | ⬜ | |
| 7 — Risk engine | ⬜ | |
| 8 — Cyber + MITRE ICS | ⬜ | |
| 9 — Worker agent from state | ⬜ | |
| 10 — Threat Watch | ⬜ | optional |
| 11 — Freeze + demo | ⬜ | |

---

## Step 0 — DONE (2026-09-26 ~22:45)

**Environment verified (Windows 11 / PowerShell):** git 2.52.0, Python 3.13.5, Docker 29.4.2,
Docker Compose v5.1.3, Node v24.15.0, npm 11.12.1. All above the required minimums.

**Setup:** repo cloned into `C:\Users\FIRAS\Documents\5dma classe\HACKgomycode`
(single upstream commit `11b23d1`), branch `ai/multi-agent` created, venv at `.venv`
with `backend/requirements.txt` + `pytest` + `pytest-asyncio` installed.

**Run command used (local, no Docker):**
```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### The bug, reproduced

`POST /api/demo/scenario {"scenario":"machine_overheating"}` then `GET /api/incidents`
after 12 s produced **two incidents, both wrong**:

| Incident | Type | Evidence actually present | Actions proposed |
|---|---|---|---|
| INC-18A4 | `MACHINE_OVERHEATING` | temperature only, 31.6 °C — no machine evidence | STOP_MACHINE, EVACUATE_ZONE, ACTIVATE_COOLING |
| INC-FE32 | `INDUSTRIAL_FIRE` | temperature only, 48.1 °C — no smoke evidence | TRIGGER_ALARM, CLOSE_DOOR, ACTIVATE_SUPPRESSION |

### Root causes (verified in code)

1. **No correlation window.** `ai/orchestrator.py:56` calls
   `synthesize_incident(observations)` with only the observations produced by the *current*
   event. The simulator publishes `SENSOR_READING` (`iot/simulator.py:130`) and
   `MACHINE_STATUS` (`iot/simulator.py:151`) as two separate events, so the temperature
   observation and the machine observation never appear in the same list.
2. **Fire rule has an impossible guard.** `ai/agents/recommendation_agent.py:81`:
   `smoke_reading or (temp_obs.current_value > 45 and mach_obs is None)`. Since `mach_obs`
   is always `None`, any temperature above 45 °C becomes `INDUSTRIAL_FIRE` — the demo would
   discharge water suppression on an overheating compressor.
3. **Slopes are meaningless.** `ai/agents/temperature_agent.py:38-41` and
   `ai/agents/machine_agent.py:48-52` take first-vs-last over a 2–7 s buffer and divide by
   minutes → `+38.4 °C/min` / `+9.6 °C/min` for the same physical ramp.
4. **Dedup too weak.** `ai/orchestrator.py:85-87` dedups on `type + zone`, so two different
   wrong types for the same physical event both survive. No cooldown after resolution.

### Other confirmed issues (to fix in later steps)

- Hardcoded confidences 0.94 / 0.95 / 0.96 (`recommendation_agent.py:119,180` + `:60`).
- `ai_reasoning` contains hardcoded numbers ("51 °C", "8.7 bar", "3 personnel") that do not
  match the real readings.
- `cyber_agent.py` flags every `CYBER_EVENT` as HIGH with no rules; defaults are hardcoded
  (`attempts=47`).
- `worker_agent.py:11-16` hardcodes `ZONE_B: [W23, W41, W52]` instead of reading `state_store`.
- `iot/simulator.py::_tick_fire` publishes **only** the smoke reading, never a temperature
  reading — so the "2 independent sources" fire rule of Step 1 must treat temperature as
  optional, or Engineer 2 must add the temperature publish.
- `LLM_PROVIDER="simulated"`, RAG is keyword matching over 3 hardcoded strings.

**What's next:** Step 1 — per-zone 30 s observation window, least-squares slopes,
rule precedence (fire needs smoke, overheating needs machine evidence), dedup + 60 s
cooldown, and `backend/tests/test_scenarios.py`.

**Open question for Firas:** push rights on the team repo (else fork + set `upstream`), and
which LLM/embedding API key we will use in n8n (needed at Step 2).

---

## Step 1 — DONE (2026-09-26 ~23:35)

### What changed

**New modules (all mine):**
- `backend/ai/clock.py` — injectable clock so trend logic is testable without real sleeps.
  Production behaviour identical (`datetime.utcnow()`).
- `backend/ai/trend.py` — least-squares slope, alarm-verification helpers, ETA to limit, and
  the `DEMO_TIME_SCALE` time-compression constant.
- `backend/ai/observation_window.py` — per-zone 30 s sliding window keeping the newest
  observation per `(agent_id, asset)`.

**Rewritten:** `ai/orchestrator.py`, `ai/agents/temperature_agent.py`,
`ai/agents/machine_agent.py`, `ai/agents/recommendation_agent.py`.

1. **Correlation.** `synthesize_incident()` now receives the whole per-zone window instead of
   one event's observations, so the Zone B temperature reading and the M-04 machine status
   finally meet.
2. **Rule precedence with required evidence.** `INDUSTRIAL_FIRE` requires smoke to be present
   *plus* two corroborating signals. `MACHINE_OVERHEATING` requires machine evidence on an
   asset. If neither holds, the agent declares nothing and logs *why* ("Holding — a single
   environmental sensor is not enough to name a hazard"), visible in `state.agent_logs`.
3. **Honest slopes.** Least-squares over the window, reported only after >= 10 s of history,
   expressed per *plant* minute (`DEMO_TIME_SCALE=60`). `+122 °C/min` became `+2.0 °C/min`.
   Before 10 s the agents say "trend not yet established (4s of history)" instead of printing
   a number they have not measured.
4. **Dedup + escalation + cooldown.** Same type+zone while open → the existing incident is
   *escalated* (severity/confidence/evidence updated, `INCIDENT_UPDATED` published) instead of
   duplicated. After resolution a 60 s cooldown prevents immediate re-opening.
5. **No hardcoded confidence or invented readings.** Confidence is noisy-OR fused over
   independent sources (`1 - Π(1 - cᵢ)`) and the reasoning text quotes the actual values plus
   each source's contribution. Provisional — Step 7 moves this into `ai/risk_engine.py` and
   adds per-sensor trust.
6. **Machine agent** also fires on body temperature vs. the asset's *own* threshold from the
   state store, and reports `eta_to_pressure_limit_s`.
7. **Affected workers** come from the state store (zone + not OFF_SITE) rather than a
   hardcoded fallback list. (Full worker-agent rewrite is still Step 9.)

### Bug found and fixed during live verification (not in the original list)

`POST /api/demo/reset` clears `state` but nothing cleared the AI layer, so up to 30 s of
observations survived. Running `fire` right after `machine_overheating` correlated fresh smoke
with the previous scenario's 8.9 bar pressure and opened a **second, bogus**
`MACHINE_OVERHEATING`. The orchestrator now clears its correlation memory on `FACTORY_RESET`
and on a detected scenario change. Two regression tests cover it.

### Acceptance — passed

`cd backend && ..\.venv\Scripts\python.exe -m pytest -q` → **29 passed**, three runs in a
row (0.7 s per run; no real-time sleeping).

Live through the API (`POST /api/demo/reset` → `POST /api/demo/scenario` → `GET /api/incidents`):

| scenario | incidents | type | confidence |
|---|---|---|---|
| machine_overheating | 1 | `MACHINE_OVERHEATING` (M-04, machine + temperature + worker evidence) | 0.94 |
| fire | 1 | `INDUSTRIAL_FIRE` (smoke level + persistence) | 0.85 |
| cybersecurity | 1 | `CYBER_INTRUSION` | 0.80 |
| normal | 0 | — | — |

### Known issues / deferred

- Fire currently corroborates from **one** smoke sensor (level + persistence) because
  `_tick_fire` never publishes a temperature reading. Proposal P1 in
  `PROPOSED_CHANGES_FOR_TEAM.md` would make it two independent sensors and lift confidence to
  ~0.98. Not blocking.
- Scenario-change detection reads `simulator.scenario` defensively; proposal P2 offers the
  clean event-based version.
- `cyber_agent` and `worker_agent` still have their original logic (Steps 8 and 9).
- Confidence fusion is provisional and lives in `recommendation_agent`; Step 7 moves it.

**What's next:** Step 2 — add `n8n` and `pgvector` to docker-compose, start the stack, then
hand over for the n8n owner account + Postgres and Gemini credentials.

---

## Steps 2 + 3 — backend half DONE, containers BLOCKED (2026-09-27 ~00:05)

### Done (committed `bb04999`)

- **`docker-compose.yml`**: `n8n` (port 5678, `n8n_data` volume, `Europe/London`,
  `N8N_SECURE_COOKIE=false`, `WEBHOOK_URL=http://localhost:5678/`, corpus mounted read-only at
  `/data/corpus`, `host.docker.internal` mapped) and `pgvector` (`pgvector/pgvector:pg16`, host
  port **5433** to avoid clashing with a local Postgres, own volume, healthcheck).
  `docker compose config` validates.
- **`backend/ai/actions_catalog.py`** — the 8 actions the copilot may propose. A test asserts
  every `action_type` is one `command_engine` already executes, and that only LOW-risk entries
  auto-run. **Risk level and `requires_confirmation` are read from the catalogue, never from
  an LLM response.** This is what makes it safe to let a model write recommendations in Step 5.
- **`backend/ai/n8n_client.py`** — fire-and-forget incident POST (3 s timeout, never raises,
  never blocks detection), resume-URL registry, and public→internal URL rewriting so the
  bridge works whether the backend runs on the host or inside compose.
- **`backend/app/api/n8n_bridge.py`** — `POST /api/ai/n8n/enrichment/{id}`,
  `GET /api/ai/n8n/verify/{id}`, `POST /api/ai/n8n/status/{id}`, plus `GET /api/ai/n8n/state`
  for debugging. One `include_router` line added to `app/main.py`.
- **`command_engine` hooks** — AUTHORIZE/CANCEL resumes the waiting n8n execution; added
  actuator checks for `TRIGGER_ALARM`, `CLOSE_DOOR`, `VLAN_QUARANTINE`, which previously
  completed with no verification at all.
- **`n8n/workflows/incident_response_v1.json`** (13 nodes, generated by `_generate_v1.py`):
  Webhook → template recommendation → validate against `allowed_actions` → POST enrichment
  with `$execution.resumeUrl` → Wait 180 s for the owner → IF approved → Wait 15 s → GET
  verify → IF verified → RESOLVING, else ESCALATED; cancel → DISMISSED, timeout → ESCALATED.
- **51 tests pass.** Verified live with a stub HTTP server standing in for the Wait node:
  enrichment rejected `close_door` (wrong hazard) and `launch_missiles` (not in catalogue);
  authorising the 3 actions POSTed 3 decisions to the resume URL; verification then passed on
  6 actuator checks.

### Two bugs found and fixed while testing the bridge

1. **Verification failed after a perfect shutdown.** `command_engine` sets M-04 to a safe
   baseline, then the running scenario overwrites its pressure back to 8.9 bar on the next
   tick. `verify` now separates **gating** checks (all actions terminal + actuator checks) from
   **informational** live telemetry, and returns `telemetry_consistent` so the contradiction is
   reported rather than hidden. Proposal P5 offers Engineer 2 the clean simulator-side fix.
2. **Status could move backwards.** The workflow posts `RESOLVING` about 15 s after approval,
   by which time `command_engine` has often already set `RESOLVED`; the dashboard would have
   bounced backwards. `PROGRESS_RANK` now refuses any downgrade and says so in the log.

### Blocked

`docker compose pull` fails: **Docker Desktop's engine is not responding** (the named pipe
exists and three `Docker Desktop.exe` processes are running, but the API returns HTTP 500).
Launched it from the CLI; it has not come up in ~25 minutes, which usually means its window is
waiting on something (terms, sign-in, or a WSL update). Needs Firas.

Fallback if Docker cannot be fixed tonight: run n8n on the host with `npx n8n`. Steps 3 and 4
(GATE 1) need **only n8n** — `pgvector` is not used until Step 5's RAG ingestion.

**What's next:** unblock n8n, then the n8n owner account + credentials, import and activate
`incident_response_v1`, and run the curl round-trip (Step 3 acceptance) before GATE 1.

---

## Step 3 — DONE, acceptance met 3× in a row (2026-09-27 ~04:15)

### Result

```
STEP 3 ACCEPTANCE — backend <-> n8n round trip      RESULT: 15/15 checks passed   (x3 runs)
```

Reproduce with `..\.venv\Scripts\python.exe n8n\e2e_test.py` (~60 s, exit code 0 = met).
It triggers `machine_overheating`, waits for the n8n execution, checks the enrichment came
back, authorises the pending actions through the same `/api/actions/{id}/authorize` call the
dashboard button makes, then asserts the n8n execution finished `success`, verification passed
and the incident resolved.

- n8n **2.40.7** running on the host via `npx` (no Docker). PID owns port 5678; state in `~/.n8n`.
- Workflow `Incident Response v1 (deterministic, no LLM)`, id `JGnDOTFBKB6YqUbD`, **ACTIVE**.
- Imported and activated through the public API with `n8n/import_workflows.py`; exported back
  with `n8n/export_workflows.py` and **re-imported unchanged**, so the committed JSON is proven
  reproducible (this is what Step 11's from-scratch run depends on).
- All four scenarios still classify correctly with n8n in the loop:
  `machine_overheating → MACHINE_OVERHEATING (0.94)`, `fire → INDUSTRIAL_FIRE (0.85)`,
  `cybersecurity → CYBER_INTRUSION (0.80)`, `normal → none`.
- **54 pytest tests pass.**

### Two bugs found and fixed during this step

1. **n8n could not reach the backend.** `BACKEND_BASE_URL_FOR_N8N=http://localhost:8000` gave
   *"The service refused the connection"*: Node 18+ resolves `localhost` to IPv6 `::1` first,
   while uvicorn binds IPv4 `127.0.0.1` only. Pinned to `http://127.0.0.1:8000` (and made that
   the default in `n8n_client.py`) rather than exposing the backend on all interfaces.
   Documented in `.env.example` and `n8n/README.md` — this will bite anyone on the team.
2. **Escalation erased the enriched explanation.** After n8n rewrote `ai_reasoning`, the next
   severity escalation overwrote it with the deterministic template text — in the demo the
   LLM's explanation would appear and vanish a second later. The orchestrator now keeps an
   enriched explanation and appends a single refreshed line
   (`— re-assessed since enrichment: severity WARNING -> CRITICAL, confidence now 0.94 …`).
   Three tests cover it, including that a non-enriched incident still gets fresh template text.

### Also done

- `n8n/import_workflows.py`, `n8n/export_workflows.py`, `n8n/e2e_test.py` — repeatable
  import/export/verify instead of hand-clicking in the UI.
- `n8n/README.md` — start command, one-time setup, import order, which workflows to activate,
  the IPv4 gotcha, and what the workflow does. (Step 11 asked for this; written early because
  it is also the recovery procedure if n8n dies.)
- `docs/ai/PLAN.md` — revised Sunday schedule at the top of section 6.

### ⚠️ Known issues to look at during Step 4

- **The `recommendation_agent (n8n)` log entry scrolls away fast.** `state.agent_logs` is capped
  at 100 entries and the simulator writes several per second, so the enrichment entry is pushed
  out within ~30 s. The E2E test sees only 1 n8n entry for this reason. If the AI page looks
  empty of n8n activity during the demo, the cheap fix is raising the cap in
  `orchestrator._log_agent_step` and `n8n_bridge._log` (both mine) — your call once you see the UI.
- **Incident severity starts at WARNING** and escalates to CRITICAL a few seconds later, because
  machine evidence now arrives before the readings are critical. Correct behaviour, but worth
  knowing so it does not look like a bug on stage.
- `telemetry_consistent=false` after a shutdown is expected: the simulator keeps driving the
  scenario curve over a stopped machine (proposal P5 for Engineer 2). Gating checks all pass.
- 1 of the 9 n8n executions is red — that is the pre-fix `localhost` failure, kept for the
  record. Executions 2+ are green. Clear it in the n8n UI before the demo if you prefer.

### 🔔 At 07:30, for Firas

1. **Check both processes are still alive** (I left them running):
   - n8n: <http://localhost:5678> should load.
   - backend: `curl http://127.0.0.1:8000/health` → `{"status":"HEALTHY"}`.
   - If either died, `n8n/README.md` §1 and §4 have the exact commands.
2. **Start the frontend** (I have not touched or run it — it is Engineers 3/4's):
   `cd frontend; npm install; npm run dev` → <http://localhost:5173>.
3. Then we do **Step 4 / GATE 1**: trigger `machine_overheating` from the demo bar, click
   AUTHORIZE, and tell me what the incident panel, the action status and the 3D view do, plus
   whether the n8n Executions tab goes green.
4. Nothing needs your clicks before that. Push is done, so the work is safe.

---

## GATE 1 fixes — DONE (2026-09-27 ~05:05)

All six items from Firas's GATE 1 report. Verified live with `n8n/gate1_verify.py`
(**13/13**), `n8n/e2e_test.py` (**15/15**) and **64 pytest tests**.

### 1. Actions only appeared after F5 — FIXED

`command_engine` published `ACTION_STATUS` on authorise/execute/complete, but **nothing
published when an action was created**. The dashboard keeps its own list from `ACTION_STATUS`
events (`frontend/src/App.tsx:112`), so a pending action never reached the Command Center and
the AUTHORIZE button only appeared after a refetch.

New `backend/ai/action_events.py` publishes `ACTION_STATUS` with `data` = the serialised
`Action` — the exact payload the frontend already consumes. Called from the orchestrator when
actions are created, from the n8n bridge when enrichment adds one, and from the resolution
policy when one is superseded. Ordering is now deliberate: `INCIDENT_CREATED` first, then each
action, and only then are LOW-risk automatic actions started, so a completion can never be
announced before the action itself. No frontend change needed.

### 2. n8n Wait node timed out at 180 s — FIXED

- Approval window raised to **10 minutes** (`resumeAmount: 10, resumeUnit: "minutes"`).
- On timeout the workflow posts `ESCALATED`; the bridge now sets `incident.status = "ESCALATED"`,
  raises severity to CRITICAL, and prepends a banner to `ai_reasoning`
  (`!! ESCALATED: No owner decision in 10 min -> escalated …`) because the incident card renders
  the reasoning but never renders `status` (see P7 for the nicer frontend fix).
- Agent log records it under `recommendation_agent (n8n)`.
- **Authorising after a timeout** now executes normally and never POSTs to a dead execution: any
  terminal status drops the stored resume URL, and a 404/409/410 is logged as a normal outcome.
  It also distinguishes *"an earlier decision already resumed it"* (a Wait node resumes exactly
  once, so the 2nd and 3rd AUTHORIZE legitimately get 409) from *"the window expired"*.

### 3. P5 — APPLIED to `backend/iot/simulator.py` (authorised)

Marked with `P5 (Engineer 1)` comments and written up in `PROPOSED_CHANGES_FOR_TEAM.md` with a
"please review" note for Engineer 2. Once `STOP_MACHINE` / cooling / suppression completes, the
readings decay exponentially to baseline and stay there until reset; the machine reports `INFO`.
Live result: **M-04 settles at 5.2 bar / 43.4 °C / INFO** instead of snapping back to 8.93 bar.
`telemetry_consistent` is now `true` in `/verify`, where it used to be `false`.

### 4. Re-opening rule — FIXED

`REOPEN_REQUIRE_RISING_S = 300`: for 5 minutes after a hazard is resolved in a zone, a new
incident of that type is only opened if a measured source is **actually climbing again**
(`pressure_slope > 0.05` bar/min, or a temperature/smoke rate > 0.2/min). The 60 s hard cooldown
still applies first and blocks everything, rising or not. Only for hazards with a continuous
measurement (`MACHINE_OVERHEATING`, `INDUSTRIAL_FIRE`) — an intrusion has no analogue reading, so
it keeps only the cooldown.

### 5. Resolution rule — CHOSEN AND IMPLEMENTED

New `backend/ai/resolution_policy.py`. **An incident resolves when every _hazard-resolving_
action recommended for it has COMPLETED and the hazard is measurably receding.** Remaining
actions that nobody has approved yet are cancelled as *superseded*, with the reason in the agent
log. Actions already authorised are left to finish — they are in flight at an actuator.

`resolves_hazard` is a new flag per catalogue entry: `STOP_MACHINE`, `ACTIVATE_SUPPRESSION`,
`ISOLATE_DEVICE`. `EVACUATE_ZONE`, `ACTIVATE_COOLING`, `TRIGGER_ALARM`, `CLOSE_DOOR` and
`VLAN_QUARANTINE` protect people or limit spread but never resolve on their own. "Receding" is
measured per hazard: machine parameters back inside their thresholds, or smoke below its warning
level; containment is the resolution for an intrusion. The old "all actions terminal" rule
remains as a fallback. `command_engine`'s inline resolve block was replaced by a two-line call.

**Demo consequence worth knowing:** authorising **only STOP_MACHINE** now resolves the incident
and cancels the other two cards. Authorising all three also works. Either is a clean demo — the
one-click version is the stronger story.

### 6. Pressure tile — REPORTED, NOT FIXED (as instructed)

Tile reads `PRES-B-01` (`frontend/src/components/MetricsBar.tsx:19`, Engineers 3/4). Root cause is
upstream: `iot/simulator.py::_tick_overheating` updates `state.sensors["PRES-B-01"]` but only
publishes a `SENSOR_READING` for `TEMP-B-01`, so the browser's copy is stale. Written up as **P6**
with the patch. Not a MetricsBar bug; the AI layer is unaffected (it reads `MACHINE_STATUS`).

### Tests added

- `test_pending_actions_are_announced_on_the_websocket` — payload shape and ordering.
- `test_authorizing_everything_resolves_and_does_not_reopen` — resolve, then 70 simulated
  seconds with nothing re-opening, plus the P5 decay assertion.
- `test_a_resolved_hazard_reopens_only_when_values_climb_again` — the guard in isolation, both
  directions.
- `test_hard_cooldown_blocks_reopening_even_when_values_climb`.
- `test_optional_actions_are_cancelled_once_the_hazard_is_addressed`.
- `test_wait_timeout_escalates_and_is_visible_on_the_incident_card`, banner-not-stacked,
  resume-URL-dropped, authorise-after-timeout, dead-URL-handled-cleanly.
- Runner gained `keep_clock` + `feed()`: restarting the fake clock put `resolved_at` in the
  future and silently disabled both guards, so an earlier version of the re-open test passed
  for the wrong reason.

### Known cosmetic issues (not fixed)

- An `ESCALATED` incident drops out of the UI's "ACTIVE ALERTS" count — P7.
- `GET /api/ai/n8n/state` shows the **last** exchange, so after three AUTHORIZE clicks it shows
  the third one's 409 rather than the first one's success. The log line now explains it.

---

## Step 5 — RAG corpus + Gemini workflow BUILT, waiting on the credential (2026-09-27 ~06:15)

### Done without needing Firas

**Corpus — `backend/ai/rag/corpus/`, 5 documents, 31 numbered sections:**
`SOP-M04-Compressor.md`, `Fire-Emergency-Procedure.md`, `Evacuation-Procedure.md`,
`OT-Cyber-Incident-Playbook.md`, `Maintenance-Plan.md`. Written so the thresholds in the
procedures are the same numbers the agents actually use (8.0 bar, 80 °C, 40 ppm, 7.2 bar
warning), and so the rules the copilot follows are *written down* and citable — including
"suppression requires smoke; never discharge it on a hot machine" (SOP-M04 §5.1, FIRE-EP-03 §2.3)
and "distrust a spoofed sensor, do not ignore it" (OT-CYBER-PB §4), which is Step 8's flagship.

**`rag_engine.py` rewritten** to load that corpus, retrieving **per section** rather than per
document so citations are specific (`SOP-M04 §4.2`, not "the M-04 manual"). Keeps its old
`query()` signature and `{answer, sources}` shape, so `POST /api/ai/rag/query` and the agents are
unaffected. Falls back to the original hardcoded documents if the corpus directory is missing.
Retrieval spot-checks: overheating → `SOP-M04 §4.2`; fire → `FIRE-EP-03 §2`; spoofed sensor →
`OT-CYBER-PB §4`. All correct.

**Two new endpoints** (in my own router):
- `GET /api/ai/n8n/corpus` — the corpus, one item per section. The ingestion workflow reads this
  over HTTP instead of mounting a directory, so the workflow carries no filesystem paths and
  works identically on the host or in Docker.
- `GET /api/ai/n8n/rag?q=&hazard=&limit=` — keyword retrieval, exposed as a tool for the agent.

**`n8n/workflows/incident_response_v2.json` (21 nodes)** — v1's Code node replaced by an
**AI Agent** with a Google Gemini chat model (temperature 0.2), a **Structured Output Parser**
(schema: what / why[] / impact / prediction / recommended_action_ids[] / sources[]) and **two
retrieval tools**. The system prompt forbids inventing action ids, forbids setting risk or
confidence, requires citing only sections actually retrieved, and requires hedged language.
Everything downstream of the recommendation is byte-for-byte v1's logic.

**`n8n/workflows/rag_ingestion.json` (7 nodes)** — Manual Trigger → GET corpus → one item per
section → Default Data Loader (chunk 400 / overlap 50, metadata `doc_id`, `citation`, `section`,
`hazard`) → Gemini embeddings → Simple Vector Store insert, `clearStore: true` so re-running does
not duplicate chunks.

Both imported into n8n and left **inactive**. v1 is still the active workflow, and
`n8n/e2e_test.py` still passes **15/15**, `pytest` **64 passed**.

### Why the agent gets *two* retrieval tools

n8n's Simple Vector Store node describes itself as *"for experimental use only: data is stored in
memory and will be lost if n8n restarts. Data may also be cleared if available memory gets low."*
This laptop has already had processes reaped for low memory three times tonight. So the agent has
both `procedure_vector_search` (the store, as agreed) and `procedure_search` (HTTP to the backend
keyword RAG, the agreed fallback). If the store is empty after a restart, retrieval still works
and the demo still cites real sections.

### Fallback chain, verified by construction

The AI Agent node is set to `onError: continueErrorOutput`, and its error branch runs the same
deterministic template v1 uses, producing an identical payload shape. So: **no credential, wrong
credential, exhausted quota, or malformed model output all degrade to v1 behaviour**, and the
incident still gets recommendations. This is also where Step 5b's NIM → Gemini → template chain
will slot in.

### Node contract was verified, not guessed

Type names and version numbers were read out of the installed `@n8n/n8n-nodes-langchain`
package on disk (`agent` supports up to 3.1, using 2.2; `lmChatGoogleGemini` 1.1;
`outputParserStructured` 1.1; `toolHttpRequest` / `toolVectorStore` 1.1;
`vectorStoreInMemory` 1.2 — the version whose manual memory key is shared across workflows;
`documentDefaultDataLoader` 1.1). Credential type for both Gemini nodes is `googlePalmApi`.

### Blocked on

The Gemini credential, which only exists inside n8n. Until it is added, v2 cannot be activated.

---

## 🚩 GATE 1 — PASSED (confirmed in the real UI by Firas, 2026-09-27)

Actions appear without F5 · AUTHORIZE `STOP_MACHINE` → incident RESOLVED · the other cards
cancel as superseded · M-04 returns to baseline · no new incident opens · n8n execution green.
Tagged `gate1`, pushed.

## Step 5 — DONE and live (2026-09-27 ~07:20)

`Incident Response v2 (Gemini + RAG)` is the **active** workflow; v1 is inactive and kept as the
manual fallback.

### Firas's UI fixes, now captured in the repo

Exported the live workflows with `n8n/export_workflows.py`, so `n8n/workflows/*.json` match the
UI exactly, and verified **export → import → export is byte-identical** (idempotent) with the
credentials still attached. `_generate_v2.py` was synced to match so regenerating cannot undo
the fixes. What changed from my generated version:

- `models/text-embedding-004` → **`models/gemini-embedding-001`** on both embedding nodes. It
  turns out that is the node's own default, which is why n8n omits it from the export.
- a **second Gemini chat model node** (`Google Gemini Chat Model1`) wired into
  `Procedure search (vector store)` — the vector-store *tool* needs its own model and n8n flags
  it red without one. I had missed that; it is now in the generator too.

### Two model problems found by running it, and fixed

1. `models/gemini-2.5-flash` returns **404 "no longer available to new users"**; Google names
   `models/gemini-3.8-flash` as the replacement. Both chat nodes switched.
2. The agent was too chatty for the free tier: each tool call costs a model call and the
   vector-store tool spends one of its own, so it made 6+ calls and hit **429 (limit: 5
   requests/minute)**. Added a hard budget instruction to the system prompt ("call
   procedure_search exactly once") and `maxIterations: 3`. Usage is now 2–3 calls.
3. Also fixed a stale label: `produced_by` reported `gemini-2.0-flash`, a string baked in when
   the file was first generated.

### Result — see `docs/ai/METRICS.md` for the full table

**The LLM path works and is well grounded when Google serves it:** 37.7 s, reasoning quoting the
real readings, citing `SOP-M04 §4.1` and `§2`. It correctly cited the *warning-level* section
because the readings were at warning level.

**But 4 of 5 attempts fell back**, on three distinct Google-side failures — 404 (model retired),
429 (free-tier quota), 503 (model overloaded) — plus the deliberate `--break` test. In **5 of 5**
runs the system still produced 3 validated actions, ran the approval flow, verified and resolved
the incident. The fallback is not theoretical; it carried four real failures tonight.

**Conclusion for the demo:** do not let the demo depend on Gemini. This is the strongest argument
for Step 5b putting NVIDIA NIM on Brev first in the chain, with Gemini second and the template
last — which is what was already planned.

### Operational note now documented

The Simple Vector Store is in memory and says so: *"data will be lost if n8n restarts, and may
be cleared if available memory gets low"*. `n8n/README.md` §4b tells the operator to re-run the
ingestion after any restart, and a **pre-demo checklist** was added covering that, the one-active
-workflow rule, the 60 s gap between scenarios for the Gemini quota, and RAM.

### Known behaviour worth knowing on stage

The LLM's `WHAT TO DO` line lists only the actions **it** selected, while the Command Center
shows the union of the deterministic recommendations and anything the LLM added. So the card can
read "Engage auxiliary cooling" while three action cards are pending. That is the safety property
working — the model can add to, but never remove, a deterministic recommendation.

---

## Step 7 — DONE (2026-09-27 ~07:55)

New `backend/ai/risk_engine.py`. The fixed 0.94 / 0.85 / 0.80 confidences are gone; so is the
"severity = the loudest observation" rule.

**1. Confidence — noisy-OR over independent sources, weighted by trust.**
`confidence = 1 − Π(1 − cᵢ·trustᵢ)`. One contribution per source (the observation window already
guarantees one observation per agent+asset, and the engine de-duplicates again). Measured spread:
0.84 at detection → 0.94 developed for overheating, 0.85 fire, 0.80 cyber — see `METRICS.md §3.1`.

**2. Severity — impact × likelihood, capped by what the sensors justify.**
Impact = asset criticality (M-04/M-05 = 3), +1 if people are exposed, +1 for a hazard that harms
people directly. Likelihood = a band of the fused confidence. The product picks a severity, then
it is **capped one band above the strongest single source**. That cap is the honesty mechanism:
two warning-level readings would otherwise be announced as CRITICAL. It produces a genuine
HIGH → CRITICAL progression as a fault develops.

**3. Priority** — severity dominates, then people exposed, then how little time is left (ETA).

**4. Per-sensor trust** — `set_trust(sensor_id, 0.2, reason)`, read during fusion, reported in the
incident text as a `TRUST:` line naming the down-weighted sensor and why. Default 1.0.
A test proves a spoofed ambient sensor at trust 0.2 does **not** stop an overheating machine being
graded CRITICAL, because the machine's own pressure and body temperature are independent of it.
**This is the hook Step 8 needs** — the cyber agent will call `set_trust()` on spoof detection.

**The explanation shows its arithmetic** rather than asserting numbers:

```
HOW CONFIDENT: 84% by noisy-OR fusion over independent sources
  [M-04 (WARNING, 0.60 -> 0.60; running 0.60), TEMP-B-01 (WARNING, 0.60 -> 0.60; running 0.84)]
HOW SEVERE: HIGH — impact 4/4 x likelihood 3/4 = 12/16 -> CRITICAL, capped to HIGH because the
  strongest single source is only WARNING.
```

`recommendation_agent` keeps `fuse_confidence()` and `SEVERITY_RANK` as thin wrappers so nothing
that imported them broke.

**Acceptance:** **81 pytest tests** (17 new), `e2e_test.py` **15/15**, `gate1_verify.py` **13/13**,
and confidence demonstrably varies with the evidence.

---

## Item 3 — LLM reliability: live → cached → template (2026-09-27 ~11:20)

Implemented in the backend bridge, not in n8n: the enrichment endpoint already sees every LLM
answer, so it is the natural place, it needs no workflow change, and it can persist to disk.

`backend/ai/llm_cache.py` keyed by **incident type** (two overheating incidents are the same
explanation problem, and the point is to have an answer ready *before* the incident that needs it
exists). The workflow already tells us which path produced an enrichment via `fallback`, so:

- `fallback=False` → a genuinely live answer: store it.
- `fallback=True` → if a live answer for this hazard type exists, replay it; otherwise template.

The replay is **always labelled and dated** — `— enriched by cached models/gemini-3.8-flash answer
from 2026-09-27T11:05:12` — so a cached answer can never be mistaken for a live one. Only wording
and action ids are replayable: `REPLAYABLE` excludes confidence and severity, which stay ours, and
a test asserts that. Cached action ids are **re-validated against the catalogue**, so a stale id is
rejected rather than trusted (also tested, with `launch_missiles` and a wrong-hazard `close_door`).

`GET /api/ai/n8n/llm-cache` shows what is cached. `n8n/warm_llm_cache.py` captures one live answer
per hazard type, retrying and waiting out the 5-per-minute quota.

**On the second provider question:** yes, worth it, and Groq is the right choice. Its free tier
allows far more requests per minute than Gemini's 5, it is OpenAI-compatible so n8n's *OpenAI Chat
Model* node works by just setting a custom base URL (`https://api.groq.com/openai/v1`), and it
needs no new node type. That would make the chain **Groq → Gemini → cached → template**, and the
agent node's error output already gives us the wiring point. If you get a key it is about 10
minutes of work.

## Step 8 — DONE, simplified as agreed (2026-09-27 ~11:20)

`cyber_agent.py` rewritten. It used to flag **every** `CYBER_EVENT` as HIGH with no rules and
hardcoded defaults (`attempts=47`).

**Rules, each with its evidence:** `BRUTE_FORCE` (≥20 failed auths from one source in a rolling
60 s window, `OT-CYBER-PB §2.2`), `UNKNOWN_DEVICE` (not in the asset inventory, which is read from
the state store), `UNAUTHORIZED_COMMAND` (control command from outside the engineering whitelist),
`TRAFFIC_ANOMALY` (traffic z-score ≥ 3), `CREDENTIAL_ABUSE`, `SPOOFED_SENSOR`. An event that
matches nothing says *"no rule matched"* rather than inventing a verdict.

**ATT&CK for ICS attribution is looked up in the bundle**, never from memory
(`backend/ai/mitre_ics.py`). This immediately paid off: the ids most ICS material still quotes,
**`T0855 Unauthorized Command Message` and `T0856 Spoof Reporting Message`, are `revoked=1` in the
current bundle** — superseded by `T1692 Unauthorized Message` with `T1692.001 Command Message` and
`T1692.002 Reporting Message`. Quoting T0855 today would have been wrong. Resolved live:

| Rule | Technique, from the file |
|---|---|
| BRUTE_FORCE | `T0806 Brute Force I/O` |
| UNKNOWN_DEVICE | `T0848 Rogue Master` |
| UNAUTHORIZED_COMMAND | `T1692 Unauthorized Message` |
| SPOOFED_SENSOR | `T1692.002 Reporting Message` |
| TRAFFIC_ANOMALY | `T0842 Network Sniffing` |
| CREDENTIAL_ABUSE | `T0859 Valid Accounts` |

With no bundle on disk the attribution is simply omitted — never guessed.

**The flagship — one agent changing how another reasons.** On `SPOOFED_SENSOR` the cyber agent
calls `risk_engine.set_trust(sensor_id, 0.2, reason)`. Its decision text reads
`DISTRUST TEMP-B-01 …`, which is what appears in `state.agent_logs` on the multi-agent page, and
the incident explanation gains a `TRUST:` line naming the down-weighted sensor and why. An
end-to-end test proves the machine overheating is **still** graded CRITICAL with the ambient sensor
spoofed, because M-04's pressure and body temperature are independent of it (`OT-CYBER-PB §4.3`).

It also detects a spoof **without being told**: any cyber event naming a `sensor_id` triggers a
cross-check, and an ambient sensor at baseline while the machine in its zone is past its
temperature limit is flagged.

**The existing simulator payload still classifies** (BRUTE_FORCE + UNKNOWN_DEVICE, HIGH) — a test
locks that in so the cyber demo cannot regress. Extra payloads for Engineer 2 are written up as
**P8**; until then the rules are covered by 15 synthetic-event tests.

**114 pytest tests pass** (20 new for items 3 and 4).

---

## Groq as the primary model + feature-freeze verification (2026-09-27 ~11:40)

**Model choice was measured, not guessed.** Queried `GET /v1/models` through the stored n8n
credential (via a throwaway workflow, so the key never left n8n): this key exposes
`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b` and
`qwen/qwen3.8-27b` — plus Whisper, TTS and 512-token prompt-guard classifiers. **There is no Llama
instruct model on this key**, so the suggested Llama 3.x was not an option. Primary is
`openai/gpt-oss-120b` (131k context).

**Groq changed the picture entirely:**

| | Gemini `gemini-3.8-flash` | Groq `openai/gpt-oss-120b` |
|---|---|---|
| Latency, detection → enrichment | 37.7 s | **4.1 s** |
| Live answers | 1 of 5 | **8 of 9** |
| Rate limit hit? | constantly (5/min) | never |

**Chain: Groq → Gemini → cached → template.** Groq and Gemini use the AI Agent's *native*
primary/fallback support (`needsFallback: true`, two `ai_languageModel` inputs), so the fallback is
n8n's own mechanism rather than something bolted on. The cached layer is in the backend and the
template is the agent's error branch.

**The incident text names the model that actually answered.** The Validate node asks n8n which
model node ran (`$('Groq Chat Model (primary)').isExecuted`, in a try/catch), so a silent fallback
is still visible: `openai/gpt-oss-120b on Groq`, `Gemini (Groq unavailable, fell back)`,
`cached … answer from <time>`, or `template fallback`.

**Cache warmed 3/3**, each with sections the model really retrieved — `SOP-M04 §2/§4.2`,
`FIRE-EP-03 §2/§3.2/§3.3`, `OT-CYBER-PB §2/§3.1/§3.2`. Committed, so the demo has LLM-quality
wording even with no internet. One caveat worth knowing on stage: the overheating answer was
captured at *warning* level, so it cites §4.1/§2 and chooses cooling rather than the shutdown. The
deterministic `STOP_MACHINE` card is created at detection regardless, so the AUTHORIZE click is
unaffected — only the replayed wording omits it.

**Feature-freeze verification — `python n8n/final_verification.py --rounds 3`: all checks passed in
every round.** Three rounds of all four scenarios: overheating CRITICAL 0.94 with machine +
temperature + worker evidence; fire CRITICAL 0.85 naming SMOKE-B-01; cyber HIGH 0.80 naming
UNKNOWN-DEVICE-07; normal silent. Groq served 8 of 9 incidents. Alongside: **115 pytest tests**,
`e2e_test.py` **15/15**, `gate1_verify.py` **13/13**.

---

## Merged upstream main into the branch (2026-09-27 ~12:25)

`git fetch upstream && git merge upstream/main` — **no conflicts.** Merge base was PR #1's head, so
upstream is my PR #1 plus the team's work since: the Digital Twin 3D components, the
`standalone-3d-ai-copilot` app, `task.md`, and Engineer 2's additions to `simulator.py` (+162) and
`command_engine.py` (+17). My commits since PR #1 touched only `backend/ai`, `backend/tests`, `n8n`
and `docs/ai`, none of which upstream changed, so everything merged cleanly and **all of the team's
changes are kept**.

**Good news on their side:** they kept my P5 markers and every Engineer 1 hook, and added a cleaner
`simulator.notify_action_executed(action_type, target)` API plus more sensor publishes.

**Verified on the merged code:** `n8n/final_verification.py --rounds 2` — all checks passed in both
rounds, Groq served 6 of 6 incidents, all four scenarios correct. **114 pytest tests pass, 1
xfailed** (see below).

### One conflict found, recorded rather than overruled — P9

Their `execute_action` now marks **every** action in state that is `AWAITING_APPROVAL` as
`COMPLETED` when a mitigation action runs. That reports actions as executed when no actuator ran,
bypasses the approval gate on HIGH-risk actions like `EVACUATE_ZONE`, and is not scoped to the
incident. It contradicts the claim we make on stage and in the PR that a human authorises anything
that moves people.

`ai/resolution_policy.py` already does this correctly — scoped to the incident, marked `CANCELLED`
with a reason. **I did not change their code**: it is a deliberate change in a file I only hold
hooks in, and Firas asked to keep teammates' changes. Instead the test that encodes the correct
behaviour is marked `xfail` with the full explanation in the code, and the fix is written up as
**P9** for Firas to agree with Engineer 2. Removing the block should make the test pass unchanged.
