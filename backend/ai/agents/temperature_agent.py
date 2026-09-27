from typing import Any, Dict, List, Optional, Tuple

from ai import clock, ml_models, trend
from ai.agents.base_agent import BaseAgent

# Absolute thresholds per sensor family. Kept identical to the original agent so the demo
# scenarios trigger at the same readings as before.
LEVEL_THRESHOLDS = {
    "temperature": {"warning": 35.0, "critical": 50.0},
    "smoke": {"warning": 20.0, "critical": 40.0},
    "water_level": {"warning": 5.0, "critical": 8.0},
    "humidity": {"warning": 70.0, "critical": 85.0},
}

# Rate thresholds, in units per *plant* minute (see ai/trend.py on time compression).
RATE_THRESHOLDS = {
    "temperature": {"warning": 2.0, "critical": 4.0},
    "smoke": {"warning": 1.0, "critical": 3.0},
}


class TemperatureAgent(BaseAgent):
    """Environmental agent: temperature, smoke, water level, humidity.

    Changes vs. the original: the slope is a least-squares fit over the retained history and
    is reported only once the history spans >= 10 s (``ai/trend.MIN_TREND_SPAN_S``). Before
    that the agent says it is still collecting a baseline instead of printing an invented
    rate of change, and rate-based thresholds are simply not evaluated.
    """

    def __init__(self):
        super().__init__(
            agent_id="temperature_agent",
            name="Temperature & Environmental Agent"
        )
        self.history: Dict[str, List[Tuple[Any, float]]] = {}  # sensor_id -> [(timestamp, value)]

    def _record(self, sensor_id: str, value: float) -> List[Tuple[Any, float]]:
        now = clock.now()
        points = self.history.setdefault(sensor_id, [])
        points.append((now, value))
        trend.prune(points, now)
        if len(points) > 120:
            del points[:-120]
        return points

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("event_type", "")
        if event_type != "SENSOR_READING":
            return None

        data = event.get("data", {})
        sensor_type = data.get("type")
        if sensor_type not in LEVEL_THRESHOLDS:
            return None

        sensor_id = data.get("sensor_id")
        val = float(data.get("value", 0.0))
        zone = data.get("zone", "ZONE_B")
        unit = data.get("unit", "°C")

        points = self._record(sensor_id, val)
        history_span = trend.span_seconds(points)

        rate = trend.slope_per_plant_minute(points)
        rate_known = rate is not None
        rate_value = rate if rate_known else 0.0

        levels = LEVEL_THRESHOLDS[sensor_type]
        rates = RATE_THRESHOLDS.get(sensor_type, {})
        sustained_critical = trend.sustained_above(points, levels["critical"])

        # Human-readable trend fragment. Never claims a rate we have not measured.
        if rate_known:
            trend_text = f"trend {rate_value:+.1f} {unit}/min"
        else:
            trend_text = f"trend not yet established ({history_span:.0f}s of history)"

        anomaly = False
        severity = "INFO"

        critical_level = val >= levels["critical"]
        critical_rate = rate_known and "critical" in rates and rate_value >= rates["critical"]
        warning_level = val >= levels["warning"]
        warning_rate = rate_known and "warning" in rates and rate_value >= rates["warning"]

        if critical_level or critical_rate:
            anomaly, severity = True, "CRITICAL"
        elif warning_level or warning_rate:
            anomaly, severity = True, "WARNING"

        # ---- Step 6: the smoke classifier is deliberately NOT used here -----------------
        # It was trained and measured (F1 0.928 on its own test split) and then rejected for
        # this purpose. In the Kaggle Smoke Detection IoT dataset every intuitive fire
        # indicator is *negatively* correlated with the "Fire Alarm" label: PM2.5 -0.085,
        # TVOC -0.215, temperature -0.164, and mean PM2.5 is 78 when alarm=1 versus 450 when
        # alarm=0. The label tracks which trial the test rig was in, not fire physics, which is
        # also why a 12-feature model scores a perfect 1.000 on it.
        # Wiring it to our smoke sensor made it report "0% fire" at 75 ppm in a hot zone. A
        # confidently wrong number on an incident card is worse than no number, so the fire path
        # stays on the rules in FIRE-EP-03 (smoke present + 2 corroborating signals).
        # ml_models.smoke_probability() is kept for the record; see docs/ai/METRICS.md §4.2.
        smoke_ml = None
        observation, decision = self._describe(
            sensor_type, sensor_id, zone, val, unit, severity, trend_text, sustained_critical
        )
        # ---------------------------------------------------------------------------------

        self.update_status(
            task=f"Monitoring environmental sensors in {zone}",
            observation=observation,
            decision=decision,
            status="WARNING" if severity in ("WARNING", "CRITICAL") else "ACTIVE"
        )

        if not anomaly:
            return None

        return {
            "agent_id": self.agent_id,
            "anomaly": True,
            "severity": severity,
            "sensor_id": sensor_id,
            "sensor_type": sensor_type,
            "zone": zone,
            "current_value": val,
            "unit": unit,
            "rate_of_change": rate_value,
            # --- added keys (never remove/rename the ones above) ---
            "rate_known": rate_known,
            "history_span_s": round(history_span, 1),
            "readings": len(points),
            "sustained_critical": sustained_critical,
            # --- Step 6 model annotation (None when no model or no temperature available) ---
            "smoke_probability": smoke_ml["smoke_probability"] if smoke_ml else None,
            "smoke_model": smoke_ml["model"] if smoke_ml else None,
            "threshold_warning": levels["warning"],
            "threshold_critical": levels["critical"],
            "observation": observation,
            "decision": decision,
        }

    @staticmethod
    def _zone_temperature(zone: str):
        """Latest ambient temperature for the zone, from the state store. None if unknown."""
        try:
            from app.services.state_store import state
            for sensor in state.sensors.values():
                if sensor.type == "temperature" and sensor.zone == zone:
                    return float(sensor.current_value)
        except Exception:
            pass
        return None

    def _describe(self, sensor_type, sensor_id, zone, val, unit, severity, trend_text, sustained):
        """Observation and decision strings, built from the real readings."""
        if sensor_type == "temperature":
            if severity == "CRITICAL":
                return (
                    f"Critical thermal level in {zone}: {val:.1f}{unit} on {sensor_id} "
                    f"({trend_text}, critical threshold {LEVEL_THRESHOLDS['temperature']['critical']:.0f}{unit}).",
                    f"TRIGGER CRITICAL THERMAL ALERT for {zone}",
                )
            if severity == "WARNING":
                return (
                    f"Elevated temperature in {zone}: {val:.1f}{unit} on {sensor_id} "
                    f"({trend_text}, warning threshold {LEVEL_THRESHOLDS['temperature']['warning']:.0f}{unit}).",
                    f"TRIGGER WARNING THERMAL ALERT for {zone}",
                )
            return (
                f"{zone} temperature nominal at {val:.1f}{unit} ({trend_text}).",
                "Environmental baseline verified.",
            )

        if sensor_type == "smoke":
            if severity == "CRITICAL":
                persistence = (
                    " Reading has persisted above the critical level across consecutive samples."
                    if sustained else
                    " Single sample above the critical level — awaiting confirmation."
                )
                return (
                    f"High particulate density in {zone}: {val:.1f} {unit} on {sensor_id} "
                    f"({trend_text}).{persistence}",
                    f"TRIGGER CRITICAL SMOKE/FIRE ALERT for {zone}",
                )
            if severity == "WARNING":
                return (
                    f"Trace combustion aerosols in {zone}: {val:.1f} {unit} on {sensor_id} ({trend_text}).",
                    f"TRIGGER WARNING SMOKE ALERT for {zone}",
                )
            return (
                f"{zone} air quality nominal at {val:.1f} {unit} ({trend_text}).",
                "Environmental baseline verified.",
            )

        if sensor_type == "water_level":
            if severity in ("WARNING", "CRITICAL"):
                return (
                    f"Flooding risk in {zone}: {sensor_id} reading {val:.1f} {unit} ({trend_text}).",
                    f"TRIGGER FLOOD HAZARD ALERT for {zone}",
                )
            return (
                f"{zone} water level nominal at {val:.1f} {unit}.",
                "Environmental baseline verified.",
            )

        # humidity and any future sensor family
        if severity in ("WARNING", "CRITICAL"):
            return (
                f"{sensor_type.replace('_', ' ').title()} out of range in {zone}: "
                f"{val:.1f} {unit} on {sensor_id} ({trend_text}).",
                f"TRIGGER {severity} ENVIRONMENTAL ALERT for {zone}",
            )
        return (
            f"{zone} {sensor_type} nominal at {val:.1f} {unit}.",
            "Environmental baseline verified.",
        )
