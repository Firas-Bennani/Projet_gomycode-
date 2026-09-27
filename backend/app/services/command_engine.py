import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from app.services.state_store import state
from app.models.schemas import ActionStatus, Severity
from app.services.event_bus import event_bus

logger = logging.getLogger("command_engine")

class CommandEngine:
    async def authorize_action(self, action_id: str, authorized_by: str = "owner_01", comment: str = None) -> Optional[Dict[str, Any]]:
        if action_id not in state.actions:
            return None

        action = state.actions[action_id]
        action.status = ActionStatus.AUTHORIZED
        action.authorized_by = authorized_by
        action.authorized_at = datetime.utcnow()

        # --- Engineer 1 (AI/n8n bridge) -------------------------------------------------
        # If an n8n execution is waiting on this incident's approval, resume it. Fire and
        # forget: a missing or unreachable n8n never affects the action itself.
        from ai.n8n_client import send_decision_background
        send_decision_background(action.incident_id, "approve", action_id, authorized_by)
        # --------------------------------------------------------------------------------

        await event_bus.publish(
            event_type="ACTION_STATUS",
            source="command_engine",
            data=action.model_dump(mode="json"),
            zone="ZONE_B",
            severity="INFO"
        )

        # Execute asynchronously
        asyncio.create_task(self.execute_action(action_id))
        return action.model_dump(mode="json")

    async def cancel_action(self, action_id: str, cancelled_by: str = "owner_01", reason: str = None) -> Optional[Dict[str, Any]]:
        if action_id not in state.actions:
            return None

        action = state.actions[action_id]
        action.status = ActionStatus.CANCELLED

        # --- Engineer 1 (AI/n8n bridge) -------------------------------------------------
        from ai.n8n_client import send_decision_background
        send_decision_background(action.incident_id, "cancel", action_id, cancelled_by)
        # --------------------------------------------------------------------------------

        await event_bus.publish(
            event_type="ACTION_STATUS",
            source="command_engine",
            data=action.model_dump(mode="json"),
            zone="ZONE_B",
            severity="INFO"
        )

        # --- Engineer 1: a cancel can be the last terminal action for the incident --------
        from ai.resolution_policy import evaluate_incident_after
        await evaluate_incident_after(action)
        # ---------------------------------------------------------------------------------

        return action.model_dump(mode="json")

    async def execute_action(self, action_id: str):
        if action_id not in state.actions:
            return

        action = state.actions[action_id]
        action.status = ActionStatus.IN_PROGRESS
        action.executed_at = datetime.utcnow()

        await event_bus.publish(
            event_type="ACTION_STATUS",
            source="command_engine",
            data=action.model_dump(mode="json"),
            zone="ZONE_B",
            severity="INFO"
        )

        # Simulate IoT actuator communication delay (e.g. 2.0s)
        await asyncio.sleep(2.0)

        # Apply action effect to simulated environment
        target = action.target
        checks = []

        # --- Engineer 1 (P5, authorised by Firas 2026-09-27 04:20) -----------------------
        # Let the simulator know this asset has been dealt with, so it stops driving the
        # scenario curve over a machine we just shut down. Without this the readings snap
        # back to 8.9 bar on the next tick and a brand-new incident opens immediately.
        try:
            from iot.simulator import simulator
            if action.action_type == "STOP_MACHINE":
                simulator.stopped_machines.add(target)
            elif action.action_type == "ACTIVATE_COOLING":
                simulator.cooling_active = True
            elif action.action_type == "ACTIVATE_SUPPRESSION":
                simulator.suppression_active = True
        except Exception as exc:  # never let this affect the action itself
            logger.warning("Could not notify the simulator about %s: %s", action.action_type, exc)
        # ---------------------------------------------------------------------------------

        if action.action_type == "STOP_MACHINE":
            if target in state.machines:
                state.machines[target].status = Severity.INFO
                # Set machine parameters to safe baseline
                state.machines[target].parameters["temperature"].value = 28.0
                state.machines[target].parameters["pressure"].value = 4.0
                state.machines[target].parameters["rpm"].value = 0.0
                state.machines[target].parameters["vibration"].value = 0.2
                checks.append({"check": f"Machine {target} spindle RPM verified zero", "passed": True})
                checks.append({"check": "Hydraulic main valve depressed", "passed": True})

        elif action.action_type == "EVACUATE_ZONE":
            if target in state.zones:
                # Move workers out of Zone B to Zone A
                for w in state.workers.values():
                    if w.zone == target:
                        w.zone = "ZONE_A"
                        w.position = {"x": -8.0, "y": 0.0, "z": 0.0}
                checks.append({"check": f"Zone {target} thermal infrared sensors confirm zero personnel", "passed": True})

        elif action.action_type == "ACTIVATE_COOLING":
            if "TEMP-B-01" in state.sensors:
                state.sensors["TEMP-B-01"].current_value = 25.0
                state.sensors["TEMP-B-01"].status = Severity.INFO
            checks.append({"check": "Coolant circulation pump flow rate 45 L/min verified", "passed": True})

        elif action.action_type == "ISOLATE_DEVICE":
            checks.append({"check": f"Switch port 14 isolated, rogue MAC {target} blacklisted", "passed": True})

        # --- Engineer 1: previously these action types completed with no checks at all ---
        elif action.action_type == "TRIGGER_ALARM":
            checks.append({"check": f"Acoustic and strobe devices on {target} reported active", "passed": True})

        elif action.action_type == "CLOSE_DOOR":
            checks.append({"check": f"Containment door {target} limit switch reports CLOSED", "passed": True})

        elif action.action_type == "VLAN_QUARANTINE":
            checks.append({"check": f"Quarantine VLAN applied on {target}", "passed": True})
        # ---------------------------------------------------------------------------------

        elif action.action_type == "ACTIVATE_SUPPRESSION":
            if "SMOKE-B-01" in state.sensors:
                state.sensors["SMOKE-B-01"].current_value = 6.0
                state.sensors["SMOKE-B-01"].status = Severity.INFO
            checks.append({"check": "Clean-agent suppression discharge confirmed in Zone B", "passed": True})

        # Mark action as COMPLETED
        action.status = ActionStatus.COMPLETED
        action.completed_at = datetime.utcnow()
        action.verification = {
            "verified": True,
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }

        await event_bus.publish(
            event_type="ACTION_STATUS",
            source="command_engine",
            data=action.model_dump(mode="json"),
            zone="ZONE_B",
            severity="INFO"
        )

        # --- Engineer 1: resolution rule lives in ai/resolution_policy.py ----------------
        # Resolve when every hazard-resolving action has completed AND the readings are
        # receding; superseded pending actions are cancelled with a reason. Falls back to the
        # original "all actions terminal" rule. Replaces the inline block that used to live
        # here, which kept incidents open on optional unapproved actions.
        from ai.resolution_policy import evaluate_incident_after
        await evaluate_incident_after(action)
        # ---------------------------------------------------------------------------------

command_engine = CommandEngine()
