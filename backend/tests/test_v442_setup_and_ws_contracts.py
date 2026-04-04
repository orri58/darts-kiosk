import json
import pytest

from backend.routers import admin as admin_router
from backend.services.ws_manager import BoardWSManager


class _FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_complete_first_setup_checks_setup_without_db_arg(monkeypatch):
    called = {"setup_check": 0}

    def fake_is_setup_complete():
        called["setup_check"] += 1
        return True

    monkeypatch.setattr(admin_router, "is_setup_complete", fake_is_setup_complete)

    with pytest.raises(Exception) as exc:
        await admin_router.complete_first_setup(
            admin_router.SetupConfig(admin_password="12345678", staff_pin="1234"),
            db=None,
        )

    assert called["setup_check"] == 1
    assert getattr(exc.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_ws_manager_supports_global_and_board_scoped_broadcasts():
    manager = BoardWSManager()
    global_ws = _FakeWebSocket()
    board_ws = _FakeWebSocket()

    await manager.connect(global_ws)
    await manager.connect(board_ws, "BOARD-1")

    await manager.broadcast("board_status", {"board_id": "BOARD-1", "status": "locked"})
    await manager.broadcast("BOARD-1", "credit_update", {"board_id": "BOARD-1", "credits_remaining": 2})

    assert global_ws.accepted is True
    assert board_ws.accepted is True
    assert len(global_ws.sent) == 2
    assert len(board_ws.sent) == 2

    first = json.loads(global_ws.sent[0])
    second = json.loads(board_ws.sent[1])

    assert first["event"] == "board_status"
    assert first["type"] == "board_status"
    assert first["data"]["board_id"] == "BOARD-1"

    assert second["event"] == "credit_update"
    assert second["data"]["credits_remaining"] == 2
