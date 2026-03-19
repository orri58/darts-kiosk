"""
Central Server Proxy — v3.5.3

Controlled forwarding of requests from the frontend to the central license server.
- Timeout: 5s
- Only forwards to localhost:8002 (never exposes the address)
- Clean error handling with structured JSON responses
"""
import logging
import os

import httpx
from fastapi import APIRouter, Request, Response

logger = logging.getLogger("central_proxy")

router = APIRouter(prefix="/central", tags=["central-proxy"])

CENTRAL_SERVER_URL = os.environ.get("CENTRAL_SERVER_URL", "http://127.0.0.1:8002")
PROXY_TIMEOUT = 5.0


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_central(path: str, request: Request):
    """Forward requests to the central license server."""
    target_url = f"{CENTRAL_SERVER_URL}/api/{path}"

    # Forward query params
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Forward relevant headers (auth, content-type)
    forward_headers = {}
    if auth := request.headers.get("Authorization"):
        forward_headers["Authorization"] = auth
    if ct := request.headers.get("Content-Type"):
        forward_headers["Content-Type"] = ct

    # Read body for non-GET requests
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
