from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from central_server.models import CentralDevice


def build_device_ws_router(
    *,
    async_session_local,
    extract_device_api_key,
    device_ws_hub,
    logger,
    ws_query_auth_mode: str,
) -> APIRouter:
    router = APIRouter(tags=["ws-devices"])

    @router.websocket("/ws/devices")
    async def ws_device_endpoint(ws: WebSocket):
        """WebSocket endpoint for device push connections.

        Preferred auth transports:
        - X-License-Key header
        - Authorization: Bearer <device_api_key>

        Compatibility fallback:
        - ?key=<device_api_key> query param
        """
        api_key, api_key_source = extract_device_api_key(ws.headers, query_params=ws.query_params)
        if not api_key:
            await ws.close(code=4001, reason="Missing device authentication")
            return

        try:
            async with async_session_local() as db:
                result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
                device = result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"[WS] Auth DB error: {e}")
            await ws.close(code=4003, reason="Server error")
            return

        if not device:
            await ws.close(code=4002, reason="Invalid API key")
            return
        if device.status == "blocked":
            await ws.close(code=4003, reason="Device is blocked")
            return
        if device.status == "inactive":
            await ws.close(code=4003, reason="Device is deactivated")
            return

        if api_key_source == "query":
            if ws_query_auth_mode == "deny":
                logger.warning("[WS] Rejected deprecated query-parameter auth for device %s", device.id)
                await ws.close(code=4001, reason="Query-parameter auth disabled; use X-License-Key or Authorization header")
                return
            logger.warning("[WS] Device %s authenticated via query parameter; prefer X-License-Key or Authorization header", device.id)

        device_id = device.id
        await ws.accept()
        await device_ws_hub.register(device_id, ws)

        try:
            await ws.send_json({"event": "connected", "device_id": device_id})
            while True:
                try:
                    msg = await ws.receive_json()
                except Exception:
                    break
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    try:
                        await ws.send_json({"event": "pong"})
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"[WS] Device {device_id} connection error: {e}")
        finally:
            await device_ws_hub.unregister(device_id)

    return router
