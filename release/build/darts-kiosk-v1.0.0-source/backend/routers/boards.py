"""Board CRUD & Session Control Routes"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from backend.database import get_db
from backend.models import User, Board, Session, BoardStatus, SessionStatus, PricingMode
from backend.schemas import (
    BoardCreate, BoardUpdate, BoardResponse,
    UnlockRequest, ExtendRequest, SessionResponse
)
from backend.dependencies import (
    get_current_user, require_admin, log_audit,
    get_active_session_for_board
)
from backend.services.ws_manager import board_ws
from backend.routers.kiosk import start_observer_for_board, stop_observer_for_board

router = APIRouter()


# ===== Board CRUD =====

@router.get("/boards", response_model=List[BoardResponse])
async def list_boards(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).order_by(Board.board_id))
    boards = result.scalars().all()
    return [BoardResponse(
        id=b.id, board_id=b.board_id, name=b.name, location=b.location,
        status=b.status, last_heartbeat_at=b.last_heartbeat_at,
        is_master=b.is_master, created_at=b.created_at
    ) for b in boards]


@router.get("/boards/{board_id}")
async def get_board(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)

    return {
        "board": BoardResponse(
            id=board.id, board_id=board.board_id, name=board.name, location=board.location,
            status=board.status, last_heartbeat_at=board.last_heartbeat_at,
            is_master=board.is_master, created_at=board.created_at
        ),
        "active_session": SessionResponse(
            id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
            game_type=session.game_type, credits_total=session.credits_total,
            credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
            price_total=session.price_total, started_at=session.started_at,
            expires_at=session.expires_at, ended_at=session.ended_at,
            players_count=session.players_count, players=session.players or [],
            status=session.status
        ) if session else None
    }


@router.post("/boards", response_model=BoardResponse)
async def create_board(data: BoardCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == data.board_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Board ID already exists")

    board = Board(
        board_id=data.board_id,
        name=data.name,
        location=data.location,
        autodarts_target_url=data.autodarts_target_url,
        agent_api_base_url=data.agent_api_base_url,
        agent_secret=str(uuid.uuid4())[:16],
        status=BoardStatus.LOCKED.value
    )
    db.add(board)
    await db.flush()
    await log_audit(db, admin, "create_board", "board", board.id, {"board_id": data.board_id})

    return BoardResponse(
        id=board.id, board_id=board.board_id, name=board.name, location=board.location,
        status=board.status, last_heartbeat_at=board.last_heartbeat_at,
        is_master=board.is_master, created_at=board.created_at
    )


@router.put("/boards/{board_id}", response_model=BoardResponse)
async def update_board(board_id: str, data: BoardUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    if data.name is not None:
        board.name = data.name
    if data.location is not None:
        board.location = data.location
    if data.autodarts_target_url is not None:
        board.autodarts_target_url = data.autodarts_target_url
    if data.agent_api_base_url is not None:
        board.agent_api_base_url = data.agent_api_base_url
    if data.status is not None:
        board.status = data.status

    await db.flush()
    await log_audit(db, admin, "update_board", "board", board.id)

    return BoardResponse(
        id=board.id, board_id=board.board_id, name=board.name, location=board.location,
        status=board.status, last_heartbeat_at=board.last_heartbeat_at,
        is_master=board.is_master, created_at=board.created_at
    )


@router.delete("/boards/{board_id}")
async def delete_board(board_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    await db.execute(delete(Board).where(Board.id == board.id))
    await log_audit(db, admin, "delete_board", "board", board.id, {"board_id": board_id})
    return {"message": "Board deleted"}


# ===== Session Control =====

@router.post("/boards/{board_id}/unlock", response_model=SessionResponse)
async def unlock_board(board_id: str, data: UnlockRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    existing = await get_active_session_for_board(db, board.id)
    if existing:
        raise HTTPException(status_code=400, detail="Board already has an active session")

    expires_at = None
    if data.pricing_mode == PricingMode.PER_TIME.value and data.minutes:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=data.minutes)

    session = Session(
        board_id=board.id,
        pricing_mode=data.pricing_mode,
        game_type=data.game_type,
        credits_total=data.credits or 0,
        credits_remaining=data.credits or 0,
        minutes_total=data.minutes or 0,
        price_total=data.price_total,
        players_count=data.players_count,
        expires_at=expires_at,
        unlocked_by_user_id=user.id,
        status=SessionStatus.ACTIVE.value
    )
    db.add(session)

    board.status = BoardStatus.UNLOCKED.value
    await db.flush()

    await log_audit(db, user, "unlock_board", "session", session.id, {
        "board_id": board_id,
        "pricing_mode": data.pricing_mode,
        "price_total": data.price_total
    })

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": "unlocked"})

    # Start Autodarts observer if board has a configured URL
    if board.autodarts_target_url:
        asyncio.create_task(start_observer_for_board(board_id, board.autodarts_target_url))

    return SessionResponse(
        id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
        game_type=session.game_type, credits_total=session.credits_total,
        credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
        price_total=session.price_total, started_at=session.started_at,
        expires_at=session.expires_at, ended_at=session.ended_at,
        players_count=session.players_count, players=session.players or [],
        status=session.status
    )


@router.post("/boards/{board_id}/extend", response_model=SessionResponse)
async def extend_session(board_id: str, data: ExtendRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session to extend")

    if data.credits:
        session.credits_remaining += data.credits
        session.credits_total += data.credits

    if data.minutes:
        session.minutes_total += data.minutes
        if session.expires_at:
            session.expires_at = session.expires_at + timedelta(minutes=data.minutes)
        else:
            session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=data.minutes)

    await db.flush()
    await log_audit(db, user, "extend_session", "session", session.id, {
        "board_id": board_id,
        "credits": data.credits,
        "minutes": data.minutes
    })

    await board_ws.broadcast("session_extended", {"board_id": board_id, "credits": data.credits, "minutes": data.minutes})

    return SessionResponse(
        id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
        game_type=session.game_type, credits_total=session.credits_total,
        credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
        price_total=session.price_total, started_at=session.started_at,
        expires_at=session.expires_at, ended_at=session.ended_at,
        players_count=session.players_count, players=session.players or [],
        status=session.status
    )


@router.post("/boards/{board_id}/lock")
async def lock_board(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if session:
        session.status = SessionStatus.CANCELLED.value
        session.ended_at = datetime.now(timezone.utc)
        session.ended_reason = "manual_lock"

    board.status = BoardStatus.LOCKED.value
    await db.flush()

    await log_audit(db, user, "lock_board", "board", board.id, {"board_id": board_id})

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": "locked"})

    # Close Autodarts observer
    asyncio.create_task(stop_observer_for_board(board_id))

    return {"message": "Board locked", "board_id": board_id}


@router.get("/boards/{board_id}/session")
async def get_board_session(board_id: str, db: AsyncSession = Depends(get_db)):
    """Get current session for kiosk (no auth required for kiosk display)"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)

    return {
        "board_status": board.status,
        "autodarts_mode": os.environ.get('AUTODARTS_MODE', 'observer'),
        "session": SessionResponse(
            id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
            game_type=session.game_type, credits_total=session.credits_total,
            credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
            price_total=session.price_total, started_at=session.started_at,
            expires_at=session.expires_at, ended_at=session.ended_at,
            players_count=session.players_count, players=session.players or [],
            status=session.status
        ) if session else None
    }
