from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.auth import AuthUser, get_current_user, require_min_role
from central_server.database import get_db

logger = logging.getLogger("central_server")


def build_device_details_router(
    *,
    get_device_detail_inner,
    get_device_detail_raw_sql,
    finalize_device_detail,
) -> APIRouter:
    router = APIRouter(tags=["device-detail"])

    @router.get("/api/telemetry/device/{device_id}")
    async def get_device_detail(
        device_id: str,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        """
        Get enriched device detail.
        v3.15.2: COMPLETELY hardened — NEVER returns 500.
        Global try/except catches ANY unhandled error and returns partial data.
        Fresh session for raw-SQL fallback to avoid corrupt session state.
        """
        require_min_role(user, "staff")

        try:
            return finalize_device_detail(await get_device_detail_inner(device_id, db, user), user)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "[DEVICE-DETAIL] UNHANDLED ERROR for %s: %s: %s",
                device_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            try:
                return finalize_device_detail(await get_device_detail_raw_sql(device_id, user), user)
            except HTTPException:
                raise
            except Exception as fallback_exc:
                logger.error(
                    "[DEVICE-DETAIL] EVEN RAW-SQL FALLBACK FAILED for %s: %s",
                    device_id,
                    fallback_exc,
                    exc_info=True,
                )
                return finalize_device_detail({
                    "id": device_id,
                    "device_name": "Fehler beim Laden",
                    "status": "error",
                    "binding_status": "unknown",
                    "is_online": False,
                    "last_heartbeat_at": None,
                    "reported_version": None,
                    "last_error": None,
                    "last_activity_at": None,
                    "license_id": None,
                    "location": None,
                    "customer": None,
                    "health_snapshot": None,
                    "device_logs": [],
                    "recent_events": [],
                    "daily_stats": [],
                    "recent_actions": [],
                    "_error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "_fallback_error": f"{type(fallback_exc).__name__}: {str(fallback_exc)[:200]}",
                    "_data_warning": "Daten konnten nicht geladen werden. Bitte pruefen Sie die Server-Logs.",
                }, user)

    return router
