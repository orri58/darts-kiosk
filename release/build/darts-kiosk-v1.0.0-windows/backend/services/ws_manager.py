"""
WebSocket Manager for Real-Time Board Status
Replaces HTTP polling with push-based updates.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class BoardWSManager:
    """Manages WebSocket connections for live board status broadcasts."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info(f"WS client connected ({len(self._connections)} total)")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
        logger.info(f"WS client disconnected ({len(self._connections)} total)")

    async def broadcast(self, event: str, data: dict):
        """Send an event to ALL connected clients."""
        if not self._connections:
            return

        payload = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self._connections.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)


# Global singleton
board_ws = BoardWSManager()
