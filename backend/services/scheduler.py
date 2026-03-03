"""
Background Tasks and Scheduler
Handles session expiry, idle timeout, and periodic maintenance
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import Board, Session, Settings, BoardStatus, SessionStatus

logger = logging.getLogger(__name__)


class SessionScheduler:
    """
    Background scheduler for session management.
    Handles:
    - Session expiry (per_time mode)
    - Idle timeout (UNLOCKED_SETUP state)
    - Periodic cleanup
    """
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 10  # seconds
        self._idle_timeout_minutes = 5  # default, loaded from settings
    
    async def start(self):
        """Start the background scheduler"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Session scheduler started")
    
    async def stop(self):
        """Stop the background scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Session scheduler stopped")
    
    async def _run_loop(self):
        """Main scheduler loop"""
        while self._running:
            try:
                await self._check_expired_sessions()
                await self._check_idle_sessions()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            await asyncio.sleep(self._check_interval)
    
    async def _get_idle_timeout(self, db: AsyncSession) -> int:
        """Get idle timeout from settings"""
        try:
            result = await db.execute(select(Settings).where(Settings.key == "pricing"))
            setting = result.scalar_one_or_none()
            if setting and setting.value:
                return setting.value.get('idle_timeout_minutes', 5)
        except:
            pass
        return 5
    
    async def _check_expired_sessions(self):
        """Check and expire time-based sessions"""
        async with AsyncSessionLocal() as db:
            try:
                now = datetime.now(timezone.utc)
                
                # Find sessions that have expired (per_time mode)
                result = await db.execute(
                    select(Session)
                    .where(Session.status == SessionStatus.ACTIVE.value)
                    .where(Session.pricing_mode == 'per_time')
                    .where(Session.expires_at != None)
                    .where(Session.expires_at <= now)
                )
                expired_sessions = result.scalars().all()
                
                for session in expired_sessions:
                    # Get the board
                    board_result = await db.execute(
                        select(Board).where(Board.id == session.board_id)
                    )
                    board = board_result.scalar_one_or_none()
                    
                    if board:
                        # Only auto-lock if NOT in game (let them finish current game)
                        if board.status != BoardStatus.IN_GAME.value:
                            session.status = SessionStatus.EXPIRED.value
                            session.ended_at = now
                            session.ended_reason = "time_expired"
                            board.status = BoardStatus.LOCKED.value
                            
                            logger.info(f"Session expired (time): {session.id[:8]} on {board.board_id}")
                        else:
                            # Flag that session should lock after current game
                            logger.info(f"Session time expired but game in progress: {board.board_id}")
                
                await db.commit()
                
            except Exception as e:
                logger.error(f"Error checking expired sessions: {e}")
                await db.rollback()
    
    async def _check_idle_sessions(self):
        """Check and lock idle sessions in UNLOCKED state"""
        async with AsyncSessionLocal() as db:
            try:
                idle_timeout = await self._get_idle_timeout(db)
                now = datetime.now(timezone.utc)
                idle_threshold = now - timedelta(minutes=idle_timeout)
                
                # Find boards that are UNLOCKED but idle (no game started)
                result = await db.execute(
                    select(Board)
                    .where(Board.status == BoardStatus.UNLOCKED.value)
                )
                unlocked_boards = result.scalars().all()
                
                for board in unlocked_boards:
                    # Get active session
                    session_result = await db.execute(
                        select(Session)
                        .where(Session.board_id == board.id)
                        .where(Session.status == SessionStatus.ACTIVE.value)
                        .order_by(Session.started_at.desc())
                    )
                    session = session_result.scalar_one_or_none()
                    
                    if session:
                        # Check if session has been idle (no game started)
                        # We use session.updated_at or started_at to track last activity
                        last_activity = session.updated_at or session.started_at
                        
                        if last_activity and last_activity < idle_threshold:
                            # Session is idle - lock it
                            session.status = SessionStatus.CANCELLED.value
                            session.ended_at = now
                            session.ended_reason = "idle_timeout"
                            board.status = BoardStatus.LOCKED.value
                            
                            logger.info(f"Session idle timeout: {session.id[:8]} on {board.board_id}")
                
                await db.commit()
                
            except Exception as e:
                logger.error(f"Error checking idle sessions: {e}")
                await db.rollback()
    
    async def force_lock_if_expired(self, board_id: str) -> bool:
        """
        Called after a game ends to check if session should be locked.
        Returns True if board was locked.
        """
        async with AsyncSessionLocal() as db:
            try:
                now = datetime.now(timezone.utc)
                
                # Get board
                result = await db.execute(select(Board).where(Board.board_id == board_id))
                board = result.scalar_one_or_none()
                if not board:
                    return False
                
                # Get active session
                session_result = await db.execute(
                    select(Session)
                    .where(Session.board_id == board.id)
                    .where(Session.status == SessionStatus.ACTIVE.value)
                )
                session = session_result.scalar_one_or_none()
                
                if not session:
                    board.status = BoardStatus.LOCKED.value
                    await db.commit()
                    return True
                
                should_lock = False
                
                # Check per_game credits
                if session.pricing_mode == 'per_game' and session.credits_remaining <= 0:
                    should_lock = True
                    session.ended_reason = "credits_exhausted"
                
                # Check per_time expiry
                if session.pricing_mode == 'per_time' and session.expires_at:
                    if now >= session.expires_at:
                        should_lock = True
                        session.ended_reason = "time_expired"
                
                if should_lock:
                    session.status = SessionStatus.FINISHED.value
                    session.ended_at = now
                    board.status = BoardStatus.LOCKED.value
                    logger.info(f"Board locked after game end: {board_id} ({session.ended_reason})")
                else:
                    # Return to unlocked for next game
                    board.status = BoardStatus.UNLOCKED.value
                
                await db.commit()
                return should_lock
                
            except Exception as e:
                logger.error(f"Error in force_lock_if_expired: {e}")
                await db.rollback()
                return False


# Global scheduler instance
scheduler = SessionScheduler()


async def start_scheduler():
    """Start the global scheduler"""
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler"""
    await scheduler.stop()
