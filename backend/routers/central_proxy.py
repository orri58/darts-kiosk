"""
Layer A: Central Server API Proxy (Read-Only)

Proxies portal requests from the frontend to the central server (port 8002).
Layer A restriction: only read-only endpoints and login are allowed.
No write operations, no control actions, no config changes.
"""
import logging
import os

import httpx
from fastapi import APIRouter, Request, Response, HTTPException

logger = logging.getLogger("central_proxy")

CENTRAL_INTERNAL_URL = os.environ.get(
    "CENTRAL_SERVER_INTERNAL_URL", "http://localhost:8002"
)

router = APIRouter(prefix="/central", tags=["Central Portal Proxy"])


def _is_allowed_layer_a(method: str, path: str) -> bool:
    """Layer A whitelist: only GET requests + POST /api/auth/login."""
    if method == "GET":
        return True
    if method == "POST" and path.rstrip("/") == "/api/auth/login":
        return True
    return False


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_to_central(path: str, request: Request):
    method = request.method
    target_path = f"/api/{path}"

    if not _is_allowed_layer_a(method, target_path):
        raise HTTPException(
            403, f"Layer A: {method} {target_path} not permitted (read-only mode)"
        )

    url = f"{CENTRAL_INTERNAL_URL}{target_path}"
    if request.url.query:
        url += f"?{request.url.query}"

    fwd_headers = {}
    for key in ("authorization", "x-license-key", "content-type", "accept"):
        val = request.headers.get(key)
        if val:
            fwd_headers[key] = val

    body = await request.body() if method == "POST" else None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=fwd_headers,
                content=body,
            )

        resp_headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower() not in ("transfer-encoding", "content-encoding", "connection")
        }

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(502, "Central server not reachable")
    except httpx.TimeoutException:
        raise HTTPException(504, "Central server timeout")
    except Exception as e:
        logger.error(f"[PROXY] {method} {target_path} -> {type(e).__name__}: {e}")
        raise HTTPException(500, "Proxy error")
