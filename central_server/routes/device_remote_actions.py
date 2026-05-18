from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db
from central_server.services.device_remote_actions import (
    ack_device_remote_action,
    get_pending_device_remote_actions,
)


def build_device_remote_actions_router(
    *,
    utcnow,
    authenticate_device,
    log_audit,
    serialize_action,
    remote_action_lifecycle_details,
) -> APIRouter:
    router = APIRouter(tags=["device-remote-actions"])

    @router.get("/api/remote-actions/{device_id}/pending")
    async def get_pending_actions(
        device_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
    ):
        device = await authenticate_device(request, db)
        return await get_pending_device_remote_actions(
            device_id,
            device=device,
            db=db,
            utcnow=utcnow,
            serialize_action=serialize_action,
            log_audit=log_audit,
            remote_action_lifecycle_details=remote_action_lifecycle_details,
        )

    @router.post("/api/remote-actions/{device_id}/ack")
    async def ack_remote_action(
        device_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
    ):
        device = await authenticate_device(request, db)
        body = await request.json()
        return await ack_device_remote_action(
            device_id,
            device=device,
            action_id=body.get("action_id"),
            success=body.get("success", True),
            message=body.get("message", ""),
            db=db,
            utcnow=utcnow,
            log_audit=log_audit,
            remote_action_lifecycle_details=remote_action_lifecycle_details,
        )

    return router
