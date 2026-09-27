# METRICS — measured results

Every number here was produced by a script in this repo, on the demo laptop. Reproduce with the
command shown. No figure in this file is estimated.

---

## 1. Detection correctness (Steps 1–4)

`cd backend && ..\.venv\Scripts\python.exe -m pytest -q` → **64 passed**, runs in ~11 s with no
real-time sleeping (a `FakeClock` drives the trends).

Live through the API, all four demo scenarios:

| Scenario | Incidents | Type | Fused confidence |
|---|---|---|---|
| `machine_overheating` | 1 | `MACHINE_OVERHEATING` (M-04, machine + temperature + worker evidence) | 0.94 |
| `fire` | 1 | `INDUSTRIAL_FIRE` (smoke level + persistence) | 0.85 |
| `cybersecurity` | 1 | `CYBER_INTRUSION` | 0.80 |
| `normal` | 0 | — | — |

Before Step 1, `machine_overheating` produced **two** incidents, one of them `INDUSTRIAL_FIRE`
recommending water suppression on a compressor, with a reported trend of **+122 °C/min**. The
same ramp now reports **+2.0 °C/min** (per plant minute) and no fire is declared without smoke.

### End-to-end acceptance scripts

| Script | Checks | Result |
|---|---|---|
| `n8n/e2e_test.py` | 15 | **15/15**, three consecutive runs |
| `n8n/gate1_verify.py` | 13 | **13/13** (real websocket client, P5 decay, no re-open) |

GATE 1 was confirmed **passed in the real UI** by Firas on 2026-09-27: actions appear without
F5, authorising `STOP_MACHINE` resolves the incident, the other cards cancel as superseded,
M-04 returns to baseline, no new incident opens, and the n8n execution goes green.

---

## 2. LLM path — Gemini via the n8n AI Agent (Step 5)

Reproduce: `..\.venv\Scripts\python.exe n8n\llm_roundtrip.py`
Break test: `..\.venv\Scripts\python.exe n8n\llm_roundtrip.py --break`

Model: `models/gemini-3.8-flash` (chat), `models/gemini-embedding-001` (embeddings),
Google AI Studio **free tier**. Latency is measured from incident creation to the enrichment
arriving back at the backend, so it includes n8n overhead and the agent's tool calls.

### 2.1 When the model answers

| Run | Latency | Citations produced | Actions validated | Incident resolved |
|---|---|---|---|---|
| exec 22 | **37.7 s** | `SOP-M04 §4.1`, `SOP-M04 §2` | 1 of 1 | ✅ |

The reasoning was genuinely model-written and grounded in the real readings, for example:

> *"M-04 hydraulic pressure at 7.77 bar, exceeding the 7.2 bar warning level (limit 8.0 bar)"*
> *"Risk of temperature and pressure escalating to critical trip limits (80 °C and 8.0 bar),
> potentially leading to hydraulic line rupture or spindle damage"*

Note it cited **§4.1 (warning level)** rather than §4.2 (critical), because the readings were at
warning level when the incident was raised. That is the procedure being followed correctly, not
a mistake.

### 2.2 When it does not — 4 of 5 attempts fell back

All three failures below are **Google-side**, and all of them degraded cleanly to the
deterministic template with no operator-visible breakage:

| Run | Latency | What Google returned | Outcome |
|---|---|---|---|
| exec 20 | 2.0 s | `404` — `models/gemini-2.5-flash` *"is no longer available to new users"* | template, incident resolved |
| exec 21 | 19.3 s | `429` — free tier quota, **limit: 5 requests/minute** | template, incident resolved |
| exec 24 | 11.2 s | `503` — *"this model is currently experiencing…"* (overload) | template, incident resolved |
| exec 25 | 3.1 s | 503 / quota | template, incident resolved |
| deliberate `--break` | 0.0 s | model id set to a non-existent value | template, incident resolved |

**Success rate of the LLM path as measured: 1 / 5.** Success rate of *the system producing
validated recommendations and resolving the incident*: **5 / 5.**

### 2.3 What this means for the demo

- **The demo must not depend on Gemini.** It currently doesn't: the AI Agent node runs with
  `onError: continueErrorOutput` into the same deterministic template v1 uses, producing an
  identical payload, so every failure above still yielded 3 validated actions, a working
  approval flow, verification, and a resolved incident.
- **The free tier allows 5 model calls per minute** and one incident costs about 3, so
  back-to-back scenarios will throttle. `n8n/README.md` tells the operator to leave ~60 s
  between runs.
- This is the strongest argument for **Step 5b (NVIDIA NIM on Brev) as the primary model**, with
  Gemini second and the template last — which is the chain already planned.
- Tool calls cost model calls. Constraining the agent to one `procedure_search` call and
  `maxIterations: 3` cut usage from 6+ calls (which hit 429) to 2–3.

### 2.4 Retrieval worked regardless

In every execution the retrieval tools themselves succeeded: `procedure_search` (HTTP to the
backend keyword RAG) returned hits 4/4 times it was called, and the Simple Vector Store
retrieval plus its embeddings node succeeded. No retrieval failure was observed in any run.

Corpus: **5 procedure documents, 31 numbered sections**. Spot-checked ranking:

| Query | Top hit |
|---|---|
| machine overheating pressure emergency shutdown | `SOP-M04 §4.2` |
| smoke combustion suppression discharge | `FIRE-EP-03 §2` |
| spoofed sensor distrust reading | `OT-CYBER-PB §4` |

---

## 3. Still to be measured

- **Step 5b** — NIM on Brev: model name, latency, and the NIM → Gemini → template chain
  demonstrated once in each of its three states.
- **Step 6** — Isolation Forest on MetroPT-3 evaluated against SKAB, and the smoke RandomForest:
  precision / recall / F1 tables, plus the Brev instance type used for training.
- **Step 7** — confidence spread across scenarios once the risk engine replaces the provisional
  fusion, and the effect of a sensor trust factor on a spoofed-sensor case.
