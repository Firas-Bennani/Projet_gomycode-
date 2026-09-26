"""Unit tests for the Step 1 building blocks: trend maths, window, fusion, cooldown."""

from datetime import datetime, timedelta

import pytest

from ai import clock, trend
from ai.agents.recommendation_agent import fuse_confidence, max_severity
from ai.observation_window import ObservationWindow
from ai.orchestrator import AgentOrchestrator, RESOLVED_COOLDOWN_S
from app.models.schemas import Incident, Severity
from app.services.state_store import state

T0 = datetime(2026, 1, 1, 0, 0, 0)


def points(values, step_s=1.0, start=T0):
    return [(start + timedelta(seconds=i * step_s), v) for i, v in enumerate(values)]


# --------------------------------------------------------------------- trend

def test_slope_is_unknown_without_enough_history():
    assert trend.slope_per_plant_minute(points([20.0, 22.0])) is None          # too few points
    assert trend.slope_per_plant_minute(points([20.0, 22.0, 24.0])) is None    # spans only 2 s


def test_slope_is_least_squares_not_first_vs_last():
    # Steady 1 unit/s ramp with a single spike at the end. First-vs-last would report the
    # spike as the trend; least squares barely moves.
    clean = points([float(i) for i in range(12)])
    spiky = points([float(i) for i in range(11)] + [40.0])
    assert trend.slope_per_plant_minute(clean) == pytest.approx(1.0, abs=0.01)
    assert trend.slope_per_plant_minute(spiky) < 4.0


def test_slope_is_reported_per_plant_minute():
    # 12 samples, 1 s apart, +1 unit per second. DEMO_TIME_SCALE=60 means one real second
    # is one plant minute, so the answer is 1.0 per plant minute, not 60.
    assert trend.DEMO_TIME_SCALE == 60.0
    assert trend.slope_per_plant_minute(points([float(i) for i in range(12)])) == pytest.approx(1.0, abs=0.01)


def test_sustained_above_requires_a_run_of_readings():
    assert not trend.sustained_above(points([10, 10, 10, 45]), 40.0)
    assert trend.sustained_above(points([10, 45, 48, 52, 60]), 40.0)


def test_eta_to_limit():
    assert trend.eta_seconds_to_limit(7.0, 8.0, 1.0) == pytest.approx(60.0)
    assert trend.eta_seconds_to_limit(7.0, 8.0, None) is None
    assert trend.eta_seconds_to_limit(7.0, 8.0, -1.0) is None
    assert trend.eta_seconds_to_limit(8.5, 8.0, 1.0) == 0.0


def test_prune_drops_old_samples():
    pts = points([1.0] * 5)
    trend.prune(pts, T0 + timedelta(seconds=120), ttl_s=60.0)
    assert pts == []


# --------------------------------------------------------------------- window

def test_window_keeps_newest_observation_per_agent_and_asset():
    fake = clock.FakeClock(T0)
    clock.set_clock(fake)
    try:
        window = ObservationWindow(ttl_s=30.0)
        window.add({"agent_id": "temperature_agent", "sensor_id": "TEMP-B-01", "zone": "ZONE_B", "current_value": 30.0})
        fake.advance(1.0)
        window.add({"agent_id": "temperature_agent", "sensor_id": "TEMP-B-01", "zone": "ZONE_B", "current_value": 40.0})
        window.add({"agent_id": "machine_agent", "machine_id": "M-04", "zone": "ZONE_B"})
        window.add({"agent_id": "temperature_agent", "sensor_id": "TEMP-C-01", "zone": "ZONE_C"})

        zone_b = window.snapshot("ZONE_B")
        assert len(zone_b) == 2, "one entry per (agent, asset)"
        temps = [o for o in zone_b if o.get("sensor_id") == "TEMP-B-01"]
        assert temps[0]["current_value"] == 40.0, "newest reading wins"
        assert len(window.snapshot("ZONE_C")) == 1, "zones are independent"
    finally:
        clock.reset_clock()


def test_window_expires_observations():
    fake = clock.FakeClock(T0)
    clock.set_clock(fake)
    try:
        window = ObservationWindow(ttl_s=30.0)
        window.add({"agent_id": "machine_agent", "machine_id": "M-04", "zone": "ZONE_B"})
        fake.advance(29.0)
        assert len(window.snapshot("ZONE_B")) == 1
        fake.advance(2.0)
        assert window.snapshot("ZONE_B") == []
    finally:
        clock.reset_clock()


# --------------------------------------------------------------------- fusion

def test_noisy_or_fusion_grows_with_independent_agreement():
    one = fuse_confidence([{"severity": "WARNING", "sensor_id": "A"}])[0]
    two = fuse_confidence([
        {"severity": "WARNING", "sensor_id": "A"},
        {"severity": "WARNING", "sensor_id": "B"},
    ])[0]
    assert one == pytest.approx(0.60)
    assert two > one
    assert two < 1.0, "no amount of evidence reaches certainty"


def test_fusion_reports_each_contribution():
    confidence, contributions = fuse_confidence([
        {"severity": "CRITICAL", "machine_id": "M-04"},
        {"severity": "WARNING", "sensor_id": "TEMP-B-01"},
    ])
    assert confidence > 0.85
    assert any("M-04" in c for c in contributions)
    assert any("TEMP-B-01" in c for c in contributions)


def test_max_severity_has_a_warning_floor():
    assert max_severity([{"severity": "INFO"}]) == "WARNING"
    assert max_severity([{"severity": "WARNING"}, {"severity": "CRITICAL"}]) == "CRITICAL"


# --------------------------------------------------------------------- cooldown

def _resolved_incident(resolved_at):
    return Incident(
        id="INC-TEST", type="MACHINE_OVERHEATING", severity=Severity.CRITICAL, confidence=0.9,
        zone="ZONE_B", timestamp=resolved_at, affected_assets=["M-04"], affected_workers=[],
        evidence=[], ai_reasoning="test", recommended_actions=[], status="RESOLVED",
        resolved_at=resolved_at,
    )


def test_cooldown_blocks_reopening_then_expires():
    fake = clock.FakeClock(T0)
    clock.set_clock(fake)
    try:
        state.initialize_state()
        orchestrator = AgentOrchestrator()
        state.incidents["INC-TEST"] = _resolved_incident(clock.now())

        assert orchestrator._cooldown_remaining("MACHINE_OVERHEATING", "ZONE_B") == pytest.approx(RESOLVED_COOLDOWN_S)
        assert orchestrator._cooldown_remaining("INDUSTRIAL_FIRE", "ZONE_B") == 0.0, "other hazards are unaffected"

        fake.advance(RESOLVED_COOLDOWN_S + 1.0)
        assert orchestrator._cooldown_remaining("MACHINE_OVERHEATING", "ZONE_B") == 0.0
    finally:
        clock.reset_clock()
        state.initialize_state()


def test_open_incident_is_found_for_dedup():
    state.initialize_state()
    orchestrator = AgentOrchestrator()
    incident = _resolved_incident(T0)
    incident.status = "ACTIVE"
    state.incidents["INC-TEST"] = incident
    try:
        assert orchestrator._find_open_incident("MACHINE_OVERHEATING", "ZONE_B") is incident
        assert orchestrator._find_open_incident("MACHINE_OVERHEATING", "ZONE_C") is None
    finally:
        state.initialize_state()
