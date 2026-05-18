from types import SimpleNamespace

from central_server.services.ws_status import (
    apply_operator_safe_ws_device_status,
    finalize_ws_device_status,
)


OWNER = SimpleNamespace(role="owner")
INSTALLER = SimpleNamespace(role="installer")


def test_apply_operator_safe_ws_device_status_redacts_internal_timing_fields():
    payload = apply_operator_safe_ws_device_status({
        "ws_connected": True,
        "connected_at": "2026-05-06T12:00:00+00:00",
        "last_event_at": "2026-05-06T12:01:00+00:00",
        "events_sent": 7,
    })

    assert payload == {
        "ws_connected": True,
        "detail_level": "operator_safe",
    }


def test_finalize_ws_device_status_preserves_internal_fields_for_installers():
    payload = finalize_ws_device_status({
        "ws_connected": True,
        "connected_at": "2026-05-06T12:00:00+00:00",
        "events_sent": 7,
    }, INSTALLER)

    assert payload["detail_level"] == "internal"
    assert payload["connected_at"] == "2026-05-06T12:00:00+00:00"
    assert payload["events_sent"] == 7


def test_finalize_ws_device_status_redacts_internal_fields_for_owners():
    payload = finalize_ws_device_status({
        "ws_connected": True,
        "connected_at": "2026-05-06T12:00:00+00:00",
        "events_sent": 7,
    }, OWNER)

    assert payload == {
        "ws_connected": True,
        "detail_level": "operator_safe",
    }
