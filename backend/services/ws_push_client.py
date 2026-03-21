"""
WebSocket Push Client — v3.10.0

Connects to the Central Server's WS endpoint for real-time push events.
Triggers immediate config sync or action poll when events arrive,
eliminating the latency of periodic polling.

Design:
- Enhancement only: polling continues in parallel as fallback
- Reconnect with exponential backoff (5s → 10s → 20s → max 60s)
- Idempotent: events trigger existing sync_now / poll_once which are lock-protected
- Never blocks, never crashes, all errors caught and logged
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("ws_push_client")

_MIN_BACKOFF = 5
_MAX_BACKOFF = 60
_PING_INTERVAL = 45  # send ping every 45s to keep connection alive


def _utcnow():
    return datetime.now(timezone.utc)


class WSPushClient:
    def __init__(self):
        self._central_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._running = False
        self._connected = False
        self._ws = None

        # Stats
        self._connected_at: Optional[datetime] = None
        self._disconnected_at: Optional[datetime] = None
        self._last_event_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._events_received: int = 0
        self._reconnect_count: int = 0
        self._consecutive_failures: int = 0

        # Callbacks
        self._on_config_updated = None
        self._on_action_created = None

    def configure(self, central_url: str, api_key: str):
        """Configure the WS client with central server URL and API key."""
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        if self._central_url and self._api_key:
            logger.info(f"[WS-PUSH] Configured: {self._central_url}")
        else:
            logger.info("[WS-PUSH] Not configured (missing URL or API key)")

    def set_handlers(self, on_config_updated=None, on_action_created=None):
        """Register async callbacks for push events."""
        self._on_config_updated = on_config_updated
        self._on_action_created = on_action_created

    @property
    def is_configured(self):
        return bool(self._central_url and self._api_key)

    @property
    def is_connected(self):
        return self._connected

    @property
    def status(self) -> dict:
        return {
            "configured": self.is_configured,
            "connected": self._connected,
            "connected_at": self._connected_at.isoformat() if self._connected_at else None,
            "disconnected_at": self._disconnected_at.isoformat() if self._disconnected_at else None,
            "last_event_at": self._last_event_at.isoformat() if self._last_event_at else None,
            "last_error": self._last_error,
            "events_received": self._events_received,
            "reconnect_count": self._reconnect_count,
            "consecutive_failures": self._consecutive_failures,
        }

    # ── Lifecycle ──

    async def start(self):
        """Start the WS client with auto-reconnect loop."""
        if self._running or not self.is_configured:
            if not self.is_configured:
                logger.info("[WS-PUSH] Skipping start — not configured")
            return
        self._running = True
        logger.info("[WS-PUSH] Starting push client")
        asyncio.create_task(self._connect_loop())

    def stop(self):
        """Stop the WS client."""
        self._running = False
        self._connected = False
        if self._ws:
            try:
                # Will be closed in the connect loop
                pass
            except Exception:
                pass
        logger.info("[WS-PUSH] Stopped")

    # ── Connection Loop ──

    async def _connect_loop(self):
        """Main reconnect loop with exponential backoff."""
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                self._last_error = str(e)
                logger.debug(f"[WS-PUSH] Connection error: {e}")

            self._connected = False
            self._disconnected_at = _utcnow()

            if not self._running:
                break

            self._consecutive_failures += 1
            backoff = min(_MIN_BACKOFF * (2 ** min(self._consecutive_failures - 1, 4)), _MAX_BACKOFF)
            logger.info(f"[WS-PUSH] Reconnecting in {backoff}s (attempt #{self._consecutive_failures})")
            await asyncio.sleep(backoff)

    async def _connect_and_listen(self):
        """Connect to central WS and process events."""
        import websockets

        # Build WS URL from HTTP URL
        ws_url = self._central_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/ws/devices?key={self._api_key}"

        logger.info(f"[WS-PUSH] Connecting to {ws_url.split('?')[0]}...")

        async with websockets.connect(ws_url, ping_interval=None, close_timeout=5) as ws:
            self._ws = ws
            self._connected = True
            self._connected_at = _utcnow()
            self._consecutive_failures = 0

            if self._reconnect_count > 0:
                logger.info(f"[WS-PUSH] Reconnected (attempt #{self._reconnect_count})")
            else:
                logger.info("[WS-PUSH] Connected to central server")
            self._reconnect_count += 1

            # Start ping task
            ping_task = asyncio.create_task(self._ping_loop(ws))

            try:
                async for raw_msg in ws:
                    if not self._running:
                        break
                    try:
                        msg = json.loads(raw_msg) if isinstance(raw_msg, str) else raw_msg
                        await self._handle_event(msg)
                    except json.JSONDecodeError:
                        logger.debug(f"[WS-PUSH] Non-JSON message: {raw_msg[:100]}")
                    except Exception as e:
                        logger.warning(f"[WS-PUSH] Event handler error: {e}")
            finally:
                ping_task.cancel()
                self._ws = None

    async def _ping_loop(self, ws):
        """Send periodic pings to keep the connection alive."""
        try:
            while self._running and self._connected:
                await asyncio.sleep(_PING_INTERVAL)
                try:
                    await ws.send(json.dumps({"type": "ping"}))
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    # ── Event Handling ──

    async def _handle_event(self, msg: dict):
        """Process a single push event from central server."""
        event = msg.get("event", "")
        data = msg.get("data", {})

        self._last_event_at = _utcnow()
        self._events_received += 1

        if event == "connected":
            logger.info(f"[WS-PUSH] Server confirmed connection: device={data.get('device_id', msg.get('device_id', '?'))}")
            return

        if event == "pong":
            return

        if event == "config_updated":
            logger.info(f"[WS-PUSH] Config updated push received: {data}")
            if self._on_config_updated:
                try:
                    asyncio.create_task(self._on_config_updated())
                except Exception as e:
                    logger.warning(f"[WS-PUSH] config_updated handler error: {e}")
            return

        if event == "action_created":
            logger.info(f"[WS-PUSH] Action created push received: {data}")
            if self._on_action_created:
                try:
                    asyncio.create_task(self._on_action_created())
                except Exception as e:
                    logger.warning(f"[WS-PUSH] action_created handler error: {e}")
            return

        if event == "force_sync":
            logger.info("[WS-PUSH] Force sync push received")
            if self._on_config_updated:
                try:
                    asyncio.create_task(self._on_config_updated())
                except Exception as e:
                    logger.warning(f"[WS-PUSH] force_sync handler error: {e}")
            return

        logger.debug(f"[WS-PUSH] Unknown event: {event}")


# Singleton
ws_push_client = WSPushClient()
