"""
WebSocket Device Hub — v3.10.0

Manages persistent WebSocket connections from device clients.
Enables real-time push of events (config_updated, action_created, force_sync)
to specific devices, eliminating polling latency.

Design:
- One WS per device, authenticated via X-License-Key query param
- Device registry tracks connected/disconnected state
- Push is fire-and-forget per device (errors logged, never raised)
- Idempotent: devices react to push by triggering their existing sync mechanisms
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger("ws_hub")


def _utcnow():
    return datetime.now(timezone.utc)


class DeviceConnection:
    __slots__ = ("device_id", "ws", "connected_at", "last_event_at", "events_sent")

    def __init__(self, device_id: str, ws: WebSocket):
        self.device_id = device_id
        self.ws = ws
        self.connected_at = _utcnow()
        self.last_event_at: Optional[datetime] = None
        self.events_sent: int = 0

    async def send_event(self, event_type: str, data: dict = None) -> bool:
        """Send JSON event. Returns True on success, False on failure."""
        try:
            if self.ws.client_state != WebSocketState.CONNECTED:
                return False
            payload = {"event": event_type, "ts": _utcnow().isoformat()}
            if data:
                payload["data"] = data
            await self.ws.send_json(payload)
            self.last_event_at = _utcnow()
            self.events_sent += 1
            return True
        except Exception as e:
            logger.debug(f"[WS-HUB] Send failed for {self.device_id}: {e}")
            return False


class DeviceWSHub:
    """Central registry of connected device WebSocket connections."""

    def __init__(self):
        self._connections: dict[str, DeviceConnection] = {}
        self._lock = asyncio.Lock()
        self._total_connections: int = 0
        self._total_events_pushed: int = 0

    # ── Connection Management ──

    async def register(self, device_id: str, ws: WebSocket):
        """Register a new device WS connection."""
        async with self._lock:
            old = self._connections.get(device_id)
            if old:
                try:
                    await old.ws.close(code=1000, reason="replaced")
                except Exception:
                    pass
                logger.info(f"[WS-HUB] Device {device_id} reconnected (replaced old)")
            self._connections[device_id] = DeviceConnection(device_id, ws)
            self._total_connections += 1
        logger.info(f"[WS-HUB] Device {device_id} connected ({len(self._connections)} total)")

    async def unregister(self, device_id: str):
        """Remove a device from the registry."""
        async with self._lock:
            self._connections.pop(device_id, None)
        logger.info(f"[WS-HUB] Device {device_id} disconnected ({len(self._connections)} total)")

    # ── Push Events ──

    async def push_to_device(self, device_id: str, event_type: str, data: dict = None):
        """Push an event to a specific device. No-op if not connected."""
        conn = self._connections.get(device_id)
        if not conn:
            return
        ok = await conn.send_event(event_type, data)
        if ok:
            self._total_events_pushed += 1
            logger.debug(f"[WS-HUB] Pushed '{event_type}' to {device_id}")
        else:
            await self.unregister(device_id)

    async def push_to_devices(self, device_ids: list[str], event_type: str, data: dict = None):
        """Push an event to multiple specific devices."""
        for did in device_ids:
            await self.push_to_device(did, event_type, data)

    async def push_to_all(self, event_type: str, data: dict = None):
        """Push an event to ALL connected devices."""
        dead = []
        for did, conn in list(self._connections.items()):
            ok = await conn.send_event(event_type, data)
            if ok:
                self._total_events_pushed += 1
            else:
                dead.append(did)
        for did in dead:
            await self.unregister(did)
        if dead:
            logger.debug(f"[WS-HUB] Broadcast '{event_type}': cleaned {len(dead)} dead connections")

    # ── Status ──

    @property
    def connected_count(self) -> int:
        return len(self._connections)

    def is_connected(self, device_id: str) -> bool:
        return device_id in self._connections

    def status(self) -> dict:
        return {
            "connected_devices": len(self._connections),
            "total_connections": self._total_connections,
            "total_events_pushed": self._total_events_pushed,
            "devices": {
                did: {
                    "connected_at": c.connected_at.isoformat(),
                    "last_event_at": c.last_event_at.isoformat() if c.last_event_at else None,
                    "events_sent": c.events_sent,
                }
                for did, c in self._connections.items()
            },
        }

    def device_ws_status(self, device_id: str) -> dict:
        """Get WS status for a specific device."""
        conn = self._connections.get(device_id)
        if conn:
            return {
                "ws_connected": True,
                "connected_at": conn.connected_at.isoformat(),
                "last_event_at": conn.last_event_at.isoformat() if conn.last_event_at else None,
                "events_sent": conn.events_sent,
            }
        return {"ws_connected": False}


# Singleton
device_ws_hub = DeviceWSHub()
