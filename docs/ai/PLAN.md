# AI Industrial Copilot — Engineer 1 master plan

> This is the verbatim master prompt for my part of the hackathon (Multi-Agent AI + n8n orchestration).
> Deadline: **Sunday 17:00 Europe/London**. Re-read this and `PROGRESS.md` if the session restarts.

---

You are my pair-programmer for a 24-hour AI hackathon. The deadline is **Sunday 17:00 (Europe/London)**. It is Saturday ~22:30 now. I am Engineer 1 of a team of 4. We work step by step, and you STOP whenever you need me. Read this whole prompt before doing anything.

## 1. Project and repository

- Team repo: `https://github.com/amalmch/Projet_gomycode-` ("AI Industrial Copilot").
- Stack already in the repo: FastAPI backend (`backend/`), React + TypeScript + Three.js frontend (`frontend/`), in-process simulator (`backend/iot/simulator.py`), in-process event bus (`backend/app/services/event_bus.py`), in-memory state (`backend/app/services/state_store.py`), docker-compose (backend, frontend, redis, mosquitto).
- Demo scenarios are triggered with `POST /api/demo/scenario` body `{"scenario": "normal|machine_overheating|cybersecurity|fire"}` and reset with `POST /api/demo/reset`.

## 2. What I own (and what I must NOT touch)

**I OWN (you may change freely):**
- `backend/ai/` — orchestrator, agents (`temperature_agent`, `machine_agent`, `worker_agent`, `cyber_agent`, `recommendation_agent`), `rag/`.
- New files I create: `backend/ai/models/`, `backend/ai/data/`, `backend/ai/rag/corpus/`, `backend/scripts/`, `backend/tests/`, `n8n/`, `docs/ai/`.
- A NEW router `backend/app/api/n8n_bridge.py` (+ ONE `include_router` line in `backend/app/main.py`).
- Small, clearly-commented hooks in `backend/app/services/command_engine.py`, `docker-compose.yml`, `backend/requirements.txt`, `.env.example`.

**I do NOT own — never modify without asking me first:**
- `frontend/**` (Engineers 3 and 4), `backend/iot/**` (Engineer 2), `backend/app/models/schemas.py` (shared contract: additive optional fields only, and only after I say OK), other routers in `backend/app/api/`.
- If a change there is needed, write the proposed patch into `docs/ai/PROPOSED_CHANGES_FOR_TEAM.md` and tell me who must apply it.

**Outputs must stay compatible:** agents keep returning the same dict keys the orchestrator/UI already uses (`agent_id`, `anomaly`, `severity`, `observation`, `decision`, …); incidents keep the `Incident` schema; `state.agent_logs` format stays the same (the AI-1 page reads it). You may ADD keys, never remove or rename.

## 3. Known problems you must fix (verified by running the repo)

1. **Correlation bug (critical):** the orchestrator processes each event alone. Running `machine_overheating` produced an `INDUSTRIAL_FIRE` incident with "Rate: +122 °C/min", because the temperature observation arrived without the machine observation and the fire rule fired; slopes are computed over fractions of a second.
2. **Hardcoded confidences** (0.94 / 0.95 / 0.96) in `recommendation_agent.py`.
3. **No LLM** (`LLM_PROVIDER="simulated"`), RAG is keyword matching over 3 hardcoded texts.
4. **No ML models.**
5. **Cyber agent** flags every `CYBER_EVENT` as HIGH without rules.
6. **Worker agent** uses a hardcoded dict `ZONE_B: [W23, W41, W52]` instead of `state_store`.
7. Mosquitto runs but nothing uses MQTT. **Decision: do NOT add MQTT for my part.** n8n talks to the backend over HTTP.

## 4. Target architecture for my part

```
simulator → event_bus → orchestrator (per-zone 30 s observation window)
   → agents (rules + trend/ETA + ML models) → risk engine (noisy-OR fusion, severity matrix, dedup)
   → Incident (existing schema) → existing Actions flow (UI AUTHORIZE → command_engine)
   → POST incident to n8n webhook (async, non-blocking, 3 s timeout)
        n8n: RAG (PGVector) + LLM AI Agent + Structured Output → validate actions against catalog
             → POST enrichment back to backend (/api/ai/n8n/enrichment/{incident_id}) incl. $execution.resumeUrl
             → Wait (On Webhook Call, limit 180 s)
        backend: when owner AUTHORIZES/CANCELS in the existing UI → command_engine POSTs decision to resume_url
        n8n: Wait 15 s → GET /api/ai/n8n/verify/{incident_id} → POST final status (RESOLVING / ESCALATED)
```

Rules:
- **Detection is deterministic and never depends on n8n or the LLM.** If n8n is down or slow, the current template recommendations are used (fallback). Env flag `N8N_ENABLED=true|false`.
- **The LLM never invents actions.** It chooses from an action catalog; risk level and `requires_confirmation` come from the catalog, never from the LLM.
- Store resume URLs in a backend-side dict (e.g. `state.n8n_resume_urls[incident_id]` created in my own module), NOT in `schemas.py`.
- Never present predictions as facts: "risk detected", "confidence", "evidence".

## 5. HOW WE WORK — the protocol (follow strictly)

1. At the start of each step, print: **step number, goal, files you will touch, expected duration**.
2. Do all the work you can do alone (code, scripts, tests, running commands). Run the code — don't just write it.
3. When you need me (a download, a login, a click in the n8n UI, an API key, a decision, a teammate), STOP and print exactly this block, then wait:

```
🛑 YOUR TURN — Step X.Y
WHAT I NEED YOU TO DO:
  1. …
  2. …
RESOURCES FOR THIS:
  🎬 Video: <url> — watch <which part / minutes>, why it helps
  📦 Repo / dataset: <url> — what to download/clone/extract, and WHERE to put it (exact path)
  📄 Doc: <url>
WHEN DONE, REPLY WITH: <exactly what to paste back, e.g. "GO", an error message, a URL, a screenshot>
```

4. Never continue past a 🛑 until I reply. Never assume a download or UI action happened — verify it (check the file exists, call the endpoint).
5. At the end of each step: run its **acceptance test**, show me the result, give a 3–5 line explanation of what changed and WHY (I must be able to explain it to the jury), then `git commit` with a clear message, and update `docs/ai/PROGRESS.md` (step done, what works, what's next, known issues).
6. If something takes more than 2× its planned time, STOP and propose a simpler alternative. The demo matters more than perfection.
7. Ask me before: deleting files, changing files I don't own, adding a new heavy dependency, or anything that costs money.
8. Keep secrets out of git: API keys go in `.env` (gitignored), with placeholders in `.env.example`.
9. Datasets and model binaries go under `backend/ai/data/raw/` and `backend/ai/models/`; add the raw data to `.gitignore` (models < 5 MB may be committed).
10. Ask me my OS at Step 0 and give commands that work on it (Windows PowerShell vs macOS/Linux).
11. If our conversation gets long or restarts, re-read `docs/ai/PLAN.md` and `docs/ai/PROGRESS.md` before continuing.

## 6. The steps

Times are targets. **GATE 1 (Step 4) must be done by 01:30 Sunday.** If late, skip Step 5 tonight.
**Cut order on Sunday if time runs out (cut from the bottom):** Step 10 → Step 9 → Step 8 → Step 6. Never cut Steps 1–4.

---

### STEP 0 — Setup and reproduce the bug (22:30–22:50)

- Ask my OS. Check versions: git, Python ≥ 3.10, Docker + Docker Compose, Node ≥ 18.
- Clone the repo into the current folder if not already there, then create branch `ai/multi-agent`.
- Save this whole prompt to `docs/ai/PLAN.md`; create `docs/ai/PROGRESS.md`.
- Run the backend (locally with a venv or via `docker compose up backend`), trigger `machine_overheating`, `GET /api/incidents`, and show me the wrong incident type (the bug).
- 🛑 if Docker isn't installed or any version is missing. Resources:
  - 🎬 Docker Compose basics: https://www.youtube.com/watch?v=Xwu1Pbmh6t0 (first 15 min)
  - 📄 Docker Desktop: https://docs.docker.com/get-started/get-docker/
- Also ask me whether I have **push rights** on the team repo. If not: I fork it, and you set `origin` to my fork and `upstream` to the team repo.
- **Acceptance:** backend runs, bug reproduced and shown.

### STEP 1 — Fix correlation + deterministic scenario tests (22:50–23:50) ⭐

- Add a per-zone sliding window of recent observations (30 s, keyed by `zone`, newest observation per agent per asset). `synthesize_incident` receives the window, not only the current event's observations.
- Agents compute slopes only when they have ≥ 10 s of history (use a least-squares slope over the window, not first-vs-last).
- Rule precedence: FIRE requires ≥ 2 independent sources (temperature rate/level + smoke); MACHINE_OVERHEATING requires machine evidence (pressure/temperature on an asset). Machine evidence present in the zone → overheating wins over fire unless smoke is present.
- Keep dedup (same type + zone while ACTIVE) and add a 60 s cooldown after resolution.
- Write `backend/tests/test_scenarios.py` (pytest): seed `random`, drive the simulator ticks without real-time sleeping (or monkeypatch time), feed events through the orchestrator, and assert: `machine_overheating → MACHINE_OVERHEATING`, `fire → INDUSTRIAL_FIRE` (or the existing fire type name), `cybersecurity → cyber type`, `normal → no incident`.
- 🛑 only if the simulator's structure prevents deterministic testing — then show me the minimal change needed in `iot/` and I'll ask Engineer 2.
- 🎬 If I need it: asyncio refresher https://www.youtube.com/watch?v=Qb9s3UiMSTA
- **Acceptance:** all scenario tests pass 3 runs in a row; live run via the API also gives the right types.

### STEP 2 — n8n + PGVector infrastructure (23:50–00:20)

- Add to `docker-compose.yml`:
  - `n8n` (image `n8nio/n8n`, port 5678, volume `n8n_data`, env `GENERIC_TIMEZONE=Europe/London`, `N8N_SECURE_COOKIE=false`, `WEBHOOK_URL=http://n8n:5678/`).
  - `pgvector` (image `pgvector/pgvector:pg16`, own volume, used only by n8n for RAG).
- Backend env: `N8N_ENABLED`, `N8N_INCIDENT_WEBHOOK_URL=http://n8n:5678/webhook/incident`. If I run the backend outside Docker, tell me to use `http://localhost:5678/...` for the backend and `http://host.docker.internal:8000` for n8n → backend calls.
- Start the stack and check n8n answers on http://localhost:5678.
- 🛑 YOUR TURN: open n8n, create the owner account; create credentials: **Postgres** (host `pgvector`, db/user/password from compose) and my **LLM provider**. Ask me which provider/API key I have (OpenAI, Google Gemini, Anthropic, or local Ollama). Note: embeddings need OpenAI, Gemini, Ollama, Cohere or Mistral — if I only have an Anthropic key, recommend a free Gemini key for embeddings (https://aistudio.google.com/apikey).
  - 🎬 n8n from zero: https://www.youtube.com/watch?v=1jDEZGjvXbk (first 30 min)
  - 🎬 n8n install + core nodes: https://www.youtube.com/watch?v=HaSaDsn3AMg (installation chapter)
  - 📄 https://docs.n8n.io/hosting/installation/docker/
- **Acceptance:** n8n reachable, both credentials show "Connection tested successfully".

### STEP 3 — Backend ↔ n8n bridge + workflow v1 without LLM (00:20–01:00)

- In my code (not schemas): after an incident is created, fire-and-forget POST of the incident JSON (plus `allowed_actions` from an action catalog, workers, evidence) to the n8n webhook, 3 s timeout, logged, never blocking the orchestrator.
- Action catalog in `backend/ai/actions_catalog.py`, mapped to the action types `command_engine` already supports (read it first). Each entry has `risk` (LOW/MEDIUM/HIGH), `auto` and `requires_confirmation`.
- New router `backend/app/api/n8n_bridge.py`:
  - `POST /api/ai/n8n/enrichment/{incident_id}` — receives `{what, why[], impact, prediction, recommended_action_ids[], sources[], resume_url}`, validates the IDs against the catalog, updates the incident's explanation fields (`ai_reasoning` etc.), stores `resume_url`, and logs an agent step "recommendation_agent (n8n)".
  - `GET /api/ai/n8n/verify/{incident_id}` → `{verified: bool, status, details}` based on actions and sensor state.
  - `POST /api/ai/n8n/status/{incident_id}` → sets RESOLVING/RESOLVED/ESCALATED + agent log.
- Hook in `command_engine.authorize_action` / `cancel_action`: if a resume URL exists for the action's incident, POST `{"decision": "approve"|"cancel", "action_id", "by"}` to it (async, timeout, error-tolerant).
- Generate `n8n/workflows/incident_response_v1.json` (importable) with the nodes: Webhook (POST `/incident`, respond immediately) → Code "Template recommendation" → Code "Validate against allowed_actions" → HTTP POST enrichment (include `{{$execution.resumeUrl}}`) → Wait (On Webhook Call, POST, limit 180 s) → IF approved → Wait 15 s → HTTP GET verify → IF verified → HTTP POST status RESOLVING, else ESCALATED. Timeout/cancel branch → POST status ESCALATED/DISMISSED.
- 🛑 YOUR TURN: import the JSON (Workflows → Import from File), select credentials if asked, **Activate/Publish it** (production webhook URL, not the test URL), reply GO.
  - 🎬 Webhooks + IF: https://www.youtube.com/watch?v=cgbtHBVmMFc
  - 🎬 HTTP Request node: https://www.youtube.com/watch?v=DC-DgmSGBBU
  - 🎬 Wait node resumed by webhook (our approval mechanism): https://www.youtube.com/watch?v=Jrlu8fOOpe8
  - 📄 Wait node docs: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait/
- Then test yourself with curl: trigger a scenario, check the n8n execution is waiting, call the resume URL, check the incident status.
- **Acceptance:** an incident triggers an n8n execution that shows in n8n's Executions view; curl-approval resumes it; the backend receives enrichment and final status.

### STEP 4 — GATE 1: end-to-end with the real UI (01:00–01:30) 🚩

- Run the whole stack (frontend included). Trigger `machine_overheating` from the demo bar.
- 🛑 YOUR TURN: in the dashboard, click AUTHORIZE on the pending action; tell me what you see (incident panel, action status, 3D). Keep n8n's Executions tab open and tell me whether the execution turned green.
- Fix whatever breaks on my side only. If the fix is in frontend/iot, write it to `docs/ai/PROPOSED_CHANGES_FOR_TEAM.md`.
- Export the workflow JSON again to `n8n/workflows/`, commit, `git tag gate1`, push.
- **Acceptance:** owner clicks AUTHORIZE → machine stops → incident RESOLVED → n8n execution green. Three runs in a row.

### STEP 5 — RAG + LLM in n8n (01:30–02:30, else Sunday 07:00)

- Write 5 short procedure documents (Markdown, numbered sections like §4.2) in `backend/ai/rag/corpus/`: `SOP-M04-Compressor.md`, `Fire-Emergency-Procedure.md`, `Evacuation-Procedure.md`, `OT-Cyber-Incident-Playbook.md`, `Maintenance-Plan.md`. Reuse and expand the 3 texts already in `rag_engine.py`. Make `rag_engine.py` read these files for the keyword fallback.
- Generate `n8n/workflows/rag_ingestion.json`: Manual Trigger → read files (mount `backend/ai/rag/corpus` into the n8n container read-only, e.g. at `/data/corpus`) → Default Data Loader (chunk ~400, overlap 50, metadata `doc_id`, `hazard`) → Embeddings → Postgres PGVector Store (Insert).
- Generate `n8n/workflows/incident_response_v2.json`: replace "Template recommendation" with an **AI Agent** (chat model temperature 0.2, PGVector "retrieve as tool", limit 4, **Structured Output Parser** with schema `{what, why[], impact, prediction, recommended_action_ids[], sources[]}`, system prompt: choose ONLY from `allowed_actions`, cite procedure sections, never claim certainty; include an example JSON in the system message). Set the agent node's error handling to "continue (error output)" → template Code node → Merge.
- 🛑 YOUR TURN: import both, set credentials, run ingestion once, activate v2 (deactivate v1), reply GO.
  - 🎬 RAG agent in n8n: https://www.youtube.com/watch?v=ToOv4mcTo50
  - 🎬 Structured Output Parser: https://www.youtube.com/watch?v=phXTLzgOohQ
  - 📄 https://docs.n8n.io/advanced-ai/rag-in-n8n/
- **Acceptance:** incidents show LLM what/why/impact with `sources`; with the LLM credential broken, the template still arrives.
- Then print: "💤 Sleep checkpoint — commit done, PROGRESS.md updated. Next: Step 6." and stop.

### STEP 6 — ML models (Sunday 07:00–09:00)

- 🛑 YOUR TURN (downloads — try the UCI download yourself first; Kaggle needs my login):
  - 📦 MetroPT-3 (compressor pressure/temperature/current, real failures): https://archive.ics.uci.edu/dataset/791/metropt+3+dataset → extract the CSV to `backend/ai/data/raw/metropt3/`
  - 📦 SKAB (labelled pump anomalies, for evaluation): `git clone https://github.com/waico/SKAB backend/ai/data/raw/SKAB` (only `data/` is needed)
  - 📦 Smoke Detection IoT (Kaggle): https://www.kaggle.com/datasets/deepcontractor/smoke-detection-dataset → `backend/ai/data/raw/smoke/smoke_detection_iot.csv`
  - 🎬 Isolation Forest: https://www.youtube.com/watch?v=O9VvmWj-JAk
- Add `scikit-learn`, `joblib`, `pandas`, `numpy` to requirements.
- `backend/scripts/train_machine_iforest.py`: MetroPT-3 features TP2, TP3, Oil_temperature, Motor_current; drop the documented failure windows (see the UCI page), resample 10 s, StandardScaler + IsolationForest(contamination=0.01) → `backend/ai/models/machine_iforest.joblib`. Evaluate on SKAB (Pressure, Temperature, Current, Voltage — z-scored) and print precision/recall/F1 into `docs/ai/METRICS.md`.
- `backend/scripts/train_smoke.py`: RandomForest on the smoke features → `backend/ai/models/smoke_rf.joblib` + feature list. Print metrics into `METRICS.md`.
- Integrate: `machine_agent` adds `anomaly_score`, `most_deviant_feature`, `eta_to_limit_s` = (limit − value)/slope when slope > 0, and a readable sentence ("At the current rate M-04 reaches 8.0 bar in ~40 s"). `temperature_agent` adds `smoke_probability` when smoke-related inputs exist. **If a model file is missing or features are unavailable, agents fall back to rules silently.** Map simulator values to model features with z-scores; document the mapping.
- If the simulator lacks features the smoke model needs, write the proposal in `PROPOSED_CHANGES_FOR_TEAM.md` (for Engineer 2) and use only available features.
- **Acceptance:** tests still pass; incidents show model score and ETA; `METRICS.md` has 2 metrics tables.

### STEP 7 — Risk engine: real confidence and severity (09:00–09:45)

- `backend/ai/risk_engine.py`: noisy-OR fusion `confidence = 1 − Π(1 − cᵢ·trustᵢ)` over independent sources; per-sensor `trust` (default 1.0); severity from an impact × likelihood matrix (impact from asset criticality, +1 if workers exposed, +1 for fire/pressure); priority = severity, workers exposed, ETA.
- Remove every hardcoded confidence in `recommendation_agent.py`; the reasoning text shows the real numbers and lists each evidence with its contribution.
- Unit tests for fusion and severity.
- **Acceptance:** confidence varies with the evidence; tests pass.

### STEP 8 — Cyber rules + spoofed sensor + MITRE ATT&CK for ICS (09:45–10:45)

- 🛑 YOUR TURN: download 📦 `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/ics-attack/ics-attack.json` to `backend/ai/data/raw/mitre/` (try it yourself first; ask me only if it fails). Repo for reference: https://github.com/mitre-attack/attack-stix-data
- Cyber agent rules: ≥ N failed auths from one source in 60 s → BRUTE_FORCE; device not in inventory → UNKNOWN_DEVICE; command to a controller from a non-whitelisted source → UNAUTHORIZED_COMMAND; traffic z-score → TRAFFIC_ANOMALY; physical inconsistency between correlated sensors → SPOOFED_SENSOR. Map each to an ATT&CK for ICS technique by **looking up names/IDs in the STIX file** (never hardcode from memory) and add the technique to evidence.
- SPOOFED_SENSOR → agent log message "Distrust <sensor_id>" → risk engine sets that sensor's trust to 0.2 → overheating stays detected even if its temperature sensor is spoofed. This is the flagship "agents influence each other" moment: make it visible in `state.agent_logs`.
- The simulator currently sends one generic cyber event. Write the extra cyber/spoof event payloads needed in `PROPOSED_CHANGES_FOR_TEAM.md` for Engineer 2; meanwhile test with synthetic events in pytest.
- 🛑 YOUR TURN: send the proposal to Engineer 2; reply GO when merged (or "SKIP" to keep the synthetic tests only).
- **Acceptance:** tests show each rule firing, and a spoofed sensor does not hide overheating.

### STEP 9 — Worker agent from real state (10:45–11:30)

- Read workers/zones/PPE from `state_store` (read `state_store.py` first); remove the hardcoded dict. Add `workers_in(zone)` / `headcount(zone)` used by the orchestrator for every incident's `affected_workers`.
- Rules: restricted zone without authorization, off-shift presence, dwell time in a dangerous zone, missing PPE in a PPE-required zone. Recommend door closing (MEDIUM) for intrusions if `command_engine` supports doors (check first; otherwise propose it to the team).
- **Acceptance:** tests for each rule; overheating incident lists the workers actually in the zone.

### STEP 10 — n8n Threat Watch (11:30–12:30, optional)

- Generate `n8n/workflows/threat_watch.json`: Schedule Trigger (daily 07:00) + Manual Trigger → HTTP Request to a public ICS advisory source (first **verify** which URL works: the CISA ICS advisories feed, or the NVD API `https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=<vendor>`) filtered by vendors in our asset list → AI Agent summary (Structured Output: title, severity, affected asset, recommendation) → POST to a new endpoint in `n8n_bridge.py` that stores "threat watch" cards in state.
- 🛑 YOUR TURN: import, set credentials, run once manually (so the demo shows cached results), reply GO. Tell me which endpoint Engineer 4 can use to display the cards.
- **Acceptance:** cards available from the endpoint.

### STEP 11 — 13:00 FEATURE FREEZE → hardening + demo (13:00–16:00)

- Export all workflows to `n8n/workflows/`. Write `n8n/README.md`: import order, credentials, which workflows to activate.
- 🛑 YOUR TURN: run `docker compose down -v` then `docker compose up --build` from scratch; re-import the workflows and credentials following `n8n/README.md`; tell me any failure.
- Run all tests + each scenario 3×. Fix blocking bugs only.
- Write `docs/ai/DEMO.md`: the exact demo script (normal 20 s → overheating 90 s with n8n Executions view on screen → fire 60 s → cyber 45 s), what to say at each step, the metrics from `METRICS.md`, and the fallback plan if the internet or the LLM fails.
- Final commit, push, open a PR to the team repo with a clear description of my changes and what teammates must know.

## 7. Style

- Short explanations, in simple English (I'm comfortable with C#/.NET; Python is fine but explain non-obvious async or pandas parts in one line).
- Show me commands before long-running operations (> 2 min) and big downloads.
- Prefer small, working increments over big rewrites.
