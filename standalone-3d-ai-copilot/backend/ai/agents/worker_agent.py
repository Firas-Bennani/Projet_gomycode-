from typing import Dict, Any, Optional, List
from datetime import datetime
from ai.agents.base_agent import BaseAgent

class WorkerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="worker_agent",
            name="Worker Safety & Productivity Agent"
        )
        self.zone_workers: Dict[str, List[str]] = {
            "ZONE_A": [],
            "ZONE_B": ["W23", "W41", "W52"],
            "ZONE_C": ["W12"],
            "ZONE_D": ["W09"]
        }

    def get_workers_in_zone(self, zone: str) -> List[str]:
        return self.zone_workers.get(zone, [])

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("event_type", "")
        data = event.get("data", {})
        zone = event.get("zone", "ZONE_B")

        # Update tracking if WORKER_UPDATE
        if event_type == "WORKER_UPDATE":
            w_id = data.get("worker_id")
            w_zone = data.get("zone", zone)
            ppe = data.get("ppe", {})

            # Check PPE compliance
            missing_ppe = []
            if not ppe.get("helmet", True): missing_ppe.append("Helmet")
            if not ppe.get("vest", True): missing_ppe.append("Safety Vest")
            if not ppe.get("gloves", True): missing_ppe.append("Gloves")
            if not ppe.get("safety_shoes", True): missing_ppe.append("Safety Shoes")

            if missing_ppe:
                obs = f"PPE VIOLATION: Worker {w_id} in {w_zone} without {', '.join(missing_ppe)}."
                dec = f"ALERT: Non-compliant worker in hazardous area {w_zone}"
                self.update_status(f"Auditing PPE in {w_zone}", obs, dec, "WARNING")
                return {
                    "agent_id": self.agent_id,
                    "anomaly": True,
                    "severity": "WARNING",
                    "worker_id": w_id,
                    "zone": w_zone,
                    "missing_ppe": missing_ppe,
                    "observation": obs,
                    "decision": dec
                }

        # If an environmental or machine hazard occurs in a zone, assess worker vulnerability
        if "CRITICAL" in event.get("severity", "") or "WARNING" in event.get("severity", ""):
            hazard_zone = event.get("zone", "ZONE_B")
            workers = self.get_workers_in_zone(hazard_zone)
            if workers:
                obs = f"VULNERABILITY DETECTED: {len(workers)} workers ({', '.join(workers)}) currently inside hazard sector {hazard_zone}."
                dec = f"URGENT: Initiate tactical zone evacuation for {len(workers)} personnel in {hazard_zone}"
                self.update_status(f"Emergency personnel routing for {hazard_zone}", obs, dec, "WARNING")
                return {
                    "agent_id": self.agent_id,
                    "anomaly": True,
                    "severity": "CRITICAL" if len(workers) > 0 else "WARNING",
                    "zone": hazard_zone,
                    "affected_workers": workers,
                    "observation": obs,
                    "decision": dec
                }

        self.update_status(
            task="Tracking on-site operators across 4 industrial sectors",
            observation=f"All personnel accounted for. 5 operators active across plant zones.",
            decision="Worker compliance normal.",
            status="ACTIVE"
        )
        return None
