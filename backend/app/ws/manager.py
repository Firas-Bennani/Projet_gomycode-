from fastapi import WebSocket
from typing import Dict, Set, Any
import json
import logging
import asyncio

logger = logging.getLogger("ws_manager")

class ConnectionManager:
    def __init__(self):
        # channel -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "all": set(),
            "sensors": set(),
            "machines": set(),
            "incidents": set(),
            "actions": set(),
            "digital_twin": set(),
            "agents": set(),
        }

    async def connect(self, websocket: WebSocket, channel: str = "all"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self.active_connections["all"].add(websocket)
        logger.info(f"WebSocket client connected to channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str = "all"):
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
        if websocket in self.active_connections["all"]:
            self.active_connections["all"].remove(websocket)
        logger.info(f"WebSocket client disconnected from channel: {channel}")

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        payload = json.dumps(message, default=str)
        # Send to specific channel listeners
        target_connections = set(self.active_connections.get(channel, [])) | self.active_connections.get("all", set())
        dead_sockets = []

        for connection in target_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                dead_sockets.append(connection)

        for dead in dead_sockets:
            for ch in self.active_connections:
                if dead in self.active_connections[ch]:
                    self.active_connections[ch].remove(dead)

    async def broadcast(self, message: Dict[str, Any]):
        channel = message.get("channel", "all")
        await self.broadcast_to_channel(channel, message)

manager = ConnectionManager()
