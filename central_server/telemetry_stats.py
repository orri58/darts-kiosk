"""Telemetry helper functions extracted from server.py for clearer separation.
Provides device ID resolution respecting user scope, and daily stats aggregation utilities.
"""

from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import select, func

from central_server.database import AsyncSessionLocal
from central_server.models import (
    CentralDevice, CentralLocation, CentralCustomer,
    DeviceDailyStats, TelemetryEvent, RegistrationToken,
)
from central_server.auth import can_access_customer, can_access_location
from central_server.services.device_trust_details import _can_view_internal_device_detail
from central_server.services.ws_status import _to_operator_safe_warning

# Note: ONLINE_THRESHOLD_SECONDS defined in telemetry.py; import if needed elsewhere.

async def _resolve_scoped_device_ids(user, db, customer_id=None, location_id=None, device_id=None):
    """Resolve device IDs respecting user scope.
    Returns list of device IDs.
    """
    if device_id:
        result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
        d = result.scalar_one_or_none()
        if not d:
            return []
        if not await can_access_location(user, d.location_id, db):
            return []
        return [device_id]

    if location_id:
        if not await can_access_location(user, location_id, db):
            return []
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id == location_id))
        return [r[0] for r in result.fetchall()]

    if customer_id:
        if not can_access_customer(user, customer_id):
            return []
        loc_r = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id == customer_id))
        loc_ids = [r[0] for r in loc_r.fetchall()]
        if not loc_ids:
            return []
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id.in_(loc_ids)))
        return [r[0] for r in result.fetchall()]

    # No specific filter – use user scope
    if user.is_superadmin:
        result = await db.execute(select(CentralDevice.id))
        return [r[0] for r in result.fetchall()]
    else:
        allowed = user.allowed_customer_ids or []
        if not allowed:
            return []
        loc_r = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id.in_(allowed)))
        loc_ids = [r[0] for r in loc_r.fetchall()]
        if not loc_ids:
            return []
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id.in_(loc_ids)))
        return [r[0] for r in result.fetchall()]

async def _get_or_create_daily_stats(db, device_id: str, date_str: str) -> DeviceDailyStats:
    """Get or create a daily stats row for device+date."""
    result = await db.execute(
        select(DeviceDailyStats).where(
            DeviceDailyStats.device_id == device_id,
            DeviceDailyStats.date == date_str,
        )
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = DeviceDailyStats(device_id=device_id, date=date_str)
        db.add(stats)
        await db.flush()
    return stats

async def _aggregate_daily_stats(db, device_ids: list, start_date: str, end_date: str) -> dict:
    """Aggregate daily stats across devices and date range."""
    if not device_ids:
        return {"revenue_cents": 0, "sessions": 0, "games": 0, "credits_added": 0, "errors": 0}

    result = await db.execute(
        select(
            func.coalesce(func.sum(DeviceDailyStats.revenue_cents), 0),
            func.coalesce(func.sum(DeviceDailyStats.sessions), 0),
            func.coalesce(func.sum(DeviceDailyStats.games), 0),
            func.coalesce(func.sum(DeviceDailyStats.credits_added), 0),
            func.coalesce(func.sum(DeviceDailyStats.errors), 0),
        ).where(
            DeviceDailyStats.device_id.in_(device_ids),
            DeviceDailyStats.date >= start_date,
            DeviceDailyStats.date <= end_date,
        )
    )
    row = result.first()
    return {
        "revenue_cents": row[0] or 0,
        "sessions": row[1] or 0,
        "games": row[2] or 0,
        "credits_added": row[3] or 0,
        "errors": row[4] or 0,
    }

