"""Announce action lifecycle changes on the websocket bus.

Why this exists: `command_engine` published `ACTION_STATUS` when an action was authorised,
started and completed, but **nothing published when an action was created**. The dashboard
subscribes to `ACTION_STATUS` (`frontend/src/App.tsx`) and keeps its own list, so freshly
created `AWAITING_APPROVAL` actions never reached the Command Center — the AUTHORIZE button
only appeared after the operator pressed F5. Found at GATE 1.

The payload shape is exactly what the frontend already expects: `event_type: "ACTION_STATUS"`
with `data` = the serialised `Action`. The event bus routes `ACTION_*` to the `actions`
channel, and the connection manager unions every channel into `all`, which is the channel the
browser connects on.
"""

import logging
from typing import Iterable

logger = logging.getLogger("action_events")


async def publish_action(action, source: str = "ai:orchestrator") -> None:
    """Announce one action's current state. Never raises."""
    try:
        from app.services.event_bus import event_bus
        await event_bus.publish(
            event_type="ACTION_STATUS",
            source=source,
            data=action.model_dump(mode="json"),
            zone=getattr(action, "zone", None) or "ZONE_B",
            severity="INFO",
        )
    except Exception as exc:  # noqa: BLE001 - a broadcast failure must not break the flow
        logger.warning("Could not publish ACTION_STATUS for %s: %s", getattr(action, "id", "?"), exc)


async def publish_actions(actions: Iterable, source: str = "ai:orchestrator") -> None:
    for action in actions:
        await publish_action(action, source=source)
