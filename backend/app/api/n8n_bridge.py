"""Inbound side of the n8n bridge (Engineer 1).

Three endpoints n8n calls back on, plus two read-only helpers for debugging and the demo:

* ``POST /api/ai/n8n/enrichment/{incident_id}`` — the LLM's explanation and its chosen action
  ids. Ids are validated against ``ai/actions_catalog.py``; risk levels and the
  "needs a human" flag are taken from the catalogue, never from the request body.
* ``GET  /api/ai/n8n/verify/{incident_id}`` — did the authorised actions actually change the
  plant? Used by the workflow to decide RESOLVING vs ESCALATED.
* ``POST /api/ai/n8n/status/{incident_id}`` — the workflow's final verdict.
* ``GET  /api/ai/n8n/state`` / ``GET /api/ai/n8n/state/{incident_id}`` — what the bridge knows.

Nothing here is required for detection. If n8n never calls, incidents keep the deterministic
recommendations created at detection time.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai import n8n_client
from ai.actions_catalog import CATALOG, context_from_incident, validate_action_ids
from app.models.schemas import Action, ActionStatus, Severity
from app.services.event_bus import event_bus
from app.services.state_store import state

logger = logging.getLogger("n8n_bridge")

router = APIRouter(prefix="/ai/n8n", tags=["AI n8n Bridge"])

N8N_AGENT_ID = "recommendation_agent (n8n)"

VALID_STATUSES = {"ACTIVE", "RESOLVING", "RESOLVED", "ESCALATED", "DISMISSED"}

#: Prefix of the banner prepended to an escalated incident's explanation. The dashboard renders
#: `ai_reasoning` in full on the incident card but never renders `status`, so this banner is how
#: an escalation actually becomes visible on screen without touching the frontend.
ESCALATION_BANNER_MARKER = "!! ESCALATED:"

#: How far through its lifecycle a status is. The workflow reports RESOLVING about 15 s after
#: approval, by which time command_engine has usually already set RESOLVED. Without this the
#: incident would visibly bounce backwards from RESOLVED to RESOLVING in the dashboard.
PROGRESS_RANK = {"ACTIVE": 0, "RESOLVING": 1, "RESOLVED": 2, "DISMISSED": 2}


# ----------------------------------------------------------------- request models

class EnrichmentRequest(BaseModel):
    what: str = ""
    why: List[str] = Field(default_factory=list)
    impact: str = ""
    prediction: str = ""
    recommended_action_ids: List[str] = Field(default_factory=list)
    sources: List[Any] = Field(default_factory=list)
    resume_url: Optional[str] = None
    #: Which path produced this: the LLM agent, or the workflow's template fallback.
    produced_by: str = "n8n"
    fallback: bool = False


class StatusRequest(BaseModel):
    status: str
    note: str = ""
    produced_by: str = "n8n"


# ----------------------------------------------------------------- helpers

def _incident_or_404(incident_id: str):
    incident = state.incidents.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Unknown incident {incident_id}")
    return incident


def _log(agent_id: str, inputs: List[str], reasoning: str, decision: str, actions: List[str] = None) -> None:
    state.agent_logs.insert(0, {
        "timestamp": datetime.utcnow(),
        "agent_id": agent_id,
        "input_from": inputs,
        "reasoning": reasoning,
        "decision": decision,
        "actions_proposed": actions or [],
    })
    if len(state.agent_logs) > 100:
        state.agent_logs.pop()


def _format_sources(sources: List[Any]) -> str:
    parts: List[str] = []
    for source in sources:
        if isinstance(source, dict):
            document = source.get("document") or source.get("doc_id") or "procedure"
            section = source.get("section") or source.get("sec") or ""
            parts.append(f"{document} {section}".strip())
        else:
            parts.append(str(source))
    return ", ".join(p for p in parts if p)


def _with_escalation_banner(reasoning: str, note: str) -> str:
    """Prepend a single escalation banner, replacing any previous one."""
    body = reasoning or ""
    if body.startswith(ESCALATION_BANNER_MARKER):
        parts = body.split("\n\n", 1)
        body = parts[1] if len(parts) == 2 else ""
    return f"{ESCALATION_BANNER_MARKER} {note}\n\n{body}".rstrip()


def _existing_action_types(incident_id: str) -> set:
    return {a.action_type for a in state.actions.values() if a.incident_id == incident_id}


# ----------------------------------------------------------------- enrichment

@router.post("/enrichment/{incident_id}")
async def receive_enrichment(incident_id: str, body: EnrichmentRequest):
    incident = _incident_or_404(incident_id)

    validation = validate_action_ids(body.recommended_action_ids, incident)
    accepted = validation["accepted"]
    rejected = validation["rejected"]

    resume_url = n8n_client.register_resume_url(incident_id, body.resume_url)

    # Any accepted action the plant is not already holding becomes a real pending action,
    # with the catalogue's risk level — not the model's opinion of it.
    context = context_from_incident(incident)
    already = _existing_action_types(incident_id)
    added: List[str] = []
    added_actions: List[Action] = []
    for entry in accepted:
        if entry.action_type in already:
            continue
        action_id = f"ACT-{uuid.uuid4().hex[:4].upper()}"
        state.actions[action_id] = Action(
            id=action_id,
            incident_id=incident_id,
            action_type=entry.action_type,
            target=entry.resolve_target(context),
            reason=entry.reason,
            risk_level=entry.risk,
            status=ActionStatus.AWAITING_APPROVAL if entry.requires_confirmation else ActionStatus.AUTHORIZED,
            created_at=datetime.utcnow(),
            created_by=N8N_AGENT_ID,
        )
        added.append(action_id)
        added_actions.append(state.actions[action_id])
        already.add(entry.action_type)

    # Rebuild the explanation. Confidence stays ours: it comes from sensor fusion, not the LLM.
    todo = "; ".join(e.label.format(target=e.resolve_target(context), zone=incident.zone) for e in accepted)
    sources_text = _format_sources(body.sources)
    why_lines = " ".join(f"{i + 1}) {w}" for i, w in enumerate(body.why)) or "No corroborating detail supplied."
    provenance = (
        f"{'template fallback' if body.fallback else body.produced_by}; "
        f"{len(accepted)} of {len(body.recommended_action_ids)} proposed action(s) validated against the catalogue"
        + (f", rejected: {', '.join(r['id'] for r in rejected)}" if rejected else "")
    )

    incident.ai_reasoning = (
        f"WHAT: {body.what or incident.type.replace('_', ' ').title()}\n"
        f"WHY: {why_lines}\n"
        f"HOW CONFIDENT: {incident.confidence * 100:.0f}% from sensor fusion at detection time "
        f"(the language model does not set this figure) — a risk assessment, not a certainty.\n"
        f"WHAT IMPACT: {body.impact or 'Not supplied.'}\n"
        f"PREDICTION: {body.prediction or 'Not supplied.'}\n"
        f"WHAT TO DO: {todo or 'No validated action — the deterministic recommendations stand.'}\n"
        f"WHO APPROVES: {'Owner confirmation required for ' + ', '.join(e.id for e in accepted if e.requires_confirmation) if any(e.requires_confirmation for e in accepted) else 'No confirmation-gated action proposed.'}\n"
        f"SOURCES: {sources_text or 'none cited'}\n"
        f"— enriched by {provenance}"
    )

    n8n_client.mark_enriched(incident_id)

    _log(
        N8N_AGENT_ID,
        ["n8n:incident_response"],
        incident.ai_reasoning,
        f"Enriched {incident_id}: {len(accepted)} action(s) accepted, {len(rejected)} rejected, "
        f"{len(added)} new action(s) created."
        + (" Resume URL registered." if resume_url else " No resume URL supplied."),
        [e.id for e in accepted],
    )

    await event_bus.publish(
        event_type="INCIDENT_UPDATED",
        source="n8n:enrichment",
        data=incident.model_dump(mode="json"),
        zone=incident.zone,
        severity=incident.severity.value,
        correlation_id=incident_id,
    )

    # Announce any action this enrichment created, or the Command Center would not show it
    # until the next page refresh.
    from ai.action_events import publish_actions
    await publish_actions(added_actions, source="n8n:enrichment")

    return {
        "incident_id": incident_id,
        "accepted_action_ids": [e.id for e in accepted],
        "rejected": rejected,
        "actions_created": added,
        "resume_url_registered": bool(resume_url),
        "catalog_size": len(CATALOG),
    }


# ----------------------------------------------------------------- verification

@router.get("/verify/{incident_id}")
def verify_incident(incident_id: str):
    """Did the plant actually change?

    Two separate questions, deliberately not mixed:

    * ``details`` -- **gating**. Did every recommended action reach a terminal state, and did
      the actuators report success? That is what the copilot commanded and can be held to.
    * ``telemetry`` -- **informational**. What do the live sensors say now? In the demo the
      simulator keeps driving the scenario curve after a shutdown, so M-04 reads 8.9 bar even
      though its spindle is verified at 0 RPM. Gating on that would mark a perfectly executed
      shutdown as failed. A real plant disagreeing here matters, so it is reported rather than
      hidden -- see ``telemetry_consistent``.
    """
    incident = _incident_or_404(incident_id)
    actions = [a for a in state.actions.values() if a.incident_id == incident_id]
    checks: List[Dict[str, Any]] = []
    telemetry: List[Dict[str, Any]] = []

    completed = [a for a in actions if a.status == ActionStatus.COMPLETED]
    outstanding = [a for a in actions if a.status in (ActionStatus.AWAITING_APPROVAL,
                                                      ActionStatus.AUTHORIZED,
                                                      ActionStatus.IN_PROGRESS,
                                                      ActionStatus.PENDING)]
    checks.append({
        "check": "All recommended actions have reached a terminal state",
        "passed": not outstanding,
        "detail": f"{len(completed)} completed, {len(outstanding)} still open of {len(actions)}",
    })
    checks.append({
        "check": "At least one action was actually executed",
        "passed": bool(completed),
        "detail": ", ".join(a.action_type for a in completed) or "nothing executed",
    })
    for action in completed:
        for item in (action.verification or {}).get("checks", []):
            checks.append({
                "check": f"{action.action_type} -> {item.get('check', 'actuator check')}",
                "passed": bool(item.get("passed")),
                "detail": action.target,
            })

    # Live telemetry: informational only (see the docstring).
    if incident.type == "MACHINE_OVERHEATING":
        for asset in incident.affected_assets:
            machine = state.machines.get(asset)
            if machine is None:
                continue
            pressure = machine.parameters.get("pressure")
            rpm = machine.parameters.get("rpm")
            telemetry.append({
                "check": f"{asset} pressure back under its limit",
                "passed": bool(pressure and pressure.threshold and pressure.value < pressure.threshold),
                "detail": f"{pressure.value if pressure else '?'} bar",
            })
            telemetry.append({
                "check": f"{asset} spindle stopped",
                "passed": bool(rpm and rpm.value == 0.0),
                "detail": f"{rpm.value if rpm else '?'} RPM",
            })
    elif incident.type == "INDUSTRIAL_FIRE":
        smoke = state.sensors.get("SMOKE-B-01")
        if smoke is not None:
            telemetry.append({
                "check": "Smoke density back below the warning threshold",
                "passed": bool(smoke.threshold_warning and smoke.current_value < smoke.threshold_warning),
                "detail": f"{smoke.current_value} {smoke.unit}",
            })
        telemetry.append({
            "check": "Zone cleared of personnel",
            "passed": not [w for w in state.workers.values() if w.zone == incident.zone],
            "detail": f"{len([w for w in state.workers.values() if w.zone == incident.zone])} present",
        })
    elif incident.type == "CYBER_INTRUSION":
        isolated = [a for a in completed if a.action_type in ("ISOLATE_DEVICE", "VLAN_QUARANTINE")]
        telemetry.append({
            "check": "Offending device isolated or segment quarantined",
            "passed": bool(isolated),
            "detail": ", ".join(a.action_type for a in isolated) or "no containment action completed",
        })

    verified = bool(checks) and all(c["passed"] for c in checks)
    telemetry_consistent = all(t["passed"] for t in telemetry) if telemetry else True
    return {
        "verified": verified,
        "telemetry_consistent": telemetry_consistent,
        "status": incident.status,
        "incident_type": incident.type,
        "zone": incident.zone,
        "severity": incident.severity.value,
        "details": checks,
        "telemetry": telemetry,
        "outstanding_actions": [a.id for a in outstanding],
    }


# ----------------------------------------------------------------- final status

@router.post("/status/{incident_id}")
async def set_status(incident_id: str, body: StatusRequest):
    incident = _incident_or_404(incident_id)
    status = body.status.strip().upper()
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")

    previous = incident.status
    # ESCALATED is a workflow outcome, not an Incident.status the UI knows; keep the incident
    # ACTIVE so it stays on screen and record the escalation in the log and the reasoning.
    if status == "ESCALATED":
        incident.status = "ESCALATED"
        if incident.severity != Severity.CRITICAL:
            incident.severity = Severity.CRITICAL
        incident.ai_reasoning = _with_escalation_banner(
            incident.ai_reasoning,
            body.note or "no owner decision within the approval window — this incident needs a human now.",
        )
    elif PROGRESS_RANK.get(status, 0) < PROGRESS_RANK.get(incident.status, 0):
        _log(
            N8N_AGENT_ID,
            ["n8n:incident_response"],
            body.note or f"Workflow reported {status} for {incident_id}.",
            f"Kept status {incident.status}: the plant had already progressed past {status}.",
        )
        return {"incident_id": incident_id, "previous": previous, "status": incident.status,
                "reported": status, "applied": False}
    else:
        incident.status = status
        if status == "RESOLVED":
            incident.resolved_at = datetime.utcnow()
            zone = state.zones.get(incident.zone)
            if zone is not None:
                zone.status = "NORMAL"
                zone.risk_level = None
                if incident_id in zone.active_incidents:
                    zone.active_incidents.remove(incident_id)

    # The workflow has reached a terminal node, so its Wait node can never be resumed again.
    # Dropping the URL stops a late AUTHORIZE from POSTing at a dead execution.
    if status in ("RESOLVED", "RESOLVING", "ESCALATED", "DISMISSED"):
        n8n_client.forget_resume_url(incident_id, f"workflow reported {status}")

    _log(
        N8N_AGENT_ID,
        ["n8n:incident_response"],
        body.note or f"Workflow reported {status} for {incident_id}.",
        f"Status {previous} -> {status}"
        + (" (raised to CRITICAL and flagged on the incident card for human handling)"
           if status == "ESCALATED" else ""),
    )

    await event_bus.publish(
        event_type="INCIDENT_UPDATED",
        source="n8n:status",
        data=incident.model_dump(mode="json"),
        zone=incident.zone,
        severity=incident.severity.value,
        correlation_id=incident_id,
    )
    return {"incident_id": incident_id, "previous": previous, "status": incident.status,
            "reported": status, "applied": True}


# ----------------------------------------------------------------- RAG for the n8n agent

@router.get("/corpus")
def corpus():
    """The whole procedure corpus, one item per section.

    Used by `rag_ingestion.json` to populate n8n's Simple Vector Store. Serving it over HTTP
    instead of mounting a directory means the workflow carries no filesystem paths and works
    the same whether n8n runs on the host or in a container.
    """
    from ai.rag.rag_engine import rag_engine
    sections = [
        {
            "doc_id": section.doc_id,
            "document_title": section.doc_title,
            "citation": section.citation,
            "section": section.label,
            "category": section.category,
            "hazard": section.hazard,
            "text": section.text,
        }
        for section in rag_engine.sections
    ]
    return {
        "documents": [
            {"id": d["id"], "title": d["title"], "hazard": d.get("hazard"),
             "category": d.get("category"), "file": d.get("file")}
            for d in rag_engine.documents
        ],
        "sections": sections,
        "count": len(sections),
    }


@router.get("/rag")
def rag_search(q: str, hazard: Optional[str] = None, limit: int = 4):
    """Keyword retrieval over the corpus, exposed as a tool for the n8n AI Agent.

    This is the retrieval path that always works. n8n's Simple Vector Store is in-memory and
    declares itself experimental ("data is lost if n8n restarts, and may be cleared if
    available memory gets low"), so the agent is given both and can fall back to this one.
    """
    from ai.rag.rag_engine import rag_engine
    hits = rag_engine.search(q, hazard=hazard, limit=max(1, min(limit, 10)))
    return {
        "query": q,
        "hazard": hazard,
        "count": len(hits),
        "hits": [
            {"citation": h["citation"], "section": h["section"], "document": h["document_title"],
             "relevance": h["relevance"], "text": h["text"]}
            for h in hits
        ],
    }


# ----------------------------------------------------------------- introspection

@router.get("/state")
def bridge_state():
    return {
        "enabled": n8n_client.enabled(),
        "incident_webhook_url": n8n_client.incident_webhook_url(),
        "backend_base_url_for_n8n": n8n_client.backend_base_for_n8n(),
        "timeout_seconds": n8n_client.timeout_seconds(),
        "tracked_resume_urls": list(n8n_client.RESUME_URLS.keys()),
        "last_exchange": n8n_client.LAST_EXCHANGE,
        "catalog": sorted(CATALOG.keys()),
    }


@router.get("/state/{incident_id}")
def bridge_state_for_incident(incident_id: str):
    _incident_or_404(incident_id)
    return {
        "incident_id": incident_id,
        "resume_url": n8n_client.get_resume_url(incident_id),
        "last_exchange": n8n_client.LAST_EXCHANGE.get(incident_id),
    }
