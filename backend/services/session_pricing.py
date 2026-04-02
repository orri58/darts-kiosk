from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.models import BoardStatus, PricingMode


AUTHORITATIVE_FINISH_TRIGGERS = frozenset(
    {
        "finished",
        "manual",
        "match_end_state_finished",
        "match_end_game_finished",
    }
)
ABORT_TRIGGERS = frozenset({"aborted", "match_abort_delete"})


@dataclass(frozen=True)
class ChargeDecision:
    accepted: bool
    charged: bool
    blocked: bool
    units: int
    required_units: int
    credits_before: int
    credits_after: int
    players_count: int
    reason: str


@dataclass(frozen=True)
class FinalizeDecision:
    consume_units: int
    credits_before: int
    credits_after: int
    should_lock: bool
    should_teardown: bool
    charge_applied: bool
    has_remaining_capacity: bool
    reason: str


def resolve_players_count(session: Any) -> int:
    players = getattr(session, "players", None) or []
    if isinstance(players, list) and players:
        return max(1, len([name for name in players if str(name).strip()]))
    count = getattr(session, "players_count", None) or 0
    return max(1, int(count or 1))


def initial_credit_seed(pricing_mode: str, credits: int | None, players_count: int | None) -> tuple[int, int]:
    if pricing_mode == PricingMode.PER_PLAYER.value:
        if credits is not None:
            units = max(0, int(credits or 0))
            return units, units
        units = max(1, int(players_count or 1))
        return units, units
    units = max(0, int(credits or 0))
    return units, units


def sync_authoritative_players(
    session: Any,
    players_count: int | None = None,
    players: list[str] | None = None,
) -> int:
    cleaned_players = [str(name).strip() for name in (players or []) if str(name).strip()]
    if cleaned_players:
        session.players = cleaned_players
        session.players_count = len(cleaned_players)
        return len(cleaned_players)
    if players_count and int(players_count) > 0:
        session.players_count = int(players_count)
    return resolve_players_count(session)


def apply_authoritative_start_charge(
    session: Any,
    board_status: str,
    players_count: int | None = None,
    players: list[str] | None = None,
) -> ChargeDecision:
    credits_before = int(getattr(session, "credits_remaining", 0) or 0)
    resolved_players = sync_authoritative_players(session, players_count=players_count, players=players)

    if getattr(session, "pricing_mode", None) != PricingMode.PER_PLAYER.value:
        return ChargeDecision(True, False, False, 0, 0, credits_before, credits_before, resolved_players, "pricing_mode_not_start_billed")
    if board_status == BoardStatus.IN_GAME.value:
        return ChargeDecision(True, False, False, 0, resolved_players, credits_before, credits_before, resolved_players, "board_already_in_game")

    billable_players = max(1, int(resolved_players or 1))

    if credits_before < billable_players:
        return ChargeDecision(
            False,
            False,
            True,
            0,
            billable_players,
            credits_before,
            credits_before,
            billable_players,
            "insufficient_credits_for_authoritative_players",
        )

    units = billable_players
    credits_after = max(0, credits_before - units)
    session.credits_remaining = credits_after
    return ChargeDecision(
        True,
        True,
        False,
        units,
        billable_players,
        credits_before,
        credits_after,
        billable_players,
        "per_player_authoritative_start",
    )


def should_record_match_completion(trigger: str) -> bool:
    return trigger in AUTHORITATIVE_FINISH_TRIGGERS


def should_charge_on_finalize(session: Any, trigger: str, board_status: str | None = None) -> bool:
    if getattr(session, "pricing_mode", None) != PricingMode.PER_GAME.value:
        return False
    if trigger in AUTHORITATIVE_FINISH_TRIGGERS:
        return True
    if trigger in ABORT_TRIGGERS:
        return board_status == BoardStatus.IN_GAME.value
    return False


def has_remaining_capacity(session: Any, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    pricing_mode = getattr(session, "pricing_mode", None)
    if pricing_mode == PricingMode.PER_TIME.value:
        expires_at = getattr(session, "expires_at", None)
        if not expires_at:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return now < expires_at
    return int(getattr(session, "credits_remaining", 0) or 0) > 0


def finalize_session_consumption(
    session: Any,
    trigger: str,
    now: datetime | None = None,
    board_status: str | None = None,
) -> FinalizeDecision:
    credits_before = int(getattr(session, "credits_remaining", 0) or 0)
    consume_units = 0
    if should_charge_on_finalize(session, trigger, board_status=board_status):
        consume_units = 1
        session.credits_remaining = max(0, credits_before - consume_units)
    credits_after = int(getattr(session, "credits_remaining", 0) or 0)
    remaining = has_remaining_capacity(session, now=now)
    should_lock = not remaining
    return FinalizeDecision(
        consume_units=consume_units,
        credits_before=credits_before,
        credits_after=credits_after,
        should_lock=should_lock,
        should_teardown=should_lock,
        charge_applied=consume_units > 0,
        has_remaining_capacity=remaining,
        reason="capacity_remaining" if remaining else "capacity_exhausted",
    )
