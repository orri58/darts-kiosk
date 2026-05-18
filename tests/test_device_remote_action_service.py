import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from central_server.services.device_remote_actions import (
    ack_device_remote_action,
    get_pending_device_remote_actions,
)


NOW = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)


def make_action(action_id: str, *, action_type='force_sync', status='pending', approval_state='not_required', issued_at=None):
    return SimpleNamespace(
        id=action_id,
        device_id='dev-1',
        action_type=action_type,
        status=status,
        approval_state=approval_state,
        request_state='queued',
        outcome_code=None,
        outcome_detail=None,
        issued_at=issued_at or NOW,
        delivered_at=None,
        acked_at=None,
        finalized_at=None,
        finalized_by=None,
        result_message='',
    )


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


class FakeDB:
    def __init__(self, *, actions=None):
        self.actions = list(actions or [])
        self.commits = 0

    async def execute(self, _stmt):
        return _ExecuteResult(self.actions)

    async def get(self, _model, action_id):
        for action in self.actions:
            if action.id == action_id:
                return action
        return None

    async def commit(self):
        self.commits += 1


def _serialize_action(action):
    return {
        'id': action.id,
        'status': action.status,
        'request_state': action.request_state,
        'outcome_code': action.outcome_code,
        'outcome_detail': action.outcome_detail,
        'finalized_by': action.finalized_by,
    }


def _lifecycle_details(action, **kwargs):
    return {'action_id': action.id, **kwargs}


async def _log_audit(_db, event, **kwargs):
    _log_audit.calls.append((event, kwargs))


_log_audit.calls = []


def test_get_pending_device_remote_actions_applies_review_policy_ttl_and_delivery_states():
    review_pending = make_action('ra-review', approval_state='pending')
    blocked = make_action('ra-blocked', action_type='lock_board')
    expired = make_action('ra-expired', issued_at=NOW - timedelta(hours=2))
    deliverable = make_action('ra-deliver')
    db = FakeDB(actions=[review_pending, blocked, expired, deliverable])
    device = SimpleNamespace(id='dev-1', license_id='lic-1')
    _log_audit.calls = []

    payload = asyncio.run(get_pending_device_remote_actions(
        'dev-1',
        device=device,
        db=db,
        utcnow=lambda: NOW,
        serialize_action=_serialize_action,
        log_audit=_log_audit,
        remote_action_lifecycle_details=_lifecycle_details,
    ))

    assert payload == [{
        'id': 'ra-deliver',
        'status': 'pending',
        'request_state': 'delivered',
        'outcome_code': 'delivered',
        'outcome_detail': 'ready_for_device_execution',
        'finalized_by': None,
    }]
    assert blocked.status == 'expired'
    assert blocked.outcome_code == 'blocked'
    assert blocked.finalized_by == 'central_policy'
    assert expired.status == 'expired'
    assert expired.outcome_code == 'expired'
    assert expired.finalized_by == 'central_ttl'
    assert review_pending.request_state == 'queued'
    assert deliverable.request_state == 'delivered'
    assert db.commits == 2
    assert [event for event, _ in _log_audit.calls] == [
        'remote_action_auto_finalized',
        'remote_action_auto_finalized',
    ]


def test_ack_device_remote_action_finalizes_success_and_persists_audit():
    action = make_action('ra-ok')
    db = FakeDB(actions=[action])
    device = SimpleNamespace(id='dev-1', license_id='lic-1')
    _log_audit.calls = []

    payload = asyncio.run(ack_device_remote_action(
        'dev-1',
        device=device,
        action_id='ra-ok',
        success=False,
        message='execution failed',
        db=db,
        utcnow=lambda: NOW,
        log_audit=_log_audit,
        remote_action_lifecycle_details=_lifecycle_details,
    ))

    assert payload == {'ok': True}
    assert action.status == 'failed'
    assert action.request_state == 'finalized'
    assert action.outcome_code == 'failed'
    assert action.outcome_detail == 'device_reported_failure'
    assert action.finalized_by == 'device'
    assert action.result_message == 'execution failed'
    assert db.commits == 2
    assert [event for event, _ in _log_audit.calls] == ['remote_action_finalized']
