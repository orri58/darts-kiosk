from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base
from backend.dependencies import hash_password
from backend.models import Board, BoardStatus, PricingMode, Session, SessionStatus, User, UserRole
from backend.routers import admin as admin_router
from backend.routers import boards as boards_router
from backend.routers import kiosk as kiosk_router
from backend.schemas import StartGameRequest, UnlockRequest
from backend.services import window_manager


async def _noop_async(*args, **kwargs):
    return None


@pytest_asyncio.fixture
async def isolated_local_core_env(tmp_path, monkeypatch):
    db_path = tmp_path / "phase789.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(kiosk_router, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(kiosk_router, "return_to_kiosk_ui", _noop_async)
    monkeypatch.setattr(kiosk_router.board_ws, "broadcast", _noop_async)
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

    monkeypatch.setattr(boards_router.board_ws, "broadcast", _noop_async)
    monkeypatch.setattr(boards_router.observer_manager, "set_desired_state", lambda board_id, state: None)
    monkeypatch.setattr(boards_router, "start_observer_for_board", _noop_async)
    monkeypatch.setattr(boards_router, "stop_observer_for_board", _noop_async)

    async with session_factory() as db:
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            pin_hash=hash_password("1234"),
            role=UserRole.ADMIN.value,
            display_name="Administrator",
        )
        board = Board(
            board_id="BOARD-P789",
            name="Validation Board",
            location="Lab",
            autodarts_target_url="https://play.autodarts.io/boards/BOARD-P789",
            status=BoardStatus.LOCKED.value,
        )
        db.add_all([admin, board])
        await db.commit()
        await db.refresh(admin)
        await db.refresh(board)
        yield SimpleNamespace(engine=engine, session_factory=session_factory, admin=admin, board=board)

    await engine.dispose()


async def _load_board(env):
    async with env.session_factory() as db:
        return (await db.execute(select(Board).where(Board.board_id == env.board.board_id))).scalar_one()


async def _load_active_session(env):
    async with env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == env.board.board_id))).scalar_one()
        return (
            await db.execute(
                select(Session)
                .where(Session.board_id == board.id)
                .where(Session.status == SessionStatus.ACTIVE.value)
                .order_by(Session.started_at.desc())
            )
        ).scalar_one_or_none()


async def _load_latest_session(env):
    async with env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == env.board.board_id))).scalar_one()
        return (
            await db.execute(
                select(Session)
                .where(Session.board_id == board.id)
                .order_by(Session.started_at.desc())
            )
        ).scalars().first()


async def _unlock_board(env, *, pricing_mode: str, credits: int | None = None, minutes: int | None = None,
                        players_count: int = 1, price_total: float = 0.0):
    async with env.session_factory() as db:
        response = await boards_router.unlock_board(
            env.board.board_id,
            UnlockRequest(
                pricing_mode=pricing_mode,
                credits=credits,
                minutes=minutes,
                players_count=players_count,
                price_total=price_total,
            ),
            user=env.admin,
            db=db,
        )
        await db.commit()
        return response


async def _create_session(env, *, pricing_mode: str, status: str = SessionStatus.ACTIVE.value,
                          credits_total: int = 0, credits_remaining: int = 0,
                          minutes_total: int = 0, players_count: int = 1,
                          price_total: float | None = 0.0, players=None,
                          started_at: datetime | None = None, expires_at: datetime | None = None,
                          board_status: str | None = None):
    async with env.session_factory() as db:
        board = (await db.execute(select(Board).where(Board.board_id == env.board.board_id))).scalar_one()
        if board_status is not None:
            board.status = board_status
        elif status == SessionStatus.ACTIVE.value:
            board.status = BoardStatus.UNLOCKED.value
        session = Session(
            board_id=board.id,
            pricing_mode=pricing_mode,
            game_type="501",
            credits_total=credits_total,
            credits_remaining=credits_remaining,
            minutes_total=minutes_total,
            players_count=players_count,
            price_total=price_total,
            players=players or [],
            started_at=started_at or datetime.now(timezone.utc),
            expires_at=expires_at,
            status=status,
            unlocked_by_user_id=env.admin.id,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session


@pytest.mark.asyncio
async def test_unlock_board_creates_active_session_and_unlocked_board(isolated_local_core_env):
    response = await _unlock_board(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        credits=2,
        players_count=2,
        price_total=6.0,
    )

    board = await _load_board(isolated_local_core_env)
    session = await _load_active_session(isolated_local_core_env)

    assert response.status == SessionStatus.ACTIVE.value
    assert board.status == BoardStatus.UNLOCKED.value
    assert session is not None
    assert session.pricing_mode == PricingMode.PER_GAME.value
    assert session.credits_total == 2
    assert session.credits_remaining == 2
    assert session.players_count == 2
    assert session.price_total == 6.0


@pytest.mark.asyncio
async def test_lock_board_cancels_active_session_and_stops_local_play(isolated_local_core_env):
    await _unlock_board(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        credits=1,
        players_count=1,
        price_total=2.0,
    )

    async with isolated_local_core_env.session_factory() as db:
        response = await boards_router.lock_board(
            isolated_local_core_env.board.board_id,
            user=isolated_local_core_env.admin,
            db=db,
        )
        await db.commit()

    board = await _load_board(isolated_local_core_env)
    session = await _load_latest_session(isolated_local_core_env)

    assert response["board_id"] == isolated_local_core_env.board.board_id
    assert board.status == BoardStatus.LOCKED.value
    assert session.status == SessionStatus.CANCELLED.value
    assert session.ended_reason == "manual_lock"
    assert session.ended_at is not None


@pytest.mark.asyncio
async def test_start_game_records_players_for_current_session(isolated_local_core_env):
    await _unlock_board(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        credits=2,
        players_count=2,
        price_total=4.0,
    )

    async with isolated_local_core_env.session_factory() as db:
        response = await kiosk_router.kiosk_start_game(
            isolated_local_core_env.board.board_id,
            StartGameRequest(game_type="Cricket", players=["Alice", "Bob"]),
            db=db,
        )
        await db.commit()

    session = await _load_active_session(isolated_local_core_env)

    assert response["message"].startswith("Game registered")
    assert session.game_type == "Cricket"
    assert session.players == ["Alice", "Bob"]
    assert session.players_count == 2


@pytest.mark.asyncio
async def test_per_game_finalize_consumes_one_credit_then_locks_on_last_credit(isolated_local_core_env):
    await _create_session(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        price_total=6.0,
        players=["A", "B"],
    )

    first = await kiosk_router.finalize_match(isolated_local_core_env.board.board_id, "match_end_state_finished")
    board_after_first = await _load_board(isolated_local_core_env)
    session_after_first = await _load_active_session(isolated_local_core_env)

    second = await kiosk_router.finalize_match(isolated_local_core_env.board.board_id, "match_end_state_finished")
    board_after_second = await _load_board(isolated_local_core_env)
    latest_session = await _load_latest_session(isolated_local_core_env)

    assert first["should_lock"] is False
    assert session_after_first.credits_remaining == 1
    assert board_after_first.status == BoardStatus.UNLOCKED.value

    assert second["should_lock"] is True
    assert board_after_second.status == BoardStatus.LOCKED.value
    assert latest_session.status == SessionStatus.FINISHED.value
    assert latest_session.credits_remaining == 0
    assert latest_session.ended_reason == "credits_exhausted"


@pytest.mark.asyncio
async def test_assistive_finish_trigger_does_not_deduct_credit(isolated_local_core_env):
    await _create_session(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        price_total=6.0,
        players=["A", "B"],
    )

    result = await kiosk_router.finalize_match(isolated_local_core_env.board.board_id, "match_end_gameshot_match")

    board = await _load_board(isolated_local_core_env)
    session = await _load_active_session(isolated_local_core_env)

    assert result["should_lock"] is False
    assert board.status == BoardStatus.UNLOCKED.value
    assert session is not None
    assert session.credits_remaining == 2


@pytest.mark.asyncio
async def test_per_player_authoritative_start_charges_once_and_finish_does_not_double_charge(isolated_local_core_env):
    await _create_session(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_PLAYER.value,
        credits_total=3,
        credits_remaining=3,
        players_count=3,
        price_total=4.5,
        players=["A", "B", "C"],
    )

    await kiosk_router._on_game_started(isolated_local_core_env.board.board_id, "match_start_turn_start")
    await kiosk_router._on_game_started(isolated_local_core_env.board.board_id, "match_start_turn_start")

    board_after_start = await _load_board(isolated_local_core_env)
    session_after_start = await _load_active_session(isolated_local_core_env)
    finish = await kiosk_router.finalize_match(isolated_local_core_env.board.board_id, "match_end_state_finished")
    latest_session = await _load_latest_session(isolated_local_core_env)

    assert board_after_start.status == BoardStatus.IN_GAME.value
    assert session_after_start.credits_total == 3
    assert session_after_start.credits_remaining == 0
    assert finish["should_lock"] is True
    assert latest_session.status == SessionStatus.FINISHED.value
    assert latest_session.credits_remaining == 0


@pytest.mark.asyncio
async def test_revenue_summary_ignores_active_sessions_and_tolerates_null_prices(isolated_local_core_env):
    now = datetime.now(timezone.utc)
    await _create_session(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        status=SessionStatus.FINISHED.value,
        credits_total=1,
        credits_remaining=0,
        players_count=1,
        price_total=5.0,
        started_at=now - timedelta(hours=2),
    )
    await _create_session(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_TIME.value,
        status=SessionStatus.CANCELLED.value,
        minutes_total=60,
        players_count=2,
        price_total=None,
        started_at=now - timedelta(hours=1),
    )
    await _create_session(
        isolated_local_core_env,
        pricing_mode=PricingMode.PER_GAME.value,
        status=SessionStatus.ACTIVE.value,
        credits_total=2,
        credits_remaining=2,
        players_count=2,
        price_total=9.0,
        started_at=now - timedelta(minutes=30),
    )

    async with isolated_local_core_env.session_factory() as db:
        summary = await admin_router.get_revenue_summary(
            days=7,
            admin=isolated_local_core_env.admin,
            db=db,
        )

    date_key = (now - timedelta(hours=2)).strftime("%Y-%m-%d")

    assert summary["total_revenue"] == 5.0
    assert summary["total_sessions"] == 2
    assert summary["by_date"][date_key]["total"] == 5.0
    assert summary["by_date"][date_key]["count"] == 2
    assert summary["by_date"][date_key]["by_board"]["Validation Board"] == 5.0
    assert summary["by_board"]["Validation Board"] == 5.0
