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

from app.api.auth import issue_token

# No `with` block: that would run the lifespan and start the background simulator.
# The API requires authentication now, so the client carries an owner token — these tests are
# about the bridge, and the auth rules themselves are covered in test_auth.py.
_OWNER_TOKEN = issue_token("firas", "owner")["token"]
client = TestClient(app, headers={"Authorization": f"Bearer {_OWNER_TOKEN}"})


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
    """Updated after GATE 1: Firas asked for ESCALATED to be the visible status.

    DetectionsView lists every incident regardless of status, so the card stays on screen; what
    changes is that it no longer counts towards "ACTIVE ALERTS" (noted for Engineers 3/4 in
    PROPOSED_CHANGES_FOR_TEAM.md) and the banner makes the escalation readable.
    """
    incident = seed_incident()
    incident.severity = Severity.WARNING
    body = client.post("/api/ai/n8n/status/INC-TEST", json={"status": "ESCALATED", "note": "no decision"}).json()
    assert body["reported"] == "ESCALATED"
    assert incident.status == "ESCALATED"
    assert incident.severity == Severity.CRITICAL
    assert incident.ai_reasoning.startswith("!! ESCALATED:")


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


# --------------------------------------------------------------------- enrichment durability

@pytest.mark.asyncio
async def test_escalation_does_not_erase_an_enriched_explanation():
    """Regression: the orchestrator overwrote n8n's explanation on the next severity change.

    In the demo the LLM's reasoning appeared and then vanished a second later, replaced by the
    deterministic template text. An escalation must now add a line, not replace the body.
    """
    from ai.orchestrator import AgentOrchestrator

    incident = seed_incident()
    incident.severity = Severity.WARNING
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "Compressor overheating", "why": ["pressure over the limit"],
        "recommended_action_ids": ["stop_machine"], "produced_by": "gemini-via-n8n",
    })
    enriched_text = incident.ai_reasoning
    assert "gemini-via-n8n" in enriched_text

    orchestrator = AgentOrchestrator()
    await orchestrator._escalate(
        incident,
        {
            "type": "MACHINE_OVERHEATING", "zone": "ZONE_B",
            "severity": Severity.CRITICAL, "confidence": 0.98,
            "evidence": [{"source": "machine_agent", "detail": "pressure 8.9 bar"}],
            "ai_reasoning": "DETERMINISTIC TEMPLATE TEXT",
            "affected_workers": ["W23"],
        },
        [{"agent_id": "machine_agent"}],
    )

    assert incident.severity == Severity.CRITICAL, "severity must still escalate"
    assert incident.confidence == 0.98
    assert "DETERMINISTIC TEMPLATE TEXT" not in incident.ai_reasoning
    assert "gemini-via-n8n" in incident.ai_reasoning, "the enriched explanation must survive"
    assert "re-assessed since enrichment" in incident.ai_reasoning
    assert incident.ai_reasoning.count("re-assessed since enrichment") == 1


@pytest.mark.asyncio
async def test_escalation_note_is_refreshed_not_stacked():
    from ai.orchestrator import AgentOrchestrator

    incident = seed_incident()
    incident.severity = Severity.WARNING
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={"what": "x", "produced_by": "n8n"})
    orchestrator = AgentOrchestrator()
    base = {
        "type": "MACHINE_OVERHEATING", "zone": "ZONE_B",
        "evidence": [], "ai_reasoning": "TEMPLATE", "affected_workers": [],
    }
    await orchestrator._escalate(incident, {**base, "severity": Severity.HIGH, "confidence": 0.90},
                                 [{"agent_id": "machine_agent"}])
    await orchestrator._escalate(incident, {**base, "severity": Severity.CRITICAL, "confidence": 0.97},
                                 [{"agent_id": "machine_agent"}])
    assert incident.ai_reasoning.count("re-assessed since enrichment") == 1
    assert "0.97" in incident.ai_reasoning


def test_escalation_still_replaces_a_non_enriched_explanation():
    """Without n8n in the loop the old behaviour is correct: refresh the template text."""
    from ai.orchestrator import AgentOrchestrator
    import asyncio

    incident = seed_incident()
    incident.severity = Severity.WARNING
    orchestrator = AgentOrchestrator()
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        orchestrator._escalate(
            incident,
            {"type": "MACHINE_OVERHEATING", "zone": "ZONE_B", "severity": Severity.CRITICAL,
             "confidence": 0.98, "evidence": [], "ai_reasoning": "FRESH TEMPLATE TEXT",
             "affected_workers": []},
            [{"agent_id": "machine_agent"}],
        )
    )
    assert incident.ai_reasoning == "FRESH TEMPLATE TEXT"


# --------------------------------------------------------------------- GATE 1: timeout path

def test_wait_timeout_escalates_and_is_visible_on_the_incident_card():
    """GATE 1 issue 2: the Wait node's window expired before the owner could authorise.

    The workflow then posts ESCALATED. The dashboard renders `ai_reasoning` on the incident
    card but never renders `status`, so the escalation has to be written into the explanation
    to be visible at all.
    """
    incident = seed_incident()
    incident.severity = Severity.WARNING
    original = incident.ai_reasoning

    response = client.post("/api/ai/n8n/status/INC-TEST", json={
        "status": "ESCALATED",
        "note": "No owner decision in 10 min -> escalated. Nobody acted on the recommendation "
                "inside the approval window, so this incident needs a human now.",
    })
    assert response.status_code == 200
    assert response.json()["reported"] == "ESCALATED"

    assert incident.status == "ESCALATED"
    assert incident.severity == Severity.CRITICAL, "an unattended incident must not stay at WARNING"
    assert incident.ai_reasoning.startswith("!! ESCALATED:")
    assert "No owner decision in 10 min" in incident.ai_reasoning
    assert original in incident.ai_reasoning, "the original explanation must be kept below the banner"

    log = next(l for l in state.agent_logs if l["agent_id"] == "recommendation_agent (n8n)")
    assert "ESCALATED" in log["decision"]
    assert "No owner decision in 10 min" in log["reasoning"]


def test_escalation_banner_is_replaced_not_stacked():
    incident = seed_incident()
    for _ in range(3):
        client.post("/api/ai/n8n/status/INC-TEST", json={"status": "ESCALATED", "note": "no decision"})
    assert incident.ai_reasoning.count("!! ESCALATED:") == 1


def test_a_final_status_drops_the_resume_url():
    """A finished execution cannot be resumed, so the backend must stop holding its URL."""
    seed_incident()
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "x", "resume_url": "http://localhost:5678/webhook-waiting/42",
    })
    assert n8n_client.get_resume_url("INC-TEST") == "http://localhost:5678/webhook-waiting/42"

    client.post("/api/ai/n8n/status/INC-TEST", json={"status": "ESCALATED", "note": "timed out"})
    assert n8n_client.get_resume_url("INC-TEST") is None, \
        "after a final status there is nothing left to resume"


@pytest.mark.asyncio
async def test_authorizing_after_a_timeout_does_not_post_to_a_dead_execution():
    """GATE 1 issue 2, third part: the owner authorised 8 minutes late.

    The action must still execute normally, and the backend must not fire a decision at an
    execution that has already finished.
    """
    from app.services.command_engine import command_engine

    seed_incident()
    action = seed_action("STOP_MACHINE", ActionStatus.AWAITING_APPROVAL)
    client.post("/api/ai/n8n/enrichment/INC-TEST", json={
        "what": "x", "resume_url": "http://127.0.0.1:1/webhook-waiting/42",
    })
    # The workflow times out and reports ESCALATED, which drops the resume URL.
    client.post("/api/ai/n8n/status/INC-TEST", json={"status": "ESCALATED", "note": "timed out"})

    calls = []

    async def _fail_if_called(*args, **kwargs):
        calls.append(args)
        return False

    import ai.n8n_client as client_module
    original = client_module.send_decision
    client_module.send_decision = _fail_if_called
    try:
        result = await command_engine.authorize_action(action.id, authorized_by="owner_01")
    finally:
        client_module.send_decision = original

    assert result is not None, "the action must still be authorised"
    assert action.status == ActionStatus.AUTHORIZED
    assert calls == [], "no decision may be sent to a finished n8n execution"


@pytest.mark.asyncio
async def test_a_dead_resume_url_is_reported_cleanly_not_as_an_error():
    """If we do try a stale URL, a 404/410 is a normal outcome, logged and forgotten."""
    seed_incident()
    n8n_client.register_resume_url("INC-TEST", "http://localhost:5678/webhook-waiting/stale")

    class _Response:
        status_code = 404

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None):
            return _Response()

    import httpx
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **k: _Client()
    try:
        assert await n8n_client.send_decision("INC-TEST", "approve", "ACT-TEST", "owner_01") is False
    finally:
        httpx.AsyncClient = original

    assert n8n_client.get_resume_url("INC-TEST") is None
    assert n8n_client.LAST_EXCHANGE["INC-TEST"]["status"] == "RESUME_URL_DROPPED"
    assert "already finished" in n8n_client.LAST_EXCHANGE["INC-TEST"]["detail"]


# --------------------------------------------------------------------- LLM answer cache

@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Point the LLM cache at a temp file.

    Without this the tests operate on the REAL cache at backend/ai/data/llm_cache.json and their
    cleanup deletes it — which is exactly what happened: a test run wiped a warmed Gemini answer
    that had taken several quota windows to capture.
    """
    from ai import llm_cache
    monkeypatch.setattr(llm_cache, "CACHE_PATH", tmp_path / "llm_cache.json")
    llm_cache.reset_memory()
    yield llm_cache
    llm_cache.reset_memory()


def test_a_live_llm_answer_is_cached_and_then_replayed_when_the_model_fails(isolated_cache):
    """live -> cached -> template. Measured need: 1 in 5 live Gemini attempts succeeded."""
    llm_cache = isolated_cache
    if True:
        seed_incident()
        live = client.post("/api/ai/n8n/enrichment/INC-TEST", json={
            "what": "Hydraulic overpressure developing on M-04 in ZONE_B",
            "why": ["M-04 pressure 8.32 bar over its 8.0 bar limit"],
            "impact": "3 people exposed in ZONE_B",
            "prediction": "Risk of hydraulic line rupture",
            "recommended_action_ids": ["stop_machine", "evacuate_zone"],
            "sources": [{"document": "SOP-M04", "section": "4.2"}],
            "produced_by": "models/gemini-3.8-flash via n8n AI Agent",
            "fallback": False,
        }).json()
        assert live["llm_path"] == "live"
        assert llm_cache.recall("MACHINE_OVERHEATING") is not None

        # Now the model fails: the workflow's template path reports fallback=True.
        seed_incident()
        replayed = client.post("/api/ai/n8n/enrichment/INC-TEST", json={
            "what": "machine overheating affecting M-04 in ZONE_B",
            "why": ["machine_agent: Warning threshold on M-04"],
            "recommended_action_ids": ["stop_machine", "evacuate_zone", "activate_cooling"],
            "produced_by": "n8n template (deterministic, no LLM)",
            "fallback": True,
        }).json()

        assert replayed["llm_path"] == "cached"
        assert "cached" in replayed["replayed_from"]

        reasoning = state.incidents["INC-TEST"].ai_reasoning
        assert "Hydraulic overpressure developing on M-04" in reasoning, "the LLM wording returns"
        assert "SOP-M04 4.2" in reasoning, "so do its citations"
        assert "cached models/gemini-3.8-flash" in reasoning
        assert "answer from" in reasoning, "a replayed answer must be dated"


def test_the_template_is_used_when_nothing_is_cached(isolated_cache):
    if True:
        seed_incident()
        body = client.post("/api/ai/n8n/enrichment/INC-TEST", json={
            "what": "machine overheating affecting M-04 in ZONE_B",
            "why": ["machine_agent: pressure over the warning level"],
            "recommended_action_ids": ["stop_machine"],
            "produced_by": "n8n template (deterministic, no LLM)",
            "fallback": True,
        }).json()
        assert body["llm_path"] == "template"
        assert body["replayed_from"] is None
        assert "template fallback" in state.incidents["INC-TEST"].ai_reasoning


def test_a_cached_answer_cannot_smuggle_in_an_invalid_action(isolated_cache):
    """A stale cached id is re-validated against the catalogue like any other."""
    llm_cache = isolated_cache
    if True:
        llm_cache.remember("MACHINE_OVERHEATING", {
            # Long enough to pass is_worth_caching(): a placeholder is deliberately refused.
            "what": "Hydraulic overpressure developing on M-04 in ZONE_B",
            "why": ["cached why"], "impact": "cached impact",
            "prediction": "cached prediction",
            "recommended_action_ids": ["stop_machine", "launch_missiles", "close_door"],
            "sources": [],
        }, "models/gemini-3.8-flash")

        seed_incident()
        body = client.post("/api/ai/n8n/enrichment/INC-TEST", json={
            "what": "template", "recommended_action_ids": ["stop_machine"],
            "produced_by": "n8n template", "fallback": True,
        }).json()

        assert body["llm_path"] == "cached"
        assert body["accepted_action_ids"] == ["stop_machine"]
        rejected = {r["id"] for r in body["rejected"]}
        assert "launch_missiles" in rejected, "not in the catalogue"
        assert "close_door" in rejected, "not permitted for MACHINE_OVERHEATING"


def test_a_cached_answer_never_carries_a_confidence_or_severity():
    """Only wording and action ids are replayable; the numbers stay ours."""
    from ai import llm_cache
    assert "confidence" not in llm_cache.REPLAYABLE
    assert "severity" not in llm_cache.REPLAYABLE
    assert set(llm_cache.REPLAYABLE) == {
        "what", "why", "impact", "prediction", "recommended_action_ids", "sources"}


def test_a_corrupt_cache_file_does_not_break_enrichment(isolated_cache):
    llm_cache = isolated_cache
    if True:
        llm_cache.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        llm_cache.CACHE_PATH.write_text("{ this is not json", encoding="utf-8")
        llm_cache.reset_memory()
        assert llm_cache.recall("MACHINE_OVERHEATING") is None

        seed_incident()
        body = client.post("/api/ai/n8n/enrichment/INC-TEST", json={
            "what": "template", "recommended_action_ids": ["stop_machine"],
            "produced_by": "n8n template", "fallback": True,
        }).json()
        assert body["llm_path"] == "template"


def test_a_threadbare_answer_is_not_cached(isolated_cache):
    """A placeholder cached now is a placeholder replayed on stage.

    This is not hypothetical: a test posting {"what": "x"} once overwrote a warmed Gemini answer
    in the real cache file before the suite was isolated from it.
    """
    llm_cache = isolated_cache
    llm_cache.remember("MACHINE_OVERHEATING", {"what": "x", "why": [], "sources": []}, "n8n")
    assert llm_cache.recall("MACHINE_OVERHEATING") is None

    llm_cache.remember("MACHINE_OVERHEATING", {
        "what": "Hydraulic overpressure developing on M-04 in ZONE_B",
        "why": ["pressure 8.32 bar over its 8.0 bar limit"],
        "recommended_action_ids": ["stop_machine"], "sources": [],
    }, "models/gemini-3.8-flash")
    assert llm_cache.recall("MACHINE_OVERHEATING") is not None
