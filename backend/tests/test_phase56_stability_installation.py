import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    import types

    class _DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    sys.modules["httpx"] = types.SimpleNamespace(
        AsyncClient=_DummyAsyncClient,
        TimeoutException=Exception,
    )

from backend.models import BoardStatus, SessionStatus
from backend.services.action_poller import ActionPoller
from backend.services.central_heartbeat_client import CentralHeartbeatClient
from backend.services.config_sync_client import ConfigSyncClient


@pytest.mark.asyncio
async def test_config_sync_start_is_non_blocking(monkeypatch):
    client = ConfigSyncClient()
    client.configure("http://central.test", "api-key", "device-1")

    async def fake_sync_now():
        return False

    monkeypatch.setattr(client, "sync_now", fake_sync_now)
    monkeypatch.setattr(client, "_compute_interval", lambda: 999)

    await asyncio.wait_for(client.start(), timeout=0.05)

    assert client._running is True
    assert client._task is not None
    client.stop()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_action_poller_start_is_non_blocking(monkeypatch):
    poller = ActionPoller()
    poller.configure("http://central.test", "api-key", "device-1")

    async def fake_poll_once():
        return None

    monkeypatch.setattr(poller, "_poll_once", fake_poll_once)

    await asyncio.wait_for(poller.start(), timeout=0.05)

    assert poller._running is True
    assert poller._task is not None
    poller.stop()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_action_poller_board_updates_use_ws_event_signature(monkeypatch):
    poller = ActionPoller()

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeDB:
        def __init__(self, value):
            self._value = value
            self.commits = 0

        async def execute(self, *_args, **_kwargs):
            return FakeResult(self._value)

        async def commit(self):
            self.commits += 1

    class Board:
        def __init__(self):
            self.id = 1
            self.board_id = "BOARD-1"
            self.status = BoardStatus.UNLOCKED.value

    class Session:
        def __init__(self):
            self.status = SessionStatus.ACTIVE.value
            self.ended_at = None
            self.ended_reason = None

    broadcast = AsyncMock()
    monkeypatch.setattr("backend.services.ws_manager.board_ws.broadcast", broadcast)

    board = Board()
    start_db = FakeDB(None)
    ok, _ = await poller._do_start_session(start_db, board, {})
    assert ok is True
    assert start_db.commits == 1
    assert broadcast.await_args_list[0].args == (
        "board_update",
        {"board_id": "BOARD-1", "status": BoardStatus.IN_GAME.value},
    )

    stop_board = Board()
    stop_board.status = BoardStatus.IN_GAME.value
    active_session = Session()
    stop_db = FakeDB(active_session)
    ok, _ = await poller._do_stop_session(stop_db, stop_board)
    assert ok is True
    assert active_session.status == SessionStatus.FINISHED.value
    assert stop_board.status == BoardStatus.UNLOCKED.value
    assert broadcast.await_args_list[1].args == (
        "board_update",
        {"board_id": "BOARD-1", "status": BoardStatus.UNLOCKED.value},
    )


@dataclass
class FakeObserverMetrics:
    total_events: int = 12
    success_rate: float = 83.3


@dataclass
class FakeSystemHealth:
    status: str = "healthy"
    uptime_seconds: int = 123
    scheduler_running: bool = False
    backup_service_running: bool = False
    observer_metrics: FakeObserverMetrics = field(default_factory=FakeObserverMetrics)
    agent_status: dict = None

    def __post_init__(self):
        if self.agent_status is None:
            self.agent_status = {
                "BOARD-1": {"is_online": True},
                "BOARD-2": {"is_online": False},
            }

class FakeHealthMonitor:
    def get_health(self):
        return FakeSystemHealth()


def test_central_heartbeat_health_payload_uses_health_monitor_snapshot(monkeypatch):
    client = CentralHeartbeatClient()
    monkeypatch.setattr("backend.services.health_monitor.health_monitor", FakeHealthMonitor())

    payload = client._get_health()

    assert payload["status"] == "healthy"
    assert payload["observer_total_events"] == 12
    assert payload["observer_success_rate"] == 83.3
    assert payload["agents_total"] == 2
    assert payload["agents_online"] == 1
