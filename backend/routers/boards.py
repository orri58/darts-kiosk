"""Board CRUD & Session Control Routes"""
import asyncio
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
from backend.runtime_features import AUTODARTS_MODE, observer_mode_requires_target, supports_local_pricing_mode
from backend.services.ws_manager import board_ws
from backend.services.session_pricing import initial_credit_seed, apply_authoritative_start_charge
from backend.routers.kiosk import start_observer_for_board, stop_observer_for_board
from backend.services.autodarts_observer import observer_manager

router = APIRouter()


def _session_state_payload(board_id: str, board_status: str, session, charge=None) -> dict:
    payload = {
        "board_id": board_id,
        "board_status": board_status,
        "pricing_mode": getattr(session, "pricing_mode", None),
        "credits_remaining": int(getattr(session, "credits_remaining", 0) or 0),
        "credits_total": int(getattr(session, "credits_total", 0) or 0),
        "players_count": int(getattr(session, "players_count", 0) or 0),
        "players": list(getattr(session, "players", None) or []),
        "pending_credit_gate": board_status == BoardStatus.BLOCKED_PENDING.value,
    }
    if charge is not None:
        required_units = int(getattr(charge, "required_units", 0) or 0)
        payload.update(
            {
                "required_units": required_units,
                "charged_units": int(getattr(charge, "units", 0) or 0),
                "credits_shortage": max(0, required_units - payload["credits_remaining"]),
                "start_gate_reason": getattr(charge, "reason", None),
            }
        )
    return payload


# ===== Board CRUD =====

@router.get("/boards", response_model=List[BoardResponse])
async def list_boards(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).order_by(Board.board_id))
    boards = result.scalars().all()
    return [BoardResponse(
        id=b.id,
        board_id=b.board_id,
        name=b.name,
        location=b.location,
        autodarts_target_url=b.autodarts_target_url,
        agent_api_base_url=b.agent_api_base_url,
        status=b.status,
        last_heartbeat_at=b.last_heartbeat_at,
        is_master=b.is_master,
        created_at=b.created_at,
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
            id=board.id,
            board_id=board.board_id,
            name=board.name,
            location=board.location,
            autodarts_target_url=board.autodarts_target_url,
            agent_api_base_url=board.agent_api_base_url,
            status=board.status,
            last_heartbeat_at=board.last_heartbeat_at,
            is_master=board.is_master,
            created_at=board.created_at,
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
        id=board.id,
        board_id=board.board_id,
        name=board.name,
        location=board.location,
        autodarts_target_url=board.autodarts_target_url,
        agent_api_base_url=board.agent_api_base_url,
        status=board.status,
        last_heartbeat_at=board.last_heartbeat_at,
        is_master=board.is_master,
        created_at=board.created_at,
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
        id=board.id,
        board_id=board.board_id,
        name=board.name,
        location=board.location,
        autodarts_target_url=board.autodarts_target_url,
        agent_api_base_url=board.agent_api_base_url,
        status=board.status,
        last_heartbeat_at=board.last_heartbeat_at,
        is_master=board.is_master,
        created_at=board.created_at,
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

    if not supports_local_pricing_mode(data.pricing_mode):
        raise HTTPException(
            status_code=400,
            detail=f"Pricing mode '{data.pricing_mode}' is not available in the stable local core"
        )

    if observer_mode_requires_target() and not board.autodarts_target_url:
        raise HTTPException(
            status_code=400,
            detail="Board is not configured for observer mode. Set an Autodarts target URL before unlocking."
        )

    if data.pricing_mode == PricingMode.PER_PLAYER.value and int(data.credits or 0) <= 0:
        raise HTTPException(status_code=400, detail="Credits must be greater than zero")
    if data.pricing_mode == PricingMode.PER_GAME.value and int(data.credits or 0) <= 0:
        raise HTTPException(status_code=400, detail="Credits must be greater than zero")
    if data.pricing_mode == PricingMode.PER_TIME.value and int(data.minutes or 0) <= 0:
        raise HTTPException(status_code=400, detail="Minutes must be greater than zero")

    existing = await get_active_session_for_board(db, board.id)
    if existing:
        raise HTTPException(status_code=400, detail="Board already has an active session")

    expires_at = None
    if data.pricing_mode == PricingMode.PER_TIME.value and data.minutes:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=data.minutes)

    credits_total, credits_remaining = initial_credit_seed(
        data.pricing_mode,
        data.credits,
        data.players_count,
    )
    player_count_hint = max(0, int(data.players_count or 0)) if data.pricing_mode == PricingMode.PER_PLAYER.value else max(1, int(data.players_count or 1))
    price_per_unit = 0.0
    if credits_total > 0 and data.price_total:
        price_per_unit = float(data.price_total) / float(credits_total)

    session = Session(
        board_id=board.id,
        pricing_mode=data.pricing_mode,
        game_type=data.game_type,
        credits_total=credits_total,
        credits_remaining=credits_remaining,
        minutes_total=data.minutes or 0,
        price_per_unit=price_per_unit,
        price_total=data.price_total,
        players_count=player_count_hint,
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
        "credits": data.credits,
        "minutes": data.minutes,
        "players_count": player_count_hint,
        "price_total": data.price_total
    })

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": "unlocked"})

    # Start Autodarts observer if board has a configured URL
    if board.autodarts_target_url:
        observer_manager.set_desired_state(board_id, "running")
        asyncio.create_task(start_observer_for_board(board_id, board.autodarts_target_url))

    # v3.2.1: Ensure Autodarts Desktop is running on board unlock
    try:
        from backend.services.autodarts_desktop_service import autodarts_desktop
        from backend.models import DEFAULT_AUTODARTS_DESKTOP
        from backend.dependencies import get_or_create_setting as _gocs
        ad_cfg = await _gocs(db, "autodarts_desktop", DEFAULT_AUTODARTS_DESKTOP)
        if ad_cfg.get("auto_start"):
            autodarts_desktop.ensure_running(ad_cfg.get("exe_path", ""), trigger=f"board_unlock:{board_id}")
    except Exception:
        pass  # non-critical, logged inside ensure_running

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

    pending_gate_resolved = False
    pending_gate_charge = None
    if board.status == BoardStatus.BLOCKED_PENDING.value and session.pricing_mode == PricingMode.PER_PLAYER.value:
        pending_gate_charge = apply_authoritative_start_charge(session, board.status)
        if pending_gate_charge.accepted and not pending_gate_charge.blocked:
            board.status = BoardStatus.IN_GAME.value
            pending_gate_resolved = True

    await db.flush()
    await log_audit(db, user, "extend_session", "session", session.id, {
        "board_id": board_id,
        "credits": data.credits,
        "minutes": data.minutes,
        "pending_gate_resolved": pending_gate_resolved,
    })

    await board_ws.broadcast("session_extended", {"board_id": board_id, "credits": data.credits, "minutes": data.minutes})
    await board_ws.broadcast("session_state", _session_state_payload(board_id, board.status, session, pending_gate_charge))

    if pending_gate_resolved:
        await board_ws.broadcast("board_status", {"board_id": board_id, "status": BoardStatus.IN_GAME.value})
        await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "start"})
        try:
            from backend.services.window_manager import ensure_autodarts_foreground
            await ensure_autodarts_foreground()
        except Exception:
            pass

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
    observer_manager.set_desired_state(board_id, "stopped")
    asyncio.create_task(stop_observer_for_board(board_id, reason="manual_lock"))

    try:
        from backend.routers.kiosk import return_to_kiosk_ui
        asyncio.create_task(return_to_kiosk_ui(board_id, should_lock=True))
    except Exception:
        pass

    return {"message": "Board locked", "board_id": board_id}


@router.get("/boards/{board_id}/session")
async def get_board_session(board_id: str, db: AsyncSession = Depends(get_db)):
    """Get current session for kiosk (no auth required for kiosk display)"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)

    from backend.services.autodarts_observer import observer_manager
    obs_status = observer_manager.get_status(board.board_id)

    return {
        "board_status": board.status,
        "autodarts_mode": AUTODARTS_MODE,
        "observer_browser_open": obs_status.get("browser_open", False),
        "observer_state": obs_status.get("state", "closed"),
        "observer_error": obs_status.get("last_error"),
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
