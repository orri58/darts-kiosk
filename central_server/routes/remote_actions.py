from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.auth import (
    AuthUser,
    can_access_customer,
    can_access_location,
    get_current_user,
    require_installer_or_above,
    require_min_role,
)
from central_server.database import get_db
from central_server.models import (
    CentralCustomer,
    CentralDevice,
    CentralLicense,
    CentralLocation,
    RemoteAction,
)
from central_server.remote_action_policy import (
    RemoteActionPolicyError,
    validate_remote_action_request,
)
from central_server.services.audit import log_audit
from central_server.services.remote_actions import (
    VALID_ACTIONS,
    build_remote_action_review_fields,
    remote_action_problem_scope_payload,
    remote_action_queue_metrics,
    remote_action_lifecycle_details,
    remote_action_scope_snapshot,
    remote_action_summary_payload,
    remote_action_triage_priority,
    utcnow,
)


logger = logging.getLogger("central_server")

_BULK_MAX_DEVICES = 50
_BULK_DEDUP_SECONDS = 30


def build_remote_actions_router(
    *,
    get_device_with_scope_check,
    serialize_action,
    finalize_remote_action,
    device_ws_hub,
) -> APIRouter:
    router = APIRouter(tags=["remote-actions"])

    async def _load_remote_action_scope_maps(db: AsyncSession, actions: list[RemoteAction]) -> tuple[dict, dict, dict, dict]:
        device_ids = {a.device_id for a in actions if getattr(a, "device_id", None)}
        devices_by_id = {}
        locations_by_id = {}
        customers_by_id = {}
        licenses_by_id = {}
        if device_ids:
            device_result = await db.execute(select(CentralDevice).where(CentralDevice.id.in_(device_ids)))
            devices = device_result.scalars().all()
            devices_by_id = {device.id: device for device in devices}
            location_ids = {device.location_id for device in devices if getattr(device, "location_id", None)}
            license_ids = {device.license_id for device in devices if getattr(device, "license_id", None)}
            if location_ids:
                location_result = await db.execute(select(CentralLocation).where(CentralLocation.id.in_(location_ids)))
                locations = location_result.scalars().all()
                locations_by_id = {location.id: location for location in locations}
                customer_ids = {location.customer_id for location in locations if getattr(location, "customer_id", None)}
                if customer_ids:
                    customer_result = await db.execute(select(CentralCustomer).where(CentralCustomer.id.in_(customer_ids)))
                    customers_by_id = {customer.id: customer for customer in customer_result.scalars().all()}
            if license_ids:
                license_result = await db.execute(select(CentralLicense).where(CentralLicense.id.in_(license_ids)))
                licenses_by_id = {license_row.id: license_row for license_row in license_result.scalars().all()}
        return devices_by_id, locations_by_id, customers_by_id, licenses_by_id

    async def _query_scoped_remote_actions(
        db: AsyncSession,
        user: AuthUser,
        *,
        customer_id: str | None = None,
        location_id: str | None = None,
        license_id: str | None = None,
        device_id: str | None = None,
        request_state: str | None = None,
        approval_state: str | None = None,
        outcome_code: str | None = None,
        action_type: str | None = None,
        include_expired: bool = True,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[RemoteAction]:
        stmt = select(RemoteAction).join(CentralDevice, RemoteAction.device_id == CentralDevice.id).join(CentralLocation, CentralDevice.location_id == CentralLocation.id)
        if customer_id:
            if not can_access_customer(user, customer_id):
                raise HTTPException(403, "Access denied")
            stmt = stmt.where(CentralLocation.customer_id == customer_id)
        elif location_id:
            if not await can_access_location(user, location_id, db):
                raise HTTPException(403, "Access denied")
            stmt = stmt.where(CentralDevice.location_id == location_id)
        elif device_id:
            await get_device_with_scope_check(device_id, user, db)
            stmt = stmt.where(RemoteAction.device_id == device_id)
        elif not user.is_superadmin:
            allowed_customer_ids = user.allowed_customer_ids or []
            stmt = stmt.where(CentralLocation.customer_id.in_(allowed_customer_ids) if allowed_customer_ids else False)

        if license_id:
            license_row = await db.get(CentralLicense, license_id)
            if not license_row:
                raise HTTPException(404, "License not found")
            if not can_access_customer(user, license_row.customer_id):
                raise HTTPException(403, "Access denied")
            stmt = stmt.where(CentralDevice.license_id == license_id)

        if request_state:
            stmt = stmt.where(RemoteAction.request_state == request_state)
        if approval_state:
            stmt = stmt.where(RemoteAction.approval_state == approval_state)
        if outcome_code:
            stmt = stmt.where(RemoteAction.outcome_code == outcome_code)
        if action_type:
            stmt = stmt.where(RemoteAction.action_type == action_type)
        if not include_expired:
            stmt = stmt.where(RemoteAction.status != "expired")

        stmt = stmt.order_by(RemoteAction.issued_at.desc())
        if offset:
            stmt = stmt.offset(max(0, offset))
        if limit:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    @router.post("/api/remote-actions/bulk")
    async def bulk_remote_actions(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        body = await request.json()
        device_ids = body.get("device_ids", [])
        action_type = body.get("action_type", "")
        action_params = body.get("params")
        is_retry = body.get("is_retry", False)
        retry_ref = body.get("retry_ref")

        if not isinstance(device_ids, list) or len(device_ids) == 0:
            raise HTTPException(400, "device_ids must be a non-empty list")
        if len(device_ids) > _BULK_MAX_DEVICES:
            raise HTTPException(400, f"Maximal {_BULK_MAX_DEVICES} Geraete pro Bulk-Aktion")
        if action_type not in VALID_ACTIONS:
            raise HTTPException(400, f"action_type must be one of: {', '.join(sorted(VALID_ACTIONS))}")
        try:
            policy = validate_remote_action_request(action_type=action_type, params=action_params, user_role=user.role)
        except RemoteActionPolicyError as e:
            raise HTTPException(403, str(e))

        unique_ids = list(dict.fromkeys(device_ids))
        results = []
        created_count = skipped_count = denied_count = 0

        for did in unique_ids:
            dev = await db.get(CentralDevice, did)
            if not dev:
                results.append({"device_id": did, "status": "error", "message": "Geraet nicht gefunden"})
                continue
            if dev.location_id:
                loc = await db.get(CentralLocation, dev.location_id)
                if loc and not can_access_customer(user, loc.customer_id):
                    results.append({"device_id": did, "device_name": dev.device_name, "status": "denied", "message": "Kein Zugriff"})
                    denied_count += 1
                    continue

            dedup_cutoff = utcnow() - timedelta(seconds=_BULK_DEDUP_SECONDS)
            dedup_q = await db.execute(
                select(RemoteAction).where(
                    RemoteAction.device_id == did,
                    RemoteAction.action_type == action_type,
                    RemoteAction.issued_at >= dedup_cutoff,
                    RemoteAction.status == "pending",
                ).limit(1)
            )
            if dedup_q.scalar_one_or_none():
                results.append({"device_id": did, "device_name": dev.device_name, "status": "skipped", "message": "Bereits ausstehend"})
                skipped_count += 1
                continue

            action = RemoteAction(
                id=secrets.token_hex(18),
                device_id=did,
                action_type=action_type,
                params=action_params,
                issued_by=user.username,
                **build_remote_action_review_fields(policy, user, body),
            )
            db.add(action)
            results.append({
                "device_id": did,
                "device_name": dev.device_name,
                "status": "created",
                "action_id": action.id,
                "request_state": action.request_state,
                "approval_state": action.approval_state,
            })
            created_count += 1

        await db.commit()
        audit_msg = f"Bulk '{action_type}': {created_count} erstellt, {skipped_count} uebersprungen, {denied_count} verweigert von {len(unique_ids)} Geraeten"
        if is_retry:
            audit_msg = f"[RETRY] {audit_msg}"
        try:
            await log_audit(db, "bulk_remote_action", actor=user.username, message=audit_msg)
            await db.commit()
        except Exception:
            pass

        try:
            created_device_ids = [r["device_id"] for r in results if r["status"] == "created"]
            if created_device_ids:
                await device_ws_hub.push_to_devices(created_device_ids, "action_created", {"action_type": action_type, "bulk": True})
        except Exception as e:
            logger.debug(f"[WS-PUSH] bulk action push error: {e}")

        return {
            "action_type": action_type,
            "total": len(unique_ids),
            "created": created_count,
            "skipped": skipped_count,
            "denied": denied_count,
            "is_retry": is_retry,
            "retry_ref": retry_ref,
            "results": results,
        }

    @router.post("/api/remote-actions/{device_id}")
    async def issue_remote_action(
        device_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "owner")

        dev = await db.get(CentralDevice, device_id)
        if not dev:
            raise HTTPException(404, "Device not found")
        if dev.location_id:
            loc = await db.get(CentralLocation, dev.location_id)
            if loc and not can_access_customer(user, loc.customer_id):
                raise HTTPException(403, "No access to this device")

        body = await request.json()
        action_type = body.get("action_type", "")
        if action_type not in VALID_ACTIONS:
            raise HTTPException(400, f"action_type must be one of: {', '.join(sorted(VALID_ACTIONS))}")

        action_params = body.get("params")
        try:
            policy = validate_remote_action_request(action_type=action_type, params=action_params, user_role=user.role)
        except RemoteActionPolicyError as e:
            raise HTTPException(403, str(e))

        action = RemoteAction(
            device_id=device_id,
            action_type=action_type,
            params=action_params if action_params else None,
            issued_by=user.username,
            **build_remote_action_review_fields(policy, user, body),
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)

        await log_audit(
            db,
            "remote_action_issued",
            device_id=device_id,
            actor=user.username,
            license_id=getattr(dev, "license_id", None),
            message=f"Action '{action_type}' issued for device {dev.device_name or device_id}",
            details=remote_action_lifecycle_details(action, event="issued", actor=user.username),
        )
        await db.commit()

        try:
            await device_ws_hub.push_to_device(device_id, "action_created", {"action_type": action_type, "action_id": action.id})
        except Exception as e:
            logger.debug(f"[WS-PUSH] action push error: {e}")

        return serialize_action(action)

    @router.post("/api/remote-actions/{action_id}/review")
    async def review_remote_action(
        action_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_installer_or_above(user)
        action = await db.get(RemoteAction, action_id)
        if not action:
            raise HTTPException(404, "Action not found")
        await get_device_with_scope_check(action.device_id, user, db)

        body = await request.json()
        decision = (body.get("decision") or "").strip().lower()
        if decision not in {"approve", "refuse"}:
            raise HTTPException(400, "decision must be approve|refuse")
        if (getattr(action, "approval_state", None) or "not_required") != "pending":
            raise HTTPException(409, f"Action review not pending (approval_state='{getattr(action, 'approval_state', None) or 'not_required'}')")

        now = utcnow()
        action.reviewed_at = now
        action.reviewed_by = user.username
        action.review_note = body.get("review_note") or body.get("note")
        if decision == "approve":
            action.approval_state = "approved"
            action.request_state = "approved"
            action.outcome_code = "accepted"
            action.outcome_detail = "approved"
            audit_action = "remote_action_review_approved"
        else:
            action.approval_state = "refused"
            action.request_state = "refused"
            action.status = "failed"
            action.outcome_code = "refused"
            action.outcome_detail = "manual_review"
            action.finalized_at = now
            action.finalized_by = user.username
            action.acked_at = now
            action.result_message = action.result_message or "Refused during central review"
            audit_action = "remote_action_review_refused"

        await db.commit()
        await db.refresh(action)
        await log_audit(
            db,
            audit_action,
            device_id=action.device_id,
            actor=user.username,
            license_id=getattr((await db.get(CentralDevice, action.device_id)), "license_id", None),
            message=f"Remote action {action.action_type} {decision}d",
            details=remote_action_lifecycle_details(action, event=f"review_{decision}d", actor=user.username, extra={"decision": decision}),
        )
        await db.commit()
        return finalize_remote_action(serialize_action(action), user)

    @router.get("/api/remote-actions/overview")
    async def get_remote_action_overview(
        customer_id: str = None,
        location_id: str = None,
        license_id: str = None,
        request_state: str = None,
        approval_state: str = None,
        outcome_code: str = None,
        action_type: str = None,
        include_expired: bool = True,
        offset: int = 0,
        limit: int = 100,
        recent_limit: int = 25,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "staff")
        capped_limit = max(1, min(limit, 250))
        actions = await _query_scoped_remote_actions(
            db,
            user,
            customer_id=customer_id,
            location_id=location_id,
            license_id=license_id,
            request_state=request_state,
            approval_state=approval_state,
            outcome_code=outcome_code,
            action_type=action_type,
            include_expired=include_expired,
            offset=max(0, offset),
            limit=capped_limit,
        )
        devices_by_id, locations_by_id, customers_by_id, licenses_by_id = await _load_remote_action_scope_maps(db, actions)

        def build_grouped_summary(group_key: str):
            grouped: dict[str, dict] = {}
            for action in actions:
                device = devices_by_id.get(action.device_id)
                if device is None:
                    continue
                location = locations_by_id.get(device.location_id)
                customer = customers_by_id.get(location.customer_id) if location is not None else None
                license_row = licenses_by_id.get(device.license_id)
                if group_key == "location" and location is None:
                    continue
                if group_key == "license" and license_row is None:
                    continue
                if group_key == "customer" and customer is None:
                    continue

                if group_key == "device":
                    gid = device.id
                    name = device.device_name or device.id
                elif group_key == "location":
                    gid = location.id
                    name = location.name
                elif group_key == "license":
                    gid = license_row.id
                    name = f"{license_row.plan_type}"
                else:
                    gid = customer.id
                    name = customer.name

                bucket = grouped.setdefault(gid, {
                    "group_id": gid,
                    "group_type": group_key,
                    "group_name": name,
                    "scope": remote_action_scope_snapshot(action, device=device, location=location, customer=customer, license_row=license_row),
                    "actions": [],
                })
                bucket["actions"].append(action)

            items = []
            for bucket in grouped.values():
                summary = remote_action_summary_payload(bucket.pop("actions"))
                items.append({
                    **bucket,
                    "summary": summary,
                    "triage_priority": {
                        "pending_approval": summary["counts"]["pending_approval"],
                        "pending_delivery": summary["counts"]["pending_delivery"],
                        "expired": summary["counts"]["expired"],
                        "refused": summary["counts"]["refused"],
                        "has_pending_review": summary["has_pending_review"],
                    },
                })
            items.sort(key=lambda item: remote_action_triage_priority(item.get("summary")))
            return items

        recent_items = []
        for action in actions[: max(1, min(recent_limit, 100))]:
            payload = serialize_action(action)
            device = devices_by_id.get(action.device_id)
            location = locations_by_id.get(device.location_id) if device is not None else None
            customer = customers_by_id.get(location.customer_id) if location is not None else None
            license_row = licenses_by_id.get(device.license_id) if device is not None else None
            payload["scope"] = remote_action_scope_snapshot(payload, device=device, location=location, customer=customer, license_row=license_row)
            recent_items.append(finalize_remote_action(payload, user))

        return {
            "scope": {
                "customer_id": customer_id,
                "location_id": location_id,
                "license_id": license_id,
            },
            "filters": {
                "request_state": request_state,
                "approval_state": approval_state,
                "outcome_code": outcome_code,
                "action_type": action_type,
                "include_expired": include_expired,
            },
            "window": {
                "offset": max(0, offset),
                "limit": capped_limit,
                "returned": len(actions),
                "has_more": len(actions) == capped_limit,
                "recent_limit": max(1, min(recent_limit, 100)),
            },
            "summary": remote_action_summary_payload(actions),
            "queue_metrics": remote_action_queue_metrics(actions),
            "customer_summaries": build_grouped_summary("customer"),
            "location_summaries": build_grouped_summary("location"),
            "license_summaries": build_grouped_summary("license"),
            "device_summaries": build_grouped_summary("device"),
            "top_problem_scopes": remote_action_problem_scope_payload([
                *build_grouped_summary("location"),
                *build_grouped_summary("license"),
                *build_grouped_summary("device"),
            ]),
            "recent_items": recent_items,
        }

    @router.get("/api/remote-actions/review-queue")
    async def get_remote_action_review_queue(
        request_state: str = None,
        approval_state: str = None,
        outcome_code: str = None,
        action_type: str = None,
        customer_id: str = None,
        location_id: str = None,
        license_id: str = None,
        device_id: str = None,
        include_expired: bool = True,
        offset: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "staff")
        capped_limit = max(1, min(limit, 250))
        actions = await _query_scoped_remote_actions(
            db,
            user,
            customer_id=customer_id,
            location_id=location_id,
            license_id=license_id,
            device_id=device_id,
            request_state=request_state,
            approval_state=approval_state,
            outcome_code=outcome_code,
            action_type=action_type,
            include_expired=include_expired,
            offset=max(0, offset),
            limit=capped_limit,
        )
        devices_by_id, locations_by_id, customers_by_id, licenses_by_id = await _load_remote_action_scope_maps(db, actions)
        items = []
        for action in actions:
            payload = serialize_action(action)
            device = devices_by_id.get(action.device_id)
            location = locations_by_id.get(device.location_id) if device is not None else None
            customer = customers_by_id.get(location.customer_id) if location is not None else None
            license_row = licenses_by_id.get(device.license_id) if device is not None else None
            payload["scope"] = remote_action_scope_snapshot(payload, device=device, location=location, customer=customer, license_row=license_row)
            items.append(finalize_remote_action(payload, user))

        return {
            "filters": {
                "request_state": request_state,
                "approval_state": approval_state,
                "outcome_code": outcome_code,
                "action_type": action_type,
                "customer_id": customer_id,
                "location_id": location_id,
                "license_id": license_id,
                "device_id": device_id,
                "include_expired": include_expired,
            },
            "window": {
                "offset": max(0, offset),
                "limit": capped_limit,
                "returned": len(items),
                "has_more": len(items) == capped_limit,
            },
            "summary": remote_action_summary_payload(actions),
            "queue_metrics": remote_action_queue_metrics(actions),
            "items": items,
        }

    @router.get("/api/remote-actions/{device_id}")
    async def list_device_actions(
        device_id: str,
        status: str = None,
        limit: int = 20,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "staff")
        await get_device_with_scope_check(device_id, user, db)
        stmt = select(RemoteAction).where(RemoteAction.device_id == device_id)
        if status:
            stmt = stmt.where(RemoteAction.status == status)
        stmt = stmt.order_by(RemoteAction.issued_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return [finalize_remote_action(serialize_action(a), user) for a in result.scalars().all()]

    @router.get("/api/remote-actions/{device_id}/summary")
    async def get_device_action_summary(
        device_id: str,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "staff")
        await get_device_with_scope_check(device_id, user, db)
        stmt = select(RemoteAction).where(RemoteAction.device_id == device_id).order_by(RemoteAction.issued_at.desc()).limit(limit)
        result = await db.execute(stmt)
        actions = result.scalars().all()
        return remote_action_summary_payload(actions)

    @router.get("/api/remote-actions/{device_id}/history")
    async def get_device_action_history(
        device_id: str,
        limit: int = 50,
        db: AsyncSession = Depends(get_db),
        user: AuthUser = Depends(get_current_user),
    ):
        require_min_role(user, "staff")
        await get_device_with_scope_check(device_id, user, db)
        stmt = select(RemoteAction).where(RemoteAction.device_id == device_id).order_by(RemoteAction.issued_at.desc()).limit(limit)
        result = await db.execute(stmt)
        actions = result.scalars().all()
        return {
            "summary": remote_action_summary_payload(actions),
            "items": [finalize_remote_action(serialize_action(a), user) for a in actions],
        }

    return router
