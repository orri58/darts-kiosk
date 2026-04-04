import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class BoardWSManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, board_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections[board_id].add(websocket)
            count = len(self._connections[board_id])
        logger.info("[WS] connected board=%s clients=%s", board_id, count)

    async def disconnect(self, board_id: str, websocket: WebSocket):
        async with self._lock:
            sockets = self._connections.get(board_id)
            if sockets and websocket in sockets:
                sockets.remove(websocket)
            if sockets is not None and not sockets:
                self._connections.pop(board_id, None)
            count = len(self._connections.get(board_id, set()))
        logger.info("[WS] disconnected board=%s clients=%s", board_id, count)

    async def _send_with_timeout(self, websocket: WebSocket, payload: str, timeout: float = 1.5) -> bool:
        try:
            await asyncio.wait_for(websocket.send_text(payload), timeout=timeout)
            return True
        except Exception:
            return False

    async def broadcast(self, board_id: str, event_type: str, data: Any = None):
        async with self._lock:
            sockets = list(self._connections.get(board_id, set()))

        if not sockets:
            return

        payload = json.dumps({"type": event_type, "data": data or {}})
        started = asyncio.get_running_loop().time()
        results = await asyncio.gather(
            *[self._send_with_timeout(ws, payload) for ws in sockets],
            return_exceptions=False,
        )

        dead = [ws for ws, ok in zip(sockets, results) if not ok]
        if dead:
            async with self._lock:
                live = self._connections.get(board_id, set())
                for ws in dead:
                    live.discard(ws)
                if not live:
                    self._connections.pop(board_id, None)
            logger.warning("[WS] pruned dead sockets board=%s removed=%s", board_id, len(dead))

        duration_ms = int((asyncio.get_running_loop().time() - started) * 1000)
        logger.debug(
            "[WS] broadcast board=%s type=%s clients=%s removed=%s duration_ms=%s",
            board_id,
            event_type,
            len(sockets),
            len(dead),
            duration_ms,
        )

    async def broadcast_all(self, event_type: str, data: Any = None):
        async with self._lock:
            board_ids = list(self._connections.keys())
        await asyncio.gather(*(self.broadcast(board_id, event_type, data) for board_id in board_ids))

    async def heartbeat(self, board_id: str):
        await self.broadcast(board_id, "heartbeat", {})


board_ws = BoardWSManager()
