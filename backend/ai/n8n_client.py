"""Outbound side of the n8n bridge.

Design rule for the whole feature: **detection never depends on n8n.** Every call in this
module is fire-and-forget with a short timeout and swallows its own errors. If n8n is down,
slow, or was never started, incidents are still detected, actions are still created from the
deterministic templates, and the only visible difference is a line in the agent log saying
the enrichment did not arrive.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("n8n_client")


def _load_env_files() -> None:
    """Load `.env` from the repo root and from `backend/` into the process environment.

    `app/config.py` reads `.env` through pydantic-settings, which populates a Settings object
    but does **not** put the values in `os.environ` — and everything in this module reads
    `os.getenv`. Without this, editing `.env` would silently have no effect on the bridge.
    Real environment variables always win (`override=False`).
    """
    try:
        from dotenv import load_dotenv
    except Exception:  # python-dotenv missing: defaults below are already correct for local use
        return
    here = os.path.dirname(os.path.abspath(__file__))          # backend/ai
    backend_dir = os.path.dirname(here)                        # backend
    repo_root = os.path.dirname(backend_dir)                   # repo
    for candidate in (os.path.join(repo_root, ".env"), os.path.join(backend_dir, ".env")):
        if os.path.exists(candidate):
            load_dotenv(candidate, override=False)


_load_env_files()

#: incident_id -> the n8n Wait node's resume URL. Lives here, not in schemas.py.
RESUME_URLS: Dict[str, str] = {}

#: incident_id -> short note about the last n8n exchange, surfaced by the bridge router.
LAST_EXCHANGE: Dict[str, Dict[str, Any]] = {}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def enabled() -> bool:
    return _env("N8N_ENABLED", "true").lower() in ("1", "true", "yes", "on")


def incident_webhook_url() -> str:
    return _env("N8N_INCIDENT_WEBHOOK_URL", "http://localhost:5678/webhook/incident")


def timeout_seconds() -> float:
    try:
        return float(_env("N8N_TIMEOUT_SECONDS", "3"))
    except ValueError:
        return 3.0


def backend_base_for_n8n() -> str:
    """The URL n8n should use to call us back. Sent in the payload so the workflow JSON
    itself never hardcodes a host.

    Default suits our actual setup: n8n on the host via `npx n8n`, backend on the host in the
    venv. If both ever run inside docker compose, set `BACKEND_BASE_URL_FOR_N8N=http://backend:8000`;
    for n8n in Docker reaching a host backend, `http://host.docker.internal:8000`.
    """
    return _env("BACKEND_BASE_URL_FOR_N8N", "http://localhost:8000")


def _running_in_container() -> bool:
    return os.path.exists("/.dockerenv")


def rewrite_resume_url(url: str) -> str:
    """Make a resume URL reachable from wherever this backend is running.

    n8n builds resume URLs from its own ``WEBHOOK_URL`` (``http://localhost:5678``), which is
    correct for a backend on the host but unreachable from inside the compose network. When we
    are in a container, swap the public base for the internal one.
    """
    public = _env("N8N_PUBLIC_BASE")
    internal = _env("N8N_INTERNAL_BASE")
    if url and public and internal and _running_in_container() and url.startswith(public):
        return internal + url[len(public):]
    return url


def register_resume_url(incident_id: str, url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    resolved = rewrite_resume_url(url)
    RESUME_URLS[incident_id] = resolved
    return resolved


def get_resume_url(incident_id: str) -> Optional[str]:
    return RESUME_URLS.get(incident_id)


def clear_resume_urls() -> None:
    RESUME_URLS.clear()
    LAST_EXCHANGE.clear()


def _note(incident_id: str, status: str, detail: str) -> None:
    LAST_EXCHANGE[incident_id] = {
        "status": status,
        "detail": detail,
        "at": datetime.utcnow().isoformat(),
    }


def build_incident_payload(incident, evidence_observations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything n8n needs, including the menu of actions the LLM may choose from."""
    from ai.actions_catalog import allowed_actions_for

    try:
        from app.services.state_store import state
        workers = [
            {"id": w.id, "name": w.name, "role": w.role, "zone": w.zone, "status": w.status}
            for w in state.workers.values() if w.id in incident.affected_workers
        ]
    except Exception:
        workers = [{"id": w} for w in incident.affected_workers]

    return {
        "incident": incident.model_dump(mode="json"),
        "incident_id": incident.id,
        "allowed_actions": allowed_actions_for(incident),
        "workers": workers,
        "evidence": [
            {"source": e.source, "detail": e.detail,
             "timestamp": e.timestamp.isoformat() if e.timestamp else None}
            for e in incident.evidence
        ],
        "observations": evidence_observations or [],
        "backend_base_url": backend_base_for_n8n(),
        "sent_at": datetime.utcnow().isoformat(),
    }


async def notify_incident(incident, evidence_observations: List[Dict[str, Any]] = None) -> bool:
    """POST a new incident to the n8n webhook. Returns True only if n8n accepted it.

    Never raises and never blocks for more than ``N8N_TIMEOUT_SECONDS``.
    """
    if not enabled():
        _note(incident.id, "DISABLED", "N8N_ENABLED is false; using template recommendations.")
        return False

    url = incident_webhook_url()
    payload = build_incident_payload(incident, evidence_observations)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout_seconds()) as client:
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            _note(incident.id, "REJECTED", f"n8n returned HTTP {response.status_code} from {url}")
            logger.warning("n8n webhook %s returned HTTP %s for %s", url, response.status_code, incident.id)
            return False
        _note(incident.id, "SENT", f"n8n accepted {incident.id} (HTTP {response.status_code}).")
        logger.info("Sent %s to n8n at %s", incident.id, url)
        return True
    except Exception as exc:  # noqa: BLE001 - deliberately never propagates
        _note(incident.id, "UNREACHABLE", f"{type(exc).__name__}: {exc}")
        logger.warning(
            "n8n unreachable at %s (%s: %s). Incident %s keeps its template recommendations.",
            url, type(exc).__name__, exc, incident.id,
        )
        return False


def notify_incident_background(incident, evidence_observations: List[Dict[str, Any]] = None) -> None:
    """Schedule :func:`notify_incident` without awaiting it, so detection is never delayed."""
    try:
        asyncio.create_task(notify_incident(incident, evidence_observations))
    except RuntimeError:
        # No running loop (e.g. a synchronous unit test) — skip silently.
        logger.debug("No event loop; skipped n8n notification for %s", getattr(incident, "id", "?"))


async def send_decision(incident_id: str, decision: str, action_id: str, by: str) -> bool:
    """Resume the waiting n8n execution with the owner's decision.

    Called from ``command_engine`` when the owner presses AUTHORIZE or CANCEL in the UI.
    """
    url = get_resume_url(incident_id)
    if not url:
        return False
    body = {"decision": decision, "action_id": action_id, "by": by, "incident_id": incident_id}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout_seconds()) as client:
            response = await client.post(url, json=body)
        ok = response.status_code < 400
        _note(incident_id, "RESUMED" if ok else "RESUME_FAILED",
              f"decision={decision} action={action_id} HTTP {response.status_code}")
        if ok:
            logger.info("Resumed n8n execution for %s with decision=%s", incident_id, decision)
        return ok
    except Exception as exc:  # noqa: BLE001
        _note(incident_id, "RESUME_FAILED", f"{type(exc).__name__}: {exc}")
        logger.warning("Could not resume n8n execution for %s: %s", incident_id, exc)
        return False


def send_decision_background(incident_id: str, decision: str, action_id: str, by: str) -> None:
    if not enabled() or not get_resume_url(incident_id):
        return
    try:
        asyncio.create_task(send_decision(incident_id, decision, action_id, by))
    except RuntimeError:
        logger.debug("No event loop; skipped n8n resume for %s", incident_id)
