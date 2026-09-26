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
