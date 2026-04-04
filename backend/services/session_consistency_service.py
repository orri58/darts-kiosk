"""Session/board consistency diagnostics + safe repair helpers.

v4.4.0 focus:
- detect stale / contradictory board-session runtime states
- expose deterministic findings for admin diagnostics
- provide a narrow, safe repair path for common terminal inconsistencies
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Board, Session, BoardStatus, SessionStatus
from backend.routers.kiosk import run_terminal_session_cleanup


@dataclass
class ConsistencyFinding:
    board_id: str
    severity: str
    code: str
    summary: str
    detail: str
    recommended_action: str
    board_status: Optional[str] = None
    session_id: Optional[str] = None
    session_status: Optional[str] = None


class SessionConsistencyService:
    async def build_snapshot(self, db: AsyncSession) -> dict:
        boards = (await db.execute(select(Board).order_by(Board.board_id.asc()))).scalars().all()
        findings: list[ConsistencyFinding] = []
        board_rows: list[dict] = []

        now = datetime.now(timezone.utc)

        for board in boards:
            sessions = (
                await db.execute(
                    select(Session)
                    .where(Session.board_id == board.id)
                    .order_by(Session.started_at.desc(), Session.created_at.desc())
                )
            ).scalars().all()

            active_sessions = [s for s in sessions if s.status == SessionStatus.ACTIVE.value]
            latest_session = sessions[0] if sessions else None

            board_findings = self._find_board_issues(board, active_sessions, latest_session, now)
            findings.extend(board_findings)
            board_rows.append(
                {
                    "board_id": board.board_id,
                    "name": board.name,
                    "board_status": board.status,
                    "active_session_count": len(active_sessions),
                    "latest_session": self._session_payload(latest_session),
                    "issues": [asdict(item) for item in board_findings],
                }
            )

        severity_rank = {"critical": 3, "warning": 2, "info": 1}
        top_severity = "healthy"
        if findings:
            top = max(findings, key=lambda item: severity_rank.get(item.severity, 0))
            top_severity = top.severity

        return {
            "status": top_severity,
            "generated_at": now.isoformat(),
            "summary": {
                "board_count": len(board_rows),
                "issue_count": len(findings),
                "critical_count": sum(1 for item in findings if item.severity == "critical"),
                "warning_count": sum(1 for item in findings if item.severity == "warning"),
            },
            "boards": board_rows,
            "findings": [asdict(item) for item in findings],
        }

    async def repair_board(self, db: AsyncSession, board_public_id: str) -> dict:
        board = (
            await db.execute(select(Board).where(Board.board_id == board_public_id))
        ).scalar_one_or_none()
        if not board:
            raise ValueError("board_not_found")

        sessions = (
            await db.execute(
                select(Session)
                .where(Session.board_id == board.id)
                .order_by(Session.started_at.desc(), Session.created_at.desc())
            )
        ).scalars().all()
        active_sessions = [s for s in sessions if s.status == SessionStatus.ACTIVE.value]
        latest_session = sessions[0] if sessions else None

        actions: list[str] = []
        cleanup_reason = None
        now = datetime.now(timezone.utc)

        if len(active_sessions) > 1:
            keeper = active_sessions[0]
            for extra in active_sessions[1:]:
                extra.status = SessionStatus.CANCELLED.value
                extra.ended_at = extra.ended_at or now
                extra.ended_reason = extra.ended_reason or "consistency_repair_duplicate_active_session"
                actions.append(f"cancelled_duplicate_active_session:{extra.id}")
            latest_session = keeper
            active_sessions = [keeper]

        active_session = active_sessions[0] if active_sessions else None

        if board.status in (BoardStatus.UNLOCKED.value, BoardStatus.IN_GAME.value, BoardStatus.BLOCKED_PENDING.value) and not active_session:
            board.status = BoardStatus.LOCKED.value
            actions.append("locked_board_without_active_session")

        if board.status == BoardStatus.LOCKED.value and active_session:
            if self._session_should_be_terminal(active_session, now):
                if active_session.status == SessionStatus.ACTIVE.value:
                    active_session.status = SessionStatus.EXPIRED.value if active_session.expires_at and now >= self._ensure_tz(active_session.expires_at) else SessionStatus.CANCELLED.value
                    active_session.ended_at = active_session.ended_at or now
                    active_session.ended_reason = active_session.ended_reason or (
                        "time_expired" if active_session.status == SessionStatus.EXPIRED.value else "consistency_repair_locked_board"
                    )
                actions.append(f"finalized_terminal_session:{active_session.id}")
            else:
                board.status = BoardStatus.UNLOCKED.value
                actions.append("restored_locked_board_to_unlocked_for_active_session")

        if board.status == BoardStatus.BLOCKED_PENDING.value and active_session and active_session.pricing_mode != "per_player":
            board.status = BoardStatus.UNLOCKED.value
            actions.append("normalized_blocked_pending_non_per_player")

        if board.status == BoardStatus.IN_GAME.value and active_session and self._session_should_be_terminal(active_session, now):
            active_session.status = SessionStatus.EXPIRED.value if active_session.expires_at and now >= self._ensure_tz(active_session.expires_at) else SessionStatus.CANCELLED.value
            active_session.ended_at = active_session.ended_at or now
            active_session.ended_reason = active_session.ended_reason or (
                "time_expired" if active_session.status == SessionStatus.EXPIRED.value else "consistency_repair_terminal_in_game"
            )
            board.status = BoardStatus.LOCKED.value
            actions.append(f"closed_terminal_in_game_session:{active_session.id}")
            cleanup_reason = "consistency_repair_terminal_in_game"

        if latest_session and latest_session.status != SessionStatus.ACTIVE.value and board.status != BoardStatus.LOCKED.value:
            board.status = BoardStatus.LOCKED.value
            actions.append("locked_board_for_terminal_latest_session")
            cleanup_reason = cleanup_reason or "consistency_repair_terminal_session"

        await db.commit()

        if cleanup_reason:
            await run_terminal_session_cleanup(board.board_id, should_lock=True, close_reason=cleanup_reason)

        refreshed = await self.build_snapshot(db)
        repaired_board = next((item for item in refreshed["boards"] if item["board_id"] == board.board_id), None)

        return {
            "board_id": board.board_id,
            "actions": actions,
            "cleanup_triggered": bool(cleanup_reason),
            "board": repaired_board,
        }

    def _find_board_issues(self, board: Board, active_sessions: list[Session], latest_session: Optional[Session], now: datetime) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []

        if len(active_sessions) > 1:
            findings.append(
                ConsistencyFinding(
                    board_id=board.board_id,
                    severity="critical",
                    code="multiple_active_sessions",
                    summary="Mehr als eine aktive Session auf demselben Board.",
                    detail=f"Board {board.board_id} hat {len(active_sessions)} aktive Sessions.",
                    recommended_action="Safe repair ausführen, damit nur die jüngste Session aktiv bleibt.",
                    board_status=board.status,
                    session_id=active_sessions[0].id,
                    session_status=active_sessions[0].status,
                )
            )

        active_session = active_sessions[0] if active_sessions else None

        if board.status in (BoardStatus.UNLOCKED.value, BoardStatus.IN_GAME.value, BoardStatus.BLOCKED_PENDING.value) and not active_session:
            findings.append(
                ConsistencyFinding(
                    board_id=board.board_id,
                    severity="critical",
                    code="board_active_without_session",
                    summary="Board wirkt aktiv, aber es existiert keine aktive Session.",
                    detail=f"Board-Status={board.status}, aktive Session fehlt.",
                    recommended_action="Board sicher sperren und ggf. terminal cleanup ausführen.",
                    board_status=board.status,
                )
            )

        if board.status == BoardStatus.LOCKED.value and active_session:
            severity = "warning"
            summary = "Board ist gesperrt, obwohl noch eine aktive Session existiert."
            detail = "Entweder ist die Session stale/terminal oder der Board-Status wurde nicht sauber zurückgesetzt."
            action = "Safe repair ausführen, um Session/Board wieder anzugleichen."
            if self._session_should_be_terminal(active_session, now):
                severity = "critical"
                summary = "Gesperrtes Board hält noch eine terminal gewordene Session offen."
                detail = "Die Session ist laut Zeiten/Kapazität abgelaufen, wurde aber nicht sauber beendet."
                action = "Session finalisieren und terminal cleanup erzwingen."
            findings.append(
                ConsistencyFinding(
                    board_id=board.board_id,
                    severity=severity,
                    code="locked_board_with_active_session",
                    summary=summary,
                    detail=detail,
                    recommended_action=action,
                    board_status=board.status,
                    session_id=active_session.id,
                    session_status=active_session.status,
                )
            )

        if board.status == BoardStatus.BLOCKED_PENDING.value and active_session and active_session.pricing_mode != "per_player":
            findings.append(
                ConsistencyFinding(
                    board_id=board.board_id,
                    severity="warning",
                    code="blocked_pending_non_per_player",
                    summary="Blocked-pending ohne per-player Session.",
                    detail=f"Board {board.board_id} steht auf blocked_pending, Session-Modus ist {active_session.pricing_mode}.",
                    recommended_action="Board auf unlocked normalisieren, wenn keine echte Pending-Credit-Gate vorliegt.",
                    board_status=board.status,
                    session_id=active_session.id,
                    session_status=active_session.status,
                )
            )

        if board.status == BoardStatus.IN_GAME.value and active_session and self._session_should_be_terminal(active_session, now):
            findings.append(
                ConsistencyFinding(
                    board_id=board.board_id,
                    severity="critical",
                    code="terminal_session_still_in_game",
                    summary="Board steht noch auf in_game, obwohl die Session terminal sein müsste.",
                    detail="Typischer Restart-/Lifecycle-Hänger: Spieloberfläche lebt weiter, Session ist aber abgelaufen oder erschöpft.",
                    recommended_action="Terminal cleanup erzwingen und Board sperren.",
                    board_status=board.status,
                    session_id=active_session.id,
                    session_status=active_session.status,
                )
            )

        if latest_session and latest_session.status != SessionStatus.ACTIVE.value and board.status != BoardStatus.LOCKED.value:
            findings.append(
                ConsistencyFinding(
                    board_id=board.board_id,
                    severity="warning",
                    code="terminal_session_board_not_locked",
                    summary="Letzte Session ist beendet, Board aber nicht gesperrt.",
                    detail=f"Session-Status={latest_session.status}, Board-Status={board.status}.",
                    recommended_action="Board sperren und Kiosk/Observer-Endzustand prüfen.",
                    board_status=board.status,
                    session_id=latest_session.id,
                    session_status=latest_session.status,
                )
            )

        return findings

    @staticmethod
    def _session_payload(session: Optional[Session]) -> Optional[dict]:
        if not session:
            return None
        return {
            "id": session.id,
            "status": session.status,
            "pricing_mode": session.pricing_mode,
            "credits_remaining": session.credits_remaining,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "ended_reason": session.ended_reason,
        }

    @staticmethod
    def _ensure_tz(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _session_should_be_terminal(self, session: Session, now: datetime) -> bool:
        if session.status != SessionStatus.ACTIVE.value:
            return True
        if session.expires_at and now >= self._ensure_tz(session.expires_at):
            return True
        if session.pricing_mode in {"per_game", "per_player"} and (session.credits_remaining or 0) <= 0:
            return True
        return False


session_consistency_service = SessionConsistencyService()
