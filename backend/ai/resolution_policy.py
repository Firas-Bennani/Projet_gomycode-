"""When is an incident actually over?

The original rule was "every action for the incident reached a terminal state". At GATE 1 that
proved wrong in both directions: an incident stayed open while an optional cooling action sat
unapproved, and the owner had to clear actions that the shutdown had already made pointless.

The rule implemented here:

**An incident resolves when every _hazard-resolving_ action recommended for it has COMPLETED
and the hazard is measurably receding.** Remaining pending actions are then cancelled as
superseded, with a reason in the agent log — never silently dropped.

Hazard-resolving actions are declared in `ai/actions_catalog.py` (`resolves_hazard`):
`STOP_MACHINE` for overheating, `ACTIVATE_SUPPRESSION` for fire, `ISOLATE_DEVICE` for an
intrusion. `EVACUATE_ZONE`, `ACTIVATE_COOLING`, `TRIGGER_ALARM`, `CLOSE_DOOR` and
`VLAN_QUARANTINE` protect people or limit spread but do not remove the cause, so they never
by themselves resolve an incident.

The old "all actions terminal" rule is kept as a fallback, so an incident whose recommended
actions contain no resolver (or whose resolver was cancelled) still closes.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from ai import clock
from app.models.schemas import ActionStatus

logger = logging.getLogger("resolution_policy")

TERMINAL = (ActionStatus.COMPLETED, ActionStatus.CANCELLED)


def resolving_action_types() -> set:
    from ai.actions_catalog import CATALOG
    return {entry.action_type for entry in CATALOG.values() if entry.resolves_hazard}


@dataclass
class Decision:
    resolve: bool = False
    reason: str = ""
    rule: str = ""
    receding: bool = True
    superseded: List = field(default_factory=list)


def hazard_receding(incident) -> tuple:
    """Is the measured hazard going the right way? Returns (receding, detail)."""
    from app.services.state_store import state

    if incident.type == "MACHINE_OVERHEATING":
        details = []
        receding = True
        for asset in incident.affected_assets:
            machine = state.machines.get(asset)
            if machine is None:
                continue
            pressure = machine.parameters.get("pressure")
            temperature = machine.parameters.get("temperature")
            if pressure is not None and pressure.threshold and pressure.value >= pressure.threshold:
                receding = False
                details.append(f"{asset} pressure still {pressure.value:.2f} bar")
            if temperature is not None and temperature.threshold and temperature.value >= temperature.threshold:
                receding = False
                details.append(f"{asset} temperature still {temperature.value:.1f}°C")
        return receding, ("; ".join(details) or "machine parameters back inside limits")

    if incident.type == "INDUSTRIAL_FIRE":
        for sensor in state.sensors.values():
            if sensor.type == "smoke" and sensor.zone == incident.zone:
                if sensor.threshold_warning and sensor.current_value >= sensor.threshold_warning:
                    return False, f"{sensor.id} still {sensor.current_value:.1f} {sensor.unit}"
        return True, "smoke back below its warning level"

    # Containment is the resolution for an intrusion; there is no analogue reading to fall.
    return True, "no continuous measurement for this hazard type"


def evaluate(incident, actions: List) -> Decision:
    resolvers = [a for a in actions if a.action_type in resolving_action_types()]
    completed_resolvers = [a for a in resolvers if a.status == ActionStatus.COMPLETED]
    open_actions = [a for a in actions if a.status not in TERMINAL]
    # Only actions nobody has committed to yet may be superseded. An action the owner already
    # authorised is in flight at an actuator, so it is left to finish and report.
    supersedable = [a for a in actions
                    if a.status in (ActionStatus.AWAITING_APPROVAL, ActionStatus.PENDING)]

    # Rule 1 — the hazard's own remedy has been carried out.
    if resolvers and len(completed_resolvers) == len(resolvers):
        receding, detail = hazard_receding(incident)
        if not receding:
            return Decision(
                resolve=False, receding=False, rule="hazard_resolver_completed",
                reason=f"{', '.join(a.action_type for a in completed_resolvers)} completed but the "
                       f"hazard is not receding yet ({detail}).",
            )
        return Decision(
            resolve=True, receding=True, rule="hazard_resolver_completed",
            reason=f"{', '.join(a.action_type for a in completed_resolvers)} completed and the hazard "
                   f"is receding ({detail}).",
            superseded=supersedable,
        )

    # Rule 2 — fallback: nothing left to do at all.
    if actions and not open_actions:
        return Decision(
            resolve=True, rule="all_actions_terminal",
            reason=f"all {len(actions)} recommended action(s) reached a terminal state.",
        )

    return Decision(
        resolve=False, rule="waiting",
        reason=f"{len(open_actions)} action(s) still open"
               + (f", including {len([a for a in resolvers if a.status not in TERMINAL])} hazard-resolving"
                  if resolvers else ""),
    )


def _log(reasoning: str, decision: str) -> None:
    from app.services.state_store import state
    state.agent_logs.insert(0, {
        "timestamp": clock.now(),
        "agent_id": "recommendation_agent",
        "input_from": ["command_engine"],
        "reasoning": reasoning,
        "decision": decision,
        "actions_proposed": [],
    })
    if len(state.agent_logs) > 100:
        state.agent_logs.pop()


async def evaluate_incident_after(action) -> Optional[Decision]:
    """Called by ``command_engine`` whenever an action reaches a terminal state.

    Resolves the incident when the policy above says so, cancels superseded actions, restores
    the zone, and broadcasts everything the dashboard needs.
    """
    from app.services.event_bus import event_bus
    from app.services.state_store import state
    from ai.action_events import publish_action

    incident_id = getattr(action, "incident_id", None)
    if not incident_id or incident_id not in state.incidents:
        return None
    incident = state.incidents[incident_id]
    if incident.status in ("RESOLVED", "DISMISSED"):
        return None

    actions = [a for a in state.actions.values() if a.incident_id == incident_id]
    decision = evaluate(incident, actions)

    if not decision.resolve:
        if decision.rule == "hazard_resolver_completed":
            _log(decision.reason, "HOLD: keeping the incident open until the readings fall.")
        return decision

    # Cancel what the remedy made unnecessary, so the owner is not left clearing stale cards.
    for superseded in decision.superseded:
        superseded.status = ActionStatus.CANCELLED
        await publish_action(superseded, source="ai:resolution_policy")

    incident.status = "RESOLVED"
    incident.resolved_at = clock.now()

    zone = state.zones.get(incident.zone)
    if zone is not None:
        zone.status = "NORMAL"
        zone.risk_level = None
        if incident_id in zone.active_incidents:
            zone.active_incidents.remove(incident_id)

    for risk in state.risks.values():
        if risk.type == incident.type and risk.zone == incident.zone and risk.status == "ACTIVE":
            risk.status = "MITIGATED"

    superseded_note = (
        f" {len(decision.superseded)} pending action(s) cancelled as superseded: "
        f"{', '.join(a.action_type for a in decision.superseded)}."
        if decision.superseded else ""
    )
    _log(
        f"{incident_id} resolved by the '{decision.rule}' rule: {decision.reason}{superseded_note}",
        f"RESOLVED {incident_id}.",
    )

    await event_bus.publish(
        event_type="INCIDENT_UPDATED",
        source="ai:resolution_policy",
        data=incident.model_dump(mode="json"),
        zone=incident.zone,
        severity=incident.severity.value,
        correlation_id=incident_id,
    )
    logger.info("Resolved %s via %s", incident_id, decision.rule)
    return decision
