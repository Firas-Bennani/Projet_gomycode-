from typing import Dict, Any, Optional
from datetime import datetime
from ai.agents.base_agent import BaseAgent

class TemperatureAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="temperature_agent",
            name="Temperature & Environmental Agent"
        )
        self.history: Dict[str, list] = {}  # sensor_id -> [(timestamp, value)]

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("event_type", "")
        if event_type != "SENSOR_READING":
            return None

        data = event.get("data", {})
        sensor_type = data.get("type")
        if sensor_type not in ["temperature", "smoke", "water_level", "humidity"]:
            return None

        sensor_id = data.get("sensor_id")
        val = float(data.get("value", 0.0))
        zone = data.get("zone", "ZONE_B")
        now = datetime.utcnow()

        # Track history
        if sensor_id not in self.history:
            self.history[sensor_id] = []
        self.history[sensor_id].append((now, val))
        if len(self.history[sensor_id]) > 30:
            self.history[sensor_id].pop(0)

        # Detect trend
        rate_of_change = 0.0
        if len(self.history[sensor_id]) >= 3:
            old_time, old_val = self.history[sensor_id][0]
            time_diff = (now - old_time).total_seconds() / 60.0
            if time_diff > 0.1:
                rate_of_change = (val - old_val) / time_diff

        # Check anomalies
        anomaly = False
        severity = "INFO"
        observation = ""
        decision = ""

        if sensor_type == "temperature":
            if val >= 50.0 or rate_of_change >= 4.0:
                anomaly = True
                severity = "CRITICAL"
                observation = f"Critical thermal spike in {zone}: {val:.1f}°C (Rate: +{rate_of_change:.1f}°C/min). Rapid overheating signature detected."
                decision = f"TRIGGER CRITICAL THERMAL ALERT for {zone}"
            elif val >= 35.0 or rate_of_change >= 2.0:
                anomaly = True
                severity = "WARNING"
                observation = f"Elevated temperature in {zone}: {val:.1f}°C (Rate: +{rate_of_change:.1f}°C/min). Exceeds normal 24°C baseline."
                decision = f"TRIGGER WARNING THERMAL ALERT for {zone}"
            else:
                observation = f"{zone} temperature nominal at {val:.1f}°C (delta: {rate_of_change:+.1f}°C/min)."
                decision = "Environmental baseline verified."

        elif sensor_type == "smoke":
            if val >= 40.0:
                anomaly = True
                severity = "CRITICAL"
                observation = f"High particulate density in {zone}: {val:.1f} ppm smoke detected. Active combustion risk."
                decision = f"TRIGGER CRITICAL SMOKE/FIRE ALERT for {zone}"
            elif val >= 20.0:
                anomaly = True
                severity = "WARNING"
                observation = f"Trace combustion aerosols in {zone}: {val:.1f} ppm smoke."
                decision = f"TRIGGER WARNING SMOKE ALERT for {zone}"

        elif sensor_type == "water_level":
            if val >= 8.0:
                anomaly = True
                severity = "CRITICAL"
                observation = f"Flooding risk in {zone}: water sensor reading {val:.1f} cm."
                decision = f"TRIGGER FLOOD HAZARD ALERT for {zone}"

        self.update_status(
            task=f"Monitoring environmental sensors in {zone}",
            observation=observation,
            decision=decision,
            status="WARNING" if severity in ["WARNING", "CRITICAL"] else "ACTIVE"
        )

        if anomaly:
            return {
                "agent_id": self.agent_id,
                "anomaly": True,
                "severity": severity,
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "zone": zone,
                "current_value": val,
                "unit": data.get("unit", "°C"),
                "rate_of_change": rate_of_change,
                "observation": observation,
                "decision": decision
            }

        return None
