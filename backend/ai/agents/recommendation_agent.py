"""Strategic recommendation agent.

Rewritten in Step 1 to fix the correlation bug. Three things changed:

1. It now receives the **whole per-zone observation window** (see
   ``ai/observation_window.py``), not the observations of a single event, so temperature
   evidence and machine evidence can corroborate each other.
2. **Rule precedence with required evidence.** ``INDUSTRIAL_FIRE`` requires smoke plus at
   least two corroborating signals; ``MACHINE_OVERHEATING`` requires machine evidence.
   If neither is satisfied the agent returns ``None`` and records *why* — it never falls
   through to a guess.
3. **No hardcoded confidences or invented readings.** Confidence is fused across
   independent sources and the reasoning text quotes the values the sensors actually
   reported. (The fusion here is provisional; Step 7 moves it into ``ai/risk_engine.py``
   and adds per-sensor trust.)
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from ai import clock
from ai.agents.base_agent import BaseAgent
from ai.rag.rag_engine import rag_engine
from app.models.schemas import RecommendedAction, RiskLevel, Severity

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}
SEVERITY_ENUM = {
    "INFO": Severity.INFO,
    "WARNING": Severity.WARNING,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}

# Per-source likelihood that the hazard is real, given that source alone.
# Provisional values, replaced by the risk engine in Step 7.
SOURCE_CONFIDENCE = {"WARNING": 0.60, "HIGH": 0.80, "CRITICAL": 0.85}

MAX_CONFIDENCE = 0.99


def _rank(severity: str) -> int:
    return SEVERITY_RANK.get(str(severity).upper(), 0)


def max_severity(observations: List[Dict[str, Any]], floor: str = "WARNING") -> str:
    best = floor
    for obs in observations:
        if _rank(obs.get("severity", "INFO")) > _rank(best):
            best = str(obs.get("severity")).upper()
    return best


def fuse_confidence(observations: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """Noisy-OR fusion over independent hazard sources.

    ``confidence = 1 - Π(1 - cᵢ)``: two weak but independent sensors agreeing is stronger
    evidence than either alone, and no single source can reach certainty.
    """
    product = 1.0
    contributions: List[str] = []
    for obs in observations:
        severity = str(obs.get("severity", "INFO")).upper()
        c = SOURCE_CONFIDENCE.get(severity)
        if c is None:
            continue
        product *= (1.0 - c)
        label = obs.get("sensor_id") or obs.get("machine_id") or obs.get("device") or obs.get("agent_id")
        contributions.append(f"{label} ({severity}, {c:.2f})")
    if not contributions:
        return 0.0, []
    return round(min(1.0 - product, MAX_CONFIDENCE), 3), contributions


class RecommendationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="recommendation_agent",
            name="Recommendation & Strategic Intelligence Agent"
        )
        self.active_hypotheses: Dict[str, Any] = {}
        #: Why the last synthesis produced no incident — surfaced in the agent log.
        self.last_gap_reason: Optional[str] = None

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # This agent processes multi-agent observations, not raw events.
        return None

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _workers_in(zone: str, worker_obs: Optional[Dict[str, Any]]) -> List[str]:
        """Workers actually present in the zone (state store first, agent report second)."""
        if worker_obs and worker_obs.get("affected_workers"):
            return list(worker_obs["affected_workers"])
        try:
            from app.services.state_store import state
            return [w.id for w in state.workers.values()
                    if w.zone == zone and w.status != "OFF_SITE"]
        except Exception:
            return []

    @staticmethod
    def _evidence(observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "source": obs.get("agent_id", "unknown"),
                "detail": obs.get("observation", ""),
                "timestamp": clock.now(),
            }
            for obs in observations
        ]

    def _reasoning(
        self,
        what: str,
        why: List[str],
        confidence: float,
        contributions: List[str],
        impact: str,
        todo: str,
        approver: str,
    ) -> str:
        why_text = " ".join(why) if why else "No corroborating detail recorded."
        contrib_text = ", ".join(contributions) if contributions else "no scored source"
        return (
            f"WHAT: {what}\n"
            f"WHY: {why_text}\n"
            f"HOW CONFIDENT: {confidence * 100:.0f}% after fusing independent sources "
            f"[{contrib_text}] — this is a risk assessment, not a certainty.\n"
            f"WHAT IMPACT: {impact}\n"
            f"WHAT TO DO: {todo}\n"
            f"WHO APPROVES: {approver}"
        )

    # ------------------------------------------------------------------ main entry

    def synthesize_incident(
        self,
        observations: List[Dict[str, Any]],
        zone: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Turn a window of agent observations into one explainable incident, or ``None``."""
        self.last_gap_reason = None
        obs_list = [o for o in (observations or []) if o]
        if not obs_list:
            return None

        resolved_zone = zone or obs_list[0].get("zone") or "ZONE_B"

        temp_obs = [o for o in obs_list
                    if o.get("agent_id") == "temperature_agent" and o.get("sensor_type") == "temperature"]
        smoke_obs = [o for o in obs_list
                     if o.get("agent_id") == "temperature_agent" and o.get("sensor_type") == "smoke"]
        machine_obs = [o for o in obs_list if o.get("agent_id") == "machine_agent"]
        cyber_obs = [o for o in obs_list if o.get("agent_id") == "cyber_agent"]
        worker_obs = next((o for o in obs_list if o.get("agent_id") == "worker_agent"), None)

        # 1. Cyber is an independent domain and never competes with physical hazards.
        if cyber_obs:
            return self._cyber_incident(cyber_obs, worker_obs, resolved_zone)

        # 2. Fire. Requires smoke to be present at all, plus >= 2 corroborating signals.
        #    Because smoke is required, machine evidence can never be mistaken for a fire.
        fire_signals = self._fire_signals(smoke_obs, temp_obs)
        if smoke_obs and len(fire_signals) >= 2:
            return self._fire_incident(smoke_obs, temp_obs, worker_obs, fire_signals, resolved_zone)

        # 3. Machine overheating / overpressure. Requires machine evidence on an asset.
        if machine_obs:
            return self._overheating_incident(machine_obs, temp_obs, worker_obs, resolved_zone)

        # 4. Not enough corroborated evidence — say so instead of guessing.
        self.last_gap_reason = self._gap_reason(temp_obs, smoke_obs, fire_signals, resolved_zone)
        if self.last_gap_reason:
            self.update_status(
                task=f"Correlating evidence for {resolved_zone}",
                observation=self.last_gap_reason,
                decision="HOLD: no incident declared until corroborating evidence arrives.",
                status="ACTIVE",
            )
        return None

    # ------------------------------------------------------------------ fire

    @staticmethod
    def _fire_signals(smoke_obs, temp_obs) -> List[str]:
        """Independent-ish signals supporting combustion. Two are required to declare a fire."""
        signals: List[str] = []
        for s in smoke_obs:
            if str(s.get("severity")).upper() == "CRITICAL":
                signals.append(
                    f"{s.get('sensor_id')} smoke density {s.get('current_value', 0):.1f} ppm at or above "
                    f"the {s.get('threshold_critical', 40):.0f} ppm critical level"
                )
            if s.get("sustained_critical"):
                signals.append(
                    f"{s.get('sensor_id')} has held above the critical level across consecutive samples "
                    "(alarm verification passed)"
                )
            elif s.get("rate_known") and s.get("rate_of_change", 0.0) > 1.0:
                signals.append(
                    f"{s.get('sensor_id')} smoke rising at {s.get('rate_of_change', 0.0):+.1f} ppm/min"
                )
        for t in temp_obs:
            if str(t.get("severity")).upper() == "CRITICAL":
                signals.append(
                    f"{t.get('sensor_id')} air temperature {t.get('current_value', 0):.1f}°C at or above "
                    f"the {t.get('threshold_critical', 50):.0f}°C critical level"
                )
            elif t.get("rate_known") and t.get("rate_of_change", 0.0) >= 4.0:
                signals.append(
                    f"{t.get('sensor_id')} air temperature rising at {t.get('rate_of_change', 0.0):+.1f}°C/min"
                )
        return signals

    def _fire_incident(self, smoke_obs, temp_obs, worker_obs, signals, zone) -> Dict[str, Any]:
        rag_engine.query("Combustion fire suppression evacuation protocol")
        hazard_obs = smoke_obs + temp_obs
        severity = max_severity(hazard_obs)
        confidence, contributions = fuse_confidence(hazard_obs)
        workers = self._workers_in(zone, worker_obs)
        zone_letter = zone.split("_")[-1]

        actions = [
            RecommendedAction(
                action=f"Trigger acoustic and strobe evacuation alarm in {zone}",
                action_type="TRIGGER_ALARM",
                target=f"ALARM-{zone.replace('_', '-')}",
                risk_level=RiskLevel.LOW,
                requires_confirmation=False,
                reason="Audible safety warning for on-site personnel.",
            ),
            RecommendedAction(
                action=f"Close industrial fire containment doors in {zone}",
                action_type="CLOSE_DOOR",
                target=f"DOOR-{zone_letter}-01",
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                reason="Contain combustion aerosols and smoke propagation.",
            ),
            RecommendedAction(
                action=f"Activate clean-agent suppression in {zone}",
                action_type="ACTIVATE_SUPPRESSION",
                target=f"SUPPRESSION-{zone_letter}-01",
                risk_level=RiskLevel.HIGH,
                requires_confirmation=True,
                reason="Extinguish the combustion source once personnel are clear.",
            ),
        ]

        impact = (
            f"Life-safety hazard to {len(workers)} person(s) currently in {zone} "
            f"({', '.join(workers) if workers else 'none detected'}) and loss of the zone's assets."
        )
        reasoning = self._reasoning(
            what=f"Combustion signature detected in {zone}.",
            why=[f"{i + 1}) {s}." for i, s in enumerate(signals)],
            confidence=confidence,
            contributions=contributions,
            impact=impact,
            todo="Sound the evacuation alarm, seal containment doors, then discharge suppression.",
            approver="Explicit owner confirmation required for suppression discharge.",
        )
        self.update_status(
            task=f"Fire hypothesis for {zone}",
            observation=f"{len(signals)} corroborating combustion signals in {zone}.",
            decision="Declare INDUSTRIAL_FIRE and request evacuation.",
            status="WARNING",
        )
        return {
            "id": f"INC-{uuid.uuid4().hex[:4].upper()}",
            "type": "INDUSTRIAL_FIRE",
            "severity": SEVERITY_ENUM[severity],
            "confidence": confidence,
            "zone": zone,
            "timestamp": clock.now(),
            "affected_assets": [f"{zone} Sector"] + [o.get("sensor_id") for o in smoke_obs if o.get("sensor_id")],
            "affected_workers": workers,
            "evidence": self._evidence(hazard_obs + ([worker_obs] if worker_obs else [])),
            "ai_reasoning": reasoning,
            "recommended_actions": actions,
            "status": "ACTIVE",
        }

    # ------------------------------------------------------------------ machine

    def _overheating_incident(self, machine_obs, temp_obs, worker_obs, zone) -> Dict[str, Any]:
        rag_engine.query("machine overheating pressure emergency shutdown EP-07")
        hazard_obs = machine_obs + temp_obs
        severity = max_severity(hazard_obs)
        confidence, contributions = fuse_confidence(hazard_obs)
        workers = self._workers_in(zone, worker_obs)

        primary = max(machine_obs, key=lambda o: _rank(o.get("severity", "INFO")))
        machine_id = primary.get("machine_id", "M-04")

        why: List[str] = []
        for obs in machine_obs:
            for reason in obs.get("failing_parameters", []) or [obs.get("observation", "")]:
                why.append(f"{obs.get('machine_id')}: {reason}.")
        for obs in temp_obs:
            rate = (f", rising {obs['rate_of_change']:+.1f}°C/min"
                    if obs.get("rate_known") else ", trend still being established")
            why.append(
                f"Ambient {obs.get('sensor_id')} at {obs.get('current_value', 0):.1f}°C{rate}."
            )

        eta = primary.get("eta_to_pressure_limit_s") or primary.get("eta_to_temperature_limit_s")
        if eta:
            why.append(f"At the current rate the operating limit is reached in ~{eta:.0f}s.")

        actions = [
            RecommendedAction(
                action=f"Emergency shutdown of machine {machine_id}",
                action_type="STOP_MACHINE",
                target=machine_id,
                risk_level=RiskLevel.HIGH,
                requires_confirmation=True,
                reason=f"Prevent hydraulic rupture and spindle seizure on {machine_id}.",
            ),
            RecommendedAction(
                action=f"Evacuate {len(workers)} operator(s) from the {zone} perimeter",
                action_type="EVACUATE_ZONE",
                target=zone,
                risk_level=RiskLevel.HIGH,
                requires_confirmation=True,
                reason="Thermal radiation and fragment risk to personnel near the asset.",
            ),
            RecommendedAction(
                action="Engage auxiliary cooling heat exchanger pump CX-02",
                action_type="ACTIVATE_COOLING",
                target="PUMP-COOL-02",
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                reason="Bring the asset back below its thermal limit.",
            ),
        ]

        impact = (
            f"Unplanned loss of {machine_id} plus injury risk to {len(workers)} person(s) in {zone} "
            f"({', '.join(workers) if workers else 'none detected'})."
        )
        reasoning = self._reasoning(
            what=f"Mechanical overheating / overpressure developing on {machine_id} in {zone}.",
            why=why,
            confidence=confidence,
            contributions=contributions,
            impact=impact,
            todo=f"Halt {machine_id}, clear {zone}, and engage auxiliary cooling.",
            approver="Explicit owner confirmation required — the shutdown stops production.",
        )
        self.update_status(
            task=f"Machine hypothesis for {machine_id}",
            observation=f"{len(hazard_obs)} corroborating sources on {machine_id} in {zone}.",
            decision=f"Declare MACHINE_OVERHEATING for {machine_id}.",
            status="WARNING",
        )
        return {
            "id": f"INC-{uuid.uuid4().hex[:4].upper()}",
            "type": "MACHINE_OVERHEATING",
            "severity": SEVERITY_ENUM[severity],
            "confidence": confidence,
            "zone": zone,
            "timestamp": clock.now(),
            "affected_assets": sorted({o.get("machine_id") for o in machine_obs if o.get("machine_id")}),
            "affected_workers": workers,
            "evidence": self._evidence(hazard_obs + ([worker_obs] if worker_obs else [])),
            "ai_reasoning": reasoning,
            "recommended_actions": actions,
            "status": "ACTIVE",
        }

    # ------------------------------------------------------------------ cyber

    def _cyber_incident(self, cyber_obs, worker_obs, zone) -> Dict[str, Any]:
        rag_engine.query("OT industrial cyber network isolation rogue device")
        severity = max_severity(cyber_obs, floor="HIGH")
        confidence, contributions = fuse_confidence(cyber_obs)
        primary = cyber_obs[0]
        device = primary.get("device", "UNKNOWN-DEVICE-07")
        target = primary.get("target", "Industrial Modbus Gateway")

        actions = [
            RecommendedAction(
                action=f"Isolate device {device}",
                action_type="ISOLATE_DEVICE",
                target=device,
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                reason="Unregistered device attempting unauthorized OT fieldbus access.",
            ),
            RecommendedAction(
                action="Engage OT VLAN quarantine mode",
                action_type="VLAN_QUARANTINE",
                target="SWITCH-CORE-01",
                risk_level=RiskLevel.LOW,
                requires_confirmation=False,
                reason="Automatic perimeter containment.",
            ),
        ]

        reasoning = self._reasoning(
            what=f"Unauthorized OT network activity from {device} towards {target}.",
            why=[o.get("observation", "") for o in cyber_obs],
            confidence=confidence,
            contributions=contributions,
            impact="Risk of PLC logic manipulation, spoofed readings, or a forced production stop.",
            todo=f"Isolate {device} and quarantine its switch port.",
            approver="Plant security officer / system owner confirmation required.",
        )
        self.update_status(
            task=f"OT intrusion hypothesis for {zone}",
            observation=f"{len(cyber_obs)} cyber source(s) implicating {device}.",
            decision=f"Declare CYBER_INTRUSION and recommend isolating {device}.",
            status="WARNING",
        )
        return {
            "id": f"INC-{uuid.uuid4().hex[:4].upper()}",
            "type": "CYBER_INTRUSION",
            "severity": SEVERITY_ENUM[severity],
            "confidence": confidence,
            "zone": zone,
            "timestamp": clock.now(),
            "affected_assets": [device, target],
            "affected_workers": [],
            "evidence": self._evidence(cyber_obs),
            "ai_reasoning": reasoning,
            "recommended_actions": actions,
            "status": "ACTIVE",
        }

    # ------------------------------------------------------------------ no-incident

    @staticmethod
    def _gap_reason(temp_obs, smoke_obs, fire_signals, zone) -> Optional[str]:
        if smoke_obs:
            return (
                f"Smoke reported in {zone} but only {len(fire_signals)} of the 2 required "
                "corroborating signals are present. Holding — no fire declared yet."
            )
        if temp_obs:
            hottest = max(temp_obs, key=lambda o: o.get("current_value", 0.0))
            return (
                f"Ambient temperature anomaly in {zone} "
                f"({hottest.get('sensor_id')} at {hottest.get('current_value', 0):.1f}°C) with no machine "
                "evidence and no smoke. Holding — a single environmental sensor is not enough to "
                "name a hazard."
            )
        return None
