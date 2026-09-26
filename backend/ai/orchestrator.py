import asyncio
from typing import Any, Dict, List, Optional
import uuid
import logging

from ai import clock
from ai.observation_window import ObservationWindow
from ai.agents.temperature_agent import TemperatureAgent
from ai.agents.machine_agent import MachineAgent
from ai.agents.worker_agent import WorkerAgent
from ai.agents.cyber_agent import CybersecurityAgent
from ai.agents.recommendation_agent import RecommendationAgent, SEVERITY_RANK
from app.services.state_store import state
from app.models.schemas import Incident, Action, ActionStatus, EvidenceItem, RiskAssessment, Severity

logger = logging.getLogger("orchestrator")

#: How long observations stay correlatable (seconds).
CORRELATION_WINDOW_S = 30.0

#: After an incident is resolved, ignore the same hazard in the same zone for this long,
#: so a cooling-down machine does not immediately re-open the incident the owner just closed.
RESOLVED_COOLDOWN_S = 60.0

#: Do not repeat the same "waiting for corroboration" note more often than this.
GAP_LOG_INTERVAL_S = 10.0


class AgentOrchestrator:
    def __init__(self):
        self.temp_agent = TemperatureAgent()
        self.machine_agent = MachineAgent()
        self.worker_agent = WorkerAgent()
        self.cyber_agent = CybersecurityAgent()
        self.rec_agent = RecommendationAgent()
        # Kept for backwards compatibility with anything reading it.
        self.recent_observations: List[Dict[str, Any]] = []
        #: Per-zone sliding window of agent observations — the correlation fix.
        self.window = ObservationWindow(ttl_s=CORRELATION_WINDOW_S)
        self._last_gap_log: Dict[str, Any] = {}
        self._last_scenario: Optional[str] = None

    def reset_correlation(self, reason: str):
        """Forget all correlation memory.

        Without this, a demo reset or a scenario switch leaves up to 30 s of observations in
        the window and the agents' history buffers. Running `fire` right after
        `machine_overheating` then correlated fresh smoke with the *previous* scenario's
        8.9 bar pressure reading and opened a second, bogus incident.
        """
        self.window.clear()
        self.temp_agent.history.clear()
        self.machine_agent.history.clear()
        self._last_gap_log.clear()
        self.recent_observations = []
        from ai.n8n_client import clear_resume_urls
        clear_resume_urls()
        self._log_agent_step(
            "recommendation_agent",
            ["SYSTEM"],
            f"Correlation memory cleared ({reason}).",
            "RESET: agents resume from a clean baseline.",
        )

    def _detect_scenario_change(self):
        """Clear correlation memory when the demo scenario changes.

        Read-only defence so the jury can jump between scenario buttons without a reset.
        The clean fix is for the simulator to publish a SCENARIO_CHANGED event — proposed to
        Engineer 2 in docs/ai/PROPOSED_CHANGES_FOR_TEAM.md.
        """
        try:
            from iot.simulator import simulator
            current = simulator.scenario
        except Exception:
            return
        if self._last_scenario is None:
            self._last_scenario = current
            return
        if current != self._last_scenario:
            previous, self._last_scenario = self._last_scenario, current
            self.reset_correlation(f"scenario {previous} -> {current}")

    async def handle_event(self, event: Dict[str, Any]):
        event_type = event.get("event_type", "")
        event_zone = event.get("zone") or "GLOBAL"
        observations: List[Dict[str, Any]] = []

        if event_type == "FACTORY_RESET":
            self.reset_correlation("factory reset")
            return

        self._detect_scenario_change()

        # 1. Temperature / environmental agent
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

        # 4. Worker agent: exposure assessment for whatever the other agents saw
        w_obs = await self.worker_agent.process_event(event)
        if w_obs:
            observations.append(w_obs)
            self._log_agent_step(self.worker_agent.agent_id, ["HAZARD_ALERT"], w_obs["observation"], w_obs["decision"])

        self._refresh_agent_cards()

        if not observations:
            return

        # 5. Correlate: remember these observations, then reason over everything recent in
        #    this zone instead of only over the event we happen to be handling.
        zones = {self.window.add(obs, zone=event_zone) for obs in observations}
        self.recent_observations = observations

        for zone in zones:
            snapshot = self.window.snapshot(zone)
            incident_data = self.rec_agent.synthesize_incident(snapshot, zone=zone)
            if incident_data:
                await self._create_or_escalate(incident_data, snapshot)
            elif self.rec_agent.last_gap_reason:
                self._log_gap(zone, self.rec_agent.last_gap_reason, snapshot)

    # ------------------------------------------------------------------ bookkeeping

    def _refresh_agent_cards(self):
        state.agents["temperature_agent"] = self.temp_agent
        state.agents["machine_agent"] = self.machine_agent
        state.agents["worker_agent"] = self.worker_agent
        state.agents["cyber_agent"] = self.cyber_agent
        state.agents["recommendation_agent"] = self.rec_agent

    def _log_agent_step(self, agent_id: str, inputs: List[str], reasoning: str, decision: str, actions: List[str] = None):
        entry = {
            "timestamp": clock.now(),
            "agent_id": agent_id,
            "input_from": inputs,
            "reasoning": reasoning,
            "decision": decision,
            "actions_proposed": actions or []
        }
        state.agent_logs.insert(0, entry)
        if len(state.agent_logs) > 100:
            state.agent_logs.pop()

    def _log_gap(self, zone: str, reason: str, snapshot: List[Dict[str, Any]]):
        """Record that the system deliberately declined to name a hazard. Rate limited."""
        last = self._last_gap_log.get(zone)
        now = clock.now()
        if last and last[0] == reason and (now - last[1]).total_seconds() < GAP_LOG_INTERVAL_S:
            return
        self._last_gap_log[zone] = (reason, now)
        self._log_agent_step(
            "recommendation_agent",
            [o.get("agent_id", "unknown") for o in snapshot],
            reason,
            "HOLD: no incident declared — required corroborating evidence is missing.",
        )

    # ------------------------------------------------------------------ incident lifecycle

    def _find_open_incident(self, incident_type: str, zone: str) -> Optional[Incident]:
        for existing in state.incidents.values():
            if existing.type == incident_type and existing.zone == zone and existing.status in ("ACTIVE", "RESOLVING"):
                return existing
        return None

    def _cooldown_remaining(self, incident_type: str, zone: str) -> float:
        """Seconds left of the post-resolution cooldown for this hazard in this zone."""
        now = clock.now()
        remaining = 0.0
        for existing in state.incidents.values():
            if existing.type != incident_type or existing.zone != zone:
                continue
            if existing.status not in ("RESOLVED", "DISMISSED") or not existing.resolved_at:
                continue
            elapsed = (now - existing.resolved_at).total_seconds()
            if 0.0 <= elapsed < RESOLVED_COOLDOWN_S:
                remaining = max(remaining, RESOLVED_COOLDOWN_S - elapsed)
        return remaining

    async def _create_or_escalate(self, incident_data: Dict[str, Any], observations: List[Dict[str, Any]]):
        incident_type = incident_data["type"]
        zone = incident_data["zone"]

        open_incident = self._find_open_incident(incident_type, zone)
        if open_incident is not None:
            await self._escalate(open_incident, incident_data, observations)
            return

        cooldown = self._cooldown_remaining(incident_type, zone)
        if cooldown > 0:
            self._log_agent_step(
                "recommendation_agent",
                [o.get("agent_id", "unknown") for o in observations],
                f"{incident_type} conditions seen again in {zone} {RESOLVED_COOLDOWN_S - cooldown:.0f}s after the "
                f"previous incident was closed.",
                f"SUPPRESSED: within the {RESOLVED_COOLDOWN_S:.0f}s post-resolution cooldown "
                f"({cooldown:.0f}s remaining).",
            )
            return

        await self._create_incident_and_actions(incident_data, observations)

    async def _escalate(self, incident: Incident, incident_data: Dict[str, Any], observations: List[Dict[str, Any]]):
        """Update an already-open incident rather than opening a duplicate.

        A hazard that gets worse should raise the severity of the incident the owner is
        already looking at — not create a second card for the same physical event.
        """
        from app.services.event_bus import event_bus

        new_severity = incident_data["severity"]
        old_rank = SEVERITY_RANK.get(str(incident.severity.value), 0)
        new_rank = SEVERITY_RANK.get(str(getattr(new_severity, "value", new_severity)), 0)
        confidence_gain = incident_data["confidence"] - incident.confidence

        if new_rank <= old_rank and confidence_gain < 0.05:
            return  # nothing materially new

        previous = incident.severity.value
        incident.severity = new_severity if new_rank > old_rank else incident.severity
        incident.confidence = max(incident.confidence, incident_data["confidence"])
        # pydantic does not validate on assignment, so coerce the dicts ourselves
        incident.evidence = [EvidenceItem(**e) if isinstance(e, dict) else e
                             for e in incident_data["evidence"]]
        incident.ai_reasoning = incident_data["ai_reasoning"]
        incident.affected_workers = incident_data["affected_workers"]

        if zone_state := state.zones.get(incident.zone):
            zone_state.risk_level = incident.severity

        for risk in state.risks.values():
            if risk.type == incident.type and risk.zone == incident.zone and risk.status == "ACTIVE":
                risk.severity = incident.severity
                risk.probability = incident.confidence
                risk.contributing_factors = [e.detail for e in incident.evidence]

        self._log_agent_step(
            "recommendation_agent",
            [o.get("agent_id", "unknown") for o in observations],
            f"{incident.id} re-assessed: severity {previous} -> {incident.severity.value}, "
            f"confidence {incident.confidence:.2f} from {len(incident.evidence)} evidence items.",
            f"ESCALATED existing incident {incident.id} instead of opening a duplicate.",
        )

        await event_bus.publish(
            event_type="INCIDENT_UPDATED",
            source="ai:orchestrator",
            data=incident.model_dump(mode="json"),
            zone=incident.zone,
            severity=incident.severity.value,
            correlation_id=incident.id
        )

    async def _create_incident_and_actions(self, incident_data: Dict[str, Any], observations: List[Dict[str, Any]]):
        from app.services.event_bus import event_bus

        inc_id = incident_data["id"]
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
            contributing_factors=[e.detail for e in incident.evidence],
            assessed_at=clock.now(),
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
                created_at=clock.now(),
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

        # Hand the incident to n8n for LLM enrichment. Fire-and-forget by design: detection
        # is already complete and the template recommendations above stand on their own.
        from ai.n8n_client import notify_incident_background
        notify_incident_background(incident, observations)

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
