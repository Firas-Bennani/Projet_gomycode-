# METRICS — measured results

Every number here was produced by a script in this repo, on the demo laptop. Reproduce with the
command shown. No figure in this file is estimated.

---

## 1. Detection correctness (Steps 1–4)

`cd backend && ..\.venv\Scripts\python.exe -m pytest -q` → **81 passed**, runs in ~11 s with no
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

## 2. LLM path (Steps 5 + item 3)

### 2.0 Groq is now the primary model, and it changed the picture entirely

Added after Gemini proved unusable on the free tier. The model was chosen from the list the key
**actually exposes** (`GET /v1/models` through the stored n8n credential): `openai/gpt-oss-120b`,
`openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b` — everything else on the
key is Whisper, TTS or a 512-token prompt-guard classifier. **No Llama instruct model is available
on this key.** Primary is `openai/gpt-oss-120b` (131k context).

| | Gemini `gemini-3.8-flash` | **Groq `openai/gpt-oss-120b`** |
|---|---|---|
| Latency, detection → enrichment back | 37.7 s | **4.1 s** (9× faster) |
| Attempts that produced a live answer | **1 of 5** | **8 of 9** |
| Rate limit | 5 requests/minute | far higher; never hit it |
| Citations produced | yes | yes |

Chain, in order: **Groq → Gemini → cached answer → deterministic template.** Groq and Gemini are
wired as the AI Agent's native primary and fallback models (`needsFallback: true`, two
`ai_languageModel` inputs); the cached layer and the template live in the backend and the
workflow's error branch respectively.

The incident text names the model that actually answered — the Validate node asks n8n which model
node executed (`$('Groq Chat Model (primary)').isExecuted`), so a silent fallback is still visible:

```
— enriched by openai/gpt-oss-120b on Groq via n8n AI Agent; 3 of 3 proposed action(s) validated
```

reading `Gemini (Groq unavailable, fell back)` or `cached … answer from <time>` on the other paths.

### 2.1 Gemini, measured before Groq existed — kept because it justifies the chain

Reproduce: `..\.venv\Scripts\python.exe n8n\llm_roundtrip.py`
Break test: `..\.venv\Scripts\python.exe n8n\llm_roundtrip.py --break`

Model: `models/gemini-3.8-flash` (chat), `models/gemini-embedding-001` (embeddings),
Google AI Studio **free tier**. Latency is measured from incident creation to the enrichment
arriving back at the backend, so it includes n8n overhead and the agent's tool calls.

#### When Gemini answered

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

#### When it did not — 4 of 5 attempts fell back

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

### 2.2 What this means for the demo

- **The demo must not depend on Gemini.** It currently doesn't: the AI Agent node runs with
  `onError: continueErrorOutput` into the same deterministic template v1 uses, producing an
  identical payload, so every failure above still yielded 3 validated actions, a working
  approval flow, verification, and a resolved incident.
- **The free tier allows 5 model calls per minute** and one incident costs about 3, so
  back-to-back scenarios will throttle. `n8n/README.md` tells the operator to leave ~60 s
  between runs.
- Brev was never approved, so the answer was a **second provider instead of a bigger model**:
  Groq, added in §2.0, which is both faster and far more reliable on its free tier. Gemini is now
  the fallback rather than the primary.
- Tool calls cost model calls. Constraining the agent to one `procedure_search` call and
  `maxIterations: 3` cut usage from 6+ calls (which hit 429) to 2–3.

### 2.3 Retrieval worked regardless

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

## 3. Risk engine (Step 7)

`cd backend && ..\.venv\Scripts\python.exe -m pytest -q` → **81 passed** (17 new risk-engine
tests). Both acceptance scripts still pass after the change: `e2e_test.py` **15/15**,
`gate1_verify.py` **13/13**.

### 3.1 Confidence now varies with the evidence

Measured live, after the fixed 0.94 / 0.85 / 0.80 literals were replaced by noisy-OR fusion
(`confidence = 1 − Π(1 − cᵢ·trustᵢ)`):

| Scenario | Sources fused | Confidence | Severity |
|---|---|---|---|
| `machine_overheating` (at detection) | M-04 WARNING + TEMP-B-01 WARNING | **0.84** | HIGH |
| `machine_overheating` (developed) | M-04 CRITICAL + TEMP-B-01 WARNING | **0.94** | CRITICAL |
| `fire` | SMOKE-B-01 CRITICAL | **0.85** | CRITICAL |
| `cybersecurity` | UNKNOWN-DEVICE-07 HIGH | **0.80** | HIGH |

The numbers happen to land near the old hardcoded ones for the developed cases — which is the
point: the literals were roughly right, but they could not move. 0.84 at detection rising to 0.94
as the second source turns critical is new behaviour, and it is derived.

### 3.2 The explanation now shows its arithmetic

Verbatim from a live run:

```
HOW CONFIDENT: 84% by noisy-OR fusion over independent sources
  [M-04 (WARNING, 0.60 -> 0.60; running 0.60), TEMP-B-01 (WARNING, 0.60 -> 0.60; running 0.84)]
  — a risk assessment, not a certainty.
HOW SEVERE: HIGH — impact 4/4 x likelihood 3/4 = 12/16 -> CRITICAL, capped to HIGH because the
  strongest single source is only WARNING.
```

That cap is the honesty mechanism: the impact × likelihood matrix wanted CRITICAL from two
warning-level readings, and the engine refuses, because no single sensor is past its critical
threshold yet. It is what produces a real HIGH → CRITICAL progression instead of shouting
CRITICAL from the first tick.

### 3.3 Sensor trust — a spoofed sensor cannot hide a hazard

`test_a_spoofed_temperature_sensor_does_not_hide_an_overheating_machine`:

| Situation | TEMP-B-01 trust | Its contribution | Fused confidence | Severity |
|---|---|---|---|---|
| Normal | 1.00 | 0.85 | 0.85 alone | — |
| Judged spoofed | **0.20** | 0.85 × 0.20 = **0.17** | **≥ 0.85** from M-04 alone | **CRITICAL** |

The hazard is still graded CRITICAL because the machine's own pressure and body temperature are
physically independent of the ambient sensor, and the incident text names the down-weighted
sensor and why. Step 8 wires the cyber agent's spoof detection into `set_trust()`.

---

## 4. ML models (Step 6) — trained locally on CPU, no GPU

Brev was never approved, so both models were trained on the demo laptop. The scripts contain
nothing CUDA-specific and would run unchanged on a GPU instance.

### 4.1 Compressor anomaly — Isolation Forest on MetroPT-3 ✅ shipped

`python backend/scripts/train_machine_iforest.py` — **27 s** end to end, ~40 MB peak RAM. The
218 MB / 1.5 M-row CSV is read in 250 k-row chunks with 5 of its 16 columns and resampled to 10 s
immediately, so the full frame never exists in memory.

Features `TP2, TP3, Oil_temperature, Motor_current`. Fitted on **normal operation only**: the four
air-leak windows were read out of the dataset's own `Data Description_Metro.pdf` ("Failure
Information" table) rather than from memory — 2020-04-18, 2020-05-29/30, 2020-06-05/07,
2020-07-15. Train 1,179,528 rows; test 294,882 held-out normal + 29,697 failure rows.

| Operating point | Precision | Recall | F1 |
|---|---|---|---|
| `contamination=0.01` (the library default cut-off) | 0.754 | 0.098 | 0.173 |
| **tuned threshold −0.5762** (swept on held-out data, stored in the bundle) | 0.624 | **0.980** | **0.763** |

**ROC AUC = 0.976.** That is the number that matters: the score separates the documented failures
from normal operation very well, and `contamination=0.01` was simply a far too strict place to put
the line — it only flags the most extreme 1% of training points. The runtime therefore uses
`score_samples()` against the measured threshold, not `predict()`.

**Cross-domain check on SKAB (different machine, z-scored into the same 4 dimensions):
ROC AUC 0.495, F1 0.035 — i.e. chance.** Reported because it was measured, not buried: an
Isolation Forest fitted on one compressor does **not** transfer to a pump rig. Anyone claiming
cross-machine transfer from a model like this should be asked for their AUC.

Runtime effect: `machine_agent` observations now carry `anomaly_score`,
`anomaly_score_threshold`, `ml_is_anomaly`, `most_deviant_feature`, `most_deviant_z`, and say so
in words. Live example from an incident's evidence:

> *"OVERPRESSURE on M-04: pressure 8.92 bar over the 8.0 bar operating limit … Isolation Forest
> trained on MetroPT-3 scores this sample −0.700 (outside its −0.576 threshold);
> furthest-from-normal channel: machine_temperature at +5.3 sigma."*

### 4.2 Smoke classifier — trained, measured, and deliberately NOT shipped ⚠️

`python backend/scripts/train_smoke.py` — 4 s, 62,630 rows.

| Model | Features | Precision | Recall | F1 | ROC AUC |
|---|---|---|---|---|---|
| full | 12 (all dataset channels) | 1.000 | 1.000 | 1.000 | 1.000 |
| deployable | 2 (`Temperature`, `PM2.5` — all our plant has) | 0.910 | 0.946 | 0.928 | 0.943 |

Those look excellent and **the model is still not used at runtime**, because of what it is actually
learning. In the Kaggle Smoke Detection IoT dataset every intuitive fire indicator is *negatively*
correlated with the `Fire Alarm` label:

| Channel | mean when alarm=1 | mean when alarm=0 | correlation with the label |
|---|---|---|---|
| PM2.5 | 78.4 | **450.0** | −0.085 |
| TVOC | 882 | **4597** | −0.215 |
| Temperature | 14.5 °C | **19.7 °C** | −0.164 |
| Humidity | 50.8 % | 42.9 % | **+0.400** |

The label tracks which trial the test rig was in, not fire physics — which is also why a
12-feature model reaches a perfect 1.000. Wired to our smoke sensor it reported **"0% probability
of a real fire signature" for 75 ppm of smoke in a hot zone.**

A confidently wrong number on an incident card is worse than no number, so the fire path stays on
the FIRE-EP-03 rules (smoke present plus two corroborating signals). The training script, the
metrics and the `.joblib` loader all remain; `temperature_agent` simply does not consult it, and a
test asserts that omission with the reason attached.

### 4.3 The design rule that makes this safe

**The models annotate; the deterministic rules decide.** A score never creates and never
suppresses an alarm. `test_machine_agent_detects_identically_without_the_models` deletes the model
file and asserts the same CRITICAL verdict with the same rule explanation. That is why rejecting
the smoke model cost nothing, and why a model regression can only ever degrade an explanation.

**94 pytest tests pass** (13 new for Step 6).

---

## 5. Cached-answer layer (item 3)

`live → cached → template`, keyed by incident type, persisted to `backend/ai/data/llm_cache.json`.
Warmed for all three hazard types, each with citations the model actually retrieved:

| Hazard | Cached from | Actions chosen | Sections cited |
|---|---|---|---|
| `MACHINE_OVERHEATING` | `openai/gpt-oss-120b` on Groq | activate_cooling, evacuate_zone, trigger_alarm | `SOP-M04 §2`, `§4.2` |
| `INDUSTRIAL_FIRE` | `gemini-3.8-flash` | trigger_alarm, evacuate_zone, close_door, activate_suppression | `FIRE-EP-03 §2`, `§3.2`, `§3.3` |
| `CYBER_INTRUSION` | `openai/gpt-oss-120b` on Groq | vlan_quarantine, isolate_device | `OT-CYBER-PB §2`, `§3.1`, `§3.2` |

A replay is always labelled and dated, cached action ids are re-validated against the catalogue,
and only wording plus action ids are replayable — confidence and severity are never cached.

Worth knowing for the demo: the overheating answer was captured while the incident was at
**warning** level, so it cites `SOP-M04 §4.1/§2` and chooses cooling rather than the shutdown. The
deterministic `STOP_MACHINE` card is created at detection regardless, so the AUTHORIZE click is
unaffected — but the replayed *wording* will not mention the shutdown. The agent is invoked once, at
incident creation, which is always the warning-level moment.

**One defect found and fixed here:** the test suite was writing *and deleting* this production
cache file — any bridge test posting an enrichment without `fallback=True` counted as a live answer
and called `remember()`, while the cache tests' cleanup called `clear()`, which unlinks it. It had
already overwritten a warmed answer with `{"what": "x"}`, which would have been replayed on stage
labelled as a cached model answer. Every test is now redirected to a temp path by an autouse
fixture, and the cache refuses to store a threadbare answer.

---

## 6. Feature-freeze verification

`python n8n/final_verification.py --rounds 3` — **all checks passed in every round**, three rounds
of all four scenarios through the live stack:

| Scenario | Incidents | Type | Severity | Confidence | Evidence checked |
|---|---|---|---|---|---|
| `machine_overheating` | 1 | `MACHINE_OVERHEATING` | CRITICAL | 0.94 | machine + temperature + worker, names M-04 |
| `fire` | 1 | `INDUSTRIAL_FIRE` | CRITICAL | 0.85 | temperature + worker, names SMOKE-B-01 |
| `cybersecurity` | 1 | `CYBER_INTRUSION` | HIGH | 0.80 | cyber, names UNKNOWN-DEVICE-07 |
| `normal` | 0 | — | — | — | stays silent |

LLM path across the 9 incidents: **Groq 8, none 1** (one read immediately after the wait, before
the enrichment landed). Alongside: **115 pytest tests**, `e2e_test.py` **15/15**,
`gate1_verify.py` **13/13**.

---

## 7. Still to be measured

- **Step 5b** — NIM on Brev: model name, latency, and the NIM → Gemini → template chain
  demonstrated once in each of its three states.
- **Step 6** — Isolation Forest on MetroPT-3 evaluated against SKAB, and the smoke RandomForest:
  precision / recall / F1 tables, plus the Brev instance type used for training.
- **Step 7** — confidence spread across scenarios once the risk engine replaces the provisional
  fusion, and the effect of a sensor trust factor on a spoofed-sensor case.
