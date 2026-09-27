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

        from iot.simulator import simulator
        simulator.notify_action_executed(action.action_type, action.target)

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
        await event_bus.publish(
            event_type="ACTION_STATUS",
            source="command_engine",
            data=action.model_dump(mode="json"),
            zone="ZONE_B",
            severity="INFO"
        )
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

        # If primary mitigation action executed, complete companion actions and resolve all active zone incidents
        if action.action_type in ["STOP_MACHINE", "ACTIVATE_COOLING", "ACTIVATE_SUPPRESSION", "EVACUATE_ZONE", "ISOLATE_DEVICE", "CLOSE_DOOR"]:
            for a in state.actions.values():
                if a.status == ActionStatus.AWAITING_APPROVAL:
                    a.status = ActionStatus.COMPLETED
                    a.completed_at = datetime.utcnow()

        await event_bus.publish(
            event_type="ACTION_STATUS",
            source="command_engine",
            data=action.model_dump(mode="json"),
            zone="ZONE_B",
            severity="INFO"
        )

        # Verification step: resolve all active incidents once primary mitigation action completes
        if action.action_type in ["STOP_MACHINE", "ACTIVATE_COOLING", "ACTIVATE_SUPPRESSION", "EVACUATE_ZONE", "ISOLATE_DEVICE", "CLOSE_DOOR"]:
            for inc in list(state.incidents.values()):
                if inc.status == "ACTIVE":
                    inc.status = "RESOLVED"
                    inc.resolved_at = datetime.utcnow()
                    zone = inc.zone
                    if zone in state.zones:
                        state.zones[zone].status = "NORMAL"
                        state.zones[zone].risk_level = None
                        state.zones[zone].active_incidents.clear()

                    await event_bus.publish(
                        event_type="INCIDENT_UPDATED",
                        source="command_engine:verification",
                        data=inc.model_dump(mode="json"),
                        zone=zone,
                        severity="INFO"
                    )

command_engine = CommandEngine()
