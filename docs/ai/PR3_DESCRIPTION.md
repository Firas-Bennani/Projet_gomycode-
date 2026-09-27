# Industrial_Copilot — rename, authentication, richer seed data, a predictive scenario, and the copilot defending itself

Final pass before submission, branch `final-touches` off `upstream/main`. Items were done in a
fixed order with a commit after each, and the three demo scenarios were kept working throughout.

## 1. Rename to `Industrial_Copilot`

The product name is exactly **`Industrial_Copilot`**. Updated everywhere it is user-visible —
browser tab title, dashboard header, backend `PROJECT_NAME` and startup logs, README title and
prose, and our own docs. **No code identifiers or file names were renamed**, so nothing imports
differently and no teammate's import breaks.

The separate `standalone-3d-ai-copilot/` app was left alone: it is a teammate's parallel build with
its own branding, and renaming inside it was not asked for.

## 3. Richer seed data — PARTIAL (shipped the safe core, ran out of clock)

`backend/scripts/generate_seed_data.py`, deterministic (`seed=20260927`), writing
`backend/app/data/seed/`:

- **`workers.json` — 35 additional workers** with Tunisian names, role, team, shift and window,
  zone, badge, PPE status, hours this week, overtime, productivity %, certifications, last
  entry/exit. Loaded on top of the existing five, giving **40 workers**.
- **`inventory.json` — 30 items** across raw material, consumables, spare parts and finished goods,
  each with SKU, unit, stock, min threshold, reorder point, supplier, lead time, daily consumption,
  days of cover, unit cost in TND and **30 days of movements**. Five items sit below threshold so
  the low-stock alerts have real data. Total **34 inventory items**.

**The loader is deliberately additive and guarded.** The simulator, the agents and the scenario
tests reference `W23/W41/W52`, `M-01..M-06` and the ZONE_B sensors *by id*, so those stay defined in
`state_store.py` and are never overwritten; a `try/except` means a missing or malformed seed file
leaves the platform running exactly as before.

**One consistency trap avoided:** the extra workers are placed in ZONE_A/C/D only. Putting any in
ZONE_B would have made the Workers page say eight people while the incident card said three,
because the worker agent still reports its own three (reading it from the state store was Step 9,
which was cut). Rather than create a visible contradiction on stage, ZONE_B stays staffed by
exactly those three, with the reason written next to the constant.

**Not done in item 3:** machine 24 h history for charts, OEE and energy series, and wiring the
richer fields (certifications, movements, days of cover) into the page components — the existing
pages read the original schema and already show the new rows, so no page is empty, but they do not
yet show the new columns.

## 4. Events page — SKIPPED, 5. Clients page — SKIPPED

Dropped on Firas's instruction: not needed for the submission video. The time went into the two
items below instead.

## A. `storm_forecast` — the first predictive scenario

The other three scenarios are reactive. Something is already too hot, too smoky, or already
talking to a rogue device, and the copilot responds well. This one raises an incident about
something that **has not happened yet**, and the value is entirely in the lead time.

**A new agent.** `backend/ai/agents/weather_agent.py` raises `SEVERE_WEATHER_RISK` with a lead
time, the exposed zones and the people in them. `backend/ai/weather.py` is the forecast source:
Open-Meteo is wired as an **optional** live source with the variable names (`weather_code`,
`precipitation_probability`, `cape`, `wind_gusts_10m`) verified against the live API, and a
**deterministic 7-step simulated forecast is the default**, so the demo never depends on the
network and a repeat run is identical. A failed live call cannot raise.

**One real change to the risk engine.** `fuse()` now honours an observation's own
`source_confidence` instead of mapping its severity label to a fixed likelihood. For a forecast
the probability *is* the evidence; mapping `WARNING → 0.60` would have thrown the actual number
away. Confidence is the forecast probability plus small boosts for instability (thunderstorm code,
CAPE band, gust band), **capped at 0.97 — a forecast is a probability, not a measurement** — and
the arithmetic is printed in the incident as `FORECAST BASIS:`.

**Four preparation actions**, all owner-confirmed, with effects you can see in the machine
parameters rather than only in a log line: `LOAD_SHEDDING` (every machine derated to 60% of rpm,
energy and production rate), `REDUCE_PRESSURE_SETPOINT` (8.0 → 6.5 bar, widening the margin to
the limit to 1.5 bar), `SWITCH_TO_UPS`, `REINFORCE_ELECTRICAL_CREW`.

**The argument of the scenario is the contrast.** Forecast updates for 7 ticks, then a quiet
stretch that is the operator's approval window, then the strike at tick 25. With load shedding and
the lower setpoint authorised, M-04 peaks at **6.8 bar against its 8.0 bar limit**, stays INFO, and
the agent writes *"PREVENTED: the forecast was acted on in time."* With nothing authorised the same
weather drives it to **8.9 bar**, CRITICAL, *"NOT PREVENTED."* Same forecast, two outcomes, one
human decision in between.

**New procedure document** `WX-SP-07` (`Severe-Weather-Procedure.md`) is where the thresholds, the
6.5 bar setpoint and the 30/30 lightning rule come from, so the incident cites a document rather
than a constant in the code. The warmed Groq answer for this hazard cites its sections 1, 2 and 6.
⚠️ n8n's Simple Vector Store was ingested before this document existed — re-run the ingestion
workflow once if you want semantic retrieval to cover it (noted in `n8n/README.md`). The keyword
RAG needs no ingestion and already retrieves it.

## B. The cyber agent defends the other agents

Until now every agent was assumed honest. They talk over an in-process event bus, so anything that
could publish an event could put words in an agent's mouth — and a forged *"machine_agent says
M-04 is nominal, close the incident"* is the dangerous shape, because it is evidence-shaped and
would have been fused with full trust. Three defences, in `backend/ai/agent_bus_auth.py`, applied
by the cyber agent:

1. **Authenticity.** Every inter-agent observation carries an **HMAC-SHA256** tag over its own
   content (`agent_id`, `zone`, `severity`, `observation`, `decision`). Unsigned, badly signed and
   unknown-`agent_id` messages are all rejected **before the fusion**; because the tag covers the
   claim, a valid tag cannot be lifted onto a different message. The log line is explicit:
   **"Cyber agent: rejected forged message claiming to be machine_agent"**, with the reason. The
   impersonated agent drops to **trust 0.2 — not 0**, so the plant stays monitored while its
   messages are in doubt, and an `AGENT_COMPROMISE` incident is raised.
2. **Behaviour.** A signature proves who sent a message, not that the sender is sane. A confidence
   outside [0, 1] is not a probability, and more than 12 observations in 10 s is not a normal
   reporting rate. Either is treated as a compromise.
3. **The LLM channel.** Enrichment text arriving through n8n is scanned for instruction injection
   **before `llm_cache.remember()`** — so a poisoned answer can never be stored and replayed on
   stage — and rejected with **422**, leaving the deterministic reasoning untouched. This sits on
   top of the rules already in place: the bridge needs the shared service secret, and any action
   the model proposes must validate against the catalogue.

Two new owner-confirmed actions: `QUARANTINE_AGENT` and `REQUIRE_HUMAN_AUTHORISATION`.

**New demo scenario `agent_attack`**, and it is safe to run at any point: no sensor is moved and no
machine is stressed. A correctly signed message is **accepted** first — a check that rejects
everything is not a check, it is an outage — then the same claim arrives unsigned and is rejected,
then a correctly signed message reporting confidence 4.7 is rejected for behaviour.

**Attribution is honest.** No ATT&CK for ICS technique is cited for this, and the incident text
says why: the attack is on the copilot's own message bus, not on an industrial protocol. No
identifiers were invented — the same rule that had us report T1692/T1692.002 instead of the
revoked T0855/T0856 earlier in the build.

The AI-1 page (SYSTEM 1) now states the rule in its header banner, and reports **6/6 agents**.

## Tests and verification

| | |
|---|---|
| `pytest` | **162 passed** (114 before this branch; +13 storm, +17 agent defence, +18 auth/seed) |
| `final_verification.py --rounds 1` | all three original scenarios pass, LLM path **groq** for all three, after each of items A and B |
| Demo scenarios | **5** (normal, machine_overheating, fire, cyber, storm_forecast, agent_attack) |
| Action catalogue | **14** actions, every one executable by the command engine (asserted by a test) |
| Procedure corpus | **6** documents |
| LLM cache | **4/4** hazard types warmed with live Groq answers |

New secrets are documented as placeholders in `.env.example` (`AGENT_BUS_SECRET`, `WEATHER_LIVE`)
and nothing real is committed.

## What is not done

- The Events and Clients pages (items 4 and 5), skipped deliberately.
- Item 3's richer seed fields (certifications, stock movements, days of cover) are loaded but the
  page components still read the original columns.
- n8n's semantic index does not contain WX-SP-07 until the ingestion workflow is re-run.
