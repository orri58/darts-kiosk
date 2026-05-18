from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.models import CentralDevice


def extract_device_api_key(headers, *, query_params=None) -> tuple[str, str]:
    """Extract a device API key from preferred transports.

    Returns (api_key, source) where source is one of:
    - x-license-key
    - authorization
    - query
    """
    api_key = (headers.get("X-License-Key") or "").strip()
    if api_key:
        return api_key, "x-license-key"

    auth_header = (headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:].strip()
        if bearer:
            return bearer, "authorization"

    if query_params is not None:
        query_key = (query_params.get("key") or "").strip()
        if query_key:
            return query_key, "query"

    return "", "missing"


async def authenticate_device(request: Request, db: AsyncSession) -> CentralDevice:
    """Authenticate a device via shared API-key extraction.
    Also rejects blocked/inactive devices."""
    api_key, _source = extract_device_api_key(request.headers)
    if not api_key:
        raise HTTPException(401, "Missing device authentication")
    result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(403, "Invalid API key")
    if device.status == "blocked":
        raise HTTPException(403, "Device is blocked")
    if device.status == "inactive":
        raise HTTPException(403, "Device is deactivated — contact your administrator")
    return device
