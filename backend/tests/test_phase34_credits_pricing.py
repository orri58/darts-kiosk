from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models import Board, BoardStatus, PricingMode, Session, SessionStatus
from backend.routers import boards as boards_router
from backend.routers import kiosk as kiosk_router
from backend.schemas import ExtendRequest
from backend.services import window_manager


async def _noop_async(*args, **kwargs):
    return None


@pytest_asyncio.fixture
async def isolated_kiosk_env(tmp_path, monkeypatch):
    db_path = tmp_path / "phase34.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(kiosk_router, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(kiosk_router, "return_to_kiosk_ui", _noop_async)
    monkeypatch.setattr(kiosk_router.board_ws, "broadcast", _noop_async)
    monkeypatch.setattr(boards_router.board_ws, "broadcast", _noop_async)
    monkeypatch.setattr(kiosk_router.observer_manager, "get", lambda board_id: None)
    monkeypatch.setattr(kiosk_router.observer_manager, "set_desired_state", lambda board_id, state: None)
    monkeypatch.setattr(kiosk_router.observer_manager, "get_desired_state", lambda board_id: "running")
    monkeypatch.setattr(kiosk_router.observer_manager, "clear_close_reason", lambda board_id: None)
    monkeypatch.setattr(kiosk_router.observer_manager, "close", _noop_async)
    monkeypatch.setattr(kiosk_router, "FINALIZE_DELAY_FINISHED", 0)
    monkeypatch.setattr(window_manager, "ensure_autodarts_foreground", _noop_async)
    kiosk_router._finalizing.clear()
    kiosk_router._finalized.clear()
    kiosk_router._last_finalized_match.clear()

    async def fake_get_or_create_setting(db, key, default):
        return default

    monkeypatch.setattr(kiosk_router, "get_or_create_setting", fake_get_or_create_setting)
    monkeypatch.setattr(boards_router, "log_audit", _noop_async)

    async with session_factory() as db:
        board = Board(board_id="BOARD-PHASE34", name="Phase 34", status=BoardStatus.UNLOCKED.value)
        db.add(board)
        await db.commit()
        await db.refresh(board)
        yield SimpleNamespace(engine=engine, session_factory=session_factory, board=board)

    await engine.dispose()


async def _create_session(env, pricing_mode: str, credits_total: int, credits_remaining: int, players_count: int, players=None):
    async with env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == env.board.board_id))).scalar_one()
        session = Session(
            board_id=board.id,
            pricing_mode=pricing_mode,
            game_type="501",
            credits_total=credits_total,
            credits_remaining=credits_remaining,
            players_count=players_count,
            players=players or [],
            status=SessionStatus.ACTIVE.value,
        )
        db.add(session)
        await db.commit()


async def _load_session(env):
    async with env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == env.board.board_id))).scalar_one()
        session = (await db.execute(
            select(Session).where(Session.board_id == board.id, Session.status == SessionStatus.ACTIVE.value)
        )).scalar_one_or_none()
        board = await db.get(Board, board.id)
        return board, session


def _fake_observer_context(monkeypatch, players_count: int, players: list[str]):
    fake_observer = SimpleNamespace(
        lifecycle_state=SimpleNamespace(value="running"),
        _context=None,
        _close_reason="",
        _ws_state=SimpleNamespace(last_match_id="match-test"),
        _page_alive=lambda: False,
        _navigate_to_home=_noop_async,
        export_match_context=lambda: {
            "players_count": players_count,
            "players": players,
        }
    )
    monkeypatch.setattr(kiosk_router.observer_manager, "get", lambda board_id: fake_observer)


@pytest.mark.asyncio
async def test_per_player_authoritative_start_charges_one_credit(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=1,
        credits_remaining=1,
        players_count=1,
        players=["Solo"],
    )

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_throw")

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.IN_GAME.value
    assert session.credits_total == 1
    assert session.credits_remaining == 0


@pytest.mark.asyncio
async def test_per_player_authoritative_start_charges_three_players(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=3,
        credits_remaining=3,
        players_count=3,
        players=["A", "B", "C"],
    )

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_turn_start")

    _, session = await _load_session(isolated_kiosk_env)
    assert session.credits_total == 3
    assert session.credits_remaining == 0


@pytest.mark.asyncio
async def test_authoritative_player_count_charges_detected_players_when_credits_are_enough(isolated_kiosk_env, monkeypatch):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=4,
        credits_remaining=4,
        players_count=2,
        players=["Configured A", "Configured B"],
    )
    _fake_observer_context(monkeypatch, 3, ["Alice", "Bob", "Cara"])

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.IN_GAME.value
    assert session.players_count == 3
    assert session.players == ["Alice", "Bob", "Cara"]
    assert session.credits_remaining == 1


@pytest.mark.asyncio
async def test_authoritative_player_count_shortage_enters_blocked_pending_without_charge(isolated_kiosk_env, monkeypatch):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        players=["Configured A", "Configured B"],
    )
    _fake_observer_context(monkeypatch, 4, ["Alice", "Bob", "Cara", "Dora"])

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.BLOCKED_PENDING.value
    assert session.players_count == 4
    assert session.players == ["Alice", "Bob", "Cara", "Dora"]
    assert session.credits_remaining == 2


@pytest.mark.asyncio
async def test_authoritative_shortage_still_blocks_when_board_is_already_in_game(isolated_kiosk_env, monkeypatch):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=1,
        credits_remaining=1,
        players_count=2,
        players=["Configured A", "Configured B"],
    )
    _fake_observer_context(monkeypatch, 2, ["Alice", "Bob"])

    async with isolated_kiosk_env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == isolated_kiosk_env.board.board_id))).scalar_one()
        board.status = BoardStatus.IN_GAME.value
        await db.commit()

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.BLOCKED_PENDING.value
    assert session.players_count == 2
    assert session.players == ["Alice", "Bob"]
    assert session.credits_remaining == 1


@pytest.mark.asyncio
async def test_authoritative_start_charges_detected_players_even_when_board_is_already_in_game(isolated_kiosk_env, monkeypatch):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        players=["Configured A", "Configured B"],
    )
    _fake_observer_context(monkeypatch, 2, ["Alice", "Bob"])

    async with isolated_kiosk_env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == isolated_kiosk_env.board.board_id))).scalar_one()
        board.status = BoardStatus.IN_GAME.value
        await db.commit()

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.IN_GAME.value
    assert session.players_count == 2
    assert session.players == ["Alice", "Bob"]
    assert session.credits_remaining == 0


@pytest.mark.asyncio
async def test_staff_top_up_resolves_blocked_pending_and_consumes_charge_once(isolated_kiosk_env, monkeypatch):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        players=["Configured A", "Configured B"],
    )
    _fake_observer_context(monkeypatch, 4, ["Alice", "Bob", "Cara", "Dora"])

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")

    async with isolated_kiosk_env.session_factory() as db:
        await boards_router.extend_session(
            isolated_kiosk_env.board.board_id,
            ExtendRequest(credits=2),
            user=SimpleNamespace(id="staff-1", username="staff"),
            db=db,
        )
        await db.commit()

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.IN_GAME.value
    assert session.players_count == 4
    assert session.credits_total == 4
    assert session.credits_remaining == 0


@pytest.mark.asyncio
async def test_match_abort_while_blocked_pending_returns_to_unlocked_without_charge(isolated_kiosk_env, monkeypatch):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        players=["Configured A", "Configured B"],
    )
    _fake_observer_context(monkeypatch, 4, ["Alice", "Bob", "Cara", "Dora"])

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")
    result = await kiosk_router.finalize_match(isolated_kiosk_env.board.board_id, "match_abort_delete")

    board, session = await _load_session(isolated_kiosk_env)
    assert result["should_lock"] is False
    assert board.status == BoardStatus.UNLOCKED.value
    assert session is not None
    assert session.players_count == 4
    assert session.credits_remaining == 2


@pytest.mark.asyncio
async def test_per_player_retry_restart_does_not_double_charge(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=3,
        credits_remaining=3,
        players_count=3,
        players=["A", "B", "C"],
    )

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_throw")
    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_throw")

    board, session = await _load_session(isolated_kiosk_env)
    assert board.status == BoardStatus.IN_GAME.value
    assert session.credits_total == 3
    assert session.credits_remaining == 0


@pytest.mark.asyncio
async def test_per_game_authoritative_finish_consumes_one_credit(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_GAME.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        players=["A", "B"],
    )

    result = await kiosk_router.finalize_match(isolated_kiosk_env.board.board_id, "match_end_state_finished")

    board, session = await _load_session(isolated_kiosk_env)
    assert result["should_lock"] is False
    assert board.status == BoardStatus.UNLOCKED.value
    assert session.credits_remaining == 1


@pytest.mark.asyncio
async def test_abort_before_authoritative_start_does_not_charge(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=3,
        credits_remaining=3,
        players_count=3,
        players=["A", "B", "C"],
    )

    result = await kiosk_router.finalize_match(isolated_kiosk_env.board.board_id, "aborted")

    board, session = await _load_session(isolated_kiosk_env)
    assert result["should_lock"] is False
    assert board.status == BoardStatus.UNLOCKED.value
    assert session is not None
    assert session.credits_remaining == 3


@pytest.mark.asyncio
async def test_per_game_abort_after_authoritative_start_consumes_one_credit(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_GAME.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        players=["A", "B"],
    )

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")
    result = await kiosk_router.finalize_match(isolated_kiosk_env.board.board_id, "match_abort_delete")

    board, session = await _load_session(isolated_kiosk_env)
    assert result["should_lock"] is False
    assert board.status == BoardStatus.UNLOCKED.value
    assert session is not None
    assert session.credits_remaining == 1


@pytest.mark.asyncio
async def test_per_player_abort_after_authoritative_start_keeps_single_charge(isolated_kiosk_env):
    await _create_session(
        isolated_kiosk_env,
        PricingMode.PER_PLAYER.value,
        credits_total=3,
        credits_remaining=3,
        players_count=3,
        players=["A", "B", "C"],
    )

    await kiosk_router._on_game_started(isolated_kiosk_env.board.board_id, "match_start_state_active")
    result = await kiosk_router.finalize_match(isolated_kiosk_env.board.board_id, "match_abort_delete")

    board, session = await _load_session(isolated_kiosk_env)
    assert result["should_lock"] is True
    assert board.status == BoardStatus.LOCKED.value
    assert session is None
