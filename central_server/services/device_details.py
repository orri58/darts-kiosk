from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from central_server.auth import AuthUser, can_access_customer
from central_server.models import (
    CentralCustomer,
    CentralDevice,
    CentralLocation,
    DeviceCredential,
    DeviceCredentialStatus,
    DeviceDailyStats,
    DeviceLease,
    DeviceLeaseStatus,
    DeviceTrustStatus,
    RemoteAction,
    TelemetryEvent,
)

logger = logging.getLogger("central_server")


def safe_raw_dt(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).isoformat()
    except Exception:
        return None


def safe_json_parse(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(str(val))
    except Exception:
        return None


async def get_device_detail_raw_sql(
    device_id: str,
    user: AuthUser,
    *,
    session_factory: async_sessionmaker,
    compute_device_connectivity,
):
    async with session_factory() as fresh_db:
        row = (await fresh_db.execute(
            text("SELECT * FROM devices WHERE id = :did"), {"did": device_id}
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Device not found")
        dev_raw = dict(row)

        loc = None
        cust = None
        try:
            loc_id = dev_raw.get("location_id")
            if loc_id:
                loc_row = (await fresh_db.execute(
                    text("SELECT id, name, customer_id, status FROM locations WHERE id = :lid"),
                    {"lid": loc_id}
                )).mappings().first()
                if loc_row:
                    cust_id = loc_row["customer_id"]
                    if cust_id and not can_access_customer(user, cust_id):
                        raise HTTPException(403, "No access to this device")
                    loc = {"id": loc_row["id"], "name": loc_row["name"]}
                    if cust_id:
                        cust_row = (await fresh_db.execute(
                            text("SELECT id, name FROM customers WHERE id = :cid"),
                            {"cid": cust_id}
                        )).mappings().first()
                        if cust_row:
                            cust = {"id": cust_row["id"], "name": cust_row["name"]}
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("[DEVICE-DETAIL-RAW] Location/customer lookup failed: %s", exc)

        recent_events = []
        try:
            ev_rows = (await fresh_db.execute(
                text("SELECT event_type, timestamp, data FROM telemetry_events WHERE device_id = :did ORDER BY timestamp DESC LIMIT 10"),
                {"did": device_id}
            )).mappings().all()
            for ev in ev_rows:
                recent_events.append({
                    "event_type": ev.get("event_type"),
                    "timestamp": safe_raw_dt(ev.get("timestamp")),
                    "data": safe_json_parse(ev.get("data")),
                })
        except Exception as exc:
            logger.warning("[DEVICE-DETAIL-RAW] Events query failed: %s", exc)

        daily_stats = []
        try:
            stats_rows = (await fresh_db.execute(
                text("SELECT date, revenue_cents, sessions, games, credits_added, errors FROM device_daily_stats WHERE device_id = :did ORDER BY date DESC LIMIT 7"),
                {"did": device_id}
            )).mappings().all()
            for stat in stats_rows:
                daily_stats.append({
                    "date": str(stat.get("date")) if stat.get("date") else None,
                    "revenue_cents": stat.get("revenue_cents", 0) or 0,
                    "sessions": stat.get("sessions", 0) or 0,
                    "games": stat.get("games", 0) or 0,
                    "credits_added": stat.get("credits_added", 0) or 0,
                    "errors": stat.get("errors", 0) or 0,
                })
        except Exception as exc:
            logger.warning("[DEVICE-DETAIL-RAW] Stats query failed: %s", exc)

        recent_actions = []
        try:
            act_rows = (await fresh_db.execute(
                text("SELECT id, action_type, status, issued_by, issued_at, acked_at, result_message, params FROM remote_actions WHERE device_id = :did ORDER BY issued_at DESC LIMIT 10"),
                {"did": device_id}
            )).mappings().all()
            for action in act_rows:
                recent_actions.append({
                    "id": action.get("id"),
                    "action_type": action.get("action_type"),
                    "status": action.get("status"),
                    "issued_by": action.get("issued_by"),
                    "issued_at": safe_raw_dt(action.get("issued_at")),
                    "acked_at": safe_raw_dt(action.get("acked_at")),
                    "result_message": action.get("result_message"),
                    "params": safe_json_parse(action.get("params")),
                })
        except Exception as exc:
            logger.warning("[DEVICE-DETAIL-RAW] Actions query failed: %s", exc)

        health_snapshot = safe_json_parse(dev_raw.get("health_snapshot"))
        device_logs = safe_json_parse(dev_raw.get("device_logs")) or []
        hb_raw = dev_raw.get("last_heartbeat_at")
        connectivity = compute_device_connectivity(hb_raw) if hb_raw else "offline"

        return {
            "id": dev_raw.get("id"),
            "device_name": dev_raw.get("device_name"),
            "hardware_id": dev_raw.get("hardware_id"),
            "status": dev_raw.get("status", "unknown"),
            "license_id": dev_raw.get("license_id"),
            "binding_status": dev_raw.get("binding_status", "unknown"),
            "is_online": connectivity == "online",
            "connectivity": connectivity,
            "last_heartbeat_at": safe_raw_dt(hb_raw),
            "reported_version": dev_raw.get("reported_version"),
            "last_error": dev_raw.get("last_error"),
            "last_activity_at": safe_raw_dt(dev_raw.get("last_activity_at")),
            "location": loc,
            "customer": cust,
            "health_snapshot": health_snapshot,
            "device_logs": device_logs,
            "recent_events": recent_events,
            "daily_stats": daily_stats,
            "recent_actions": recent_actions,
            "_data_warning": "Teilweise Daten — ORM-Fallback auf Raw-SQL aktiv",
        }


async def get_device_detail_inner(
    device_id: str,
    db: AsyncSession,
    user: AuthUser,
    *,
    get_device_detail_raw_sql_fallback,
    compute_device_connectivity,
    serialize_action,
):
    dev = None
    try:
        dev = await db.get(CentralDevice, device_id)
    except Exception as exc:
        logger.warning(
            "[DEVICE-DETAIL] ORM load failed for %s: %s: %s — raw SQL fallback",
            device_id,
            type(exc).__name__,
            exc,
        )
        try:
            await db.rollback()
        except Exception:
            pass
        return await get_device_detail_raw_sql_fallback(device_id, user)

    if not dev:
        raise HTTPException(404, "Device not found")

    loc = None
    cust = None
    try:
        if dev.location_id:
            loc = await db.get(CentralLocation, dev.location_id)
            if loc and not can_access_customer(user, loc.customer_id):
                raise HTTPException(403, "No access to this device")
            if loc and loc.customer_id:
                cust = await db.get(CentralCustomer, loc.customer_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("[DEVICE-DETAIL] Access/location check failed for %s: %s", device_id, exc)

    connectivity = compute_device_connectivity(dev.last_heartbeat_at)
    is_online = connectivity == "online"

    def _safe_dt(val):
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    recent_events = []
    try:
        events_q = await db.execute(
            select(TelemetryEvent)
            .where(TelemetryEvent.device_id == device_id)
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(10)
        )
        for event in events_q.scalars().all():
            try:
                timestamp = event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp) if event.timestamp else None
            except Exception:
                timestamp = str(event.timestamp) if event.timestamp else None
            recent_events.append({
                "event_type": event.event_type,
                "timestamp": timestamp,
                "data": event.data if isinstance(event.data, (dict, list, type(None))) else str(event.data),
            })
    except Exception as exc:
        logger.warning("[DEVICE-DETAIL] Events query failed for %s: %s", device_id, exc)

    daily_stats = []
    try:
        stats_q = await db.execute(
            select(DeviceDailyStats)
            .where(DeviceDailyStats.device_id == device_id)
            .order_by(DeviceDailyStats.date.desc())
            .limit(7)
        )
        for stat in stats_q.scalars().all():
            daily_stats.append({
                "date": str(stat.date) if stat.date else None,
                "revenue_cents": stat.revenue_cents or 0,
                "sessions": stat.sessions or 0,
                "games": stat.games or 0,
                "credits_added": stat.credits_added or 0,
                "errors": stat.errors or 0,
            })
    except Exception as exc:
        logger.warning("[DEVICE-DETAIL] Stats query failed for %s: %s", device_id, exc)

    recent_credentials = []
    try:
        credentials_q = await db.execute(
            select(DeviceCredential)
            .where(DeviceCredential.device_id == device_id)
            .order_by(DeviceCredential.created_at.desc())
            .limit(5)
        )
        for credential in credentials_q.scalars().all():
            recent_credentials.append({
                "id": credential.id,
                "status": credential.status,
                "credential_kind": credential.credential_kind,
                "fingerprint": credential.fingerprint,
                "issued_at": _safe_dt(credential.issued_at),
                "expires_at": _safe_dt(credential.expires_at),
                "revoked_at": _safe_dt(credential.revoked_at),
            })
    except Exception as exc:
        logger.warning("[DEVICE-DETAIL] Credential query failed for %s: %s", device_id, exc)

    recent_leases = []
    try:
        leases_q = await db.execute(
            select(DeviceLease)
            .where(DeviceLease.device_id == device_id)
            .order_by(DeviceLease.created_at.desc())
            .limit(5)
        )
        for lease in leases_q.scalars().all():
            recent_leases.append({
                "id": lease.id,
                "lease_id": lease.lease_id,
                "status": lease.status,
                "issued_at": _safe_dt(lease.issued_at),
                "expires_at": _safe_dt(lease.expires_at),
                "grace_until": _safe_dt(lease.grace_until),
                "revoked_at": _safe_dt(lease.revoked_at),
            })
    except Exception as exc:
        logger.warning("[DEVICE-DETAIL] Lease query failed for %s: %s", device_id, exc)

    recent_actions = []
    try:
        actions_q = await db.execute(
            select(RemoteAction)
            .where(RemoteAction.device_id == device_id)
            .order_by(RemoteAction.issued_at.desc())
            .limit(10)
        )
        for action in actions_q.scalars().all():
            try:
                recent_actions.append(serialize_action(action))
            except Exception as action_exc:
                logger.warning("[DEVICE-DETAIL] Action serialization failed: %s", action_exc)
                recent_actions.append({
                    "id": str(getattr(action, "id", "?")),
                    "action_type": str(getattr(action, "action_type", "?")),
                    "status": str(getattr(action, "status", "?")),
                    "issued_by": str(getattr(action, "issued_by", "?")),
                    "issued_at": None,
                    "acked_at": None,
                    "result_message": None,
                })
    except Exception as exc:
        logger.warning("[DEVICE-DETAIL] Actions query failed for %s: %s", device_id, exc)

    health_snapshot = None
    stored_logs = []
    try:
        if dev.health_snapshot:
            health_snapshot = json.loads(dev.health_snapshot)
    except Exception:
        pass
    try:
        if dev.device_logs:
            stored_logs = json.loads(dev.device_logs)
    except Exception:
        pass

    return {
        "id": dev.id,
        "device_name": dev.device_name,
        "hardware_id": getattr(dev, "hardware_id", None),
        "status": dev.status,
        "license_id": dev.license_id,
        "binding_status": getattr(dev, "binding_status", None),
        "trust_status": getattr(dev, "trust_status", DeviceTrustStatus.LEGACY_UNBOUND.value),
        "trust_reason": getattr(dev, "trust_reason", None),
        "trust_last_changed_at": _safe_dt(getattr(dev, "trust_last_changed_at", None)),
        "replacement_of_device_id": getattr(dev, "replacement_of_device_id", None),
        "credential_status": getattr(dev, "credential_status", DeviceCredentialStatus.NONE.value),
        "credential_fingerprint": getattr(dev, "credential_fingerprint", None),
        "credential_issued_at": _safe_dt(getattr(dev, "credential_issued_at", None)),
        "credential_expires_at": _safe_dt(getattr(dev, "credential_expires_at", None)),
        "lease_status": getattr(dev, "lease_status", DeviceLeaseStatus.NONE.value),
        "lease_id": getattr(dev, "lease_id", None),
        "lease_issued_at": _safe_dt(getattr(dev, "lease_issued_at", None)),
        "lease_expires_at": _safe_dt(getattr(dev, "lease_expires_at", None)),
        "lease_grace_until": _safe_dt(getattr(dev, "lease_grace_until", None)),
        "lease_metadata": safe_json_parse(getattr(dev, "lease_metadata", None)),
        "is_online": is_online,
        "connectivity": connectivity,
        "last_heartbeat_at": _safe_dt(dev.last_heartbeat_at),
        "reported_version": dev.reported_version,
        "last_error": dev.last_error,
        "last_activity_at": _safe_dt(dev.last_activity_at),
        "location": {"id": loc.id, "name": loc.name} if loc else None,
        "customer": {"id": cust.id, "name": cust.name} if cust else None,
        "health_snapshot": health_snapshot,
        "device_logs": stored_logs,
        "recent_events": recent_events,
        "daily_stats": daily_stats,
        "recent_credentials": recent_credentials,
        "recent_leases": recent_leases,
        "recent_actions": recent_actions,
    }
