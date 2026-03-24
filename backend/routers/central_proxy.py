"""
Central Server Proxy — v3.5.4

Unified proxy for all central server communication.
- Admin Panel: Sends local kiosk JWT → proxy auto-authenticates with central server
- Operator Portal: Sends central JWT → proxy forwards as-is
- No separate login needed in the admin UI
- Timeout: 5s, clean error handling, structured JSON responses
"""
import logging
import os
import time

import httpx
from jose import jwt, JWTError
from fastapi import APIRouter, Request, Response

logger = logging.getLogger("central_proxy")

router = APIRouter(prefix="/central", tags=["central-proxy"])

CENTRAL_SERVER_URL = os.environ.get("CENTRAL_SERVER_URL", "http://127.0.0.1:8002")
PROXY_TIMEOUT = 12.0

# Local kiosk JWT secret — used to detect admin panel requests
_LOCAL_JWT_SECRET = os.environ.get("JWT_SECRET", "darts-kiosk-secret-key-change-in-production")

# Cached central admin token
_cached_token: str | None = None
_token_expires_at: float = 0


async def _get_central_admin_token() -> str | None:
    """Get a cached central server admin token, refreshing if expired."""
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at:
        return _cached_token

    username = os.environ.get("CENTRAL_ADMIN_USERNAME", "superadmin")
    password = os.environ.get("CENTRAL_ADMIN_PASSWORD", "admin")

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            resp = await client.post(
                f"{CENTRAL_SERVER_URL}/api/auth/login",
                json={"username": username, "password": password},
            )
        if resp.status_code == 200:
            data = resp.json()
            _cached_token = data.get("access_token")
            _token_expires_at = time.time() + 23 * 3600  # refresh ~1h before 24h expiry
            logger.info("[PROXY] Central admin token acquired/refreshed")
            return _cached_token
        else:
            logger.error(f"[PROXY] Central admin login failed: HTTP {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"[PROXY] Central admin login error: {e}")
        return None


def _is_local_kiosk_jwt(token_str: str) -> bool:
    """Check if a Bearer token is a local kiosk JWT (not a central server JWT)."""
    try:
        jwt.decode(token_str, _LOCAL_JWT_SECRET, algorithms=["HS256"])
        return True
    except JWTError:
        return False


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_central(path: str, request: Request):
    """Forward requests to the central license server.

    Auth behavior:
    - Request with local kiosk JWT → replace with cached central admin token (admin panel flow)
    - Request with central JWT → forward as-is (operator portal flow)
    - Request without auth → inject cached central admin token (fallback)
    """
    target_url = f"{CENTRAL_SERVER_URL}/api/{path}"

    if request.url.query:
        target_url += f"?{request.url.query}"

    # Determine auth header to forward
    forward_headers = {}
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        bearer_token = auth_header.split(" ", 1)[1]
        if _is_local_kiosk_jwt(bearer_token):
            # Local kiosk admin token → replace with central admin token
            central_token = await _get_central_admin_token()
            if central_token:
                forward_headers["Authorization"] = f"Bearer {central_token}"
            # else: forward without auth, central server will reject
        else:
            # Not a local token → assume central JWT, forward as-is
            forward_headers["Authorization"] = auth_header
    else:
        # No auth → use cached central admin token
        central_token = await _get_central_admin_token()
        if central_token:
            forward_headers["Authorization"] = f"Bearer {central_token}"

    if ct := request.headers.get("Content-Type"):
        forward_headers["Content-Type"] = ct

    body = None
    if request.method != "GET":
        body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
            )

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={"Content-Type": resp.headers.get("Content-Type", "application/json")},
        )

    except httpx.ConnectError:
        logger.warning(f"[PROXY] Central server unreachable: {target_url}")
        return Response(
            content='{"error":"central_server_unreachable","message":"Zentraler Server nicht erreichbar"}',
            status_code=502,
            headers={"Content-Type": "application/json"},
        )
    except httpx.TimeoutException:
        logger.warning(f"[PROXY] Central server timeout: {target_url}")
        return Response(
            content='{"error":"central_server_timeout","message":"Zentraler Server Timeout"}',
            status_code=504,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.error(f"[PROXY] Unexpected error: {e}")
        return Response(
            content='{"error":"proxy_error","message":"Interner Proxy-Fehler"}',
            status_code=500,
            headers={"Content-Type": "application/json"},
        )
