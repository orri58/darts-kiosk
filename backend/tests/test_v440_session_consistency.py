import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, delete

from backend.database import AsyncSessionLocal, init_db
from backend.models import Board, Session, BoardStatus, SessionStatus
from backend.services.session_consistency_service import session_consistency_service


async def _reset(board_public_id: str):
    async with AsyncSessionLocal() as db:
        board = (await db.execute(select(Board).where(Board.board_id == board_public_id))).scalar_one_or_none()
        if board:
            await db.execute(delete(Session).where(Session.board_id == board.id))
            await db.execute(delete(Board).where(Board.id == board.id))
        await db.commit()


@pytest.mark.asyncio
async def test_snapshot_detects_board_active_without_session():
    await init_db()
    await _reset("CONSIST-1")

    async with AsyncSessionLocal() as db:
        db.add(Board(board_id="CONSIST-1", name="Consistency 1", status=BoardStatus.UNLOCKED.value))
        await db.commit()

    async with AsyncSessionLocal() as db:
        snapshot = await session_consistency_service.build_snapshot(db)

    codes = {item["code"] for item in snapshot["findings"]}
    assert "board_active_without_session" in codes
    assert snapshot["summary"]["critical_count"] >= 1


@pytest.mark.asyncio
async def test_snapshot_detects_locked_board_with_terminal_active_session():
    await init_db()
    await _reset("CONSIST-2")

    async with AsyncSessionLocal() as db:
        board = Board(board_id="CONSIST-2", name="Consistency 2", status=BoardStatus.LOCKED.value)
        db.add(board)
        await db.flush()
        db.add(Session(
            board_id=board.id,
            pricing_mode="per_time",
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        snapshot = await session_consistency_service.build_snapshot(db)

    finding = next(item for item in snapshot["findings"] if item["board_id"] == "CONSIST-2")
    assert finding["code"] == "locked_board_with_active_session"
    assert finding["severity"] == "critical"


@pytest.mark.asyncio
async def test_repair_locks_unlocked_board_without_session():
    await init_db()
    await _reset("CONSIST-3")

    async with AsyncSessionLocal() as db:
        db.add(Board(board_id="CONSIST-3", name="Consistency 3", status=BoardStatus.UNLOCKED.value))
        await db.commit()

    async with AsyncSessionLocal() as db:
        with patch("backend.services.session_consistency_service.run_terminal_session_cleanup", new=AsyncMock()) as cleanup_mock:
            result = await session_consistency_service.repair_board(db, "CONSIST-3")
            cleanup_mock.assert_not_awaited()

    assert "locked_board_without_active_session" in result["actions"]
    assert result["board"]["board_status"] == BoardStatus.LOCKED.value
    assert result["board"]["issues"] == []


@pytest.mark.asyncio
async def test_repair_finalizes_terminal_in_game_session_and_triggers_cleanup():
    await init_db()
    await _reset("CONSIST-4")

    async with AsyncSessionLocal() as db:
        board = Board(board_id="CONSIST-4", name="Consistency 4", status=BoardStatus.IN_GAME.value)
        db.add(board)
        await db.flush()
        db.add(Session(
            board_id=board.id,
            pricing_mode="per_time",
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=40),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        with patch("backend.services.session_consistency_service.run_terminal_session_cleanup", new=AsyncMock()) as cleanup_mock:
            result = await session_consistency_service.repair_board(db, "CONSIST-4")
            cleanup_mock.assert_awaited_once_with(
                "CONSIST-4",
                should_lock=True,
                close_reason="consistency_repair_terminal_in_game",
            )

    assert "closed_terminal_in_game_session" in " ".join(result["actions"])
    assert result["cleanup_triggered"] is True
    assert result["board"]["board_status"] == BoardStatus.LOCKED.value
    assert result["board"]["issues"] == []


@pytest.mark.asyncio
async def test_repair_collapses_duplicate_active_sessions():
    await init_db()
    await _reset("CONSIST-5")

    async with AsyncSessionLocal() as db:
        board = Board(board_id="CONSIST-5", name="Consistency 5", status=BoardStatus.UNLOCKED.value)
        db.add(board)
        await db.flush()
        db.add(Session(
            board_id=board.id,
            pricing_mode="per_game",
            status=SessionStatus.ACTIVE.value,
            credits_total=3,
            credits_remaining=2,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        ))
        db.add(Session(
            board_id=board.id,
            pricing_mode="per_game",
            status=SessionStatus.ACTIVE.value,
            credits_total=3,
            credits_remaining=2,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        with patch("backend.services.session_consistency_service.run_terminal_session_cleanup", new=AsyncMock()):
            result = await session_consistency_service.repair_board(db, "CONSIST-5")

    assert any(action.startswith("cancelled_duplicate_active_session:") for action in result["actions"])
    assert result["board"]["active_session_count"] == 1
    assert result["board"]["issues"] == []
