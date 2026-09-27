"""Remember the last good LLM explanation per hazard type, and replay it when the model fails.

Measured reality (docs/ai/METRICS.md §2): on the Gemini free tier only **1 of 5** attempts
returned an answer. The other four were Google-side — a retired model (404), the 5-per-minute
quota (429) and model overload (503). Each fell back to the deterministic template, which is
correct but visibly plainer, and on a demo stage it is the difference between showing the
product and showing its safety net.

So the chain becomes:

    live LLM  ->  cached LLM answer (clearly labelled and dated)  ->  deterministic template

The cache is keyed by **incident type**, not by incident id: two overheating incidents are the
same explanation problem, and the whole point is to have something ready before the incident that
needs it exists. The replayed text is always stamped with where it came from and when, so nobody
can mistake a cached answer for a live one. Action ids from a cached answer are re-validated
against the catalogue exactly like live ones — a stale id is rejected, not trusted.

The cache is persisted to ``backend/ai/data/llm_cache.json`` so it survives a backend restart and
can be warmed before a demo, or committed so the demo works with no internet at all.
"""

import json
import logging
import pathlib
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("llm_cache")

CACHE_PATH = pathlib.Path(__file__).resolve().parent / "data" / "llm_cache.json"

#: Fields worth replaying. Deliberately only the wording and the chosen action ids — never a
#: confidence, a severity or a risk level, all of which are ours to compute.
REPLAYABLE = ("what", "why", "impact", "prediction", "recommended_action_ids", "sources")

_cache: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    try:
        if CACHE_PATH.exists():
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            logger.info("Loaded %d cached LLM answer(s) from %s",
                        len(_cache), CACHE_PATH.name)
    except Exception as exc:  # noqa: BLE001 - a bad cache file must never break enrichment
        logger.warning("Could not read %s (%s); starting with an empty cache.", CACHE_PATH, exc)
        _cache = {}
    return _cache


def _save() -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(_load(), indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not write %s (%s).", CACHE_PATH, exc)


def remember(incident_type: str, payload: Dict[str, Any], produced_by: str) -> None:
    """Store a *live* LLM answer for this hazard type. Overwrites any older one."""
    entry = {field: payload.get(field) for field in REPLAYABLE}
    entry["produced_by"] = produced_by
    entry["cached_at"] = datetime.utcnow().isoformat(timespec="seconds")
    cache = _load()
    cache[incident_type] = entry
    _save()
    logger.info("Cached a live %s answer for %s", produced_by, incident_type)


def recall(incident_type: str) -> Optional[Dict[str, Any]]:
    """The last good LLM answer for this hazard type, or ``None``."""
    entry = _load().get(incident_type)
    if not entry or not entry.get("what"):
        return None
    return entry


def describe(entry: Dict[str, Any]) -> str:
    """Provenance label for a replayed answer — always says it is cached, and when."""
    when = entry.get("cached_at", "an earlier run")
    return f"cached {entry.get('produced_by', 'LLM')} answer from {when}"


def status() -> Dict[str, Any]:
    cache = _load()
    return {
        "path": str(CACHE_PATH),
        "exists": CACHE_PATH.exists(),
        "types_cached": sorted(cache.keys()),
        "entries": {
            key: {"produced_by": value.get("produced_by"), "cached_at": value.get("cached_at"),
                  "action_ids": value.get("recommended_action_ids"),
                  "sources": value.get("sources")}
            for key, value in cache.items()
        },
    }


def clear() -> None:
    global _cache
    _cache = {}
    try:
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()
    except Exception:
        pass


def reset_memory() -> None:
    """Forget the in-process copy without deleting the file (used by tests)."""
    global _cache
    _cache = None
