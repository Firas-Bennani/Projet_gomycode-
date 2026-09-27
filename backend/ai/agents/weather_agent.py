"""Weather agent: the only agent that reasons about something that has not happened yet.

Every other agent reports what the plant *is* doing. This one reports what the sky is about to do,
which makes its incident **predictive**: there is a lead time, and the whole point is to act before
the event rather than after it. That is also why its confidence comes from the forecast probability
and the instability indicators rather than from a sensor threshold — and why it is capped below
certainty, because a forecast is a forecast.
"""

from typing import Any, Dict, Optional

from ai import weather
from ai.agents.base_agent import BaseAgent


class WeatherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="weather_agent",
            name="Weather & Environmental Forecast Agent"
        )

    @staticmethod
    def _log(reasoning: str, decision: str) -> None:
        """Write straight to the agent log: the strike outcome is worth showing even though it
        creates no new incident."""
        try:
            from ai import clock
            from app.services.state_store import state
            state.agent_logs.insert(0, {
                "timestamp": clock.now(), "agent_id": "weather_agent",
                "input_from": ["STORM_IMPACT"], "reasoning": reasoning,
                "decision": decision, "actions_proposed": [],
            })
            if len(state.agent_logs) > 100:
                state.agent_logs.pop()
        except Exception:
            pass

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event.get("event_type") == "STORM_IMPACT":
            data = event.get("data", {}) or {}
            if data.get("mitigated"):
                self._log(
                    "Storm front arrived over the plant. Load had been shed and the compressor "
                    "setpoint lowered to 6.5 bar, so the surge transient peaked at 6.8 bar "
                    "against an 8.0 bar limit. No overpressure, no trip.",
                    "PREVENTED: the forecast was acted on in time; no incident resulted.")
                self.update_status(
                    task="Storm passing over the site",
                    observation="Storm arrived; mitigations held. Peak 6.8 bar against the "
                                "8.0 bar limit — overpressure prevented.",
                    decision="PREVENTED: no overpressure, no trip.")
            else:
                missing = []
                if not data.get("load_shed"):
                    missing.append("load shedding")
                if not data.get("pressure_setpoint_reduced"):
                    missing.append("the pressure setpoint reduction")
                self._log(
                    "Storm front arrived over the plant with "
                    + (" and ".join(missing) if missing else "no mitigation")
                    + " not authorised. The surge drove M-04 to 8.9 bar, past its 8.0 bar limit.",
                    "NOT PREVENTED: the forecast was not acted on; an overpressure is now real.")
                self.update_status(
                    task="Storm passing over the site",
                    observation="Storm arrived without full mitigation; M-04 driven to 8.9 bar.",
                    decision="NOT PREVENTED: overpressure is now a measured event.",
                    status="WARNING")
            return None

        if event.get("event_type") != "FORECAST_UPDATE":
            return None

        data = event.get("data", {}) or {}
        assessment = weather.assess(data)

        lead = assessment["lead_minutes"]
        source = "Open-Meteo live feed" if assessment["source"] == "open-meteo" else "site forecast feed"

        if not assessment["at_risk"]:
            observation = (
                f"Forecast nominal for the site ({source}): thunderstorm probability "
                f"{assessment['probability']:.0f}%, CAPE {assessment['cape']:.0f} J/kg, "
                f"gusts {assessment['gusts']:.0f} km/h."
            )
            self.update_status(task="Monitoring the site weather forecast",
                               observation=observation, decision="No weather action required.")
            return None

        observation = (
            f"Thunderstorm forecast over the plant in ~{lead} min ({source}): "
            f"probability {assessment['probability']:.0f}%, CAPE {assessment['cape']:.0f} J/kg, "
            f"gusts {assessment['gusts']:.0f} km/h, WMO code {assessment['weather_code']}. "
            f"Exposed: {', '.join(weather.EXPOSED_ASSETS)}. "
            f"This is a prediction with {lead} min of lead time, not a measured event."
        )
        decision = (
            f"PREPARE THE PLANT: shed non-critical load, widen the pressure margin and move "
            f"controllers to UPS before the front arrives in ~{lead} min"
        )

        self.update_status(
            task="Monitoring the site weather forecast",
            observation=observation,
            decision=decision,
            status="WARNING",
        )

        return {
            "agent_id": self.agent_id,
            "anomaly": True,
            "severity": assessment["severity"],
            "zone": event.get("zone") or "GLOBAL",
            "observation": observation,
            "decision": decision,
            # --- predictive specifics ---
            "forecast": True,
            "lead_time_minutes": lead,
            "probability_pct": assessment["probability"],
            "cape_j_per_kg": assessment["cape"],
            "gusts_kmh": assessment["gusts"],
            "weather_code": assessment["weather_code"],
            "instability_indicators": assessment["indicators"],
            "exposed_zones": list(weather.EXPOSED_ZONES),
            "exposed_assets": list(weather.EXPOSED_ASSETS),
            "forecast_source": assessment["source"],
            # The risk engine uses this instead of deriving a likelihood from the severity label:
            # for a forecast, the probability *is* the evidence.
            "source_confidence": assessment["confidence"],
            "source_confidence_math": assessment["confidence_math"],
        }
