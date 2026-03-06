"""
Player Statistics & Leaderboard Routes
Stats computed from MatchResult records (not public links).
Guest-first model: nickname only, no PII.
"""
import time
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from backend.database import get_db
from backend.models import MatchResult, Player, Settings, DEFAULT_STAMMKUNDE_DISPLAY

logger = logging.getLogger(__name__)

router = APIRouter()

PERIOD_DAYS = {
    "today": 1,
    "week": 7,
    "month": 30,
    "all": 9999,
}

# In-memory cache for top-registered endpoint (30-60s)
_top_registered_cache: dict = {"data": None, "ts": 0, "key": ""}
TOP_REGISTERED_CACHE_TTL = 45  # seconds


async def _compute_stats(db: AsyncSession, since: Optional[datetime] = None) -> dict:
    """Aggregate per-player stats from MatchResult records."""
    query = select(MatchResult)
    if since:
        query = query.where(MatchResult.played_at >= since)
    query = query.order_by(MatchResult.played_at.desc())

    result = await db.execute(query)
    matches = result.scalars().all()

    # Pre-load registered player lookup
    reg_result = await db.execute(select(Player).where(Player.is_registered == True))
    registered = {p.nickname_lower: p for p in reg_result.scalars().all()}

    players = defaultdict(lambda: {
        "nickname": "",
        "games_played": 0,
        "games_won": 0,
        "total_score": 0,
        "score_entries": 0,
        "best_checkout": None,
        "highest_throw": None,
        "game_types": defaultdict(int),
        "last_played": None,
        "is_registered": False,
        "player_id": None,
    })

    for m in matches:
        played_at = m.played_at or m.created_at
        if played_at and played_at.tzinfo is None:
            played_at = played_at.replace(tzinfo=timezone.utc)

        for name in (m.players or []):
            p = players[name.lower()]
            p["nickname"] = name
            p["games_played"] += 1
            p["game_types"][m.game_type] += 1

            # Check registered status
            reg = registered.get(name.lower())
            if reg:
                p["is_registered"] = True
                p["player_id"] = reg.id

            if not p["last_played"] or (played_at and played_at > p["last_played"]):
                p["last_played"] = played_at

            if m.winner and m.winner.lower() == name.lower():
                p["games_won"] += 1

            if m.scores and name in m.scores:
                val = m.scores[name]
                if isinstance(val, (int, float)):
                    p["total_score"] += val
                    p["score_entries"] += 1
                elif isinstance(val, dict):
                    score_val = val.get("score", val.get("total", 0))
                    if isinstance(score_val, (int, float)):
                        p["total_score"] += score_val
                        p["score_entries"] += 1

                    checkout = val.get("best_checkout")
                    if checkout and (p["best_checkout"] is None or checkout > p["best_checkout"]):
                        p["best_checkout"] = checkout

                    throw = val.get("highest_throw")
                    if throw and (p["highest_throw"] is None or throw > p["highest_throw"]):
                        p["highest_throw"] = throw

    result_list = []
    for data in players.values():
        avg_score = round(data["total_score"] / data["score_entries"], 1) if data["score_entries"] > 0 else None
        win_rate = round(data["games_won"] / data["games_played"] * 100, 1) if data["games_played"] > 0 else 0

        result_list.append({
            "nickname": data["nickname"],
            "games_played": data["games_played"],
            "games_won": data["games_won"],
            "win_rate": win_rate,
            "avg_score": avg_score,
            "best_checkout": data["best_checkout"],
            "highest_throw": data["highest_throw"],
            "game_types": dict(data["game_types"]),
            "last_played": data["last_played"].isoformat() if data["last_played"] else None,
            "is_registered": data["is_registered"],
            "player_id": data["player_id"],
        })

    return result_list


@router.get("/stats/leaderboard")
async def get_leaderboard(
    period: str = "all",
    sort_by: str = "games_won",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Get leaderboard for a time period.
    period: today, week, month, all
    sort_by: games_won, games_played, win_rate, avg_score
    """
    days = PERIOD_DAYS.get(period, 9999)
    since = None
    if days < 9999:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    stats = await _compute_stats(db, since)

    valid_sorts = {"games_won", "games_played", "win_rate", "avg_score"}
    if sort_by not in valid_sorts:
        sort_by = "games_won"

    def sort_key(p):
        val = p.get(sort_by)
        return val if val is not None else -1

    stats.sort(key=sort_key, reverse=True)

    return {
        "period": period,
        "sort_by": sort_by,
        "total_players": len(stats),
        "leaderboard": stats[:limit],
    }


@router.get("/stats/player/{nickname}")
async def get_player_stats(nickname: str, db: AsyncSession = Depends(get_db)):
    """Get detailed stats for a specific player nickname."""
    all_stats = await _compute_stats(db)
    player = next((p for p in all_stats if p["nickname"].lower() == nickname.lower()), None)

    if not player:
        return {"nickname": nickname, "found": False}

    return {"found": True, **player}


@router.get("/stats/top-today")
async def get_top_today(limit: int = 5, db: AsyncSession = Depends(get_db)):
    """Get top players of the day – used by kiosk idle screen rotation."""
    since = datetime.now(timezone.utc) - timedelta(days=1)
    stats = await _compute_stats(db, since)
    stats.sort(key=lambda p: p["games_won"], reverse=True)

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "players": stats[:limit],
    }



@router.get("/stats/top-registered")
async def get_top_registered(
    period: str = "month",
    limit: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """
    Top registered Stammkunden for the kiosk locked screen.
    Cached in-memory for ~45s to avoid DB thrashing.
    Returns only is_registered=True players, sorted by games_won.
    Includes highlight stat (180+ > best_checkout > fallback).
    """
    global _top_registered_cache
    cache_key = f"{period}:{limit}"
    now = time.time()

    if (
        _top_registered_cache["data"] is not None
        and _top_registered_cache["key"] == cache_key
        and now - _top_registered_cache["ts"] < TOP_REGISTERED_CACHE_TTL
    ):
        return _top_registered_cache["data"]

    days = PERIOD_DAYS.get(period, 30)
    since = None
    if days < 9999:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    stats = await _compute_stats(db, since)
    registered_only = [p for p in stats if p.get("is_registered")]
    registered_only.sort(key=lambda p: (p["games_won"], p["games_played"]), reverse=True)
    top = registered_only[:limit]

    # Enrich with highlight stat
    for p in top:
        ht = p.get("highest_throw")
        bc = p.get("best_checkout")
        if ht and ht >= 180:
            p["highlight"] = {"type": "180+", "value": ht, "label": "180!"}
        elif bc and bc >= 80:
            p["highlight"] = {"type": "checkout", "value": bc, "label": f"{bc} Checkout"}
        elif ht and ht >= 100:
            p["highlight"] = {"type": "throw", "value": ht, "label": f"Best: {ht}"}
        else:
            p["highlight"] = {"type": "winrate", "value": p["win_rate"], "label": f"{p['win_rate']}%"}

    # Load display settings
    result = await db.execute(select(Settings).where(Settings.key == "stammkunde_display"))
    setting = result.scalar_one_or_none()
    config = setting.value if setting else DEFAULT_STAMMKUNDE_DISPLAY

    response = {
        "period": period,
        "players": top,
        "config": config,
    }

    _top_registered_cache = {"data": response, "ts": now, "key": cache_key}
    return response


@router.get("/settings/stammkunde-display")
async def get_stammkunde_display(db: AsyncSession = Depends(get_db)):
    """Get Stammkunde display settings (no auth – kiosk needs it)."""
    result = await db.execute(select(Settings).where(Settings.key == "stammkunde_display"))
    setting = result.scalar_one_or_none()
    return setting.value if setting else DEFAULT_STAMMKUNDE_DISPLAY
