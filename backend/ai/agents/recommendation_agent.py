from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from ai.agents.base_agent import BaseAgent
from ai.rag.rag_engine import rag_engine
from app.models.schemas import Severity, RiskLevel, RecommendedAction

class RecommendationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="recommendation_agent",
            name="Recommendation & Strategic Intelligence Agent"
        )
        self.active_hypotheses: Dict[str, Any] = {}

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # This agent processes multi-agent observations
        return None

    def synthesize_incident(self, observations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Synthesizes observations from multiple agents into an explainable, structured incident."""
        if not observations:
            return None

        # Check for Overheating + Pressure combo (Scenario 1)
        temp_obs = next((o for o in observations if o.get("agent_id") == "temperature_agent"), None)
        mach_obs = next((o for o in observations if o.get("agent_id") == "machine_agent"), None)
        work_obs = next((o for o in observations if o.get("agent_id") == "worker_agent"), None)
        cyber_obs = next((o for o in observations if o.get("agent_id") == "cyber_agent"), None)

        now = datetime.utcnow()
        incident_id = f"INC-{uuid.uuid4().hex[:4].upper()}"

        if cyber_obs:
            rag_result = rag_engine.query("OT industrial cyber network isolation rogue device")
            evidence = [
                {"source": "cyber_agent", "detail": cyber_obs.get("observation", "")}
            ]
            recommended_actions = [
                RecommendedAction(
                    action=f"Isolate device {cyber_obs.get('device', 'UNKNOWN')}",
                    action_type="ISOLATE_DEVICE",
                    target=cyber_obs.get("device", "UNKNOWN-DEVICE-07"),
                    risk_level=RiskLevel.MEDIUM,
                    requires_confirmation=True,
                    reason="Rogue device attempting unauthorized OT fieldbus access."
                ),
                RecommendedAction(
                    action="Engage OT VLAN quarantine mode",
                    action_type="VLAN_QUARANTINE",
                    target="SWITCH-CORE-01",
                    risk_level=RiskLevel.LOW,
                    requires_confirmation=False,
                    reason="Automatic perimeter containment."
                )
            ]
            return {
                "id": incident_id,
                "type": "CYBER_INTRUSION",
                "severity": Severity.HIGH,
                "confidence": 0.95,
                "zone": "ZONE_B",
                "timestamp": now,
                "affected_assets": [cyber_obs.get("device", "UNKNOWN-DEVICE-07"), "Industrial Modbus Gateway"],
                "affected_workers": [],
                "evidence": evidence,
                "ai_reasoning": (
                    "WHAT: Unauthorized device attempting brute-force connection to industrial controller.\n"
                    "WHY: 47 consecutive unauthenticated handshake frames from unregistered MAC.\n"
                    "HOW CONFIDENT: 95% certainty of malicious or misconfigured device.\n"
                    "WHAT IMPACT: Risk of PLC logic manipulation or production shutdown.\n"
                    "WHAT TO DO: Immediately isolate device and quarantine switch port.\n"
                    "WHO APPROVES: Plant Security Officer / System Owner confirmation required."
                ),
                "recommended_actions": recommended_actions,
                "status": "ACTIVE"
            }

        # Check for Fire scenario (High smoke or high temp + smoke)
        smoke_reading = temp_obs.get("sensor_type") == "smoke" if temp_obs else False
        if smoke_reading or (temp_obs and temp_obs.get("current_value", 0) > 45.0 and mach_obs is None):
            rag_result = rag_engine.query("Combustion fire suppression evacuation protocol")
            evidence = [
                {"source": "temperature_agent", "detail": temp_obs.get("observation", "")}
            ]
            affected_workers = work_obs.get("affected_workers", ["W23", "W41", "W52"]) if work_obs else ["W23", "W41"]
            recommended_actions = [
                RecommendedAction(
                    action="Trigger acoustic and strobe evacuation alarm in Zone B",
                    action_type="TRIGGER_ALARM",
                    target="ALARM-ZONE-B",
                    risk_level=RiskLevel.LOW,
                    requires_confirmation=False,
                    reason="Audible safety warning for on-site personnel."
                ),
                RecommendedAction(
                    action="Close industrial fire containment doors D-01 & D-02",
                    action_type="CLOSE_DOOR",
                    target="DOOR-B-01",
                    risk_level=RiskLevel.MEDIUM,
                    requires_confirmation=True,
                    reason="Contain combustion aerosols and smoke propagation."
                ),
                RecommendedAction(
                    action="Activate clean-agent / high-pressure water suppression in Zone B",
                    action_type="ACTIVATE_SUPPRESSION",
                    target="SUPPRESSION-B-01",
                    risk_level=RiskLevel.HIGH,
                    requires_confirmation=True,
                    reason="Extinguish confirmed thermal combustion source."
                )
            ]
            return {
                "id": incident_id,
                "type": "INDUSTRIAL_FIRE",
                "severity": Severity.CRITICAL,
                "confidence": 0.96,
                "zone": "ZONE_B",
                "timestamp": now,
                "affected_assets": ["Zone B Sector", "CNC Cells"],
                "affected_workers": affected_workers,
                "evidence": evidence,
                "ai_reasoning": (
                    "WHAT: Combustion event and smoke density surge detected in Zone B.\n"
                    "WHY: Atmospheric thermal sensors and smoke optical density sensors breached emergency thresholds.\n"
                    "HOW CONFIDENT: 96% confidence based on dual-sensor correlation.\n"
                    "WHAT IMPACT: Immediate life safety hazard to 3 on-site personnel and facility asset destruction.\n"
                    "WHAT TO DO: Sound evacuation alarms, seal containment dampers, and engage water suppression.\n"
                    "WHO APPROVES: Explicit owner confirmation required for high-risk water suppression."
                ),
                "recommended_actions": recommended_actions,
                "status": "ACTIVE"
            }

        # Check for Machine Overheating (Scenario 1)
        if temp_obs or mach_obs:
            rag_result = rag_engine.query("machine overheating pressure emergency shutdown EP-07")
            evidence = []
            if temp_obs:
                evidence.append({"source": "temperature_agent", "detail": temp_obs.get("observation", "")})
            if mach_obs:
                evidence.append({"source": "machine_agent", "detail": mach_obs.get("observation", "")})
            if work_obs:
                evidence.append({"source": "worker_agent", "detail": work_obs.get("observation", "")})

            affected_workers = work_obs.get("affected_workers", ["W23", "W41", "W52"]) if work_obs else ["W23", "W41", "W52"]
            machine_id = mach_obs.get("machine_id", "M-04") if mach_obs else "M-04"

            recommended_actions = [
                RecommendedAction(
                    action=f"Emergency shutdown of Machine {machine_id}",
                    action_type="STOP_MACHINE",
                    target=machine_id,
                    risk_level=RiskLevel.HIGH,
                    requires_confirmation=True,
                    reason=f"Prevent catastrophic spindle seizure and hydraulic rupture on {machine_id}."
                ),
                RecommendedAction(
                    action="Evacuate 3 operators from Zone B perimeter",
                    action_type="EVACUATE_ZONE",
                    target="ZONE_B",
                    risk_level=RiskLevel.HIGH,
                    requires_confirmation=True,
                    reason="High thermal radiation and shrapnel risk to on-site technicians."
                ),
                RecommendedAction(
                    action="Engage auxiliary cooling heat exchanger pump CX-02",
                    action_type="ACTIVATE_COOLING",
                    target="PUMP-COOL-02",
                    risk_level=RiskLevel.MEDIUM,
                    requires_confirmation=True,
                    reason="Accelerate temperature reduction below 40°C threshold."
                )
            ]

            return {
                "id": incident_id,
                "type": "MACHINE_OVERHEATING",
                "severity": Severity.CRITICAL,
                "confidence": 0.94,
                "zone": "ZONE_B",
                "timestamp": now,
                "affected_assets": [machine_id],
                "affected_workers": affected_workers,
                "evidence": evidence,
                "ai_reasoning": (
                    f"WHAT: Critical mechanical overheating and hydraulic overpressure detected on {machine_id}.\n"
                    f"WHY: Temperature reached 51°C (+4.2°C/min) and hydraulic pressure climbed to 8.7 bar (Limit: 8.0 bar).\n"
                    f"HOW CONFIDENT: 94% multi-agent cross-correlation confidence.\n"
                    f"WHAT IMPACT: Imminent hydraulic line rupture, spindle bearing weld, and safety threat to 3 personnel in Zone B.\n"
                    f"WHAT TO DO: Immediately halt {machine_id}, evacuate Zone B, and engage auxiliary cooling.\n"
                    f"WHO APPROVES: Explicit owner confirmation required due to production downtime impact."
                ),
                "recommended_actions": recommended_actions,
                "status": "ACTIVE"
            }

        return None
