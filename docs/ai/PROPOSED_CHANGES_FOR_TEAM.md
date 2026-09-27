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

---

## P8 — `backend/iot/simulator.py` (Engineer 2) — richer cyber payloads for the Step 8 rules

**Priority: low. The cyber demo works without this; these payloads would let the new rules fire
live instead of only in tests.**

`_tick_cyber()` emits one payload forever:

```python
data={"cyber_type": "UNAUTHORIZED_DEVICE", "device": "UNKNOWN-DEVICE-07",
      "attempts": 47, "target": "Industrial Modbus Gateway (192.168.10.45)"}
```

The cyber agent now classifies that into **BRUTE_FORCE** (47 ≥ 20 failed auths in 60 s) and
**UNKNOWN_DEVICE** (not in the asset inventory), attributed to `T0806 Brute Force I/O` and
`T0848 Rogue Master`. A test locks that in, so **this payload must keep working**.

Four more rules exist and cannot fire from the simulator yet. Any of these, cycled by
`scenario_step`, would exercise them:

```python
# UNAUTHORIZED_COMMAND -> T1692 Unauthorized Message  (severity CRITICAL)
{"cyber_type": "UNAUTHORIZED_COMMAND", "device": "UNKNOWN-DEVICE-07",
 "source": "10.0.0.66", "command": "write_setpoint", "target": "PLC-B-01"}

# SPOOFED_SENSOR -> T1692.002 Reporting Message  (severity CRITICAL) -- the flagship
{"cyber_type": "SPOOFED_SENSOR", "device": "UNKNOWN-DEVICE-07",
 "sensor_id": "TEMP-B-01", "target": "TEMP-B-01"}

# TRAFFIC_ANOMALY -> T0842 Network Sniffing  (severity WARNING)
{"cyber_type": "TRAFFIC_ANOMALY", "device": "SWITCH-CORE-01",
 "source": "10.0.0.66", "traffic_z": 4.2}

# CREDENTIAL_ABUSE -> T0859 Valid Accounts  (severity HIGH)
{"cyber_type": "VALID_ACCOUNTS", "device": "ENG-WS-01", "source": "ENG-WS-01",
 "valid_account_misuse": True, "target": "PLC-B-01"}
```

### The one that is worth the most on stage

**`SPOOFED_SENSOR` while `machine_overheating` is running.** The cyber agent distrusts
`TEMP-B-01` (trust 0.2, `OT-CYBER-PB §4.2`), and the machine hazard is *still* detected as
CRITICAL because M-04's own pressure and body temperature are independent of the spoofed ambient
sensor. The incident text then carries a `TRUST:` line naming the down-weighted sensor. That is
one agent changing how another reasons, visible on screen.

It also works with **no new payload at all**: the agent cross-checks any cyber event that names a
`sensor_id`, so a spoof is detected when an ambient sensor sits at baseline while the machine in
its zone is past its own temperature limit. To drive it live, the cyber scenario only needs to run
*while* the overheating scenario is active, or emit the `SPOOFED_SENSOR` payload above.

Nothing on Engineer 1's side needs changing when this lands — the rules are already there.

---

## ✅ P9 — APPLIED by Engineer 1 on 2026-09-27 at 12:45, on Firas's instruction. **Please review.**

**Engineer 2 had not replied at the time of writing, so this was applied on Firas's decision after
no reply.** Raised at ~12:20 after merging upstream main; applied at ~12:45. If you disagree,
reverting is deleting one comment block and restoring five lines — but please read why first.

**What was removed:** the five lines in `execute_action` quoted below. **What replaces it:** nothing
new — `ai/resolution_policy.evaluate_incident_after(action)` was already being called a few lines
further down and already did the job properly.

**Verified live after applying:** authorising **only** `STOP_MACHINE` on an overheating incident
leaves `ACTIVATE_COOLING` and `EVACUATE_ZONE` as **CANCELLED** (2 of 2), **zero** actions marked
COMPLETED without a verification record, the incident **RESOLVED**, and the agent log carries the
reason: *"INC-E10D resolved by the 'hazard_resolver_completed' rule: STOP_MACHINE completed and the
hazard is receding (machine parameters back inside limits). 2 pending action(s) cancelled as
superseded"*. 115 pytest tests pass (the test that encoded this is a normal passing test again, no
longer xfail), `final_verification.py` all green, `e2e_test.py` 15/15 three runs in a row.

---

### The original report, for the record

Detection, the demo and every scenario were unaffected; this was about what the dashboard *claims*.

The merged `execute_action` now contains:

```python
# If primary mitigation action executed, complete companion actions and resolve all active zone incidents
if action.action_type in ["STOP_MACHINE", "ACTIVATE_COOLING", "ACTIVATE_SUPPRESSION",
                          "EVACUATE_ZONE", "ISOLATE_DEVICE", "CLOSE_DOOR"]:
    for a in state.actions.values():
        if a.status == ActionStatus.AWAITING_APPROVAL:
            a.status = ActionStatus.COMPLETED
            a.completed_at = datetime.utcnow()
```

I understand the intent — don't leave cards stuck at AWAITING_APPROVAL once the hazard is handled.
Three problems with this particular form:

1. **It reports work that never happened.** Those actions are marked `COMPLETED` without any
   actuator running and with `verification` left empty. `EVACUATE_ZONE` shows as completed when
   nobody was evacuated and no thermal sweep confirmed the zone is clear.
2. **It bypasses the approval gate.** `EVACUATE_ZONE` and `ACTIVATE_SUPPRESSION` are HIGH risk and
   `requires_confirmation=True` precisely so a human decides. This completes them without a click,
   which contradicts what we say on stage and in the PR: *"a human authorises anything that costs
   money or moves people."*
3. **It is not scoped to the incident.** `state.actions.values()` is every action in the plant, so
   it also completes actions belonging to other, unrelated incidents.

**The intent is already implemented correctly** in `ai/resolution_policy.py`: when every
hazard-resolving action has completed and the readings are receding, the remaining actions **for
that incident** are set to `CANCELLED` — "superseded, hazard already addressed" — with the reason
written to the agent log. Nothing is claimed to have run that did not.

### Suggested fix — delete the block

`resolution_policy.evaluate_incident_after(action)` is already called a few lines below and does the
job. If you would rather keep an explicit step there, the honest version is:

```python
        # Companion actions the remedy made unnecessary, scoped to THIS incident, marked
        # cancelled rather than completed because no actuator ran for them.
        if action.action_type in ("STOP_MACHINE", "ACTIVATE_SUPPRESSION", "ISOLATE_DEVICE"):
            for a in state.actions.values():
                if a.incident_id == action.incident_id and a.status == ActionStatus.AWAITING_APPROVAL:
                    a.status = ActionStatus.CANCELLED
```

**Status in my branch:** the test that encodes the correct behaviour
(`test_optional_actions_are_cancelled_once_the_hazard_is_addressed`) is marked `xfail` with this
whole explanation attached, so the conflict is visible in the code rather than papered over. Remove
the `xfail` when the block is fixed and the test should pass unchanged.
