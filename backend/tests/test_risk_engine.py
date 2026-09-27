"""Unit tests for ai/risk_engine.py — fusion, trust, the severity matrix and priority."""

import pytest

from ai import risk_engine
from ai.risk_engine import (
    assess, fuse, get_trust, impact_score, likelihood_band, matrix_severity,
    priority_score, reset_trust, set_trust, severity_cap,
)


@pytest.fixture(autouse=True)
def clean_trust():
    reset_trust()
    yield
    reset_trust()


def obs(severity, sensor_id=None, machine_id=None, agent_id="temperature_agent"):
    payload = {"severity": severity, "agent_id": agent_id}
    if sensor_id:
        payload["sensor_id"] = sensor_id
    if machine_id:
        payload["machine_id"] = machine_id
    return payload


# --------------------------------------------------------------------- fusion

def test_one_source_contributes_its_own_likelihood():
    confidence, contributions, _ = fuse([obs("WARNING", sensor_id="TEMP-B-01")])
    assert confidence == pytest.approx(0.60)
    assert len(contributions) == 1
    assert contributions[0].source_id == "TEMP-B-01"
    assert contributions[0].running_total == pytest.approx(0.60)


def test_independent_agreement_raises_confidence_but_never_to_certainty():
    one, _, _ = fuse([obs("CRITICAL", machine_id="M-04", agent_id="machine_agent")])
    two, _, _ = fuse([
        obs("CRITICAL", machine_id="M-04", agent_id="machine_agent"),
        obs("WARNING", sensor_id="TEMP-B-01"),
    ])
    assert one == pytest.approx(0.85)
    assert two == pytest.approx(0.94)          # 1 - 0.15*0.40
    assert two < 1.0
    many, _, _ = fuse([obs("CRITICAL", sensor_id=f"S-{i}") for i in range(20)])
    assert many <= risk_engine.MAX_CONFIDENCE


def test_the_same_sensor_cannot_be_counted_twice():
    confidence, contributions, _ = fuse([
        obs("CRITICAL", sensor_id="TEMP-B-01"),
        obs("CRITICAL", sensor_id="TEMP-B-01"),
    ])
    assert len(contributions) == 1
    assert confidence == pytest.approx(0.85)


def test_contributions_show_their_arithmetic():
    _, contributions, _ = fuse([obs("WARNING", sensor_id="TEMP-B-01")])
    text = contributions[0].text
    assert "TEMP-B-01" in text and "WARNING" in text and "0.60" in text
    assert "running" in text


# --------------------------------------------------------------------- trust

def test_trust_is_one_by_default_and_clamped_when_set():
    assert get_trust("TEMP-B-01") == 1.0
    set_trust("TEMP-B-01", 5.0)
    assert get_trust("TEMP-B-01") == 1.0
    set_trust("TEMP-B-01", -3.0)
    assert get_trust("TEMP-B-01") == 0.0


def test_a_distrusted_sensor_contributes_less():
    before, _, _ = fuse([obs("CRITICAL", sensor_id="TEMP-B-01")])
    set_trust("TEMP-B-01", 0.2, "physically inconsistent with M-04 body temperature")
    after, contributions, distrusted = fuse([obs("CRITICAL", sensor_id="TEMP-B-01")])
    assert after < before
    assert after == pytest.approx(0.17)        # 0.85 * 0.2
    assert distrusted == ["TEMP-B-01"]
    assert "trust 0.20" in contributions[0].text


def test_a_spoofed_temperature_sensor_does_not_hide_an_overheating_machine():
    """The Step 8 flagship, tested at the engine level.

    An attacker pins the ambient sensor low. The machine's own pressure and body temperature are
    independent of it, so the hazard must still be assessed as critical.
    """
    set_trust("TEMP-B-01", 0.2, "spoofed: reading flat while M-04 heats")
    result = assess(
        [obs("CRITICAL", machine_id="M-04", agent_id="machine_agent"),
         obs("WARNING", sensor_id="TEMP-B-01")],
        "MACHINE_OVERHEATING", assets=["M-04"], workers_exposed=3,
    )
    assert result.severity == "CRITICAL"
    assert result.confidence >= 0.85, "machine evidence alone must still carry the assessment"
    assert "TEMP-B-01" in result.distrusted
    assert "spoofed" in risk_engine.trust_reason("TEMP-B-01")


# --------------------------------------------------------------------- severity

def test_likelihood_bands():
    assert likelihood_band(0.95) == 4
    assert likelihood_band(0.80) == 3
    assert likelihood_band(0.60) == 2
    assert likelihood_band(0.10) == 1


def test_impact_rises_with_people_and_with_direct_harm():
    bare = impact_score("MACHINE_OVERHEATING", ["M-01"], workers_exposed=0)
    with_people = impact_score("MACHINE_OVERHEATING", ["M-01"], workers_exposed=3)
    assert with_people == bare + 1
    # M-04 is more critical than M-01, so it scores at least as high.
    assert impact_score("MACHINE_OVERHEATING", ["M-04"], 0) >= bare
    # A fire is a life-safety hazard whatever the asset.
    assert impact_score("INDUSTRIAL_FIRE", [], 3) == 4


def test_impact_is_capped():
    assert impact_score("INDUSTRIAL_FIRE", ["M-04"], 9) <= 4


def test_matrix_severity_thresholds():
    assert matrix_severity(4, 4) == "CRITICAL"
    assert matrix_severity(3, 3) == "HIGH"
    assert matrix_severity(2, 2) == "WARNING"
    assert matrix_severity(1, 1) == "INFO"


def test_severity_is_capped_one_band_above_the_strongest_source():
    """Two warning-level readings must not be announced as CRITICAL.

    This is what keeps the escalation honest: the matrix would say CRITICAL, but while no single
    sensor is past its critical threshold the incident is reported HIGH.
    """
    warning_only = assess(
        [obs("WARNING", machine_id="M-04", agent_id="machine_agent"),
         obs("WARNING", sensor_id="TEMP-B-01")],
        "MACHINE_OVERHEATING", assets=["M-04"], workers_exposed=3,
    )
    assert warning_only.matrix_severity == "CRITICAL"
    assert warning_only.severity == "HIGH"
    assert warning_only.severity_cap == "HIGH"
    assert "capped" in warning_only.severity_explanation

    escalated = assess(
        [obs("CRITICAL", machine_id="M-04", agent_id="machine_agent"),
         obs("WARNING", sensor_id="TEMP-B-01")],
        "MACHINE_OVERHEATING", assets=["M-04"], workers_exposed=3,
    )
    assert escalated.severity == "CRITICAL"
    assert "capped" not in escalated.severity_explanation


def test_severity_never_drops_below_the_floor():
    result = assess([obs("WARNING", sensor_id="HUM-B-01")], "MACHINE_OVERHEATING",
                    assets=["M-01"], workers_exposed=0)
    assert result.severity in ("WARNING", "HIGH")
    assert risk_engine.SEVERITY_RANK[result.severity] >= risk_engine.SEVERITY_RANK["WARNING"]


def test_severity_explanation_shows_the_arithmetic():
    result = assess([obs("CRITICAL", machine_id="M-04", agent_id="machine_agent")],
                    "MACHINE_OVERHEATING", assets=["M-04"], workers_exposed=3)
    text = result.severity_explanation
    assert f"impact {result.impact}/4" in text
    assert f"likelihood {result.likelihood}/4" in text
    assert str(result.impact * result.likelihood) in text


# --------------------------------------------------------------------- priority

def test_priority_is_dominated_by_severity_then_people_then_time():
    critical = priority_score("CRITICAL", 0, None)
    high_with_people = priority_score("HIGH", 5, None)
    assert critical > high_with_people, "severity must dominate"

    people = priority_score("HIGH", 3, None)
    no_people = priority_score("HIGH", 0, None)
    assert people > no_people

    urgent = priority_score("HIGH", 0, eta_seconds=10)
    relaxed = priority_score("HIGH", 0, eta_seconds=600)
    assert urgent > relaxed, "less time left must rank higher"


def test_assess_reports_priority_and_eta():
    result = assess([obs("CRITICAL", machine_id="M-04", agent_id="machine_agent")],
                    "MACHINE_OVERHEATING", assets=["M-04"], workers_exposed=3, eta_seconds=40)
    assert result.eta_seconds == 40
    assert result.workers_exposed == 3
    assert result.priority > 0


# --------------------------------------------------------------------- no evidence

def test_no_scored_source_gives_no_confidence():
    confidence, contributions, _ = fuse([obs("INFO", sensor_id="TEMP-B-01")])
    assert confidence == 0.0
    assert contributions == []
    result = assess([], "MACHINE_OVERHEATING")
    assert result.confidence == 0.0
    assert result.contribution_text == "no scored source"
