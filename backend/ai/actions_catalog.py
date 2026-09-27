"""The catalogue of actions the copilot is allowed to propose.

Why a catalogue exists: from Step 5 an LLM writes the recommendation. An LLM must never be
able to invent an action, and must never be able to decide how dangerous one is. So it only
ever returns **ids from this file**, and the risk level and the "needs a human" flag are read
from here, never from the model's output.

Every ``action_type`` below is one ``backend/app/services/command_engine.py`` already knows
how to execute, so nothing here can produce an action the plant cannot carry out.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.schemas import RecommendedAction, RiskLevel

# Incident types the catalogue knows about.
FIRE = "INDUSTRIAL_FIRE"
OVERHEAT = "MACHINE_OVERHEATING"
CYBER = "CYBER_INTRUSION"
WEATHER = "SEVERE_WEATHER_RISK"
AGENT = "AGENT_COMPROMISE"

# What the action's target is derived from.
TARGET_MACHINE = "machine"
TARGET_ZONE = "zone"
TARGET_DEVICE = "device"
TARGET_ZONE_ASSET = "zone_asset"   # a fixture belonging to the zone, e.g. ALARM-ZONE-B
TARGET_FIXED = "fixed"


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    label: str
    action_type: str
    risk: RiskLevel
    #: True = execute without asking. Only ever LOW risk actions.
    auto: bool
    #: True = an owner must press AUTHORIZE first. Always the opposite of ``auto``.
    requires_confirmation: bool
    target_kind: str
    reason: str
    #: Incident types this action may be proposed for.
    hazards: List[str] = field(default_factory=list)
    target_pattern: Optional[str] = None
    #: True when carrying this action out removes the *cause* of the hazard, so the incident
    #: can be resolved once it completes (see ai/resolution_policy.py). Actions that protect
    #: people or limit spread without removing the cause are False.
    resolves_hazard: bool = False

    def resolve_target(self, context: Dict[str, Any]) -> str:
        zone = context.get("zone", "ZONE_B")
        zone_letter = zone.split("_")[-1]
        if self.target_kind == TARGET_MACHINE:
            return context.get("machine_id") or "M-04"
        if self.target_kind == TARGET_ZONE:
            return zone
        if self.target_kind == TARGET_DEVICE:
            return context.get("device") or "UNKNOWN-DEVICE-07"
        if self.target_kind == TARGET_ZONE_ASSET and self.target_pattern:
            return self.target_pattern.format(zone=zone, zone_dash=zone.replace("_", "-"), letter=zone_letter)
        return self.target_pattern or "UNKNOWN"

    def to_recommended_action(self, context: Dict[str, Any]) -> RecommendedAction:
        target = self.resolve_target(context)
        return RecommendedAction(
            action=self.label.format(target=target, zone=context.get("zone", "ZONE_B")),
            action_type=self.action_type,
            target=target,
            risk_level=self.risk,
            requires_confirmation=self.requires_confirmation,
            reason=self.reason,
        )


CATALOG: Dict[str, CatalogEntry] = {
    entry.id: entry
    for entry in [
        # ---- machine ---------------------------------------------------------------
        CatalogEntry(
            id="stop_machine",
            label="Emergency shutdown of machine {target}",
            action_type="STOP_MACHINE",
            risk=RiskLevel.HIGH,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_MACHINE,
            reason="Prevent hydraulic rupture and spindle seizure; stops production.",
            hazards=[OVERHEAT, FIRE],
            resolves_hazard=True,
        ),
        CatalogEntry(
            id="activate_cooling",
            label="Engage auxiliary cooling heat exchanger pump",
            action_type="ACTIVATE_COOLING",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_FIXED,
            target_pattern="PUMP-COOL-02",
            reason="Bring the asset back below its thermal limit.",
            hazards=[OVERHEAT, FIRE],
        ),
        # ---- people ----------------------------------------------------------------
        CatalogEntry(
            id="evacuate_zone",
            label="Evacuate personnel from {target}",
            action_type="EVACUATE_ZONE",
            risk=RiskLevel.HIGH,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_ZONE,
            reason="Remove people from thermal radiation, fragment and smoke exposure.",
            hazards=[OVERHEAT, FIRE],
        ),
        CatalogEntry(
            id="trigger_alarm",
            label="Trigger acoustic and strobe alarm in {zone}",
            action_type="TRIGGER_ALARM",
            risk=RiskLevel.LOW,
            auto=True,
            requires_confirmation=False,
            target_kind=TARGET_ZONE_ASSET,
            target_pattern="ALARM-{zone_dash}",
            reason="Audible safety warning for on-site personnel.",
            hazards=[FIRE, OVERHEAT],
        ),
        # ---- containment -----------------------------------------------------------
        CatalogEntry(
            id="close_door",
            label="Close fire containment doors in {zone}",
            action_type="CLOSE_DOOR",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_ZONE_ASSET,
            target_pattern="DOOR-{letter}-01",
            reason="Contain combustion aerosols and smoke propagation.",
            hazards=[FIRE],
        ),
        CatalogEntry(
            id="activate_suppression",
            label="Activate clean-agent suppression in {zone}",
            action_type="ACTIVATE_SUPPRESSION",
            risk=RiskLevel.HIGH,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_ZONE_ASSET,
            target_pattern="SUPPRESSION-{letter}-01",
            reason="Extinguish the combustion source once personnel are clear.",
            hazards=[FIRE],
            resolves_hazard=True,
        ),
        # ---- severe weather: acted on BEFORE the event, which is the point ----------
        CatalogEntry(
            id="load_shedding",
            label="Shed non-critical electrical load and derate machines to 60%",
            action_type="LOAD_SHEDDING",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_ZONE,
            reason="Reduce the electrical load exposed to a surge, and lower the energy stored in "
                   "the plant before the front arrives.",
            hazards=[WEATHER],
            resolves_hazard=True,
        ),
        CatalogEntry(
            id="reduce_pressure_setpoint",
            label="Lower the compressor pressure setpoint on {target} to 6.5 bar",
            action_type="REDUCE_PRESSURE_SETPOINT",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_MACHINE,
            reason="Widen the margin to the 8.0 bar limit so a surge-driven excursion cannot "
                   "reach it.",
            hazards=[WEATHER],
            resolves_hazard=True,
        ),
        CatalogEntry(
            id="switch_to_ups",
            label="Move PLCs and critical controllers to UPS and verify generator readiness",
            action_type="SWITCH_TO_UPS",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_FIXED,
            target_pattern="UPS-MAIN-01",
            reason="Keep the control layer alive through a transient or an outage.",
            hazards=[WEATHER],
        ),
        CatalogEntry(
            id="reinforce_electrical_crew",
            label="Call the on-call electrical crew to {zone}",
            action_type="REINFORCE_ELECTRICAL_CREW",
            risk=RiskLevel.LOW,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_ZONE,
            reason="Shift reinforcement so a fault during the storm is handled in minutes.",
            hazards=[WEATHER],
        ),
        # ---- the copilot defending itself -------------------------------------------
        CatalogEntry(
            id="quarantine_agent",
            label="Quarantine the impersonated agent on the internal message bus",
            action_type="QUARANTINE_AGENT",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_FIXED,
            target_pattern="AGENT-BUS",
            reason="Stop accepting messages that claim to come from the impersonated agent until "
                   "the bus is verified, so forged evidence cannot reach the fusion.",
            hazards=[AGENT],
            resolves_hazard=True,
        ),
        CatalogEntry(
            id="require_human_authorisation",
            label="Suspend autonomous execution until the message bus is verified",
            action_type="REQUIRE_HUMAN_AUTHORISATION",
            risk=RiskLevel.LOW,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_FIXED,
            target_pattern="COPILOT-AUTONOMY",
            reason="While the reasoning layer's inputs are in doubt, no action should execute "
                   "without a person approving it.",
            hazards=[AGENT],
        ),
        # ---- cyber -----------------------------------------------------------------
        CatalogEntry(
            id="isolate_device",
            label="Isolate device {target} from the OT network",
            action_type="ISOLATE_DEVICE",
            risk=RiskLevel.MEDIUM,
            auto=False,
            requires_confirmation=True,
            target_kind=TARGET_DEVICE,
            reason="Cut an unregistered device off the industrial fieldbus.",
            hazards=[CYBER],
            resolves_hazard=True,
        ),
        CatalogEntry(
            id="vlan_quarantine",
            label="Engage OT VLAN quarantine mode",
            action_type="VLAN_QUARANTINE",
            risk=RiskLevel.LOW,
            auto=True,
            requires_confirmation=False,
            target_kind=TARGET_FIXED,
            target_pattern="SWITCH-CORE-01",
            reason="Automatic perimeter containment of the affected segment.",
            hazards=[CYBER],
        ),
    ]
}


def context_from_incident(incident) -> Dict[str, Any]:
    """Everything the catalogue needs to resolve targets, taken from an Incident."""
    machine_id = next((a for a in incident.affected_assets if str(a).startswith("M-")), None)
    device = next((a for a in incident.affected_assets if "DEVICE" in str(a).upper()), None)
    return {"zone": incident.zone, "machine_id": machine_id, "device": device}


def allowed_actions_for(incident) -> List[Dict[str, Any]]:
    """The menu handed to n8n: ids the LLM may choose from, with resolved targets.

    Risk and ``requires_confirmation`` are included so the workflow can display them, but
    the backend re-reads them from the catalogue when it builds the real action — the model
    cannot downgrade a HIGH risk action into an automatic one.
    """
    context = context_from_incident(incident)
    return [
        {
            "id": entry.id,
            "label": entry.label.format(target=entry.resolve_target(context), zone=incident.zone),
            "action_type": entry.action_type,
            "target": entry.resolve_target(context),
            "risk": entry.risk.value,
            "requires_confirmation": entry.requires_confirmation,
            "reason": entry.reason,
        }
        for entry in CATALOG.values()
        if incident.type in entry.hazards
    ]


def validate_action_ids(action_ids: List[str], incident) -> Dict[str, Any]:
    """Split proposed ids into accepted and rejected, with a reason for each rejection."""
    accepted: List[CatalogEntry] = []
    rejected: List[Dict[str, str]] = []
    seen = set()
    for raw in action_ids or []:
        action_id = str(raw).strip().lower()
        if action_id in seen:
            continue
        seen.add(action_id)
        entry = CATALOG.get(action_id)
        if entry is None:
            rejected.append({"id": action_id, "why": "not in the action catalogue"})
        elif incident.type not in entry.hazards:
            rejected.append({"id": action_id, "why": f"not permitted for {incident.type}"})
        else:
            accepted.append(entry)
    return {"accepted": accepted, "rejected": rejected}
