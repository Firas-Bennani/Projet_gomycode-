import asyncio
from typing import Callable, Dict, List, Any
from datetime import datetime
import uuid
import logging
from app.ws.manager import manager as ws_manager

logger = logging.getLogger("event_bus")

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(
        self,
        event_type: str,
        source: str,
        data: Dict[str, Any],
        zone: str = "GLOBAL",
        severity: str = "INFO",
        correlation_id: str = None,
        metadata: Dict[str, Any] = None
    ):
        event = {
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "event_type": event_type,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "zone": zone,
            "severity": severity,
            "data": data,
            "correlation_id": correlation_id,
            "metadata": metadata or {}
        }

        # Determine websocket channel
        ws_channel = "all"
        if "SENSOR" in event_type:
            ws_channel = "sensors"
        elif "MACHINE" in event_type:
            ws_channel = "machines"
        elif "INCIDENT" in event_type:
            ws_channel = "incidents"
        elif "ACTION" in event_type:
            ws_channel = "actions"
        elif "TWIN" in event_type or "ZONE" in event_type:
            ws_channel = "digital_twin"
        elif "AGENT" in event_type:
            ws_channel = "agents"

        # Broadcast via WebSockets
        try:
            await ws_manager.broadcast_to_channel(ws_channel, {
                "channel": ws_channel,
                "event_type": event_type,
                "timestamp": event["timestamp"],
                "data": event["data"],
                "event": event
            })
        except Exception as e:
            logger.error(f"Error broadcasting event to websocket: {e}")

        # Dispatch to async internal subscribers
        handlers = self._subscribers.get(event_type, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Handler error for event {event_type}: {e}")

        return event

event_bus = EventBus()
