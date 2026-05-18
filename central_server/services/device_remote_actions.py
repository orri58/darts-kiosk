from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.models import RemoteAction
from central_server.remote_action_policy import can_deliver_remote_action, is_remote_action_expired


async def get_pending_device_remote_actions(
    device_id: str,
    *,
    device,
    db: AsyncSession,
    utcnow,
    serialize_action,
    log_audit,
    remote_action_lifecycle_details,
) -> list[dict]:
    if device.id != device_id:
        raise HTTPException(403, "Authenticated device may only fetch its own actions")

    stmt = (
        select(RemoteAction)
        .where(RemoteAction.device_id == device_id, RemoteAction.status == "pending")
        .order_by(RemoteAction.issued_at.asc())
    )
    result = await db.execute(stmt)
    actions = result.scalars().all()

    deliverable = []
    mutated = False
    for action in actions:
        if (getattr(action, "approval_state", None) or "not_required") == "pending":
            continue
        if not can_deliver_remote_action(action.action_type):
            action.status = "expired"
            action.request_state = "expired"
            action.approval_state = getattr(action, "approval_state", None) or "not_required"
            action.outcome_code = "blocked"
            action.outcome_detail = "central_policy"
            action.acked_at = utcnow()
            action.finalized_at = action.acked_at
            action.finalized_by = "central_policy"
            action.result_message = "Blocked by central remote-action policy before device delivery"
            mutated = True
            continue
        if is_remote_action_expired(action.action_type, action.issued_at, utcnow()):
            action.status = "expired"
            action.request_state = "expired"
            action.outcome_code = "expired"
            action.outcome_detail = "ttl_elapsed"
            action.acked_at = utcnow()
            action.finalized_at = action.acked_at
            action.finalized_by = "central_ttl"
            action.result_message = "Expired before device delivery"
            mutated = True
            continue
        action.request_state = "delivered"
        action.delivered_at = action.delivered_at or utcnow()
        action.outcome_code = "delivered"
        action.outcome_detail = "ready_for_device_execution"
        mutated = True
        deliverable.append(action)

    if mutated:
        await db.commit()
        for action in actions:
            if action.status == "expired" and action.outcome_code in {"blocked", "expired"}:
                await log_audit(
                    db,
                    "remote_action_auto_finalized",
                    device_id=action.device_id,
                    license_id=getattr(device, "license_id", None),
                    actor="central",
                    message=f"Remote action {action.action_type} auto-finalized ({action.outcome_detail})",
                    details=remote_action_lifecycle_details(
                        action,
                        event="auto_finalized",
                        actor="central",
                        extra={"auto_finalized_reason": action.outcome_detail},
                    ),
                )
        await db.commit()

    return [serialize_action(action) for action in deliverable]


async def ack_device_remote_action(
    device_id: str,
    *,
    device,
    action_id: str,
    success: bool,
    message: str,
    db: AsyncSession,
    utcnow,
    log_audit,
    remote_action_lifecycle_details,
) -> dict:
    if device.id != device_id:
        raise HTTPException(403, "Authenticated device may only ack its own actions")

    action = await db.get(RemoteAction, action_id)
    if not action or action.device_id != device_id:
        raise HTTPException(404, "Action not found")
    if action.status != "pending":
        raise HTTPException(409, f"Action already finalized with status '{action.status}'")

    action.status = "acked" if success else "failed"
    action.request_state = "finalized"
    action.outcome_code = "succeeded" if success else "failed"
    action.outcome_detail = "device_ack" if success else "device_reported_failure"
    action.acked_at = utcnow()
    action.finalized_at = action.acked_at
    action.finalized_by = "device"
    action.result_message = message
    await db.commit()
    await log_audit(
        db,
        "remote_action_finalized",
        device_id=device_id,
        license_id=getattr(device, "license_id", None),
        actor="device",
        message=f"Remote action {action.action_type} finalized with {action.outcome_code}",
        details=remote_action_lifecycle_details(
            action,
            event="finalized",
            actor="device",
            extra={"success": bool(success)},
        ),
    )
    await db.commit()
    return {"ok": True}
