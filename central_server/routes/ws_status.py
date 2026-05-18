from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.auth import AuthUser, get_current_user, require_min_role
from central_server.database import get_db


def build_ws_status_router(
    *,
    device_ws_hub,
    resolve_scoped_device_ids,
    get_device_with_scope_check,
    finalize_ws_device_status,
    can_view_internal_device_detail,
) -> APIRouter:
    router = APIRouter(tags=["ws-status"])

    @router.get("/api/ws/status")
    async def ws_status(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        """Get WebSocket hub status — scoped to the caller's visible devices."""
        require_min_role(user, "owner")
        hub_status = device_ws_hub.status()
        scoped_device_ids = set(await resolve_scoped_device_ids(user, db))
        scoped_raw_devices = {
            did: status
            for did, status in (hub_status.get("devices") or {}).items()
            if did in scoped_device_ids
        }
        devices = {
            did: finalize_ws_device_status(status, user)
            for did, status in scoped_raw_devices.items()
        }
        return {
            "connected_devices": len(devices),
            "total_connections": len(devices),
            "total_events_pushed": sum(int((status or {}).get("events_sent") or 0) for status in scoped_raw_devices.values()),
            "devices": devices,
            "detail_level": "internal" if can_view_internal_device_detail(user) else "operator_safe",
        }

    @router.get("/api/ws/device/{device_id}")
    async def ws_device_status(device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        """Get WS connection status for a specific device."""
        require_min_role(user, "staff")
        await get_device_with_scope_check(device_id, user, db)
        return finalize_ws_device_status(device_ws_hub.device_ws_status(device_id), user)

    return router
