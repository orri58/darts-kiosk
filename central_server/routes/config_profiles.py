from __future__ import annotations

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db
from central_server.services.config_profiles import (
    apply_config_import_payload,
    ensure_config_scope_access,
    ensure_config_scope_read_access,
    ensure_valid_scope_type,
    export_config_payload,
    get_config_diff_payload,
    get_config_history_payload,
    get_config_profile_payload,
    get_global_config_payload,
    list_config_profiles_payload,
    rollback_config_payload,
    upsert_config_profile_payload,
    validate_config_import_payload,
)


def build_config_profiles_router(
    *,
    get_current_user,
    require_min_role,
    can_access_customer,
    utcnow,
    log_audit,
    resolve_affected_devices,
    device_ws_hub,
) -> APIRouter:
    router = APIRouter(tags=["config-profiles"])

    @router.get("/api/config/profiles")
    async def list_config_profiles(
        scope_type: str = None,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        return await list_config_profiles_payload(db=db, scope_type=scope_type)

    @router.get("/api/config/profile/{scope_type}/{scope_id}")
    async def get_config_profile(
        scope_type: str,
        scope_id: str,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        return await get_config_profile_payload(db=db, scope_type=scope_type, scope_id=scope_id)

    @router.get("/api/config/profile/global")
    async def get_global_config(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        return await get_global_config_payload(db=db)

    @router.put("/api/config/profile/{scope_type}/{scope_id}")
    async def upsert_config_profile(
        scope_type: str,
        scope_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        ensure_valid_scope_type(scope_type)

        body = await request.json()
        config_data = body.get("config_data", {})
        if not isinstance(config_data, dict):
            raise HTTPException(400, "config_data must be a JSON object")

        from central_server.config_schema import validate_config
        validation_errors = validate_config(config_data)
        if validation_errors:
            raise HTTPException(422, detail={"validation_errors": validation_errors})

        await ensure_config_scope_access(
            db=db,
            user=user,
            scope_type=scope_type,
            scope_id=scope_id,
            can_access_customer=can_access_customer,
        )
        return await upsert_config_profile_payload(
            db=db,
            user=user,
            scope_type=scope_type,
            scope_id=scope_id,
            config_data=config_data,
            utcnow=utcnow,
            log_audit=log_audit,
            resolve_affected_devices=resolve_affected_devices,
            device_ws_hub=device_ws_hub,
        )

    @router.get("/api/config/history/{scope_type}/{scope_id}")
    async def get_config_history(
        scope_type: str,
        scope_id: str,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        return await get_config_history_payload(db=db, scope_type=scope_type, scope_id=scope_id)

    @router.post("/api/config/rollback/{scope_type}/{scope_id}/{version}")
    async def rollback_config(
        scope_type: str,
        scope_id: str,
        version: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        return await rollback_config_payload(
            db=db,
            user=user,
            scope_type=scope_type,
            scope_id=scope_id,
            version=version,
            utcnow=utcnow,
            log_audit=log_audit,
            resolve_affected_devices=resolve_affected_devices,
            device_ws_hub=device_ws_hub,
        )

    @router.get("/api/config/diff/{scope_type}/{scope_id}")
    async def get_config_diff(
        scope_type: str,
        scope_id: str,
        version: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        return await get_config_diff_payload(db=db, scope_type=scope_type, scope_id=scope_id, version=version)

    @router.get("/api/config/export/{scope_type}/{scope_id}")
    async def export_config(
        scope_type: str,
        scope_id: str,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        ensure_valid_scope_type(scope_type)
        await ensure_config_scope_read_access(
            db=db,
            user=user,
            scope_type=scope_type,
            scope_id=scope_id,
            can_access_customer=can_access_customer,
        )
        export_data = await export_config_payload(
            db=db,
            user=user,
            scope_type=scope_type,
            scope_id=scope_id,
            utcnow=utcnow,
        )
        try:
            sid = None if scope_type == "global" else scope_id
            await log_audit(db, "config_export", actor=user.username, message=f"Config exported: {scope_type}/{sid} v{export_data['meta']['version']}")
            await db.commit()
        except Exception:
            pass
        return export_data

    @router.post("/api/config/import/validate")
    async def validate_import(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        body = await request.json()
        return await validate_config_import_payload(
            db=db,
            user=user,
            import_data=body.get("import_data", {}),
            target_scope_type=body.get("target_scope_type"),
            target_scope_id=body.get("target_scope_id"),
            mode=body.get("mode", "merge"),
            can_access_customer=can_access_customer,
        )

    @router.post("/api/config/import/apply")
    async def apply_import(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ):
        require_min_role(user, "owner")
        body = await request.json()
        target_scope_type = body.get("target_scope_type", "global")
        target_scope_id = body.get("target_scope_id")

        await ensure_config_scope_access(
            db=db,
            user=user,
            scope_type=target_scope_type,
            scope_id=target_scope_id,
            can_access_customer=can_access_customer,
        )
        return await apply_config_import_payload(
            db=db,
            user=user,
            import_data=body.get("import_data", {}),
            target_scope_type=target_scope_type,
            target_scope_id=target_scope_id,
            mode=body.get("mode", "merge"),
            utcnow=utcnow,
            log_audit=log_audit,
            resolve_affected_devices=resolve_affected_devices,
            device_ws_hub=device_ws_hub,
        )

    return router
