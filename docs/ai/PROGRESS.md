# PROGRESS — Engineer 1 (Multi-Agent AI + n8n)

Branch: `ai/multi-agent`. Plan: [PLAN.md](PLAN.md).

| Step | Status | Notes |
|---|---|---|
| 0 — Setup + reproduce bug | ✅ DONE | Bug reproduced, 2 wrong incidents |
| 1 — Fix correlation + tests | ⏳ next | |
| 2 — n8n + PGVector infra | ⬜ | |
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
