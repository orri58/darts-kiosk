from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from central_server.server import (
    _derive_remote_action_outcome,
    _normalize_remote_action_request_state,
    _remote_action_queue_metrics,
    _remote_action_summary_payload,
)


NOW = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)


def make_action(action_id: str, *, status='pending', approval_state='not_required', request_state=None, outcome_code=None, result_message='', issued_offset_minutes=0):
    issued_at = NOW + timedelta(minutes=issued_offset_minutes)
    finalized_at = issued_at + timedelta(minutes=5) if status in {'acked', 'failed'} else None
    return SimpleNamespace(
        id=action_id,
        device_id='dev-1',
        action_type='refresh_config',
        status=status,
        approval_state=approval_state,
        request_state=request_state,
        outcome_code=outcome_code,
        outcome_detail=None,
        result_message=result_message,
        issued_by='operator',
        issued_at=issued_at,
        requested_at=issued_at,
        reviewed_at=None,
        reviewed_by=None,
        delivered_at=None,
        finalized_at=finalized_at,
        finalized_by='device' if finalized_at else None,
        acked_at=finalized_at,
        params={'force': True},
        request_note=None,
        review_note=None,
    )


def test_remote_action_state_and_outcome_normalization_cover_review_and_policy_block():
    pending_review = make_action('ra-review', approval_state='pending')
    blocked = make_action('ra-blocked', status='expired', result_message='Blocked by central policy')

    assert _normalize_remote_action_request_state(pending_review) == 'pending_approval'
    assert _derive_remote_action_outcome(pending_review) == ('accepted', 'awaiting_review')
    assert _derive_remote_action_outcome(blocked) == ('blocked', 'central_policy')


def test_remote_action_summary_and_queue_metrics_count_review_delivery_and_finalized_states():
    actions = [
        make_action('ra-review', approval_state='pending', issued_offset_minutes=-20),
        make_action('ra-queued', status='pending', issued_offset_minutes=-10),
        make_action('ra-ok', status='acked', request_state='finalized', outcome_code='succeeded'),
        make_action('ra-fail', status='failed', request_state='finalized', outcome_code='failed'),
    ]

    summary = _remote_action_summary_payload(actions)
    metrics = _remote_action_queue_metrics(actions)

    assert summary['counts'] == {
        'total': 4,
        'pending_delivery': 1,
        'pending_approval': 1,
        'approved': 0,
        'refused': 0,
        'finalized_success': 1,
        'finalized_failed': 1,
        'expired': 0,
    }
    assert metrics['totals']['needs_triage'] == 2
    assert metrics['sla']['has_pending_review'] is True
    assert metrics['sla']['oldest_pending_approval_at'] == actions[0].issued_at.isoformat()
