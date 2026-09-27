from typing import Dict, Any, Optional
from datetime import datetime
from ai.agents.base_agent import BaseAgent

class MachineAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="machine_agent",
            name="Machine KPI & Diagnostics Agent"
        )
        self.history: Dict[str, list] = {}  # machine_id -> [(timestamp, pressure, temp, vib)]

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("event_type", "")
        if event_type not in ["MACHINE_STATUS", "SENSOR_READING"]:
            return None

        data = event.get("data", {})
        machine_id = data.get("machine_id") or "M-04"
        zone = data.get("zone", "ZONE_B")

        # Extract values
        if "parameters" in data:
            params = data["parameters"]
            pressure = float(params.get("pressure", {}).get("value", 5.0))
            temp = float(params.get("temperature", {}).get("value", 40.0))
            vib = float(params.get("vibration", {}).get("value", 2.0))
            rpm = float(params.get("rpm", {}).get("value", 1400.0))
        elif data.get("type") in ["pressure", "vibration"]:
            sensor_type = data.get("type")
            val = float(data.get("value", 0.0))
            pressure = val if sensor_type == "pressure" else 5.0
            vib = val if sensor_type == "vibration" else 2.0
            temp = 45.0
            rpm = 1420.0
        else:
            return None

        now = datetime.utcnow()
        if machine_id not in self.history:
            self.history[machine_id] = []
        self.history[machine_id].append((now, pressure, temp, vib))
        if len(self.history[machine_id]) > 30:
            self.history[machine_id].pop(0)

        # Detect pressure trend
        pressure_slope = 0.0
        if len(self.history[machine_id]) >= 3:
            old_time, old_p, _, _ = self.history[machine_id][0]
            time_diff = (now - old_time).total_seconds() / 60.0
            if time_diff > 0.1:
                pressure_slope = (pressure - old_p) / time_diff

        anomaly = False
        severity = "INFO"
        observation = ""
        decision = ""

        if pressure >= 8.5 or (pressure >= 7.8 and pressure_slope > 0.3):
            anomaly = True
            severity = "CRITICAL"
            observation = f"OVERPRESSURE on {machine_id}: {pressure:.2f} bar (Threshold: 8.0 bar, Trend: +{pressure_slope:.2f} bar/min). Mechanical breach imminent."
            decision = f"TRIGGER EMERGENCY SHUTDOWN RECOMMENDED for {machine_id}"
        elif pressure >= 7.2 or vib >= 5.0:
            anomaly = True
            severity = "WARNING"
            observation = f"Warning threshold reached on {machine_id}: Pressure={pressure:.2f} bar, Vibration={vib:.2f} mm/s."
            decision = f"TRIGGER MECHANICAL WARNING for {machine_id}"
        else:
            observation = f"{machine_id} mechanical parameters nominal (P={pressure:.1f} bar, T={temp:.1f}°C, Vib={vib:.1f} mm/s)."
            decision = "KPI baseline verified."

        self.update_status(
            task=f"Analyzing real-time kinematics for {machine_id} in {zone}",
            observation=observation,
            decision=decision,
            status="WARNING" if severity in ["WARNING", "CRITICAL"] else "ACTIVE"
        )

        if anomaly:
            return {
                "agent_id": self.agent_id,
                "anomaly": True,
                "severity": severity,
                "machine_id": machine_id,
                "zone": zone,
                "pressure": pressure,
                "pressure_slope": pressure_slope,
                "temperature": temp,
                "vibration": vib,
                "rpm": rpm,
                "observation": observation,
                "decision": decision
            }

        return None
