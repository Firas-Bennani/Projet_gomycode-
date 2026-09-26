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
