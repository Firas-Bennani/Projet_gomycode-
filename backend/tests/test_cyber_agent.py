"""Step 8: cyber rules, ATT&CK for ICS attribution, and the spoofed-sensor trust story.

Before this the agent flagged every CYBER_EVENT as HIGH with no rules at all. These tests drive
it with synthetic events, because the simulator still emits a single generic payload — the extra
payloads are written up for Engineer 2 in docs/ai/PROPOSED_CHANGES_FOR_TEAM.md.
"""

import pytest

from ai import clock, mitre_ics, risk_engine
from ai.agents.cyber_agent import (
    BRUTE_FORCE_ATTEMPTS, SPOOFED_SENSOR_TRUST, CybersecurityAgent,
)
from app.services.state_store import state


@pytest.fixture(autouse=True)
def clean():
    risk_engine.reset_trust()
    state.initialize_state()
    yield
    risk_engine.reset_trust()
    state.initialize_state()


def cyber_event(**data):
    return {"event_type": "CYBER_EVENT", "zone": "ZONE_B", "severity": "HIGH", "data": data}


# --------------------------------------------------------------------- ATT&CK lookup

def test_every_rule_resolves_to_a_real_non_revoked_technique():
    if not mitre_ics.available():
        pytest.skip("ATT&CK for ICS bundle not present")
    for rule in mitre_ics.RULE_LOOKUP:
        technique = mitre_ics.for_rule(rule)
        assert technique, f"{rule} resolved to nothing"
        assert technique["technique_id"].startswith("T")
        assert technique["name"]
        assert technique["url"].startswith("https://attack.mitre.org/")


def test_revoked_ids_are_never_returned():
    """T0855 / T0856 are revoked in the current bundle; quoting them would be wrong."""
    if not mitre_ics.available():
        pytest.skip("ATT&CK for ICS bundle not present")
    returned = {mitre_ics.describe(mitre_ics.for_rule(r)) for r in mitre_ics.RULE_LOOKUP}
    assert not any(bad in text for text in returned for bad in ("T0855", "T0856", "T0803"))


def test_attribution_is_omitted_rather_than_invented_when_the_bundle_is_missing(monkeypatch):
    monkeypatch.setattr(mitre_ics, "CANDIDATE_PATHS", [])
    mitre_ics.reset_cache()
    try:
        assert mitre_ics.available() is False
        assert mitre_ics.for_rule("BRUTE_FORCE") is None
        assert mitre_ics.describe(None) == ""
    finally:
        mitre_ics.reset_cache()


# --------------------------------------------------------------------- rules

@pytest.mark.asyncio
async def test_brute_force_needs_enough_failed_attempts():
    agent = CybersecurityAgent()
    few = await agent.process_event(cyber_event(
        device="ENG-WS-01", source="ENG-WS-01", attempts=3, target="PLC-B-01"))
    assert "BRUTE_FORCE" not in few["rules"], "three failures is not a brute-force attempt"

    agent = CybersecurityAgent()
    many = await agent.process_event(cyber_event(
        device="ENG-WS-01", source="ENG-WS-01",
        attempts=BRUTE_FORCE_ATTEMPTS + 5, target="PLC-B-01"))
    assert "BRUTE_FORCE" in many["rules"]
    assert many["severity"] in ("HIGH", "CRITICAL")


@pytest.mark.asyncio
async def test_brute_force_accumulates_across_a_60_second_window():
    """Several small bursts from one source add up; the window then forgets them."""
    fake = clock.FakeClock()
    clock.set_clock(fake)
    try:
        agent = CybersecurityAgent()
        for _ in range(3):
            result = await agent.process_event(cyber_event(
                device="ENG-WS-01", source="10.0.0.9", attempts=8, target="PLC-B-01"))
            fake.advance(5.0)
        assert "BRUTE_FORCE" in result["rules"], "24 failures in 15 s must trip the rule"

        fake.advance(120.0)
        later = await agent.process_event(cyber_event(
            device="ENG-WS-01", source="10.0.0.9", attempts=2, target="PLC-B-01"))
        assert "BRUTE_FORCE" not in later["rules"], "the window must forget old failures"
    finally:
        clock.reset_clock()


@pytest.mark.asyncio
async def test_a_device_in_the_inventory_is_not_flagged_as_unknown():
    agent = CybersecurityAgent()
    known = await agent.process_event(cyber_event(device="M-04", source="M-04", attempts=1))
    assert "UNKNOWN_DEVICE" not in known["rules"]

    agent = CybersecurityAgent()
    rogue = await agent.process_event(cyber_event(device="UNKNOWN-DEVICE-07", attempts=1))
    assert "UNKNOWN_DEVICE" in rogue["rules"]
    attributed = {m["rule"]: m for m in rogue["mitre_techniques"]}
    if mitre_ics.available():
        assert attributed["UNKNOWN_DEVICE"]["technique_id"] == "T0848"


@pytest.mark.asyncio
async def test_a_command_from_a_whitelisted_source_is_allowed():
    agent = CybersecurityAgent()
    allowed = await agent.process_event(cyber_event(
        device="ENG-WS-01", source="ENG-WS-01", command="write_setpoint", target="PLC-B-01"))
    assert "UNAUTHORIZED_COMMAND" not in allowed["rules"]

    agent = CybersecurityAgent()
    denied = await agent.process_event(cyber_event(
        device="UNKNOWN-DEVICE-07", source="10.0.0.66",
        command="write_setpoint", target="PLC-B-01"))
    assert "UNAUTHORIZED_COMMAND" in denied["rules"]
    assert denied["severity"] == "CRITICAL"
    assert "BLOCK the command path" in denied["decision"]


@pytest.mark.asyncio
async def test_traffic_anomaly_uses_a_z_score():
    agent = CybersecurityAgent()
    quiet = await agent.process_event(cyber_event(device="M-04", source="M-04", traffic_z=1.1))
    assert "TRAFFIC_ANOMALY" not in [r for r in quiet["rules"] if not quiet["findings"][0].get("unclassified")]

    agent = CybersecurityAgent()
    loud = await agent.process_event(cyber_event(device="M-04", source="M-04", traffic_z=4.2))
    assert "TRAFFIC_ANOMALY" in loud["rules"]


@pytest.mark.asyncio
async def test_an_unmatched_event_says_so_instead_of_inventing_a_verdict():
    agent = CybersecurityAgent()
    result = await agent.process_event(cyber_event(device="M-04", source="M-04"))
    assert result["severity"] == "WARNING"
    assert "no rule matched" in result["observation"]


@pytest.mark.asyncio
async def test_the_existing_simulator_payload_still_classifies():
    """The simulator's one generic event must keep working — the cyber demo depends on it."""
    agent = CybersecurityAgent()
    result = await agent.process_event(cyber_event(
        cyber_type="UNAUTHORIZED_DEVICE", device="UNKNOWN-DEVICE-07", attempts=47,
        target="Industrial Modbus Gateway (192.168.10.45)"))
    assert result["anomaly"] is True
    assert set(result["rules"]) >= {"BRUTE_FORCE", "UNKNOWN_DEVICE"}
    assert result["severity"] == "HIGH"
    assert result["device"] == "UNKNOWN-DEVICE-07"
    assert result["attempts"] == 47


# --------------------------------------------------------------------- spoofed sensor

@pytest.mark.asyncio
async def test_a_declared_spoof_distrusts_the_sensor_and_says_so():
    agent = CybersecurityAgent()
    result = await agent.process_event(cyber_event(
        cyber_type="SPOOFED_SENSOR", device="UNKNOWN-DEVICE-07",
        sensor_id="TEMP-B-01", target="TEMP-B-01"))

    assert "SPOOFED_SENSOR" in result["rules"]
    assert result["spoofed_sensor"] == "TEMP-B-01"
    assert result["severity"] == "CRITICAL"
    # The decision text is what appears in state.agent_logs on the multi-agent page.
    assert "DISTRUST TEMP-B-01" in result["decision"]
    assert "Distrust TEMP-B-01" in result["observation"]
    assert risk_engine.get_trust("TEMP-B-01") == SPOOFED_SENSOR_TRUST
    assert "spoofed" in risk_engine.trust_reason("TEMP-B-01")
    if mitre_ics.available():
        assert any(m["rule"] == "SPOOFED_SENSOR" for m in result["mitre_techniques"])


@pytest.mark.asyncio
async def test_a_physical_inconsistency_is_detected_without_being_told():
    """The ambient sensor sits at baseline while the machine beside it is past its limit."""
    state.sensors["TEMP-B-01"].current_value = 24.0          # attacker pinned it low
    state.machines["M-04"].parameters["temperature"].value = 95.0   # really cooking

    agent = CybersecurityAgent()
    result = await agent.process_event(cyber_event(
        device="UNKNOWN-DEVICE-07", sensor_id="TEMP-B-01", attempts=1))

    assert "SPOOFED_SENSOR" in result["rules"]
    assert risk_engine.get_trust("TEMP-B-01") == SPOOFED_SENSOR_TRUST


@pytest.mark.asyncio
async def test_a_consistent_sensor_is_left_alone():
    state.sensors["TEMP-B-01"].current_value = 48.0
    state.machines["M-04"].parameters["temperature"].value = 60.0

    agent = CybersecurityAgent()
    result = await agent.process_event(cyber_event(
        device="UNKNOWN-DEVICE-07", sensor_id="TEMP-B-01", attempts=1))

    assert "SPOOFED_SENSOR" not in result["rules"]
    assert risk_engine.get_trust("TEMP-B-01") == 1.0


@pytest.mark.asyncio
async def test_the_spoof_does_not_hide_the_overheating_end_to_end():
    """The flagship: distrust the lying sensor, still declare the machine hazard.

    Cyber agent distrusts TEMP-B-01, then the machine agent's own evidence drives an incident
    that is still CRITICAL — which is exactly what OT-CYBER-PB 4.3 requires.
    """
    from ai.agents.machine_agent import MachineAgent
    from ai.agents.recommendation_agent import RecommendationAgent

    # 1. the attacker pins the ambient sensor low while M-04 overheats
    state.sensors["TEMP-B-01"].current_value = 24.0
    state.machines["M-04"].parameters["temperature"].value = 95.0

    cyber = await CybersecurityAgent().process_event(cyber_event(
        cyber_type="SPOOFED_SENSOR", device="UNKNOWN-DEVICE-07", sensor_id="TEMP-B-01"))
    assert cyber["spoofed_sensor"] == "TEMP-B-01"
    assert risk_engine.get_trust("TEMP-B-01") == SPOOFED_SENSOR_TRUST

    # 2. the machine's own sensors are independent of the spoofed one
    machine_obs = await MachineAgent().process_event({
        "event_type": "MACHINE_STATUS", "zone": "ZONE_B",
        "data": {"machine_id": "M-04", "zone": "ZONE_B", "parameters": {
            "pressure": {"value": 8.9}, "temperature": {"value": 95.0},
            "vibration": {"value": 6.2}, "rpm": {"value": 1420}}},
    })
    assert machine_obs["severity"] == "CRITICAL"

    # 3. the spoofed ambient reading is still used, at a fifth of its weight
    spoofed_ambient = {
        "agent_id": "temperature_agent", "sensor_type": "temperature", "severity": "WARNING",
        "sensor_id": "TEMP-B-01", "zone": "ZONE_B", "current_value": 24.0, "unit": "°C",
        "rate_of_change": 0.0, "rate_known": False,
        "observation": "TEMP-B-01 reads 24.0°C", "decision": "monitor",
    }
    incident = RecommendationAgent().synthesize_incident(
        [machine_obs, spoofed_ambient], zone="ZONE_B")

    assert incident is not None
    assert incident["type"] == "MACHINE_OVERHEATING"
    assert incident["severity"].value == "CRITICAL", "the hazard must survive the spoof"
    assert "TRUST:" in incident["ai_reasoning"]
    assert "TEMP-B-01" in incident["ai_reasoning"]
    assert "down-weighted" in incident["ai_reasoning"]


@pytest.mark.asyncio
async def test_distrust_is_not_repeated_for_the_same_sensor_forever():
    agent = CybersecurityAgent()
    for _ in range(3):
        result = await agent.process_event(cyber_event(
            cyber_type="SPOOFED_SENSOR", device="UNKNOWN-DEVICE-07", sensor_id="TEMP-B-01"))
    assert result["distrusted_sensors"] == ["TEMP-B-01"], "recorded once, not three times"
