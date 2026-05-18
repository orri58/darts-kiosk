import asyncio
from types import SimpleNamespace

from fastapi import HTTPException

from central_server.services.device_trust_enrollment import enroll_device_trust_payload


class DummyDB:
    async def execute(self, _stmt):
        raise AssertionError('db.execute should not be reached for early validation failures')

    async def flush(self):
        raise AssertionError('db.flush should not be reached for early validation failures')

    def add(self, _item):
        raise AssertionError('db.add should not be reached for early validation failures')


async def _log_audit(_db, _event, **_kwargs):
    raise AssertionError('log_audit should not be reached for early validation failures')


async def _register_device(_body, _request, _db):
    raise AssertionError('register_device should not be reached for early validation failures')


def test_enroll_requires_token_before_db_work():
    request = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))

    try:
        asyncio.run(enroll_device_trust_payload(
            body={'install_id': 'inst-1', 'csr_pem': 'csr'},
            request=request,
            db=DummyDB(),
            utcnow=lambda: None,
            hash_token=lambda raw: raw,
            aware=lambda value: value,
            normalize_enrollment_material=lambda **kwargs: kwargs,
            log_audit=_log_audit,
            register_device=_register_device,
            serialize_device=lambda device: device,
            serialize_device_credential=lambda credential, device=None: credential,
        ))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == 'Enrollment token fehlt'
    else:
        raise AssertionError('expected HTTPException for missing enrollment token')
