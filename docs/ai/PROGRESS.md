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
