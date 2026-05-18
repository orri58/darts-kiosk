from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.auth import AuthUser, get_current_user
from central_server.database import AsyncSessionLocal, get_db
from central_server.services.admin_crud import (
    create_customer_payload,
    create_device_payload,
    create_license_payload,
    create_location_payload,
    get_license_detail_payload,
    license_portfolio_summary_payload,
    list_customers_payload,
    list_devices_payload,
    list_licenses_payload,
    list_locations_payload,
    update_customer_payload,
    update_device_payload,
    update_license_payload,
    update_location_payload,
)


def build_admin_crud_router(
    *,
    logger,
    utcnow,
    aware,
    log_audit,
    require_installer_or_above,
    can_access_customer,
    can_access_location,
    apply_customer_scope,
    serialize_customer,
    serialize_location,
    serialize_device,
    serialize_license,
    build_device_advisory_posture_map,
    compact_advisory_posture,
    can_view_internal_device_detail,
    finalize_device_summary,
    summarize_posture_collection,
    summarize_license_token_state,
    compute_status,
    build_license_commercial_readiness,
    build_license_portfolio_summary,
    refine_license_detail_suggested_actions,
    serialize_reg_token_summary,
    finalize_reg_token_summary,
) -> APIRouter:
    router = APIRouter(tags=["admin-crud"])

    @router.get("/api/licensing/customers")
    async def list_customers(
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await list_customers_payload(
            db=db,
            user=user,
            apply_customer_scope=apply_customer_scope,
            serialize_customer=serialize_customer,
        )

    @router.post("/api/licensing/customers")
    async def create_customer(
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await create_customer_payload(
            db=db,
            user=user,
            data=data,
            log_audit=log_audit,
            serialize_customer=serialize_customer,
        )

    @router.put("/api/licensing/customers/{customer_id}")
    async def update_customer(
        customer_id: str,
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await update_customer_payload(
            db=db,
            user=user,
            customer_id=customer_id,
            data=data,
            can_access_customer=can_access_customer,
            log_audit=log_audit,
            serialize_customer=serialize_customer,
        )

    @router.get("/api/licensing/locations")
    async def list_locations(
        customer_id: str = None,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await list_locations_payload(
            db=db,
            user=user,
            customer_id=customer_id,
            can_access_customer=can_access_customer,
            apply_customer_scope=apply_customer_scope,
            serialize_location=serialize_location,
        )

    @router.post("/api/licensing/locations")
    async def create_location(
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await create_location_payload(
            db=db,
            user=user,
            data=data,
            can_access_customer=can_access_customer,
            log_audit=log_audit,
            serialize_location=serialize_location,
        )

    @router.put("/api/licensing/locations/{location_id}")
    async def update_location(
        location_id: str,
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await update_location_payload(
            db=db,
            user=user,
            location_id=location_id,
            data=data,
            can_access_location=can_access_location,
            log_audit=log_audit,
            serialize_location=serialize_location,
        )

    @router.get("/api/licensing/devices")
    async def list_devices(
        location_id: str = None,
        customer_id: str = None,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await list_devices_payload(
            db=db,
            user=user,
            location_id=location_id,
            customer_id=customer_id,
            async_session_local=AsyncSessionLocal,
            can_access_location=can_access_location,
            can_access_customer=can_access_customer,
            apply_customer_scope=apply_customer_scope,
            build_device_advisory_posture_map=build_device_advisory_posture_map,
            compact_advisory_posture=compact_advisory_posture,
            can_view_internal_device_detail=can_view_internal_device_detail,
            finalize_device_summary=finalize_device_summary,
            serialize_device=serialize_device,
            logger=logger,
        )

    @router.post("/api/licensing/devices")
    async def create_device(
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await create_device_payload(
            db=db,
            user=user,
            data=data,
            can_access_location=can_access_location,
            log_audit=log_audit,
            serialize_device=serialize_device,
            secrets_module=secrets,
        )

    @router.put("/api/licensing/devices/{device_id}")
    async def update_device(
        device_id: str,
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await update_device_payload(
            db=db,
            user=user,
            device_id=device_id,
            data=data,
            can_access_location=can_access_location,
            log_audit=log_audit,
            serialize_device=serialize_device,
        )

    @router.get("/api/licensing/licenses")
    async def list_licenses(
        customer_id: str = None,
        status: str = None,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await list_licenses_payload(
            db=db,
            user=user,
            customer_id=customer_id,
            status=status,
            can_access_customer=can_access_customer,
            apply_customer_scope=apply_customer_scope,
            utcnow=utcnow,
            summarize_license_token_state=summarize_license_token_state,
            compute_status=compute_status,
            build_device_advisory_posture_map=build_device_advisory_posture_map,
            summarize_posture_collection=summarize_posture_collection,
            build_license_commercial_readiness=build_license_commercial_readiness,
            serialize_license=serialize_license,
        )

    @router.get("/api/licensing/licenses/portfolio-summary")
    async def license_portfolio_summary(
        customer_id: str = None,
        status: str = None,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await license_portfolio_summary_payload(
            db=db,
            user=user,
            customer_id=customer_id,
            status=status,
            can_access_customer=can_access_customer,
            apply_customer_scope=apply_customer_scope,
            utcnow=utcnow,
            build_device_advisory_posture_map=build_device_advisory_posture_map,
            summarize_posture_collection=summarize_posture_collection,
            summarize_license_token_state=summarize_license_token_state,
            build_license_portfolio_summary=build_license_portfolio_summary,
        )

    @router.post("/api/licensing/licenses")
    async def create_license(
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await create_license_payload(
            db=db,
            user=user,
            data=data,
            can_access_customer=can_access_customer,
            utcnow=utcnow,
            log_audit=log_audit,
            serialize_license=serialize_license,
        )

    @router.put("/api/licensing/licenses/{license_id}")
    async def update_license(
        license_id: str,
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        require_installer_or_above(user)
        return await update_license_payload(
            db=db,
            user=user,
            license_id=license_id,
            data=data,
            can_access_customer=can_access_customer,
            log_audit=log_audit,
            serialize_license=serialize_license,
        )

    @router.get("/api/licensing/licenses/{license_id}")
    async def get_license_detail(
        license_id: str,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_license_detail_payload(
            db=db,
            user=user,
            license_id=license_id,
            can_access_customer=can_access_customer,
            utcnow=utcnow,
            aware=aware,
            compute_status=compute_status,
            build_license_commercial_readiness=build_license_commercial_readiness,
            refine_license_detail_suggested_actions=refine_license_detail_suggested_actions,
            summarize_license_token_state=summarize_license_token_state,
            summarize_posture_collection=summarize_posture_collection,
            finalize_device_summary=finalize_device_summary,
            serialize_device=serialize_device,
            serialize_license=serialize_license,
            serialize_reg_token_summary=serialize_reg_token_summary,
            finalize_reg_token_summary=finalize_reg_token_summary,
        )

    return router
