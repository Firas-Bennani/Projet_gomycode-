# AI layer: multi-agent correlation, n8n orchestration, risk engine, ML and cyber rules

Engineer 1's work, branch `ai/multi-agent`. Everything is additive to the AI layer plus a small
number of clearly-commented hooks. **One file outside my area was changed —
`backend/iot/simulator.py` — with Firas's explicit authorisation; see "For Engineer 2" below.**

**115 tests pass** (`cd backend && ..\.venv\Scripts\python.exe -m pytest -q`, ~22 s, no real-time
sleeping). Two end-to-end scripts: `n8n/e2e_test.py` **15/15** and `n8n/gate1_verify.py` **13/13**.
All measured numbers are in `docs/ai/METRICS.md` with the command that produced each one.

---

## The bug this started from

`POST /api/demo/scenario {"scenario":"machine_overheating"}` produced **two** incidents, one of
them `INDUSTRIAL_FIRE` recommending **water suppression on an overheating compressor**, with a
reported trend of `+122 °C/min`.

Cause: the orchestrator called `synthesize_incident()` with only the observations from the event it
happened to be handling. The simulator publishes the temperature reading and the machine status as
two separate events, so they never met — and the fire rule's guard was "hot but no machine
evidence", which was always true.

## What changed

**Correlation.** A per-zone 30 s observation window (`ai/observation_window.py`) keeps the newest
observation per `(agent, asset)`. Rule precedence with *required* evidence: fire needs smoke plus
two corroborating signals, overheating needs machine evidence. When neither holds the system
declares nothing and writes *why* into the agent log instead of guessing.

**Honest trends.** Least-squares slopes over the window, reported only after ≥10 s of history and
expressed per *plant* minute (the simulator compresses one minute of plant time into one tick).
`+122 °C/min` became `+2.0 °C/min`.

**Risk engine** (`ai/risk_engine.py`). The hardcoded 0.94 / 0.95 / 0.96 confidences are gone.
Confidence is noisy-OR fusion over independent sources weighted by per-sensor trust; severity is
impact × likelihood **capped one band above the strongest single source**, so two warning-level
readings can never be announced as CRITICAL. The incident text shows the arithmetic.

**n8n orchestration.** Incidents are POSTed to n8n fire-and-forget (3 s timeout, never blocking
detection). n8n retrieves the relevant procedure sections, asks Gemini for the explanation, posts
it back, then **waits up to 10 minutes for a human**. The owner's AUTHORIZE in the existing
dashboard resumes the execution, which then verifies the plant actually changed before closing the
incident. `backend/app/api/n8n_bridge.py` + one `include_router` line in `main.py`.

**The LLM cannot do anything dangerous.** It chooses only from the 8 entries in
`ai/actions_catalog.py`; risk level and "needs a human" come from the catalogue, never from the
model; it never sets the confidence. Ids it invents are rejected and logged.

**Resolution and re-opening.** An incident resolves when every *hazard-resolving* action has
completed and the readings are receding; unapproved actions are cancelled as superseded with a
reason. A resolved hazard only re-opens if values start climbing again (plus a 60 s cooldown).

**ML** (`ai/ml_models.py`). Isolation Forest on MetroPT-3, ROC AUC **0.976** in-domain, fitted only
on normal operation after removing the failure windows documented in the dataset's own PDF. It
**annotates**; the deterministic rules still decide, and a test deletes the model file and asserts
an identical verdict. A smoke classifier was trained, measured (F1 0.93) and **deliberately not
shipped** — in that public dataset every fire indicator is *negatively* correlated with the alarm
label, and wired up it reported 0% fire at 75 ppm of smoke. The reasoning is in `METRICS.md §4.2`.

**Cyber** (`ai/mitre_ics.py`, `ai/agents/cyber_agent.py`). Real rules instead of "everything is
HIGH": brute force over a rolling 60 s window, unknown device against the asset inventory,
unauthorized command, traffic z-score, credential abuse, spoofed sensor. ATT&CK for ICS techniques
are **looked up in the published STIX bundle at runtime** — which mattered: `T0855` and `T0856`,
the two ids most ICS material still quotes, are **revoked** in the current release.

**The flagship.** When the cyber agent concludes a sensor is lying it calls
`risk_engine.set_trust(sensor_id, 0.2)` — distrust, not ignore. A machine overheating is still
detected as CRITICAL with its ambient sensor spoofed, because the machine's own pressure and body
temperature are independent of it. Visible in `state.agent_logs` as *"Distrust TEMP-B-01"*.

---

## ⚠️ For Engineer 2 — one change in your file, and four proposals

**Applied with Firas's authorisation (please review): `backend/iot/simulator.py`, marked with
`P5 (Engineer 1)` comments.** Once `STOP_MACHINE` / cooling / suppression completes, the readings
decay to baseline and stay there until reset, and `reset()` clears the flags. Without it,
`command_engine` set M-04 to a safe baseline and the next tick overwrote it with the fault curve
(8.93 bar), so a brand-new CRITICAL incident opened seconds after the operator resolved the first
one — observed live in the UI. The behaviour I depend on is only *"once the remedy has executed,
stop driving that asset's fault until reset"*; any implementation of that is fine.

Everything else is a **proposal only**, written up in `docs/ai/PROPOSED_CHANGES_FOR_TEAM.md`:

- **P1** — publish the temperature reading in `_tick_fire` (would take fire evidence from one
  sensor to two independent ones).
- **P2** — publish a `SCENARIO_CHANGED` event so I can drop a defensive workaround.
- **P6** — `_tick_overheating` updates `PRES-B-01` but never *publishes* it, so the dashboard's
  pressure tile shows a stale 5.33 bar while the machine card shows 8.31. **This is the cause of
  the tile mismatch Firas spotted** — not a frontend bug.
- **P8** — extra cyber payloads so the new rules can fire live. The existing payload keeps working
  and a test locks that in.

## For Engineers 3 and 4 (frontend)

No frontend changes were made or are required. Two optional niceties in
`PROPOSED_CHANGES_FOR_TEAM.md` **P7**: the incident card never renders `incident.status`, so
`RESOLVING` / `RESOLVED` / `ESCALATED` are invisible and an escalated incident drops out of the
"ACTIVE ALERTS" count. I work around it by writing a banner into `ai_reasoning`, which *is*
rendered.

One thing worth knowing: the AI layer previously never announced an action when it was **created**
— only `command_engine` published on authorise/execute/complete. So pending actions never reached
the Command Center until a page refresh. `ai/action_events.py` now publishes `ACTION_STATUS` with
exactly the payload `App.tsx` already consumes, and the incident is announced before its actions.

## Running the n8n part

Full instructions in **`n8n/README.md`**. The short version:

1. `npx --yes n8n@2.40.7` with the env in §1 (Docker Desktop would not start on the demo laptop,
   so n8n runs as a plain Node process; the compose services are still declared for a bigger box).
2. Create the owner account, then an API key, into `.env` as `N8N_API_KEY`.
3. `python n8n/import_workflows.py n8n/workflows/incident_response_v2.json --activate`.
4. Add the Gemini credential to the three Gemini nodes in the n8n UI.

**Two things that will bite you:**

- Use `127.0.0.1`, **not** `localhost`, for `BACKEND_BASE_URL_FOR_N8N`. Node resolves `localhost`
  to IPv6 `::1` first while uvicorn binds IPv4 only, and n8n's HTTP node just says "connection
  refused".
- **The Simple Vector Store is in memory. Re-run the RAG ingestion after any n8n restart.** The
  node itself warns data is lost on restart. Retrieval also falls back to the backend's keyword
  RAG, which needs no ingestion, so nothing breaks — you just lose semantic search.

**If n8n is not running at all, none of this matters:** detection, actions, approval, verification
and resolution are entirely backend-side. Set `N8N_ENABLED=false` to run with no n8n.

## Gemini reliability, measured

Only **1 of 5** live attempts succeeded: 404 (model retired), 429 (free tier is 5 requests/minute),
503 (overload), plus a deliberate break test. All five still produced validated recommendations and
a resolved incident, because the AI Agent's error branch runs the same deterministic template.
There is now also a **cached-answer layer**: the last good LLM answer per hazard type is replayed,
clearly labelled and dated, before falling back to the template. Chain:
**live → cached → template**.

Leave ~60 s between demo scenarios or the quota throttles you.

## Files

| Area | Files |
|---|---|
| New AI modules | `ai/{clock,trend,observation_window,risk_engine,resolution_policy,ml_models,llm_cache,mitre_ics,action_events,actions_catalog}.py` |
| Rewritten agents | `ai/orchestrator.py`, `ai/agents/{temperature,machine,recommendation,cyber}_agent.py`, `ai/rag/rag_engine.py` |
| New router | `app/api/n8n_bridge.py` (+1 line in `main.py`) |
| Hooks | `app/services/command_engine.py`, `docker-compose.yml`, `.env.example`, `requirements.txt` |
| Authorised change | `iot/simulator.py` (P5) |
| Corpus | `ai/rag/corpus/*.md` — 5 procedures, 31 numbered sections |
| Model | `ai/models/machine_iforest.joblib` (686 KB) |
| n8n | `n8n/workflows/*.json`, `n8n/{README,import_workflows,export_workflows,e2e_test,gate1_verify,llm_roundtrip,warm_llm_cache}` |
| Tests | `backend/tests/*` — 115 tests |
| Docs | `docs/ai/{PLAN,PROGRESS,METRICS,DEMO,PROPOSED_CHANGES_FOR_TEAM}.md` |

Raw datasets are gitignored; the training scripts take `--metro` / `--skab` / `--csv` paths.
