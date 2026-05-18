from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db
from central_server.services.effective_config import (
    build_effective_config_payload,
    resolve_effective_config_access,
)


def build_effective_config_router(
    *,
    get_current_user,
    require_min_role,
    authenticate_device,
    can_access_location,
    can_access_customer,
    deep_merge,
) -> APIRouter:
    router = APIRouter(tags=["effective-config"])

    @router.get("/api/config/effective")
    async def get_effective_config(
        request: Request,
        device_id: str = None,
        location_id: str = None,
        customer_id: str = None,
        db: AsyncSession = Depends(get_db),
    ):
        access = await resolve_effective_config_access(
            request=request,
            db=db,
            device_id=device_id,
            location_id=location_id,
            customer_id=customer_id,
            get_current_user=get_current_user,
            require_min_role=require_min_role,
            authenticate_device=authenticate_device,
            can_access_location=can_access_location,
            can_access_customer=can_access_customer,
        )
        return await build_effective_config_payload(
            db=db,
            resolved_customer_id=access.resolved_customer_id,
            resolved_location_id=access.resolved_location_id,
            resolved_device_id=access.resolved_device_id,
            deep_merge=deep_merge,
        )

    return router
