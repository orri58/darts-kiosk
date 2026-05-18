from __future__ import annotations

from central_server.auth import AuthUser
from central_server.services.device_trust_details import can_view_internal_device_detail

_OPERATOR_SAFE_WS_DEVICE_STATUS_INTERNAL_KEYS = {
    "connected_at",
    "last_event_at",
    "events_sent",
}


def apply_operator_safe_ws_device_status(device_status: dict) -> dict:
    payload = dict(device_status)
    for key in _OPERATOR_SAFE_WS_DEVICE_STATUS_INTERNAL_KEYS:
        payload.pop(key, None)
    payload["detail_level"] = "operator_safe"
    return payload


def _to_operator_safe_warning(warning: dict) -> dict:
    payload = dict(warning)
    if payload.get("type") == "error":
        payload["message"] = payload.get("message") or "Verbindung meldet Fehler"
    return payload


def finalize_ws_device_status(device_status: dict, user: AuthUser) -> dict:
    payload = dict(device_status)
    payload.setdefault("detail_level", "internal" if can_view_internal_device_detail(user) else "operator_safe")
    if can_view_internal_device_detail(user):
        return payload
    return apply_operator_safe_ws_device_status(payload)
