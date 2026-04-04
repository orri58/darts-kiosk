import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class BoardWSManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._global_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, board_id: Optional[str] = None):
        await websocket.accept()
        async with self._lock:
            self._global_connections.add(websocket)
            if board_id:
                self._connections[board_id].add(websocket)
                count = len(self._connections[board_id])
            else:
                count = len(self._global_connections)
        logger.info("[WS] connected board=%s clients=%s", board_id or "*", count)

    async def disconnect(self, websocket: WebSocket, board_id: Optional[str] = None):
        async with self._lock:
            self._global_connections.discard(websocket)
            if board_id:
                sockets = self._connections.get(board_id)
                if sockets and websocket in sockets:
                    sockets.remove(websocket)
                if sockets is not None and not sockets:
                    self._connections.pop(board_id, None)
                count = len(self._connections.get(board_id, set()))
            else:
                for key, sockets in list(self._connections.items()):
                    sockets.discard(websocket)
                    if not sockets:
                        self._connections.pop(key, None)
                count = len(self._global_connections)
        logger.info("[WS] disconnected board=%s clients=%s", board_id or "*", count)

    async def _send_with_timeout(self, websocket: WebSocket, payload: str, timeout: float = 1.5) -> bool:
        try:
            await asyncio.wait_for(websocket.send_text(payload), timeout=timeout)
            return True
        except Exception:
            return False

    async def broadcast(self, *args):
        if len(args) == 3:
            board_id, event_type, data = args
        elif len(args) == 2:
            event_type, data = args
            board_id = data.get("board_id") if isinstance(data, dict) else None
        elif len(args) == 1:
            event_type = args[0]
            data = {}
            board_id = None
        else:
            raise TypeError("broadcast expects (event, data) or (board_id, event, data)")

        async with self._lock:
            sockets = set(self._global_connections)
            if board_id:
                sockets.update(self._connections.get(board_id, set()))
            sockets = list(sockets)

        if not sockets:
            return

        payload = json.dumps({"event": event_type, "type": event_type, "data": data or {}})
        started = asyncio.get_running_loop().time()
        results = await asyncio.gather(
            *[self._send_with_timeout(ws, payload) for ws in sockets],
            return_exceptions=False,
        )

        dead = [ws for ws, ok in zip(sockets, results) if not ok]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._global_connections.discard(ws)
                for key, live in list(self._connections.items()):
                    for ws in dead:
                        live.discard(ws)
                    if not live:
                        self._connections.pop(key, None)
            logger.warning("[WS] pruned dead sockets board=%s removed=%s", board_id or "*", len(dead))

        duration_ms = int((asyncio.get_running_loop().time() - started) * 1000)
        logger.debug(
            "[WS] broadcast board=%s type=%s clients=%s removed=%s duration_ms=%s",
            board_id or "*",
            event_type,
            len(sockets),
            len(dead),
            duration_ms,
        )

    async def broadcast_all(self, event_type: str, data: Any = None):
        await self.broadcast(event_type, data or {})

    async def heartbeat(self, board_id: str):
        await self.broadcast(board_id, "heartbeat", {"board_id": board_id})


board_ws = BoardWSManager()
