"""
v4.3.0/4.3.1 targeted tests — scheduler terminal cleanup alignment.

Goal:
- scheduler-driven expiry/idle lock paths must trigger the same terminal cleanup
  semantics as normal finalize session-end logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, delete

from backend.database import AsyncSessionLocal, init_db
from backend.models import Board, Session, BoardStatus, SessionStatus, Settings
from backend.services.scheduler import SessionScheduler


async def _reset_test_records(board_public_id: str):
    async with AsyncSessionLocal() as db:
        board = (await db.execute(select(Board).where(Board.board_id == board_public_id))).scalar_one_or_none()
        if board:
            await db.execute(delete(Session).where(Session.board_id == board.id))
            await db.execute(delete(Board).where(Board.id == board.id))
        await db.commit()


@pytest.mark.asyncio
async def test_scheduler_expired_per_time_session_triggers_terminal_cleanup_once():
    await init_db()
    await _reset_test_records("TEST-SCHED-EXP-1")

    async with AsyncSessionLocal() as db:
        board = Board(
            board_id="TEST-SCHED-EXP-1",
            name="Test Board Expired",
            status=BoardStatus.UNLOCKED.value,
        )
        db.add(board)
        await db.flush()

        session = Session(
            board_id=board.id,
            pricing_mode="per_time",
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(session)
        await db.commit()

    scheduler = SessionScheduler()

    with patch.object(scheduler, "_run_terminal_cleanup", new=AsyncMock()) as cleanup_mock:
        await scheduler._check_expired_sessions()
        cleanup_mock.assert_awaited_once_with(
            "TEST-SCHED-EXP-1",
            close_reason="scheduler_time_expired",
        )

    async with AsyncSessionLocal() as db:
        board = (await db.execute(
            select(Board).where(Board.board_id == "TEST-SCHED-EXP-1")
        )).scalar_one()
        session = (await db.execute(
            select(Session).where(Session.board_id == board.id)
        )).scalar_one()

        assert board.status == BoardStatus.LOCKED.value
        assert session.status == SessionStatus.EXPIRED.value
        assert session.ended_reason == "time_expired"
        assert session.ended_at is not None


@pytest.mark.asyncio
async def test_scheduler_in_game_expired_session_defers_cleanup():
    await init_db()
    await _reset_test_records("TEST-SCHED-EXP-INGAME-1")

    async with AsyncSessionLocal() as db:
        board = Board(
            board_id="TEST-SCHED-EXP-INGAME-1",
            name="Test Board In Game",
            status=BoardStatus.IN_GAME.value,
        )
        db.add(board)
        await db.flush()

        session = Session(
            board_id=board.id,
            pricing_mode="per_time",
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(session)
        await db.commit()

    scheduler = SessionScheduler()

    with patch.object(scheduler, "_run_terminal_cleanup", new=AsyncMock()) as cleanup_mock:
        await scheduler._check_expired_sessions()
        cleanup_mock.assert_not_awaited()

    async with AsyncSessionLocal() as db:
        board = (await db.execute(
            select(Board).where(Board.board_id == "TEST-SCHED-EXP-INGAME-1")
        )).scalar_one()
        session = (await db.execute(
            select(Session).where(Session.board_id == board.id)
        )).scalar_one()

        assert board.status == BoardStatus.IN_GAME.value
        assert session.status == SessionStatus.ACTIVE.value
        assert session.ended_reason is None


@pytest.mark.asyncio
async def test_scheduler_idle_timeout_triggers_terminal_cleanup_once():
    await init_db()
    await _reset_test_records("TEST-SCHED-IDLE-1")

    async with AsyncSessionLocal() as db:
        await db.execute(delete(Settings).where(Settings.key == "pricing"))
        db.add(Settings(key="pricing", value={"idle_timeout_minutes": 5}))

        board = Board(
            board_id="TEST-SCHED-IDLE-1",
            name="Test Board Idle",
            status=BoardStatus.UNLOCKED.value,
        )
        db.add(board)
        await db.flush()

        session = Session(
            board_id=board.id,
            pricing_mode="per_game",
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db.add(session)
        await db.commit()

    scheduler = SessionScheduler()

    with patch.object(scheduler, "_run_terminal_cleanup", new=AsyncMock()) as cleanup_mock:
        await scheduler._check_idle_sessions()
        cleanup_mock.assert_awaited_once_with(
            "TEST-SCHED-IDLE-1",
            close_reason="scheduler_idle_timeout",
        )

    async with AsyncSessionLocal() as db:
        board = (await db.execute(
            select(Board).where(Board.board_id == "TEST-SCHED-IDLE-1")
        )).scalar_one()
        session = (await db.execute(
            select(Session).where(Session.board_id == board.id)
        )).scalar_one()

        assert board.status == BoardStatus.LOCKED.value
        assert session.status == SessionStatus.CANCELLED.value
        assert session.ended_reason == "idle_timeout"
        assert session.ended_at is not None


@pytest.mark.asyncio
async def test_run_terminal_cleanup_import_bridge_calls_shared_kiosk_cleanup():
    scheduler = SessionScheduler()

    with patch("backend.routers.kiosk.run_terminal_session_cleanup", new=AsyncMock()) as cleanup_mock:
        await scheduler._run_terminal_cleanup("BOARD-X", close_reason="scheduler_idle_timeout")
        cleanup_mock.assert_awaited_once_with(
            "BOARD-X",
            should_lock=True,
            close_reason="scheduler_idle_timeout",
        )
