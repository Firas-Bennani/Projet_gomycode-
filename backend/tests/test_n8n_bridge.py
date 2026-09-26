"""Tests for the backend side of the n8n bridge.

These run without n8n. The point of most of them is the safety property that makes it
acceptable to let a language model write recommendations at all: **the model can only pick
ids from the action catalogue, and it cannot influence how dangerous an action is.**
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from ai import n8n_client
from ai.actions_catalog import CATALOG, allowed_actions_for, validate_action_ids
from app.main import app
from app.models.schemas import Action, ActionStatus, EvidenceItem, Incident, RiskLevel, Severity
from app.services.state_store import state

# No `with` block: that would run the lifespan and start the background simulator.
client = TestClient(app)


def seed_incident(incident_type="MACHINE_OVERHEATING", status="ACTIVE", assets=None):
    state.initialize_state()
    n8n_client.clear_resume_urls()
    incident = Incident(
        id="INC-TEST",
        type=incident_type,
        severity=Severity.CRITICAL,
        confidence=0.94,
        zone="ZONE_B",
        timestamp=datetime.utcnow(),
        affected_assets=assets if assets is not None else ["M-04"],
        affected_workers=["W23", "W41", "W52"],
        evidence=[EvidenceItem(source="machine_agent", detail="pressure 8.9 bar over the 8.0 bar limit")],
        ai_reasoning="deterministic detection text",
        recommended_actions=[],
        status=status,
    )
    state.incidents[incident.id] = incident
    return incident


def seed_action(action_type="STOP_MACHINE", status=ActionStatus.AWAITING_APPROVAL,
                action_id="ACT-TEST", target="M-04", verification=None):
    action = Action(
        id=action_id, incident_id="INC-TEST", action_type=action_type, target=target,
        reason="test", risk_level=RiskLevel.HIGH, status=status,
        created_at=datetime.utcnow(), verification=verification,
    )
    state.actions[action_id] = action
    return action


# --------------------------------------------------------------------- catalogue

def test_catalog_actions_are_all_executable_by_the_command_engine():
    """Every catalogue action_type must be one command_engine handles, or nothing happens."""
    import inspect
    from app.services import command_engine as ce_module
    source = inspect.getsource(ce_module)
    for entry in CATALOG.values():
        assert f'"{entry.action_type}"' in source, f"{entry.action_type} is not handled by command_engine"


def test_low_risk_actions_are_the_only_automatic_ones():
    for entry in CATALOG.values():
        assert entry.auto != entry.requires_confirmation, f"{entry.id} is inconsistent"
        if entry.auto:
            assert entry.risk == RiskLevel.LOW, f"{entry.id} auto-executes but is not LOW risk"


def test_allowed_actions_are_filtered_by_hazard():
    fire = allowed_actions_for(seed_incident("INDUSTRIAL_FIRE", assets=["ZONE_B Sector"]))
    ids = {a["id"] for a in fire}
    assert "activate_suppression" in ids
    assert "isolate_device" not in ids, "a cyber action must not be offered for a fire"


def test_validation_rejects_unknown_and_wrong_hazard_ids():
    incident = seed_incident("MACHINE_OVERHEATING")
    result = validate_action_ids(["stop_machine", "close_door", "launch_missiles", "stop_machine"], incident)
    assert [e.id for e in result["accepted"]] == ["stop_machine"]
    reasons = {r["id"]: r["why"] for r in result["rejected"]}
    assert "not in the action catalogue" in reasons["launch_missiles"]
    assert "not permitted" in reasons["close_door"]


# --------------------------------------------------------------------- enrichment

def test_enrichment_accepts_valid_ids_and_rejects_the_rest():
    seed_incident()
    response = client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "Compressor overheating",
        "why": ["pressure over the limit"],
        "impact": "loss of M-04",
        "prediction": "seal failure",
        "recommended_action_ids": ["stop_machine", "evacuate_zone", "launch_missiles"],
        "sources": [{"document": "SOP-M04-Compressor", "section": "4.2"}],
        "resume_url": "http://localhost:5678/webhook-waiting/abc",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_action_ids"] == ["stop_machine", "evacuate_zone"]
    assert [r["id"] for r in body["rejected"]] == ["launch_missiles"]
    assert body["resume_url_registered"] is True
    assert n8n_client.get_resume_url("INC-TEST") == "http://localhost:5678/webhook-waiting/abc"


def test_enrichment_takes_risk_from_the_catalogue_not_the_request():
    """The model asks for stop_machine; the catalogue decides it is HIGH and needs a human."""
    seed_incident()
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "x", "recommended_action_ids": ["stop_machine"],
    })
    created = [a for a in state.actions.values() if a.action_type == "STOP_MACHINE"]
    assert created, "an accepted action should become a real pending action"
    action = created[0]
    assert action.risk_level == RiskLevel.HIGH
    assert action.status == ActionStatus.AWAITING_APPROVAL, "a HIGH risk action must wait for an owner"


def test_enrichment_does_not_duplicate_an_action_the_plant_already_holds():
    seed_incident()
    seed_action("STOP_MACHINE")
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "x", "recommended_action_ids": ["stop_machine"],
    })
    assert len([a for a in state.actions.values() if a.action_type == "STOP_MACHINE"]) == 1


def test_enrichment_cannot_change_the_confidence():
    incident = seed_incident()
    before = incident.confidence
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "x", "impact": "y", "recommended_action_ids": [],
    })
    assert incident.confidence == before
    assert "the language model does not set this figure" in incident.ai_reasoning
    assert f"{before * 100:.0f}%" in incident.ai_reasoning


def test_enrichment_records_its_provenance_and_sources():
    seed_incident()
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "x", "recommended_action_ids": ["stop_machine"],
        "sources": [{"document": "SOP-M04-Compressor", "section": "4.2"}],
        "produced_by": "gemini-via-n8n",
    })
    reasoning = state.incidents["INC-TEST"].ai_reasoning
    assert "SOP-M04-Compressor 4.2" in reasoning
    assert "gemini-via-n8n" in reasoning
    assert any(l["agent_id"] == "recommendation_agent (n8n)" for l in state.agent_logs)


def test_enrichment_on_an_unknown_incident_is_404():
    seed_incident()
    assert client.post("/api/ai/n8n/enrichment/INC-NOPE", json={"what": "x"}).status_code == 404


# --------------------------------------------------------------------- verification

def test_verify_fails_while_actions_are_still_open():
    seed_incident()
    seed_action("STOP_MACHINE", ActionStatus.AWAITING_APPROVAL)
    body = client.get("/api/ai/n8n/verify/INC-TEST").json()
    assert body["verified"] is False
    assert body["outstanding_actions"] == ["ACT-TEST"]


def test_verify_passes_on_executed_actions_even_if_the_simulator_keeps_ramping():
    """The regression this encodes: gating on live telemetry marked a good shutdown as failed.

    command_engine sets M-04 to a safe baseline, then the running scenario overwrites its
    pressure back to 8.9 bar on the next tick. The shutdown itself was verified by the
    actuator, so `verified` is true while `telemetry_consistent` honestly reports the clash.
    """
    incident = seed_incident()
    seed_action("STOP_MACHINE", ActionStatus.COMPLETED, verification={
        "verified": True,
        "checks": [{"check": "Machine M-04 spindle RPM verified zero", "passed": True}],
    })
    state.machines["M-04"].parameters["pressure"].value = 8.9   # simulator keeps ramping
    state.machines["M-04"].parameters["rpm"].value = 1420.0

    body = client.get("/api/ai/n8n/verify/INC-TEST").json()
    assert body["verified"] is True, body["details"]
    assert body["telemetry_consistent"] is False
    assert any("pressure back under its limit" in t["check"] for t in body["telemetry"])
    assert incident.type == "MACHINE_OVERHEATING"


def test_verify_reports_a_failed_actuator_check():
    seed_incident()
    seed_action("STOP_MACHINE", ActionStatus.COMPLETED, verification={
        "verified": False,
        "checks": [{"check": "Hydraulic main valve depressed", "passed": False}],
    })
    body = client.get("/api/ai/n8n/verify/INC-TEST").json()
    assert body["verified"] is False
    assert any("Hydraulic main valve" in c["check"] and not c["passed"] for c in body["details"])


# --------------------------------------------------------------------- status

def test_status_resolving_then_resolved():
    seed_incident()
    assert client.post("/api/ai/n8n/status/INC-TEST", json={"status": "RESOLVING"}).json()["status"] == "RESOLVING"
    body = client.post("/api/ai/n8n/status/INC-TEST", json={"status": "RESOLVED"}).json()
    assert body["status"] == "RESOLVED"
    assert state.incidents["INC-TEST"].resolved_at is not None


def test_status_never_moves_an_incident_backwards():
    """The workflow posts RESOLVING ~15 s after approval; command_engine may already have
    set RESOLVED. The dashboard must not bounce backwards."""
    seed_incident(status="RESOLVED")
    body = client.post("/api/ai/n8n/status/INC-TEST", json={"status": "RESOLVING"}).json()
    assert body["applied"] is False
    assert state.incidents["INC-TEST"].status == "RESOLVED"


def test_escalated_keeps_the_incident_visible_and_raises_severity():
    incident = seed_incident()
    incident.severity = Severity.WARNING
    body = client.post("/api/ai/n8n/status/INC-TEST", json={"status": "ESCALATED", "note": "no decision"}).json()
    assert body["reported"] == "ESCALATED"
    assert incident.status == "ACTIVE", "an escalated incident must stay on screen"
    assert incident.severity == Severity.CRITICAL


def test_status_rejects_an_unknown_value():
    seed_incident()
    assert client.post("/api/ai/n8n/status/INC-TEST", json={"status": "NONSENSE"}).status_code == 422


# --------------------------------------------------------------------- client behaviour

@pytest.mark.asyncio
async def test_notify_incident_is_skipped_when_disabled(monkeypatch):
    incident = seed_incident()
    monkeypatch.setenv("N8N_ENABLED", "false")
    assert await n8n_client.notify_incident(incident) is False
    assert n8n_client.LAST_EXCHANGE[incident.id]["status"] == "DISABLED"


@pytest.mark.asyncio
async def test_notify_incident_survives_an_unreachable_n8n(monkeypatch):
    """Detection must never depend on n8n being up."""
    incident = seed_incident()
    monkeypatch.setenv("N8N_ENABLED", "true")
    monkeypatch.setenv("N8N_INCIDENT_WEBHOOK_URL", "http://127.0.0.1:1/webhook/incident")
    monkeypatch.setenv("N8N_TIMEOUT_SECONDS", "1")
    assert await n8n_client.notify_incident(incident) is False
    assert n8n_client.LAST_EXCHANGE[incident.id]["status"] == "UNREACHABLE"


def test_payload_hands_n8n_the_action_menu_and_a_callback_address(monkeypatch):
    monkeypatch.setenv("BACKEND_BASE_URL_FOR_N8N", "http://host.docker.internal:8000")
    incident = seed_incident()
    payload = n8n_client.build_incident_payload(incident)
    assert payload["backend_base_url"] == "http://host.docker.internal:8000"
    assert {a["id"] for a in payload["allowed_actions"]} == {"stop_machine", "evacuate_zone",
                                                             "activate_cooling", "trigger_alarm"}
    assert {w["id"] for w in payload["workers"]} == {"W23", "W41", "W52"}


def test_resume_url_is_left_alone_outside_a_container(monkeypatch):
    monkeypatch.setenv("N8N_PUBLIC_BASE", "http://localhost:5678")
    monkeypatch.setenv("N8N_INTERNAL_BASE", "http://n8n:5678")
    monkeypatch.setattr(n8n_client, "_running_in_container", lambda: False)
    url = "http://localhost:5678/webhook-waiting/abc"
    assert n8n_client.rewrite_resume_url(url) == url


def test_resume_url_is_rewritten_inside_a_container(monkeypatch):
    monkeypatch.setenv("N8N_PUBLIC_BASE", "http://localhost:5678")
    monkeypatch.setenv("N8N_INTERNAL_BASE", "http://n8n:5678")
    monkeypatch.setattr(n8n_client, "_running_in_container", lambda: True)
    assert n8n_client.rewrite_resume_url("http://localhost:5678/webhook-waiting/abc") == \
        "http://n8n:5678/webhook-waiting/abc"
