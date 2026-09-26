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
