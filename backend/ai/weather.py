"""Site weather forecast: deterministic by default, Open-Meteo optionally.

The demo must never depend on the network, so the default source is a deterministic simulated
forecast driven by the scenario step. Set `WEATHER_LIVE=true` to fetch the real thing from
Open-Meteo (free, no API key); if that call fails for any reason the simulated forecast is used and
the incident says which source it came from.

**Variable names were verified against the live API**, not assumed
(`GET https://api.open-meteo.com/v1/forecast?...&hourly=weather_code,precipitation_probability,cape,wind_gusts_10m`):

| field | unit as returned |
|---|---|
| `weather_code` | WMO code |
| `precipitation_probability` | % |
| `cape` | J/kg |
| `wind_gusts_10m` | km/h |

`THUNDERSTORM_CODES` are the WMO thunderstorm codes Open-Meteo documents: 95 thunderstorm,
96 thunderstorm with slight hail, 99 thunderstorm with heavy hail.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("weather")

#: WMO codes that mean thunderstorm in Open-Meteo's documented mapping.
THUNDERSTORM_CODES = {95, 96, 99}

#: Thresholds from SEVERE-WEATHER-PROCEDURE §2.
PROBABILITY_WARNING = 50.0      # %
PROBABILITY_CRITICAL = 70.0     # %
CAPE_MODERATE = 1000.0          # J/kg — moderate instability
CAPE_STRONG = 2000.0            # J/kg — strong instability
GUST_WARNING = 60.0             # km/h
GUST_CRITICAL = 90.0            # km/h

#: Zones exposed to an electrical storm, from SEVERE-WEATHER-PROCEDURE §1.
EXPOSED_ZONES = ["ZONE_B", "ZONE_D"]
EXPOSED_ASSETS = ["Outdoor switchyard", "Electrical room B", "Compressor house (M-04)"]

SITE_LAT = float(os.getenv("SITE_LATITUDE", "36.80"))
SITE_LON = float(os.getenv("SITE_LONGITUDE", "10.18"))


def live_enabled() -> bool:
    return os.getenv("WEATHER_LIVE", "false").strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------- simulated

#: A storm building over the site. Index = scenario step, so the demo is identical every run.
#: lead_minutes counts down: the front is approaching.
SIMULATED_TIMELINE = [
    {"lead_minutes": 95, "probability": 24.0, "cape": 320.0,  "gusts": 28.0, "weather_code": 3},
    {"lead_minutes": 80, "probability": 41.0, "cape": 780.0,  "gusts": 37.0, "weather_code": 80},
    {"lead_minutes": 65, "probability": 58.0, "cape": 1240.0, "gusts": 46.0, "weather_code": 81},
    {"lead_minutes": 52, "probability": 71.0, "cape": 1810.0, "gusts": 58.0, "weather_code": 95},
    {"lead_minutes": 40, "probability": 82.0, "cape": 2350.0, "gusts": 70.0, "weather_code": 95},
    {"lead_minutes": 28, "probability": 88.0, "cape": 2610.0, "gusts": 78.0, "weather_code": 96},
    {"lead_minutes": 15, "probability": 91.0, "cape": 2740.0, "gusts": 84.0, "weather_code": 96},
]


def simulated_forecast(step: int) -> Dict[str, Any]:
    entry = SIMULATED_TIMELINE[min(max(step, 0), len(SIMULATED_TIMELINE) - 1)]
    return {**entry, "source": "simulated", "site": {"lat": SITE_LAT, "lon": SITE_LON}}


# --------------------------------------------------------------------- live

def live_forecast(timeout: float = 4.0) -> Optional[Dict[str, Any]]:
    """The next thunderstorm hour from Open-Meteo, or ``None``. Never raises."""
    try:
        import json
        import urllib.request
        from datetime import datetime

        url = (f"https://api.open-meteo.com/v1/forecast?latitude={SITE_LAT}&longitude={SITE_LON}"
               "&hourly=weather_code,precipitation_probability,cape,wind_gusts_10m"
               "&forecast_days=1")
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.load(response)
        hourly = data.get("hourly", {})
        times = hourly.get("time") or []
        if not times:
            return None

        now = datetime.utcnow()
        best = None
        for index, stamp in enumerate(times):
            try:
                when = datetime.fromisoformat(stamp)
            except ValueError:
                continue
            lead = (when - now).total_seconds() / 60.0
            if lead < 0:
                continue
            candidate = {
                "lead_minutes": round(lead),
                "probability": float(hourly.get("precipitation_probability", [0])[index] or 0),
                "cape": float(hourly.get("cape", [0])[index] or 0),
                "gusts": float(hourly.get("wind_gusts_10m", [0])[index] or 0),
                "weather_code": int(hourly.get("weather_code", [0])[index] or 0),
            }
            # Prefer the soonest thunderstorm hour; otherwise keep the soonest hour at all.
            if candidate["weather_code"] in THUNDERSTORM_CODES:
                best = candidate
                break
            if best is None:
                best = candidate
        if best is None:
            return None
        return {**best, "source": "open-meteo", "site": {"lat": SITE_LAT, "lon": SITE_LON}}
    except Exception as exc:  # noqa: BLE001 - the demo must not depend on the network
        logger.info("Open-Meteo unavailable (%s); using the simulated forecast.", exc)
        return None


def current_forecast(step: int) -> Dict[str, Any]:
    """Live when enabled and reachable, simulated otherwise. Always returns something."""
    if live_enabled():
        live = live_forecast()
        if live:
            return live
    return simulated_forecast(step)


# --------------------------------------------------------------------- assessment

def assess(forecast: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a forecast into a graded risk, with the arithmetic kept so it can be shown.

    Confidence is the forecast probability, adjusted up by the instability indicators that make a
    thunderstorm forecast more trustworthy: a WMO thunderstorm code, CAPE, and gust speed. It is
    never allowed to reach certainty — a forecast is a forecast.
    """
    probability = float(forecast.get("probability", 0.0))
    cape = float(forecast.get("cape", 0.0))
    gusts = float(forecast.get("gusts", 0.0))
    code = int(forecast.get("weather_code", 0))

    base = probability / 100.0
    indicators = []
    boost = 0.0
    if code in THUNDERSTORM_CODES:
        boost += 0.06
        indicators.append(f"WMO code {code} (thunderstorm)")
    if cape >= CAPE_STRONG:
        boost += 0.05
        indicators.append(f"CAPE {cape:.0f} J/kg (strong instability, >= {CAPE_STRONG:.0f})")
    elif cape >= CAPE_MODERATE:
        boost += 0.03
        indicators.append(f"CAPE {cape:.0f} J/kg (moderate instability, >= {CAPE_MODERATE:.0f})")
    if gusts >= GUST_CRITICAL:
        boost += 0.04
        indicators.append(f"gusts {gusts:.0f} km/h (>= {GUST_CRITICAL:.0f})")
    elif gusts >= GUST_WARNING:
        boost += 0.02
        indicators.append(f"gusts {gusts:.0f} km/h (>= {GUST_WARNING:.0f})")

    confidence = round(min(base + boost, 0.97), 3)

    severity = "INFO"
    if probability >= PROBABILITY_CRITICAL and (code in THUNDERSTORM_CODES or cape >= CAPE_MODERATE):
        severity = "CRITICAL"
    elif probability >= PROBABILITY_WARNING:
        severity = "WARNING"

    return {
        "at_risk": severity in ("WARNING", "CRITICAL"),
        "severity": severity,
        "confidence": confidence,
        "confidence_math": (f"forecast probability {probability:.0f}% = {base:.2f}"
                            + (f", +{boost:.2f} from " + "; ".join(indicators) if indicators else "")
                            + f" -> {confidence:.2f} (a forecast, capped at 0.97)"),
        "indicators": indicators,
        "probability": probability,
        "cape": cape,
        "gusts": gusts,
        "weather_code": code,
        "lead_minutes": int(forecast.get("lead_minutes", 0)),
        "source": forecast.get("source", "simulated"),
    }
