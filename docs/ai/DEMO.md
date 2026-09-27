# DEMO — Industrial_Copilot, the multi-agent + n8n part

Engineer 1's script. Total **3 min 35 s** of demo across four scenarios, plus ~40 s of setup.
Every number quoted here is in `docs/ai/METRICS.md` with the command that produced it.

---

## 0. Before you start — 5 minutes, do not skip

```powershell
# 1. Close heavy applications. This laptop has killed background processes for low memory
#    four times during the build. The demo needs backend + n8n + Vite + a Three.js browser tab.

# 2. n8n (leave running)
$env:GENERIC_TIMEZONE="Europe/London"; $env:N8N_SECURE_COOKIE="false"
$env:N8N_HOST="localhost"; $env:N8N_PORT="5678"; $env:N8N_PROTOCOL="http"
$env:WEBHOOK_URL="http://localhost:5678/"
npx --yes n8n@2.40.7

# 3. Backend (one process, no --reload)
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning

# 4. Frontend
cd frontend; npm run dev        # http://localhost:5173
```

Then the checklist in `n8n/README.md` §4b, of which these three actually bite:

- [ ] `python n8n/import_workflows.py --list` → **exactly one** active incident workflow
      (`Incident Response v2 (Gemini + RAG)` — the name predates Groq; Groq is now the primary
      model inside it and Gemini the fallback).
- [ ] **Re-run the RAG ingestion** in n8n. The Simple Vector Store is in memory and says so:
      *"data will be lost if n8n restarts."* Assume it is empty.
- [ ] `curl http://127.0.0.1:8000/api/ai/n8n/llm-cache` → shows cached answers per hazard type.
      This is the last-resort safety net; see §5. All three hazard types are pre-warmed.

Open two browser windows side by side: **the dashboard** (left, larger) and **n8n → Executions**
(right). The n8n window is half the story — it is the evidence that this is an orchestrated
system and not a hardcoded animation.

---

## 0b. Sign in — the platform is now closed without a login

Open <http://localhost:5173> and you get a sign-in page, not the dashboard.

| Account | Password | Role | Can do |
|---|---|---|---|
| **`firas`** | `Copilot#Owner2026` | owner | everything, **including AUTHORIZE** — use this for the demo |
| `operator` | `Copilot#Operator2026` | operator | read-only; AUTHORIZE returns 403 |
| `auditor` | `Copilot#Auditor2026` | operator | read-only |

Worth a sentence on stage: *"the approval gate is enforced by the server, not by hiding a button —
signed in as an operator, the AUTHORIZE call comes back 403."* 15 seconds to show.

Sessions end after **30 minutes of inactivity** or when the 30-minute token expires, whichever
comes first, with a warning banner one minute before. Any 401 returns you to the login.

## 1. Normal operation — 20 s

Click **RESET**, then leave the plant idle.

> "Four zones, five machines, five workers, live sensors at 1 Hz. Five agents are reading this
> continuously. Nothing is happening, and that matters: the system is not alarming. Before we
> fixed it, this demo produced a fire alarm from a hot machine."

Point at the **multi-agent page**: agents are ACTIVE and reporting nominal.

---

## 2. Machine overheating — 90 s. This is the main act.

Click **machine_overheating**. Keep the n8n Executions tab visible.

**Seconds 0–5.** An incident appears, and three action cards land in the Command Center
**without a page refresh**.

> "Two independent agents corroborated: the machine agent sees pressure and body temperature,
> the environmental agent sees the ambient sensor. Neither alone is enough."

**Point at the `HOW CONFIDENT` line.**

> "84%, and it shows its arithmetic — noisy-OR fusion over the two sources, each with its own
> weight. Not a number we typed in. As the fault develops it becomes 94%."

**Point at `HOW SEVERE`.**

> "Impact 4 times likelihood 3 is 12 out of 16, which says CRITICAL — but it reports **HIGH**,
> capped, because no single sensor is past its critical threshold yet. The system refuses to
> shout. Watch it become CRITICAL in a moment, on its own."

**Point at the Isolation Forest sentence in the evidence.**

> "That is a model trained on MetroPT-3, 1.5 million rows of real compressor telemetry, fitted
> only on normal operation after removing the four failure windows documented in the dataset's
> own PDF. ROC AUC 0.976. It says this sample is outside its threshold and names the
> furthest-from-normal channel. It **annotates** — the deterministic rules still decide, so a
> model regression can never invent or hide an alarm."

**Point at `SOURCES`.**

> "`SOP-M04 §4.2` — it retrieved our written procedure and cited the section. The language model
> chose the actions, but only from a fixed catalogue of eight; it cannot invent an action, and it
> cannot set the risk level or decide what needs a human."

**Point at the last line of the reasoning.**

> "And it tells you which model wrote this — `openai/gpt-oss-120b on Groq`. If Groq were down it
> tries Gemini and says so; if both are down, a cached answer with its timestamp; if all three,
> the deterministic template. Four levels, and the incident resolves on every one of them."

That is verified, not asserted: breaking the Groq model id produced one execution in which Groq
errored, **Gemini was attempted** and hit its 429 quota, the agent took its error branch, the
template ran, and the backend replaced it with the cached Groq answer — citations intact, incident
resolved. See `METRICS.md §2.0b`. If you want to show it live, break the Groq node's model in n8n
and re-run.

**Seconds 30–60. Switch to the n8n window.** The execution is sitting on **Wait**.

> "The incident went to n8n. It ran retrieval, called the model, posted the explanation back, and
> is now *waiting* — for a human. It will wait ten minutes."

**Now click AUTHORIZE on STOP_MACHINE only.**

> "One click. Watch three things."

1. The action goes IN_PROGRESS → COMPLETED with its actuator checks.
2. **The other two cards cancel themselves** — "superseded, hazard already addressed".
3. The incident resolves, and **M-04 returns to baseline and stays there**.

**Back to n8n:** the execution resumes, waits 15 s, calls `/verify`, and goes **green**.

> "It verified that the plant actually changed before closing the incident — not that the command
> was sent, that the spindle reads zero and the valve is depressed. And nothing re-opens: a
> resolved hazard only re-opens if the readings start climbing again."

---

## 3. Fire — 60 s

Click **RESET**, wait 3 s, click **fire**.

> "Same machinery, different hazard, and the important part is what it does **not** do."

- The fire is declared only at ~6 s, on **two corroborating signals** — smoke above the critical
  level *and* the reading persisting across consecutive samples.
- **It never declares a fire without smoke.** The old version turned a hot compressor into a fire
  and recommended discharging water suppression on it. `FIRE-EP-03 §2.3` forbids that and the
  rule enforces it.
- Actions come in procedure order: alarm automatically (LOW risk), then doors and suppression,
  both needing a human.

> "We also trained a smoke classifier for this and **threw it away**. It scored F1 0.93 — but in
> that public dataset every fire indicator is *negatively* correlated with the alarm label: mean
> PM2.5 is 78 when the alarm is on and 450 when it is off. Wired up, it reported 0% fire at
> 75 ppm of smoke. A confidently wrong number on this card is worse than no number, so the fire
> path stays on the written rules. That decision is in the repo with the evidence."

---

## 4. Cyber — 45 s

Click **RESET**, wait 3 s, click **cybersecurity**.

> "An unregistered device is hammering the Modbus gateway."

Point at the rules in the evidence:

> "Two rules fired — brute force, 47 failed authentications from one source inside 60 seconds, and
> unknown device, because it is not in the asset inventory. Each is attributed to a MITRE ATT&CK
> for ICS technique: `T0806 Brute Force I/O`, `T0848 Rogue Master`."

**The line worth saying out loud:**

> "Those ids are looked up in MITRE's published data file at runtime, never from memory. That is
> not pedantry — the two techniques you would expect here, T0855 and T0856, are **revoked** in the
> current release. If we had quoted them from memory we would have been wrong on stage."

**If you have time (30 s more), the flagship.** With overheating still running, trigger a spoof:

```powershell
curl -X POST http://127.0.0.1:8000/api/demo/scenario -H "Content-Type: application/json" -d '{"scenario":"cybersecurity"}'
```

> "When the cyber agent decides a sensor is lying, it does not ignore it — it tells the risk engine
> to **distrust** it, weight 0.2. Look at the agent log: *Distrust TEMP-B-01*. And the overheating
> is **still** CRITICAL, because the machine's own pressure and body temperature are independent
> of the sensor the attacker pinned. One agent changed how another reasons."

---

## 4b. Storm forecast — 60 s. The predictive one. Record this.

The other three scenarios are reactive: something is already too hot, too smoky, or already
talking to a rogue device. This is the only one where the hazard has not happened yet, and the
point is entirely the lead time. **The plant is prepared, the storm arrives, and nothing breaks.**

Exact click order:

1. **Reset** in the demo bar. Wait for the tiles to settle (~3 s).
2. Click **Scenario 4: Storm Forecast (predictive)**.
3. Go to the **multi-agent page (SYSTEM 1)**. For the first ~7 seconds the Weather &
   Environmental Forecast Agent posts one forecast update per second: probability climbing
   24% → 91%, CAPE 320 → 2740 J/kg, gusts 28 → 84 km/h, lead time falling 95 → 15 min.
   Say out loud: *"this agent is the only one reasoning about something that has not happened."*
4. Around **4–5 s** a `SEVERE_WEATHER_RISK` incident appears. Open it. Read three things:
   - `LEAD TIME: ~N min. Acting now is what makes this preventable` — the whole argument.
   - `FORECAST BASIS:` — the confidence arithmetic, probability plus CAPE/gust boosts, capped at
     0.97 because a forecast is a probability and not a measurement.
   - the four actions, in order: **shed load**, **lower the pressure setpoint to 6.5 bar**,
     **move controllers to UPS**, **call the electrical crew**. Every one needs the owner.
5. **Authorize LOAD_SHEDDING and REDUCE_PRESSURE_SETPOINT** (the other two are optional for the
   video). Watch the machine parameters: rpm/energy drop to 60%, pressure drops to 6.5 bar. This
   is the part to linger on — the plant is measurably safer *before* anything happened.
6. At **tick 25 (~25 s after step 2)** the storm hits. With both authorised, M-04 peaks at
   **6.8 bar against its 8.0 bar limit**, stays INFO, and the weather agent writes
   **"PREVENTED: the forecast was acted on in time; no incident resulted."**
7. Optional contrast shot, 20 s: **Reset**, click Scenario 4 again, authorise **nothing**, wait
   for the strike. Same weather, M-04 goes to **8.9 bar**, CRITICAL, and the log says
   **"NOT PREVENTED"**. Same forecast, two outcomes, and the difference is one human decision.

If the incident does not appear by ~8 s: **Reset** and click Scenario 4 again. The forecast is a
deterministic 7-step timeline (`backend/ai/weather.py`), so a repeat run is identical.

The demo uses the **simulated** forecast on purpose — no network dependency in the room.
Open-Meteo is wired as an optional live source (`WEATHER_LIVE=true`); the variable names
(`weather_code`, `precipitation_probability`, `cape`, `wind_gusts_10m`) were verified against the
live API, and a failed call can never raise.

## 4c. Forged agent message — 45 s. The copilot defending itself.

Safe to run at any time: **no sensor is moved and no machine is stressed.** The attack is on the
reasoning layer, not the plant.

Exact click order:

1. **Reset**. Wait ~3 s.
2. Click **Scenario 5: Forged Agent Message**.
3. Stay on the **multi-agent page (SYSTEM 1)**. Read the amber paragraph in the header banner
   first — it states the rule: every inter-agent message carries an HMAC-SHA256 signature over
   its own content.
4. At **~2 s** a correctly signed message from `machine_agent` is **accepted**. Say why that
   matters: *"a check that rejects everything is not a check, it is an outage."*
5. At **~4 s** the attack lands — the same claim ("M-04 nominal, close any open incident"),
   no valid signature. The log line is explicit:
   **"Cyber agent: rejected forged message claiming to be machine_agent"**, and it names the
   reason (`bad signature`). `machine_agent` drops from trust **1.0 → 0.2**: not zero, so the
   plant stays monitored while its messages are in doubt.
6. An **AGENT_COMPROMISE** incident opens. Open it. Affected asset is
   **"Inter-agent message bus"**, affected workers is **empty** — nobody is in danger; the
   copilot is. Two owner-confirmed actions: **quarantine the impersonated agent** and
   **suspend autonomous execution**.
7. At **~7 s** a third message arrives, correctly signed but reporting **confidence 4.7**. It is
   rejected too: a signature proves who sent a message, not that the sender is sane.
8. The line to land: *"no ATT&CK for ICS technique is cited here, and the incident says why —
   this is an attack on our own message bus, not on an industrial protocol. We do not invent
   identifiers."*

The third defence is not on the timeline because it lives on the n8n path: enrichment text is
scanned for instruction injection **before** it is cached, so a poisoned answer can never be
stored and replayed on stage. To show it, POST an enrichment containing "ignore all previous
instructions" and it comes back **422** with the deterministic reasoning untouched
(`backend/tests/test_agent_defence.py` does exactly this).

## 5. Fallback plan — what to do when something breaks

**Read this section before the demo, not during it.**

| If this happens | What you will see | What to do |
|---|---|---|
| **The model fails** | reasoning reads `Gemini (Groq unavailable, fell back)`, `cached … answer from <time>`, or `template fallback` | **Nothing. Say it out loud:** "the primary model is unavailable, so it fell through the chain — and the incident still resolved. Every one of those paths ran for real while we built this." |
| Groq is fine but you want to show the fallback | — | In n8n, set the Groq node's model to nonsense and re-run: Gemini answers instead, and the incident text says so. `python n8n/llm_roundtrip.py --break` does the same for Gemini. |
| Gemini-only (if Groq is down too) | slower, ~38 s, may 429 | Gemini free tier is **5 calls/minute** and one incident costs ~3. Leave 60 s between scenarios. |
| n8n restarted, RAG returns nothing | no `SOURCES` line | Re-run the RAG ingestion (15 s). Retrieval also falls back to the backend keyword RAG, which needs no ingestion. |
| n8n is down entirely | no enrichment, plainer text | **The demo still works.** Detection, actions, approval, verification and resolution are all backend-side. Say so — it is the point. |
| Backend was killed for memory | dashboard goes stale | restart with the command in §0; n8n keeps its state on disk |
| The bottom pressure tile disagrees with the machine card | tile stuck at 5.33 bar | Known, not ours: the simulator updates `PRES-B-01` but never publishes it. Proposal **P6** for Engineer 2. Do not draw attention to it. |
| An incident shows ESCALATED but the header still says 0 active | ESCALATED is not counted | Known, cosmetic, proposal **P7**. |

**If the internet is gone completely:** everything above still runs. Gemini fails, the cache
replays a real answer that is already on disk, and the rest of the system is local. Nothing in the
detection path needs a network.

---

## 6. Numbers to have ready

| Claim | Number |
|---|---|
| Tests | **162** passing, ~30 s, no real-time sleeping |
| End-to-end acceptance | `e2e_test.py` **15/15**, `gate1_verify.py` **13/13** |
| Compressor anomaly model | **ROC AUC 0.976** in-domain; tuned threshold P 0.62 / R 0.98 / F1 0.76 |
| Cross-machine transfer (SKAB) | **AUC 0.495 — chance.** We measured it and we say so |
| Smoke model | F1 0.93, **rejected for cause** |
| Procedure corpus | **6 documents** (WX-SP-07 added for severe weather), retrieved and cited by section |
| LLM live latency | **4.1 s** on Groq (`openai/gpt-oss-120b`), 8 of 9 incidents served; Gemini was 37.7 s and 1 of 5, hence the fallback chain |
| Action catalogue | **14 actions**, the only ones the model may choose from |
| Confidence | fused, **0.80 – 0.94** depending on evidence; never a literal. For a forecast the probability itself is the likelihood, capped at 0.97 |

## 7. The three sentences to land

1. **"Detection is deterministic and never depends on the language model."** The LLM explains and
   chooses from a fixed catalogue; the rules decide, the catalogue sets the risk, sensor fusion
   sets the confidence.
2. **"It refuses to guess."** No fire without smoke, no overheating without machine evidence, no
   CRITICAL while every sensor is merely at warning, no rate quoted before 10 s of history, and
   "holding — insufficient corroboration" written into the log when evidence is missing.
3. **"A human authorises anything that costs money or moves people, and the system then verifies
   the plant actually changed."** Not that the command was sent — that the spindle reads zero.
