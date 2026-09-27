"""Per-zone sliding window of agent observations.

This is the fix for the correlation bug. The simulator publishes the Zone B temperature
reading and the M-04 machine status as two *separate* events. The old orchestrator called
``synthesize_incident()`` with only the observations produced by the event it was handling,
so the temperature evidence and the machine evidence never met — and the fire rule, whose
guard was "hot but no machine evidence", fired on an overheating compressor.

The window keeps the freshest observation per ``(agent_id, asset)`` pair per zone for
:data:`DEFAULT_TTL_S` seconds, so the recommendation agent always reasons over everything
the plant has said about that zone recently, not over one packet.
"""

from typing import Any, Dict, List, Optional, Tuple

from ai import clock

#: How long an observation stays relevant for correlation (seconds).
DEFAULT_TTL_S = 30.0


def asset_key(observation: Dict[str, Any]) -> str:
    """Identify *what* an observation is about, so a new reading replaces the old one."""
    for field in ("machine_id", "sensor_id", "device", "worker_id"):
        value = observation.get(field)
        if value:
            return str(value)
    return "zone"


class ObservationWindow:
    def __init__(self, ttl_s: float = DEFAULT_TTL_S):
        self.ttl_s = ttl_s
        # zone -> {(agent_id, asset): (timestamp, observation)}
        self._by_zone: Dict[str, Dict[Tuple[str, str], Tuple[Any, Dict[str, Any]]]] = {}

    def add(self, observation: Dict[str, Any], zone: Optional[str] = None) -> str:
        """Store an observation, replacing any earlier one from the same agent+asset."""
        resolved_zone = observation.get("zone") or zone or "GLOBAL"
        key = (observation.get("agent_id", "unknown"), asset_key(observation))
        self._by_zone.setdefault(resolved_zone, {})[key] = (clock.now(), observation)
        return resolved_zone

    def snapshot(self, zone: str) -> List[Dict[str, Any]]:
        """Fresh observations for ``zone``, oldest first. Expired entries are dropped."""
        bucket = self._by_zone.get(zone)
        if not bucket:
            return []
        cutoff = clock.now().timestamp() - self.ttl_s
        for key in [k for k, (ts, _) in bucket.items() if ts.timestamp() < cutoff]:
            del bucket[key]
        return [obs for _, obs in sorted(bucket.values(), key=lambda item: item[0])]

    def zones(self) -> List[str]:
        return list(self._by_zone.keys())

    def clear(self, zone: Optional[str] = None) -> None:
        """Forget observations — for a zone once its incident is resolved, or everything."""
        if zone is None:
            self._by_zone.clear()
        else:
            self._by_zone.pop(zone, None)
