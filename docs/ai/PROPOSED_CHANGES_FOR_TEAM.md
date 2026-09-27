# Proposed changes in files Engineer 1 does not own

Engineer 1 owns `backend/ai/**`, `backend/tests/**`, `backend/app/api/n8n_bridge.py`, `n8n/**`
and `docs/ai/**`. Everything below is in someone else's file, so it is written as a patch
here instead of applied. **Nothing in this list is required for the demo to work** — the AI
layer already works around each one. They are improvements.

---

## P1 — `backend/iot/simulator.py` (Engineer 2) — publish the temperature reading in the fire scenario

**Priority: medium. Improves the fire evidence from one sensor to two independent sensors.**

`_tick_fire()` updates `state.sensors["TEMP-B-01"]` but only publishes the **smoke** event.
So during the fire scenario the AI layer never receives a temperature reading, and the fire
rule ("smoke plus two corroborating signals") has to satisfy its second signal from the same
smoke sensor (level + persistence across consecutive samples) instead of from a physically
independent sensor.

Patch — add this right after the existing `SMOKE-B-01` publish in `_tick_fire`:

```python
        await event_bus.publish(
            event_type="SENSOR_READING",
            source="sensor:TEMP-B-01",
            data={
                "sensor_id": "TEMP-B-01",
                "type": "temperature",
                "value": cur_temp,
                "unit": "°C",
                "zone": "ZONE_B"
            },
            zone="ZONE_B",
            severity="CRITICAL"
        )
```

Effect on my side: no code change needed. The fire incident's confidence rises from 0.85
(one sensor) to ~0.98 (two independent sensors) and the evidence list shows both, which is a
much stronger story for the jury. **Nothing breaks if this is not merged.**

---

## P2 — `backend/iot/simulator.py` (Engineer 2) — announce scenario changes

**Priority: low. Replaces a defensive workaround with a clean signal.**

`POST /api/demo/reset` publishes `FACTORY_RESET`, which my orchestrator now listens for and
uses to clear its 30 s correlation window and the agents' history buffers. Without that
clearing, running `fire` straight after `machine_overheating` correlated the new smoke with
the *previous* scenario's 8.9 bar pressure reading and opened a second, bogus
`MACHINE_OVERHEATING` incident. (Found and fixed in Step 1.)

`set_scenario()` publishes nothing, so `POST /api/demo/scenario` without a reset has the same
problem. I work around it by reading `simulator.scenario` defensively in
`ai/orchestrator.py::_detect_scenario_change`. The clean version:

```python
    def set_scenario(self, scenario_name: str):
        self.scenario = scenario_name
        self.scenario_step = 0
        logger.info(f"Simulator scenario switched to: {scenario_name}")
```

becomes

```python
    async def set_scenario(self, scenario_name: str):
        previous, self.scenario = self.scenario, scenario_name
        self.scenario_step = 0
        logger.info(f"Simulator scenario switched to: {scenario_name}")
        await event_bus.publish(
            event_type="SCENARIO_CHANGED",
            source="simulator",
            data={"previous": previous, "current": scenario_name},
            zone="GLOBAL",
            severity="INFO",
        )
```

⚠️ This makes `set_scenario` **async**, so `backend/app/api/demo.py::trigger_scenario` must
become `async def` and `await simulator.set_scenario(...)`. If Engineer 2 prefers not to
touch the signature, leave it — my workaround covers the demo. Tell me if you merge it and I
will switch to listening for `SCENARIO_CHANGED` and drop the workaround.

---

## P3 — `backend/iot/simulator.py` (Engineer 2) — richer cyber events (needed for Step 8, not before)

The cyber scenario currently emits one hardcoded event every tick:
`{"cyber_type": "UNAUTHORIZED_DEVICE", "device": "UNKNOWN-DEVICE-07", "attempts": 47, ...}`.
Step 8 adds real cyber rules (brute force, unknown device, unauthorized command, traffic
anomaly, spoofed sensor) and needs distinguishable payloads. I will write the exact payload
list here when I reach Step 8; until then Step 8's rules are tested with synthetic events in
pytest, so no simulator change is needed yet.

---

## P4 — FYI for everyone: reported trends are per *plant* minute

Not a change request — something to know before the jury asks.

The simulator compresses time: one tick (1 real second) moves the compressor by about one
minute's worth of heating (26 °C → 53 °C in 8 ticks). Reported per real second that is
~160 °C/min, and the old code printed exactly that kind of number ("Rate: +122 °C/min").

`backend/ai/trend.py` now converts real seconds to plant seconds with
`DEMO_TIME_SCALE = 60.0` (overridable by the `DEMO_TIME_SCALE` env var) and reports all
slopes **per plant minute**. The same ramp now reads ~+2 to +3 °C/min, which is a realistic
industrial figure and makes the existing 2.0 / 4.0 °C-per-minute thresholds meaningful.
Set `DEMO_TIME_SCALE=1` to get raw per-real-second behaviour back.

---

## P5 — `backend/iot/simulator.py` (Engineer 2) — stop driving a machine that has been shut down

**Priority: low (cosmetic for the demo, but a jury may notice).**

`command_engine.execute_action("STOP_MACHINE")` sets M-04 to a safe baseline
(`pressure=4.0`, `rpm=0`, `temperature=28`). On the very next tick `_tick_overheating()`
overwrites `pressure` back to the scenario curve (8.9 bar) and `_tick_fire()` does the same
for smoke after suppression. So after a successful shutdown the dashboard can still show
8.9 bar on a machine whose spindle is verified at 0 RPM.

I handled it on my side: `GET /api/ai/n8n/verify/{id}` separates **gating** checks (did every
action reach a terminal state, did the actuators report success) from **telemetry** (what the
live sensors say), and returns `telemetry_consistent` so the contradiction is reported rather
than hidden. Verification no longer fails because of it.

The clean fix, if Engineer 2 wants it: track stopped machines and skip them in the tick.

```python
    def __init__(self):
        ...
        self.stopped_machines: set = set()      # honoured by _tick_overheating

    async def _tick_overheating(self):
        ...
        if "M-04" in state.machines and "M-04" not in self.stopped_machines:
            ...                                  # existing parameter updates
```

and in `command_engine.execute_action`, inside the `STOP_MACHINE` branch:

```python
                from iot.simulator import simulator
                simulator.stopped_machines.add(target)
```

plus `self.stopped_machines.clear()` in `reset()`. Same idea for suppression vs. smoke.
Tell me if you merge it and I will add `telemetry_consistent` to the gating set.

---

## ✅ P5 — APPLIED by Engineer 1 on 2026-09-27 at 04:20, authorised by Firas. **Please review.**

**This is the one change Engineer 1 has made inside `backend/iot/simulator.py`.** It was
authorised explicitly because it was the blocker at GATE 1, and Firas said he would tell
Engineer 2. Everything else in this document is still only a proposal.

**The problem it fixes.** `command_engine` sets M-04 to a safe baseline when `STOP_MACHINE`
completes. On the very next tick `_tick_overheating()` overwrote it with the scenario curve
(8.93 bar / 52.9 °C), so the thresholds were still breached, and a brand-new CRITICAL incident
opened seconds after the operator had resolved the first one. Observed live in the UI.

**What changed** (all marked with `P5 (Engineer 1)` comments in the file):

- `__init__` gained `self.stopped_machines: set`, `self.cooling_active`, `self.suppression_active`.
- A `_decay(current, baseline, rate=0.35)` static helper: exponential approach that settles and
  stays, rather than a hard jump.
- `_tick_overheating()`: when M-04 is stopped or cooling is running, temperature, pressure and
  vibration decay toward the calm baseline instead of following `temp_curve` / `pres_curve`; the
  machine reports `INFO`, its body temperature uses the normal scenario's +18 °C offset rather
  than the fault +35 °C, and the published event severity becomes `INFO`.
- `_tick_fire()`: when suppression has been discharged, smoke and temperature decay to baseline;
  sensor statuses and the published severity are now derived from the thresholds instead of
  being hardcoded `CRITICAL`.
- `reset()` clears all three flags, so a fresh demo run ramps up normally again.

`command_engine.execute_action` sets the flags (in a `try/except` that can never affect the
action) when `STOP_MACHINE`, `ACTIVATE_COOLING` or `ACTIVATE_SUPPRESSION` completes.

**Engineer 2:** if you would rather own this differently, the behaviour Engineer 1 depends on is
only *"once the remedy has executed, stop driving that asset's fault until reset"*. Any
implementation of that is fine. Verified by `backend/tests/test_scenarios.py::
test_authorizing_everything_resolves_and_does_not_reopen` and by `n8n/gate1_verify.py`.

---

## P6 — `backend/iot/simulator.py` (Engineer 2) — publish the PRESSURE reading too

**Priority: medium. Reported by Firas from the live UI at GATE 1.**

The bottom metrics bar showed **5.33 bar "Normal"** while the M-04 card showed **8.31 bar**.

- The tile reads sensor `PRES-B-01` (`frontend/src/components/MetricsBar.tsx:19`).
- `_tick_overheating()` *updates* `state.sensors["PRES-B-01"]` but only ever **publishes** a
  `SENSOR_READING` event for `TEMP-B-01`. The browser keeps its own live sensor list from those
  events, so `PRES-B-01` stays at whatever it held when the page loaded — 5.33 is the normal
  scenario's value. It "corrects itself" later only because something else triggers a refetch.

This is **not** a MetricsBar bug and nothing in the AI layer is affected (the machine agent reads
`MACHINE_STATUS`, which is published). Fix is the same shape as P1 — add alongside the existing
`TEMP-B-01` publish in `_tick_overheating`:

```python
        await event_bus.publish(
            event_type="SENSOR_READING",
            source="sensor:PRES-B-01",
            data={"sensor_id": "PRES-B-01", "type": "pressure", "value": round(cur_pres, 2),
                  "unit": "bar", "zone": "ZONE_B"},
            zone="ZONE_B",
            severity=("INFO" if remedied else ("CRITICAL" if cur_pres >= 8.0 else "WARNING")),
        )
```

⚠️ Note for Engineer 1 if this is merged: the machine agent also accepts `SENSOR_READING` of
type `pressure` and would then see M-04's pressure twice (once per event). It de-duplicates by
`(agent_id, asset)` in the observation window, so there is no double counting — but the smoke/
vibration defaults in that branch (`temp=45.0`) would enter the history. Tell me when it lands
and I will make the agent ignore pressure readings for assets it already tracks via
`MACHINE_STATUS`.

---

## P7 — `frontend/src/components/views/DetectionsView.tsx` (Engineers 3/4) — show the incident status

**Priority: low. Cosmetic, discovered while implementing the GATE 1 escalation requirement.**

The incident card renders severity, type, confidence, reasoning and evidence, but never renders
`incident.status`, and the header counts only `status === 'ACTIVE'`. Two consequences:

1. An incident the n8n workflow marks `ESCALATED` (nobody approved within 10 minutes) stays on
   screen but drops out of the "ACTIVE ALERTS" count, and the word ESCALATED appears nowhere.
2. `RESOLVING` and `RESOLVED` are equally invisible.

Engineer 1's workaround, so no frontend change is required for the demo: an escalation writes a
banner at the top of `ai_reasoning`, which *is* rendered in full —
`!! ESCALATED: No owner decision in 10 min -> escalated …`.

The nicer fix, if you have a spare minute:

```tsx
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    incident.status === 'RESOLVED' ? 'bg-emerald-700 text-white'
                    : incident.status === 'ESCALATED' ? 'bg-fuchsia-700 text-white'
                    : incident.status === 'RESOLVING' ? 'bg-sky-700 text-white'
                    : 'bg-slate-700 text-slate-200'}`}>
                    {incident.status}
                  </span>
```

and count `['ACTIVE', 'ESCALATED'].includes(i.status)` for the header badge.
