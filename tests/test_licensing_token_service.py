import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from central_server.services.licensing_tokens import (
    get_or_create_license_token_payload,
    revoke_registration_token_payload,
)


NOW = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _ExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class FakeDB:
    def __init__(self, *, license_row=None, tokens=None):
        self.license_row = license_row
        self.tokens = list(tokens or [])
        self.added = []
        self.flushes = 0
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        if self.calls == 1:
            return _ExecuteResult([self.license_row] if self.license_row else [])
        return _ExecuteResult(self.tokens)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1


def _serialize_reg_token(token):
    return {
        'id': getattr(token, 'id', 'tok-new'),
        'token_preview': token.token_preview,
        'status': 'active',
    }


def _generate_reg_token():
    return ('raw-token', 'hashed-token', 'drt_abcd...wxyz')


async def _log_audit(_db, event, **kwargs):
    _log_audit.calls.append((event, kwargs))


_log_audit.calls = []


def test_get_or_create_license_token_reuses_existing_active_token():
    lic = SimpleNamespace(id='lic-1', customer_id='cust-1', location_id='loc-1', plan_type='standard')
    existing = SimpleNamespace(
        id='tok-1',
        token_preview='drt_old...0001',
        expires_at=NOW + timedelta(hours=1),
        used_at=None,
        is_revoked=False,
        created_at=NOW,
    )
    db = FakeDB(license_row=lic, tokens=[existing])

    payload = asyncio.run(get_or_create_license_token_payload(
        db=db,
        user=SimpleNamespace(username='installer'),
        license_id='lic-1',
        utcnow=lambda: NOW,
        aware=lambda value: value,
        require_installer_or_above=lambda user: user,
        can_access_customer=lambda user, customer_id: True,
        generate_reg_token=_generate_reg_token,
        serialize_reg_token=_serialize_reg_token,
        log_audit=_log_audit,
        token_ttl=timedelta(hours=72),
    ))

    assert payload == {
        'exists': True,
        'token': {'id': 'tok-1', 'token_preview': 'drt_old...0001', 'status': 'active'},
        'message': 'Aktiver Token vorhanden',
    }
    assert db.added == []
    assert db.flushes == 0


def test_revoke_registration_token_rejects_used_tokens():
    token = SimpleNamespace(
        id='tok-used',
        customer_id='cust-1',
        token_preview='drt_used...0001',
        is_revoked=False,
        used_at=NOW,
    )

    class RevokeDB:
        async def execute(self, _stmt):
            return _ExecuteResult([token])

        async def flush(self):
            raise AssertionError('flush should not be called for used token')

    db = RevokeDB()

    try:
        asyncio.run(revoke_registration_token_payload(
            db=db,
            user=SimpleNamespace(username='installer'),
            token_id='tok-used',
            utcnow=lambda: NOW,
            require_installer_or_above=lambda user: user,
            can_access_customer=lambda user, customer_id: True,
            serialize_reg_token=_serialize_reg_token,
            log_audit=_log_audit,
        ))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == 'Token already used'
    else:
        raise AssertionError('expected HTTPException for used token')
