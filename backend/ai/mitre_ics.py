"""Look up MITRE ATT&CK for ICS techniques **in the published STIX bundle**, never from memory.

Technique ids and names are easy to misremember and a wrong `T0xxx` on an incident card is the
kind of detail a security-literate jury will catch. So the cyber agent names a behaviour in
words, and this module searches the bundle for a technique whose name matches. If the bundle is
not on disk, or nothing matches, the caller gets ``None`` and simply omits the attribution rather
than inventing one.

Bundle location, in order: ``MITRE_ICS_PATH``, then ``backend/ai/data/raw/mitre/ics-attack.json``,
then ``Dataset/MITRE ATT&CK for ICS.json`` (where Firas downloaded it). Source:
https://github.com/mitre-attack/attack-stix-data — ``ics-attack/ics-attack.json``.
"""

import json
import logging
import os
import pathlib
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mitre_ics")

REPO = pathlib.Path(__file__).resolve().parents[2]
CANDIDATE_PATHS = [
    pathlib.Path(os.getenv("MITRE_ICS_PATH", "")) if os.getenv("MITRE_ICS_PATH") else None,
    REPO / "backend" / "ai" / "data" / "raw" / "mitre" / "ics-attack.json",
    REPO / "Dataset" / "MITRE ATT&CK for ICS.json",
]

#: Words to search the bundle for, per behaviour the cyber agent can name, plus an optional
#: parent-id preference to break ties. The *file* decides which technique those words resolve to.
#:
#: Worth knowing: the ids a lot of ICS material still quotes are **revoked** in the current
#: bundle. `T0855 Unauthorized Command Message` and `T0856 Spoof Reporting Message` are both
#: revoked=1 here, superseded by `T1692 Unauthorized Message` with `T1692.001 Command Message`
#: and `T1692.002 Reporting Message`. Quoting T0855 today would be wrong — which is the whole
#: argument for reading the file instead of trusting memory.
RULE_LOOKUP = {
    "BRUTE_FORCE": {"phrases": ["brute force"]},
    "UNKNOWN_DEVICE": {"phrases": ["rogue master"]},
    "UNAUTHORIZED_COMMAND": {"phrases": ["unauthorized message", "command message"],
                             "prefer_prefix": "T1692"},
    "SPOOFED_SENSOR": {"phrases": ["spoof reporting message", "reporting message"],
                       "prefer_prefix": "T1692"},
    "TRAFFIC_ANOMALY": {"phrases": ["network sniffing"]},
    "CREDENTIAL_ABUSE": {"phrases": ["valid accounts"]},
}

#: Kept for backwards compatibility with anything reading the old name.
RULE_KEYWORDS = {rule: spec["phrases"] for rule, spec in RULE_LOOKUP.items()}

_index: Optional[List[Dict[str, Any]]] = None


def _bundle_path() -> Optional[pathlib.Path]:
    for candidate in CANDIDATE_PATHS:
        if candidate and candidate.exists():
            return candidate
    return None


def _load() -> List[Dict[str, Any]]:
    """Index the bundle's techniques once. Returns [] when the bundle is unavailable."""
    global _index
    if _index is not None:
        return _index
    _index = []
    path = _bundle_path()
    if path is None:
        logger.info("MITRE ATT&CK for ICS bundle not found; technique attribution disabled.")
        return _index
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for obj in data.get("objects", []):
            if obj.get("type") != "attack-pattern":
                continue
            if obj.get("revoked") or obj.get("x_mitre_deprecated"):
                continue
            reference = next((r for r in obj.get("external_references", [])
                              if r.get("source_name") == "mitre-attack"), None)
            if not reference or not reference.get("external_id"):
                continue
            _index.append({
                "technique_id": reference["external_id"],
                "name": obj.get("name", ""),
                "url": reference.get("url", ""),
                "is_subtechnique": bool(obj.get("x_mitre_is_subtechnique")),
                "tactics": [p.get("phase_name") for p in obj.get("kill_chain_phases", [])],
            })
        logger.info("Indexed %d ATT&CK for ICS techniques from %s", len(_index), path.name)
    except Exception as exc:  # noqa: BLE001 - never let a bad file break the cyber agent
        logger.warning("Could not read the ATT&CK bundle at %s (%s).", path, exc)
        _index = []
    return _index


def reset_cache() -> None:
    global _index
    _index = None


def available() -> bool:
    return bool(_load())


def find(*keywords: str, prefer_prefix: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The best technique whose *name* matches all the words of any keyword phrase.

    Phrases are tried in order, so the caller can go from most to least specific. Within one
    phrase's matches, a technique under ``prefer_prefix`` wins (several ICS sub-techniques share
    a name such as "Reporting Message" under different parents), then top-level over
    sub-technique, then the shortest name.
    """
    techniques = _load()
    if not techniques:
        return None
    for phrase in keywords:
        words = [w for w in phrase.lower().split() if w]
        matches = [t for t in techniques if all(w in t["name"].lower() for w in words)]
        if not matches:
            continue
        matches.sort(key=lambda t: (
            not (prefer_prefix and t["technique_id"].startswith(prefer_prefix)),
            t["is_subtechnique"],
            len(t["name"]),
        ))
        return matches[0]
    return None


def for_rule(rule: str) -> Optional[Dict[str, Any]]:
    """Technique attribution for one of the cyber agent's rules, or ``None``."""
    spec = RULE_LOOKUP.get(rule)
    if not spec:
        return None
    return find(*spec["phrases"], prefer_prefix=spec.get("prefer_prefix"))


def describe(technique: Optional[Dict[str, Any]]) -> str:
    if not technique:
        return ""
    return f"{technique['technique_id']} {technique['name']}"
