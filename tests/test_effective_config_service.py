import asyncio
from types import SimpleNamespace

from fastapi import HTTPException

from central_server.services.effective_config import (
    build_effective_config_payload,
    resolve_effective_config_access,
)


class _ScalarOneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class SequencedDB:
    def __init__(self, values):
        self._values = list(values)

    async def execute(self, _stmt):
        return _ScalarOneResult(self._values.pop(0))


class AccessDB:
    def __init__(self, *, devices=None, locations=None):
        self.devices = devices or {}
        self.locations = locations or {}

    async def get(self, model, obj_id):
        name = getattr(model, "__name__", "")
        if name == "CentralDevice":
            return self.devices.get(obj_id)
        if name == "CentralLocation":
            return self.locations.get(obj_id)
        return None


class FakeRequest:
    def __init__(self, headers):
        self.headers = headers


async def _get_current_user(_request, _db):
    return SimpleNamespace(role="owner", username="owner")


def _require_min_role(_user, _role):
    return None


async def _authenticate_device(_request, _db):
    return SimpleNamespace(id="dev-1", location_id="loc-1")


async def _can_access_location(_user, _location_id, _db):
    return True


def _can_access_customer(_user, _customer_id):
    return True


def test_build_effective_config_payload_merges_layers_and_uses_loaded_versions():
    db = SequencedDB([
        SimpleNamespace(config_data={"theme": {"mode": "dark"}, "global": True}, version=2),
        SimpleNamespace(config_data={"theme": {"accent": "blue"}, "customer": True}, version=7),
        SimpleNamespace(config_data={"location": True}, version=3),
        SimpleNamespace(config_data={"device": True, "theme": {"mode": "light"}}, version=9),
    ])

    payload = asyncio.run(build_effective_config_payload(
        db=db,
        resolved_customer_id="cust-1",
        resolved_location_id="loc-1",
        resolved_device_id="dev-1",
        deep_merge=lambda base, override: {
            **base,
            **{
                key: (lambda bv, ov: {**bv, **ov} if isinstance(bv, dict) and isinstance(ov, dict) else ov)(base.get(key), value)
                for key, value in override.items()
            },
        },
    ))

    assert payload == {
        "config": {
            "theme": {"mode": "light", "accent": "blue"},
            "global": True,
            "customer": True,
            "location": True,
            "device": True,
        },
        "version": 9,
        "layers_applied": ["global", "customer", "location", "device"],
        "scope": {
            "customer_id": "cust-1",
            "location_id": "loc-1",
            "device_id": "dev-1",
        },
    }


def test_resolve_effective_config_access_for_device_auth_locks_scope_to_authenticated_device():
    db = AccessDB(locations={"loc-1": SimpleNamespace(customer_id="cust-1")})
    request = FakeRequest({"X-License-Key": "key-1"})

    access = asyncio.run(resolve_effective_config_access(
        request=request,
        db=db,
        device_id=None,
        location_id=None,
        customer_id=None,
        get_current_user=_get_current_user,
        require_min_role=_require_min_role,
        authenticate_device=_authenticate_device,
        can_access_location=_can_access_location,
        can_access_customer=_can_access_customer,
    ))

    assert access.resolved_device_id == "dev-1"
    assert access.resolved_location_id == "loc-1"
    assert access.resolved_customer_id == "cust-1"
    assert access.device.id == "dev-1"
    assert access.user is None


def test_resolve_effective_config_access_rejects_device_cross_scope_request():
    db = AccessDB(locations={"loc-1": SimpleNamespace(customer_id="cust-1")})
    request = FakeRequest({"X-License-Key": "key-1"})

    try:
        asyncio.run(resolve_effective_config_access(
            request=request,
            db=db,
            device_id="dev-2",
            location_id=None,
            customer_id=None,
            get_current_user=_get_current_user,
            require_min_role=_require_min_role,
            authenticate_device=_authenticate_device,
            can_access_location=_can_access_location,
            can_access_customer=_can_access_customer,
        ))
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "own effective config" in exc.detail
