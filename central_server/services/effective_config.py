from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.models import CentralDevice, CentralLocation, ConfigProfile


@dataclass(slots=True)
class EffectiveConfigAccess:
    user: object | None
    device: CentralDevice | None
    resolved_customer_id: str | None
    resolved_location_id: str | None
    resolved_device_id: str | None


async def resolve_effective_config_access(
    *,
    request: Request,
    db: AsyncSession,
    device_id: str | None,
    location_id: str | None,
    customer_id: str | None,
    get_current_user,
    require_min_role,
    authenticate_device,
    can_access_location,
    can_access_customer,
) -> EffectiveConfigAccess:
    auth_header = request.headers.get("Authorization", "")
    has_user_auth = auth_header.startswith("Bearer ")
    has_device_auth = bool(request.headers.get("X-License-Key"))

    authed_user = None
    authed_device = None

    if has_user_auth:
        authed_user = await get_current_user(request, db)
        require_min_role(authed_user, "owner")
    elif has_device_auth:
        authed_device = await authenticate_device(request, db)
    else:
        raise HTTPException(401, "Authentication required")

    resolved_customer_id = customer_id
    resolved_location_id = location_id
    resolved_device_id = device_id

    if authed_device:
        if device_id and device_id != authed_device.id:
            raise HTTPException(403, "Authenticated device may only access its own effective config")
        resolved_device_id = authed_device.id
        resolved_location_id = authed_device.location_id
        loc = await db.get(CentralLocation, authed_device.location_id) if authed_device.location_id else None
        resolved_customer_id = loc.customer_id if loc else None
        if location_id and resolved_location_id and location_id != resolved_location_id:
            raise HTTPException(403, "Authenticated device may only access its own location scope")
        if customer_id and resolved_customer_id and customer_id != resolved_customer_id:
            raise HTTPException(403, "Authenticated device may only access its own customer scope")
    else:
        if device_id:
            dev = await db.get(CentralDevice, device_id)
            if not dev:
                raise HTTPException(404, "Device not found")
            if not await can_access_location(authed_user, dev.location_id, db):
                raise HTTPException(403, "No access to this device")
            resolved_device_id = dev.id
            resolved_location_id = resolved_location_id or dev.location_id

        if resolved_location_id:
            if not await can_access_location(authed_user, resolved_location_id, db):
                raise HTTPException(403, "No access to this location")
            loc = await db.get(CentralLocation, resolved_location_id)
            if loc:
                resolved_customer_id = resolved_customer_id or loc.customer_id

        if resolved_customer_id and not can_access_customer(authed_user, resolved_customer_id):
            raise HTTPException(403, "No access to this customer")

    return EffectiveConfigAccess(
        user=authed_user,
        device=authed_device,
        resolved_customer_id=resolved_customer_id,
        resolved_location_id=resolved_location_id,
        resolved_device_id=resolved_device_id,
    )


async def build_effective_config_payload(
    *,
    db: AsyncSession,
    resolved_customer_id: str | None,
    resolved_location_id: str | None,
    resolved_device_id: str | None,
    deep_merge,
) -> dict:
    layers: dict[str, dict] = {}
    layer_versions: list[int] = []

    async def _load_layer(scope_type: str, scope_id: str | None = None):
        stmt = select(ConfigProfile).where(ConfigProfile.scope_type == scope_type)
        if scope_type != "global":
            stmt = stmt.where(ConfigProfile.scope_id == scope_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    scope_ids = {
        "customer": resolved_customer_id,
        "location": resolved_location_id,
        "device": resolved_device_id,
    }

    for scope in ("global", "customer", "location", "device"):
        scope_id = None if scope == "global" else scope_ids[scope]
        if scope != "global" and not scope_id:
            continue
        profile = await _load_layer(scope, scope_id)
        if not profile:
            continue
        layers[scope] = profile.config_data or {}
        if profile.version:
            layer_versions.append(profile.version)

    merged: dict = {}
    for scope in ("global", "customer", "location", "device"):
        if scope in layers:
            merged = deep_merge(merged, layers[scope])

    return {
        "config": merged,
        "version": max(layer_versions) if layer_versions else 0,
        "layers_applied": list(layers.keys()),
        "scope": {
            "customer_id": resolved_customer_id,
            "location_id": resolved_location_id,
            "device_id": resolved_device_id,
        },
    }
