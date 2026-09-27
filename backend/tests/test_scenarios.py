"""Scenario-level tests: every demo scenario must produce the right incident type.

The bug these lock down: before Step 1, ``machine_overheating`` produced an
``INDUSTRIAL_FIRE`` incident (and a second, evidence-free ``MACHINE_OVERHEATING`` one),
because the orchestrator synthesized incidents from one event's observations at a time.
"""

import re

import pytest

from scenario_runner import run_scenario, run_scenario_sequence


# --------------------------------------------------------------------- overheating

@pytest.mark.asyncio
async def test_machine_overheating_produces_machine_incident():
    run = await run_scenario("machine_overheating", ticks=12)

    assert run.types == ["MACHINE_OVERHEATING"], f"expected one machine incident, got {run.types}"

    incident = run.incidents[0]
    assert "M-04" in incident.affected_assets
    assert incident.severity.value == "CRITICAL"
    sources = {e.source for e in incident.evidence}
    assert "machine_agent" in sources, "a machine incident must be backed by machine evidence"


@pytest.mark.asyncio
async def test_machine_overheating_is_never_diagnosed_as_fire():
    """Regression test for the Step 0 bug."""
    run = await run_scenario("machine_overheating", ticks=20)

    assert "INDUSTRIAL_FIRE" not in run.types
    for incident in run.incidents:
        actions = {a.action_type for a in incident.recommended_actions}
        assert "ACTIVATE_SUPPRESSION" not in actions, "never discharge suppression on a hot machine"


@pytest.mark.asyncio
async def test_overheating_creates_exactly_one_incident_over_a_long_run():
    """Dedup: a hazard that persists must not open a new incident on every tick."""
    run = await run_scenario("machine_overheating", ticks=40)
    assert len(run.incidents) == 1


@pytest.mark.asyncio
async def test_overheating_escalates_instead_of_duplicating():
    run = await run_scenario("machine_overheating", ticks=20)
    escalations = [l for l in run.logs if "ESCALATED existing incident" in l["decision"]]
    assert escalations, "severity should rise on the open incident as the hazard worsens"


@pytest.mark.asyncio
async def test_incident_lists_workers_really_present_in_the_zone():
    run = await run_scenario("machine_overheating", ticks=12)
    incident = run.incidents[0]
    # W23, W41, W52 are the Zone B workers in the state store; W12/W09 are elsewhere.
    assert set(incident.affected_workers) == {"W23", "W41", "W52"}


# --------------------------------------------------------------------- fire

@pytest.mark.asyncio
async def test_fire_scenario_produces_fire_incident():
    run = await run_scenario("fire", ticks=12)

    assert run.types == ["INDUSTRIAL_FIRE"], f"expected one fire incident, got {run.types}"

    incident = run.incidents[0]
    details = " ".join(e.detail for e in incident.evidence)
    assert "SMOKE-B-01" in details, "a fire incident must be backed by smoke evidence"
    assert {"TRIGGER_ALARM", "ACTIVATE_SUPPRESSION"} <= {a.action_type for a in incident.recommended_actions}


@pytest.mark.asyncio
async def test_fire_needs_two_corroborating_signals():
    """One smoke sample above threshold is not yet a fire."""
    run = await run_scenario("fire", ticks=4)
    holds = [l for l in run.logs if "Holding" in l["reasoning"]]
    assert run.types == [] or holds, "early fire ticks must hold rather than declare"


# --------------------------------------------------------------------- cyber

@pytest.mark.asyncio
async def test_cyber_scenario_produces_cyber_incident():
    run = await run_scenario("cybersecurity", ticks=10)

    assert run.types == ["CYBER_INTRUSION"], f"expected one cyber incident, got {run.types}"
    incident = run.incidents[0]
    assert "UNKNOWN-DEVICE-07" in incident.affected_assets
    assert "ISOLATE_DEVICE" in {a.action_type for a in incident.recommended_actions}


# --------------------------------------------------------------------- normal

@pytest.mark.asyncio
async def test_normal_scenario_produces_no_incident():
    run = await run_scenario("normal", ticks=40)
    assert run.incidents == [], f"quiet plant must stay quiet, got {run.types}"


# --------------------------------------------------------------------- honest numbers

RATE_PATTERN = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*°C/min")


@pytest.mark.asyncio
async def test_reported_temperature_rates_are_physically_plausible():
    """Before Step 1 the demo printed '+122 °C/min'. Slopes are now per plant minute."""
    run = await run_scenario("machine_overheating", ticks=20)
    text = " ".join(l["reasoning"] for l in run.logs)
    rates = [abs(float(m)) for m in RATE_PATTERN.findall(text)]
    assert rates, "the run should report at least one temperature trend"
    assert max(rates) < 20.0, f"implausible rate reported: {max(rates)} °C/min"


@pytest.mark.asyncio
async def test_no_rate_is_claimed_before_ten_seconds_of_history():
    run = await run_scenario("machine_overheating", ticks=4)
    early = " ".join(l["reasoning"] for l in run.logs)
    assert "trend not yet established" in early
    assert not RATE_PATTERN.search(early), "must not quote a rate it has not measured"


@pytest.mark.asyncio
async def test_confidence_is_derived_from_the_evidence():
    """Confidence must be a function of what the sensors said, not a literal in the source."""
    overheating = await run_scenario("machine_overheating", ticks=12)
    cyber = await run_scenario("cybersecurity", ticks=10)

    hot = overheating.incidents[0]
    intrusion = cyber.incidents[0]

    # Different evidence sets must not land on the same number.
    assert hot.confidence != intrusion.confidence
    assert all(0.0 < i.confidence < 1.0 for i in (hot, intrusion))

    # The overheating incident fuses several hazard sources, the cyber one has a single
    # source, so the fused figure must be higher and must be reproducible from the sources.
    hazard_sources = [e for e in hot.evidence if e.source in ("machine_agent", "temperature_agent")]
    assert len(hazard_sources) >= 2
    assert hot.confidence > intrusion.confidence
    assert str(int(hot.confidence * 100)) in hot.ai_reasoning, "the reasoning must quote the real figure"


@pytest.mark.asyncio
async def test_reasoning_quotes_the_real_readings():
    run = await run_scenario("machine_overheating", ticks=12)
    reasoning = run.incidents[0].ai_reasoning
    # The old text hardcoded "51°C" / "8.7 bar" regardless of what the sensors said.
    assert "risk assessment, not a certainty" in reasoning
    assert "M-04" in reasoning


# --------------------------------------------------------------------- scenario switching

@pytest.mark.asyncio
async def test_fire_after_overheating_with_reset_is_only_a_fire():
    """Live-run regression: a demo reset must wipe the correlation window.

    Otherwise the fire scenario's smoke correlates with the previous scenario's 8.9 bar
    pressure reading and a second, bogus MACHINE_OVERHEATING incident appears.
    """
    run = await run_scenario_sequence(
        [("machine_overheating", 12), ("fire", 12)], factory_reset_between=True
    )
    assert run.types == ["INDUSTRIAL_FIRE"], f"stale evidence leaked across the reset: {run.types}"


@pytest.mark.asyncio
async def test_fire_after_overheating_without_reset_does_not_reuse_stale_evidence():
    """Switching scenario without a reset must clear correlation memory.

    The first scenario's own MACHINE_OVERHEATING incident legitimately survives in the
    state store (nothing reset it), so what we check is that the *fire* step builds its
    incident from smoke only — not from the previous scenario's pressure reading.
    """
    run = await run_scenario_sequence([("machine_overheating", 12), ("fire", 12)])

    assert sorted(run.types) == ["INDUSTRIAL_FIRE", "MACHINE_OVERHEATING"], run.types
    fire = next(i for i in run.incidents if i.type == "INDUSTRIAL_FIRE")
    assert "machine_agent" not in {e.source for e in fire.evidence}, \
        "the fire incident must not cite the previous scenario's machine evidence"
    assert not any("bar" in e.detail for e in fire.evidence), "stale pressure evidence leaked"


@pytest.mark.asyncio
async def test_reset_is_recorded_in_the_agent_log():
    run = await run_scenario_sequence(
        [("machine_overheating", 6), ("normal", 6)], factory_reset_between=True
    )
    assert any("Correlation memory cleared" in l["reasoning"] for l in run.logs)


# --------------------------------------------------------------------- GATE 1 regressions

@pytest.mark.asyncio
async def test_pending_actions_are_announced_on_the_websocket():
    """GATE 1 issue 1: the Command Center only showed actions after F5.

    Nothing published when an action was *created* — only command_engine published on
    authorise/execute/complete — so the dashboard, which keeps its own list from
    ACTION_STATUS events, never learned about a pending action.
    """
    run = await run_scenario("machine_overheating", ticks=12)

    action_events = run.events_of("ACTION_STATUS")
    assert action_events, "creating actions must publish ACTION_STATUS"

    awaiting = [e for e in action_events if e["data"]["status"] == "AWAITING_APPROVAL"]
    assert awaiting, f"expected an AWAITING_APPROVAL announcement, saw {[e['data']['status'] for e in action_events]}"

    # The payload must be the shape frontend/src/App.tsx already consumes.
    payload = awaiting[0]["data"]
    for field in ("id", "incident_id", "action_type", "target", "status", "risk_level"):
        assert field in payload, f"{field} missing from the ACTION_STATUS payload"

    # The incident must be announced before its actions, or the UI has nowhere to put them.
    order = [e["event_type"] for e in run.published
             if e["event_type"] in ("INCIDENT_CREATED", "ACTION_STATUS")]
    assert order.index("INCIDENT_CREATED") < order.index("ACTION_STATUS")

    announced_ids = {e["data"]["id"] for e in action_events}
    pending_ids = {a.id for a in run.actions if a.status.value == "AWAITING_APPROVAL"}
    assert pending_ids <= announced_ids, "every pending action must have been announced"


@pytest.mark.asyncio
async def test_authorizing_everything_resolves_and_does_not_reopen():
    """GATE 1 issues 3+4: a new CRITICAL incident opened seconds after the operator resolved.

    The simulator kept driving M-04 to 8.93 bar after the shutdown (P5), so the thresholds were
    still breached and a fresh incident was created. Now P5 decays the readings and a
    just-resolved hazard may only re-open if the values are climbing again.

    ``keep_clock`` matters: restarting the fake clock would put ``resolved_at`` in the future and
    silently disable both the cooldown and the re-open guard, so the test would pass for the
    wrong reason.
    """
    from app.services.command_engine import command_engine
    from app.services.state_store import state
    from ai import clock
    from iot.simulator import simulator

    run = await run_scenario("machine_overheating", ticks=12, keep_clock=True)
    try:
        incident = run.incidents[0]
        assert incident.status == "ACTIVE"

        pending = [a for a in run.actions if a.status.value == "AWAITING_APPROVAL"]
        assert pending, "the scenario should leave actions awaiting approval"
        for action in pending:
            await command_engine.authorize_action(action.id, authorized_by="owner_01")
            await command_engine.execute_action(action.id)

        assert incident.status == "RESOLVED", f"expected RESOLVED, got {incident.status}"
        assert incident.resolved_at is not None
        resolved_count = len(state.incidents)

        # Keep the plant running for another 70 simulated seconds — past the 60 s cooldown.
        await run.feed(70, scenario="machine_overheating")

        assert len(state.incidents) == resolved_count, (
            "a new incident was opened after resolution: "
            f"{[(i.id, i.type, i.status) for i in state.incidents.values()]}"
        )
        machine = state.machines["M-04"]
        assert machine.parameters["pressure"].value < 7.0, (
            f"P5: a stopped machine must decay, still at {machine.parameters['pressure'].value} bar")
        assert machine.parameters["temperature"].value < 80.0
    finally:
        clock.reset_clock()
        simulator.stopped_machines.clear()
        simulator.cooling_active = False
        simulator.suppression_active = False
        simulator.set_scenario("normal")


@pytest.mark.asyncio
async def test_a_resolved_hazard_reopens_only_when_values_climb_again():
    """The re-open guard itself, isolated from the simulator.

    Same readings, same zone, twice: once with the machine's pressure trending down, once with
    it trending up. Only the rising case may open a new incident.
    """
    from datetime import timedelta

    from ai import clock
    from ai.orchestrator import AgentOrchestrator, REOPEN_REQUIRE_RISING_S, RESOLVED_COOLDOWN_S
    from app.models.schemas import Incident, Severity
    from app.services.state_store import state

    fake = clock.FakeClock()
    clock.set_clock(fake)
    try:
        state.initialize_state()
        orchestrator = AgentOrchestrator()

        resolved = Incident(
            id="INC-OLD", type="MACHINE_OVERHEATING", severity=Severity.CRITICAL, confidence=0.9,
            zone="ZONE_B", timestamp=clock.now(), affected_assets=["M-04"], affected_workers=[],
            evidence=[], ai_reasoning="resolved earlier", recommended_actions=[],
            status="RESOLVED", resolved_at=clock.now(),
        )
        state.incidents["INC-OLD"] = resolved

        # Past the hard cooldown, still inside the "must be rising" window.
        fake.advance(RESOLVED_COOLDOWN_S + 5.0)
        assert orchestrator._seconds_since_resolved("MACHINE_OVERHEATING", "ZONE_B") < REOPEN_REQUIRE_RISING_S

        falling = {
            "agent_id": "machine_agent", "anomaly": True, "severity": "WARNING",
            "machine_id": "M-04", "zone": "ZONE_B", "pressure": 7.4,
            "pressure_slope": -0.8, "pressure_slope_known": True,
            "observation": "pressure 7.40 bar, falling", "decision": "monitor",
        }
        rising = {**falling, "pressure_slope": 0.9,
                  "observation": "pressure 7.40 bar, climbing again"}

        assert orchestrator._evidence_rising([falling])[0] is False
        assert orchestrator._evidence_rising([rising])[0] is True

        incident_data = {
            "id": "INC-NEW1", "type": "MACHINE_OVERHEATING", "severity": Severity.WARNING,
            "confidence": 0.6, "zone": "ZONE_B", "timestamp": clock.now(),
            "affected_assets": ["M-04"], "affected_workers": [], "evidence": [],
            "ai_reasoning": "new", "recommended_actions": [], "status": "ACTIVE",
        }

        await orchestrator._create_or_escalate(dict(incident_data), [falling])
        assert "INC-NEW1" not in state.incidents, "a receding hazard must not re-open"
        assert any("receding rather than returning" in l["reasoning"] for l in state.agent_logs)

        await orchestrator._create_or_escalate({**incident_data, "id": "INC-NEW2"}, [rising])
        assert "INC-NEW2" in state.incidents, "a genuinely climbing hazard must re-open"
    finally:
        clock.reset_clock()
        state.initialize_state()


@pytest.mark.asyncio
async def test_hard_cooldown_blocks_reopening_even_when_values_climb():
    """Inside the 60 s cooldown nothing re-opens, rising or not."""
    from ai import clock
    from ai.orchestrator import AgentOrchestrator
    from app.models.schemas import Incident, Severity
    from app.services.state_store import state

    fake = clock.FakeClock()
    clock.set_clock(fake)
    try:
        state.initialize_state()
        orchestrator = AgentOrchestrator()
        state.incidents["INC-OLD"] = Incident(
            id="INC-OLD", type="MACHINE_OVERHEATING", severity=Severity.CRITICAL, confidence=0.9,
            zone="ZONE_B", timestamp=clock.now(), affected_assets=["M-04"], affected_workers=[],
            evidence=[], ai_reasoning="resolved earlier", recommended_actions=[],
            status="RESOLVED", resolved_at=clock.now(),
        )
        fake.advance(10.0)

        rising = {
            "agent_id": "machine_agent", "anomaly": True, "severity": "CRITICAL",
            "machine_id": "M-04", "zone": "ZONE_B", "pressure": 8.9,
            "pressure_slope": 1.2, "pressure_slope_known": True,
            "observation": "pressure 8.90 bar, climbing", "decision": "stop",
        }
        await orchestrator._create_or_escalate({
            "id": "INC-NEW", "type": "MACHINE_OVERHEATING", "severity": Severity.CRITICAL,
            "confidence": 0.9, "zone": "ZONE_B", "timestamp": clock.now(),
            "affected_assets": ["M-04"], "affected_workers": [], "evidence": [],
            "ai_reasoning": "new", "recommended_actions": [], "status": "ACTIVE",
        }, [rising])
        assert "INC-NEW" not in state.incidents
        assert any("cooldown" in l["decision"].lower() for l in state.agent_logs)
    finally:
        clock.reset_clock()
        state.initialize_state()


@pytest.mark.asyncio
async def test_optional_actions_are_cancelled_once_the_hazard_is_addressed():
    """The resolution rule: STOP_MACHINE completing resolves the incident, and the remaining
    supporting actions are cancelled as superseded rather than left for the owner to clear."""
    from app.services.command_engine import command_engine
    from app.services.state_store import state

    run = await run_scenario("machine_overheating", ticks=12)
    incident = run.incidents[0]
    stop = next(a for a in run.actions if a.action_type == "STOP_MACHINE")
    others = [a for a in run.actions
              if a.incident_id == incident.id and a.action_type != "STOP_MACHINE"]

    await command_engine.authorize_action(stop.id, authorized_by="owner_01")
    await command_engine.execute_action(stop.id)

    assert incident.status == "RESOLVED"
    assert all(a.status.value == "CANCELLED" for a in others), \
        f"supporting actions should be superseded, got {[(a.action_type, a.status.value) for a in others]}"
    assert any("superseded" in l["reasoning"] for l in state.agent_logs), \
        "the cancellation must be explained in the agent log"
    try:
        from iot.simulator import simulator
        simulator.stopped_machines.clear()
    except Exception:
        pass
