from typing import Any, Dict, List, Optional, Tuple

from ai import clock, trend
from ai.agents.base_agent import BaseAgent

# Pressure thresholds in bar, unchanged from the original agent.
PRESSURE_WARNING = 7.2
PRESSURE_CRITICAL = 8.5
PRESSURE_TREND_CRITICAL = 7.8          # critical when rising fast from here
PRESSURE_SLOPE_CRITICAL = 0.3          # bar per plant minute
PRESSURE_LIMIT = 8.0                   # documented operating limit used for ETA

VIBRATION_WARNING = 5.0

# Fallback machine temperature limit when the asset is unknown to the state store.
DEFAULT_TEMP_LIMIT = 80.0
TEMP_WARNING_FRACTION = 0.9            # warn at 90% of the asset's own limit


class MachineAgent(BaseAgent):
    """Machine KPI agent: pressure, machine-body temperature, vibration.

    Changes vs. the original: least-squares pressure slope that is only reported once there
    is >= 10 s of history, machine-body temperature compared against the asset's *own*
    threshold from the state store, and an ETA to the operating limit. The returned
    observation is what makes an incident count as "machine evidence" in the correlation
    rules, so it now also fires on an over-temperature body, not only on pressure.
    """

    def __init__(self):
        super().__init__(
            agent_id="machine_agent",
            name="Machine KPI & Diagnostics Agent"
        )
        # machine_id -> [(timestamp, pressure, temp, vib)]
        self.history: Dict[str, List[Tuple[Any, float, float, float]]] = {}

    @staticmethod
    def _temp_limit(machine_id: str) -> float:
        """The asset's documented temperature threshold, from the state store when known."""
        try:
            from app.services.state_store import state
            machine = state.machines.get(machine_id)
            if machine is not None:
                detail = machine.parameters.get("temperature")
                if detail is not None and detail.threshold:
                    return float(detail.threshold)
        except Exception:
            pass
        return DEFAULT_TEMP_LIMIT

    def _record(self, machine_id: str, pressure: float, temp: float, vib: float):
        now = clock.now()
        points = self.history.setdefault(machine_id, [])
        points.append((now, pressure, temp, vib))
        cutoff = now.timestamp() - trend.HISTORY_TTL_S
        while points and points[0][0].timestamp() < cutoff:
            points.pop(0)
        if len(points) > 120:
            del points[:-120]
        return points

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

        points = self._record(machine_id, pressure, temp, vib)
        history_span = trend.span_seconds([(p[0], p[1]) for p in points])

        pressure_points = [(p[0], p[1]) for p in points]
        temp_points = [(p[0], p[2]) for p in points]
        pressure_slope = trend.slope_per_plant_minute(pressure_points)
        temp_slope = trend.slope_per_plant_minute(temp_points)
        slope_known = pressure_slope is not None
        pressure_slope_value = pressure_slope if slope_known else 0.0

        eta_pressure_s = trend.eta_seconds_to_limit(pressure, PRESSURE_LIMIT, pressure_slope)
        temp_limit = self._temp_limit(machine_id)
        temp_warning_at = temp_limit * TEMP_WARNING_FRACTION
        eta_temp_s = trend.eta_seconds_to_limit(temp, temp_limit, temp_slope)

        if slope_known:
            trend_text = f"pressure trend {pressure_slope_value:+.2f} bar/min"
        else:
            trend_text = f"pressure trend not yet established ({history_span:.0f}s of history)"

        # ---- severity from the strongest failing parameter -------------------------------
        reasons: List[str] = []
        severity = "INFO"
        headline = "Warning threshold"

        if pressure >= PRESSURE_CRITICAL or (
            pressure >= PRESSURE_TREND_CRITICAL and slope_known and pressure_slope_value > PRESSURE_SLOPE_CRITICAL
        ):
            severity = "CRITICAL"
            headline = "OVERPRESSURE"
            reasons.append(f"pressure {pressure:.2f} bar over the {PRESSURE_LIMIT:.1f} bar operating limit")
        elif pressure >= PRESSURE_WARNING:
            severity = "WARNING"
            reasons.append(f"pressure {pressure:.2f} bar above the {PRESSURE_WARNING:.1f} bar warning level")

        if temp >= temp_limit:
            severity = "CRITICAL"
            if headline == "Warning threshold":
                headline = "OVERTEMPERATURE"
            reasons.append(f"body temperature {temp:.1f}°C at or over its {temp_limit:.0f}°C limit")
        elif temp >= temp_warning_at:
            severity = "CRITICAL" if severity == "CRITICAL" else "WARNING"
            reasons.append(f"body temperature {temp:.1f}°C within 10% of its {temp_limit:.0f}°C limit")

        if vib >= VIBRATION_WARNING:
            severity = "CRITICAL" if severity == "CRITICAL" else "WARNING"
            reasons.append(f"vibration {vib:.2f} mm/s above the {VIBRATION_WARNING:.1f} mm/s warning level")

        anomaly = severity in ("WARNING", "CRITICAL")

        if anomaly:
            eta_text = ""
            if eta_pressure_s is not None and eta_pressure_s > 0:
                eta_text = f" At the current rate {machine_id} reaches {PRESSURE_LIMIT:.1f} bar in ~{eta_pressure_s:.0f}s."
            elif eta_temp_s is not None and eta_temp_s > 0:
                eta_text = f" At the current rate {machine_id} reaches {temp_limit:.0f}°C in ~{eta_temp_s:.0f}s."
            observation = (
                f"{headline} on {machine_id}: {'; '.join(reasons)} ({trend_text}).{eta_text}"
            )
            decision = (
                f"TRIGGER EMERGENCY SHUTDOWN RECOMMENDED for {machine_id}"
                if severity == "CRITICAL" else
                f"TRIGGER MECHANICAL WARNING for {machine_id}"
            )
        else:
            observation = (
                f"{machine_id} mechanical parameters nominal "
                f"(P={pressure:.1f} bar, T={temp:.1f}°C, Vib={vib:.1f} mm/s, {trend_text})."
            )
            decision = "KPI baseline verified."

        self.update_status(
            task=f"Analyzing real-time kinematics for {machine_id} in {zone}",
            observation=observation,
            decision=decision,
            status="WARNING" if anomaly else "ACTIVE"
        )

        if not anomaly:
            return None

        return {
            "agent_id": self.agent_id,
            "anomaly": True,
            "severity": severity,
            "machine_id": machine_id,
            "zone": zone,
            "pressure": pressure,
            "pressure_slope": pressure_slope_value,
            "temperature": temp,
            "vibration": vib,
            "rpm": rpm,
            # --- added keys (never remove/rename the ones above) ---
            "pressure_slope_known": slope_known,
            "pressure_limit": PRESSURE_LIMIT,
            "temperature_limit": temp_limit,
            "eta_to_pressure_limit_s": eta_pressure_s,
            "eta_to_temperature_limit_s": eta_temp_s,
            "history_span_s": round(history_span, 1),
            "failing_parameters": reasons,
            "observation": observation,
            "decision": decision,
        }
