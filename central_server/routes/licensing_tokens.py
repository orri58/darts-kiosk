from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.auth import AuthUser, get_current_user
from central_server.database import get_db
from central_server.services.licensing_tokens import (
    create_registration_token_payload,
    get_or_create_license_token_payload,
    list_registration_tokens_payload,
    register_device_with_token_payload,
    regenerate_license_token_payload,
    revoke_registration_token_payload,
)


def build_licensing_tokens_router(
    *,
    logger,
    utcnow,
    aware,
    log_audit,
    require_installer_or_above,
    can_access_customer,
    hash_token,
    generate_reg_token,
    serialize_reg_token,
    find_best_license,
    compute_status,
) -> APIRouter:
    router = APIRouter(tags=["licensing-tokens"])

    @router.get("/api/licensing/licenses/{license_id}/token")
    async def get_or_create_license_token(
        license_id: str,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_or_create_license_token_payload(
            db=db,
            user=user,
            license_id=license_id,
            utcnow=utcnow,
            aware=aware,
            require_installer_or_above=require_installer_or_above,
            can_access_customer=can_access_customer,
            generate_reg_token=generate_reg_token,
            serialize_reg_token=serialize_reg_token,
            log_audit=log_audit,
            token_ttl=timedelta(hours=72),
        )

    @router.post("/api/licensing/licenses/{license_id}/regenerate-token")
    async def regenerate_license_token(
        license_id: str,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await regenerate_license_token_payload(
            db=db,
            user=user,
            license_id=license_id,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            can_access_customer=can_access_customer,
            generate_reg_token=generate_reg_token,
            serialize_reg_token=serialize_reg_token,
            log_audit=log_audit,
            token_ttl=timedelta(hours=72),
        )

    @router.post("/api/registration-tokens")
    async def create_registration_token(
        data: dict,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await create_registration_token_payload(
            db=db,
            user=user,
            data=data,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            can_access_customer=can_access_customer,
            generate_reg_token=generate_reg_token,
            serialize_reg_token=serialize_reg_token,
            log_audit=log_audit,
        )

    @router.get("/api/registration-tokens")
    async def list_registration_tokens(
        status: str = None,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await list_registration_tokens_payload(
            db=db,
            user=user,
            status=status,
            serialize_reg_token=serialize_reg_token,
        )

    @router.post("/api/registration-tokens/{token_id}/revoke")
    async def revoke_registration_token(
        token_id: str,
        data: dict = None,
        user: AuthUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        _ = data
        return await revoke_registration_token_payload(
            db=db,
            user=user,
            token_id=token_id,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            can_access_customer=can_access_customer,
            serialize_reg_token=serialize_reg_token,
            log_audit=log_audit,
        )

    @router.post("/api/register-device")
    async def register_device(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
        return await register_device_with_token_payload(
            body=body,
            request=request,
            db=db,
            logger=logger,
            utcnow=utcnow,
            aware=aware,
            hash_token=hash_token,
            log_audit=log_audit,
            find_best_license=find_best_license,
            compute_status=compute_status,
        )

    return router
