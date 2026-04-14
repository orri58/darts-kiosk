from types import SimpleNamespace

import pytest

from backend.routers import kiosk
from backend.services.autodarts_observer import AutodartsObserver


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeBegin:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeDB:
    def __init__(self, board):
        self.board = board

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return _FakeBegin()

    async def execute(self, _query):
        return _FakeResult(self.board)


@pytest.mark.asyncio
async def test_on_game_ended_skips_preliminary_variant_mismatch(monkeypatch):
    board = SimpleNamespace(id=1, board_id="BOARD-1", status="unlocked")
    session = SimpleNamespace(game_type="501")

    monkeypatch.setattr(kiosk, "AsyncSessionLocal", lambda: _FakeDB(board))

    async def _fake_get_active_session_for_board(_db, _board_id):
        return session

    monkeypatch.setattr(kiosk, "get_active_session_for_board", _fake_get_active_session_for_board)
    monkeypatch.setattr(kiosk, "_observer_match_context", lambda _board_id: {"variant": "Gotcha"})
    monkeypatch.setattr(kiosk, "_get_observer_match_id", lambda _board_id: "match-prelude-1")

    finalize_called = False

    async def _fake_finalize_match(_board_id, _reason):
        nonlocal finalize_called
        finalize_called = True
        return {"should_lock": True, "should_teardown": True, "credits_remaining": 0}

    monkeypatch.setattr(kiosk, "finalize_match", _fake_finalize_match)

    result = await kiosk._on_game_ended("BOARD-1", "match_end_state_finished")

    assert finalize_called is False
    assert result["skipped"] is True
    assert result["skip_reason"] == "preliminary_variant_mismatch"
    assert result["observed_variant"] == "Gotcha"
    assert result["should_lock"] is False
    assert result["should_teardown"] is False


@pytest.mark.asyncio
async def test_on_game_ended_allows_same_game_family(monkeypatch):
    board = SimpleNamespace(id=1, board_id="BOARD-1", status="in_game")
    session = SimpleNamespace(game_type="501")

    monkeypatch.setattr(kiosk, "AsyncSessionLocal", lambda: _FakeDB(board))

    async def _fake_get_active_session_for_board(_db, _board_id):
        return session

    monkeypatch.setattr(kiosk, "get_active_session_for_board", _fake_get_active_session_for_board)
    monkeypatch.setattr(kiosk, "_observer_match_context", lambda _board_id: {"variant": "X01"})
    monkeypatch.setattr(kiosk, "_get_observer_match_id", lambda _board_id: "match-x01-1")

    async def _fake_finalize_match(_board_id, _reason):
        return {
            "should_lock": True,
            "should_teardown": True,
            "credits_remaining": 0,
            "board_status": "locked",
        }

    monkeypatch.setattr(kiosk, "finalize_match", _fake_finalize_match)

    result = await kiosk._on_game_ended("BOARD-1", "match_end_state_finished")

    assert result["should_lock"] is True
    assert result["should_teardown"] is True
    assert result["credits_remaining"] == 0


@pytest.mark.asyncio
async def test_on_game_started_ignores_preliminary_variant_mismatch(monkeypatch):
    board = SimpleNamespace(id=1, board_id="BOARD-1", status="unlocked")
    session = SimpleNamespace(game_type="501", pricing_mode="per_player", credits_remaining=2)

    monkeypatch.setattr(kiosk, "AsyncSessionLocal", lambda: _FakeDB(board))

    async def _fake_get_active_session_for_board(_db, _board_id):
        return session

    monkeypatch.setattr(kiosk, "get_active_session_for_board", _fake_get_active_session_for_board)
    monkeypatch.setattr(kiosk, "_observer_match_context", lambda _board_id: {"variant": "Gotcha", "players_count": 2, "players": ["A", "B"]})

    charge_called = False

    def _fake_apply_authoritative_start_charge(*args, **kwargs):
        nonlocal charge_called
        charge_called = True
        raise AssertionError("start charge must not run for preliminary variant mismatch")

    monkeypatch.setattr(kiosk, "apply_authoritative_start_charge", _fake_apply_authoritative_start_charge)

    broadcast_calls = []

    async def _fake_broadcast(event, payload):
        broadcast_calls.append((event, payload))

    monkeypatch.setattr(kiosk.board_ws, "broadcast", _fake_broadcast)

    await kiosk._on_game_started("BOARD-1", "match_start_state_active")

    assert charge_called is False
    assert broadcast_calls == []


def test_normalize_game_family_maps_x01_variants_together():
    assert kiosk._normalize_game_family("501") == "x01"
    assert kiosk._normalize_game_family("301") == "x01"
    assert kiosk._normalize_game_family("X01") == "x01"
    assert kiosk._normalize_game_family("Gotcha") == "gotcha"
    assert kiosk._normalize_game_family("Bull-off") == "bulloff"
    assert kiosk._normalize_game_family("Cricket") == "cricket"


def test_observer_extract_variant_reads_nested_bull_off_payloads():
    observer = AutodartsObserver("BOARD-1")
    payload = {
        "data": {
            "activity": {
                "activity": "playing-match",
                "body": {
                    "matchID": "abc",
                    "variant": "Bull-off",
                },
            }
        }
    }

    assert observer._extract_variant(payload) == "Bull-off"


def test_observer_ignores_preliminary_bull_off_start_and_finish():
    observer = AutodartsObserver("BOARD-1")

    start_payload = {
        "data": {
            "body": {
                "coords": {"x": 0.1, "y": 0.2},
                "segment": {"name": "S20"},
            },
            "event": "throw",
            "matchId": "match-bulloff-1",
            "variant": "Bull-off",
        }
    }
    observer._update_ws_state("match_start_throw", "autodarts.matches", start_payload, raw="")

    assert observer._ws_state.variant == "Bull-off"
    assert observer._ws_state.match_active is False
    assert observer._ws_state.last_start_trigger is None

    observer._ws_state.match_active = True
    finish_payload = {
        "data": {
            "finished": False,
            "gameFinished": True,
            "id": "match-bulloff-1",
            "variant": "Bull-off",
        }
    }
    observer._update_ws_state("match_end_game_finished", "autodarts.matches", finish_payload, raw="")

    assert observer._ws_state.match_finished is False
    assert observer._ws_state.finish_trigger is None
