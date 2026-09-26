import asyncio
from typing import Dict, Any, List
from datetime import datetime
import uuid
import logging
from ai.agents.temperature_agent import TemperatureAgent
from ai.agents.machine_agent import MachineAgent
from ai.agents.worker_agent import WorkerAgent
from ai.agents.cyber_agent import CybersecurityAgent
from ai.agents.recommendation_agent import RecommendationAgent
from app.services.state_store import state
from app.models.schemas import Incident, Action, ActionStatus, RiskAssessment, Severity

logger = logging.getLogger("orchestrator")

class AgentOrchestrator:
    def __init__(self):
        self.temp_agent = TemperatureAgent()
        self.machine_agent = MachineAgent()
        self.worker_agent = WorkerAgent()
        self.cyber_agent = CybersecurityAgent()
        self.rec_agent = RecommendationAgent()
        self.recent_observations: List[Dict[str, Any]] = []

    async def handle_event(self, event: Dict[str, Any]):
        event_type = event.get("event_type", "")
        # Forward event to specialized agents
        observations = []

        # 1. Temperature agent
        t_obs = await self.temp_agent.process_event(event)
        if t_obs:
            observations.append(t_obs)
            self._log_agent_step(self.temp_agent.agent_id, [event_type], t_obs["observation"], t_obs["decision"])

        # 2. Machine agent
        m_obs = await self.machine_agent.process_event(event)
        if m_obs:
            observations.append(m_obs)
            self._log_agent_step(self.machine_agent.agent_id, [event_type], m_obs["observation"], m_obs["decision"])

        # 3. Cyber agent
        c_obs = await self.cyber_agent.process_event(event)
        if c_obs:
            observations.append(c_obs)
            self._log_agent_step(self.cyber_agent.agent_id, [event_type], c_obs["observation"], c_obs["decision"])

        # 4. If an anomaly was detected in any domain, consult Worker Agent
        if observations:
            w_obs = await self.worker_agent.process_event(event)
            if w_obs:
                observations.append(w_obs)
                self._log_agent_step(self.worker_agent.agent_id, ["HAZARD_ALERT"], w_obs["observation"], w_obs["decision"])

            # 5. Strategic Recommendation Agent synthesizes incident
            incident_data = self.rec_agent.synthesize_incident(observations)
            if incident_data:
                await self._create_incident_and_actions(incident_data, observations)

        # Update state store agent cards
        state.agents["temperature_agent"] = self.temp_agent
        state.agents["machine_agent"] = self.machine_agent
        state.agents["worker_agent"] = self.worker_agent
        state.agents["cyber_agent"] = self.cyber_agent
        state.agents["recommendation_agent"] = self.rec_agent

    def _log_agent_step(self, agent_id: str, inputs: List[str], reasoning: str, decision: str, actions: List[str] = None):
        entry = {
            "timestamp": datetime.utcnow(),
            "agent_id": agent_id,
            "input_from": inputs,
            "reasoning": reasoning,
            "decision": decision,
            "actions_proposed": actions or []
        }
        state.agent_logs.insert(0, entry)
        if len(state.agent_logs) > 100:
            state.agent_logs.pop()

    async def _create_incident_and_actions(self, incident_data: Dict[str, Any], observations: List[Dict[str, Any]]):
        from app.services.event_bus import event_bus

        inc_id = incident_data["id"]
        # Check if an active incident of same type already exists
        for existing in state.incidents.values():
            if existing.status == "ACTIVE" and existing.type == incident_data["type"] and existing.zone == incident_data["zone"]:
                return  # already active

        incident = Incident(**incident_data)
        state.incidents[inc_id] = incident

        # Update zone status
        zone = incident.zone
        if zone in state.zones:
            state.zones[zone].status = "ALERT"
            state.zones[zone].risk_level = incident.severity
            if inc_id not in state.zones[zone].active_incidents:
                state.zones[zone].active_incidents.append(inc_id)

        # Create active risk entry
        risk_id = f"RSK-{uuid.uuid4().hex[:4].upper()}"
        risk = RiskAssessment(
            id=risk_id,
            type=incident.type,
            zone=incident.zone,
            severity=incident.severity,
            probability=incident.confidence,
            impact=f"Potential critical impact to {', '.join(incident.affected_assets)}",
            contributing_factors=[e["detail"] for e in incident_data["evidence"]],
            assessed_at=datetime.utcnow(),
            status="ACTIVE"
        )
        state.risks[risk_id] = risk

        # Create actionable items in Command Center
        for rec in incident.recommended_actions:
            action_id = f"ACT-{uuid.uuid4().hex[:4].upper()}"
            act = Action(
                id=action_id,
                incident_id=inc_id,
                action_type=rec.action_type,
                target=rec.target,
                reason=rec.reason,
                risk_level=rec.risk_level,
                status=ActionStatus.AWAITING_APPROVAL if rec.requires_confirmation else ActionStatus.AUTHORIZED,
                created_at=datetime.utcnow(),
                created_by="recommendation_agent"
            )
            state.actions[action_id] = act

            if not rec.requires_confirmation:
                # Automatic execution for LOW risk
                from app.services.command_engine import command_engine
                asyncio.create_task(command_engine.execute_action(action_id))

        self._log_agent_step(
            "recommendation_agent",
            [o["agent_id"] for o in observations],
            incident.ai_reasoning,
            f"Created Incident {inc_id} ({incident.type}) with {len(incident.recommended_actions)} recommended actions",
            [r.action for r in incident.recommended_actions]
        )

        # Broadcast incident to Frontend
        await event_bus.publish(
            event_type="INCIDENT_CREATED",
            source="ai:orchestrator",
            data=incident.model_dump(mode="json"),
            zone=incident.zone,
            severity=incident.severity.value,
            correlation_id=inc_id
        )

orchestrator = AgentOrchestrator()
