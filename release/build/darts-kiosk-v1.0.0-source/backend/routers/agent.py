"""Agent API Routes (Master-Agent communication)"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import Board
from backend.schemas import AgentStatusResponse, SessionResponse
from backend.dependencies import get_active_session_for_board, verify_agent_secret

logger = logging.getLogger(__name__)

MODE = os.environ.get('MODE', 'MASTER')

router = APIRouter()


@router.get("/agent/health")
async def agent_health():
    return {"status": "ok", "mode": MODE, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/agent/status")
async def agent_status(request: Request, db: AsyncSession = Depends(get_db)):
    local_board_id = os.environ.get('LOCAL_BOARD_ID', 'BOARD-1')
    result = await db.execute(select(Board).where(Board.board_id == local_board_id))
    board = result.scalar_one_or_none()

    if not board:
        return {"error": "Local board not configured"}

    session = await get_active_session_for_board(db, board.id)

    return AgentStatusResponse(
        board_id=board.board_id,
        status=board.status,
        current_session=SessionResponse(
            id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
            game_type=session.game_type, credits_total=session.credits_total,
            credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
            price_total=session.price_total, started_at=session.started_at,
            expires_at=session.expires_at, ended_at=session.ended_at,
            players_count=session.players_count, players=session.players or [],
            status=session.status
        ) if session else None,
        mode=MODE
    )


@router.post("/agent/update")
async def agent_receive_update(request: Request, data: dict):
    """Receive update command from master (agent endpoint)"""
    if not verify_agent_secret(request):
        raise HTTPException(status_code=403, detail="Invalid agent secret")

    target_version = data.get("target_version", "latest")

    logger.info(f"Received update command: {target_version}")

    return {
        "success": True,
        "message": f"Update to {target_version} initiated",
        "note": "Container will restart shortly"
    }
