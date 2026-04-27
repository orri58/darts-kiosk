from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from central_server.server import (
    _build_license_commercial_readiness,
    _build_license_portfolio_summary,
    _refine_license_detail_suggested_actions,
    _summarize_license_token_state,
)


NOW = datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc)


def make_license(license_id: str, *, status='active', max_devices=2, ends_in_days=30, plan_type='standard'):
    ends_at = NOW + timedelta(days=ends_in_days) if ends_in_days is not None else None
    return SimpleNamespace(
        id=license_id,
        customer_id='cust-1',
        location_id='loc-1',
        plan_type=plan_type,
        max_devices=max_devices,
        status=status,
        starts_at=NOW - timedelta(days=30),
        ends_at=ends_at,
        grace_days=7,
        grace_until=ends_at + timedelta(days=7) if ends_at is not None else None,
    )


def posture_summary(*, device_count=0, overall='ready', ready=0, degraded=0, review_required=0, blocked=0):
    return {
        'device_count': device_count,
        'overall_posture': overall,
        'counts': {
            'ready': ready,
            'degraded': degraded,
            'review_required': review_required,
            'blocked': blocked,
        },
    }


def make_token(token_id: str, *, expires_in_days=3, used=False, revoked=False):
    expires_at = NOW + timedelta(days=expires_in_days) if expires_in_days is not None else None
    return SimpleNamespace(
        id=token_id,
        token_preview=f'{token_id[:8]}...tok',
        license_id='lic-1',
        device_name_template=None,
        expires_at=expires_at,
        used_at=NOW - timedelta(hours=1) if used else None,
        is_revoked=revoked,
        revoked_at=NOW - timedelta(hours=2) if revoked else None,
        created_at=NOW - timedelta(days=1),
    )


def test_license_commercial_readiness_flags_activation_gap_and_renewal_due():
    license_row = make_license('lic-gap', max_devices=3, ends_in_days=10)

    readiness = _build_license_commercial_readiness(license_row, posture_summary(device_count=0), NOW)

    assert readiness['action_bucket'] == 'attention'
    assert 'activation_gap' in readiness['risk_flags']
    assert 'renewal_due' in readiness['risk_flags']
    assert readiness['capacity_state'] == 'unassigned'
    assert readiness['renewal_days'] == 10
    assert [item['type'] for item in readiness['suggested_actions'][:2]] == [
        'renew_license',
        'generate_activation_token',
    ]
    assert readiness['suggested_actions'][1]['execution'] == {
        'mode': 'direct',
        'action': 'ensure_activation_token',
    }


def test_license_commercial_readiness_escalates_blocked_or_over_capacity_cases():
    license_row = make_license('lic-over', max_devices=1, ends_in_days=45)

    readiness = _build_license_commercial_readiness(
        license_row,
        posture_summary(device_count=2, overall='blocked', blocked=1),
        NOW,
    )

    assert readiness['action_bucket'] == 'urgent'
    assert readiness['capacity_state'] == 'over_capacity'
    assert 'capacity_over' in readiness['risk_flags']
    assert 'device_blocked' in readiness['risk_flags']
    assert {item['type'] for item in readiness['suggested_actions']} >= {
        'upgrade_capacity',
        'review_bound_devices',
    }
    device_review_action = next(item for item in readiness['suggested_actions'] if item['type'] == 'review_bound_devices')
    assert device_review_action['execution'] == {
        'mode': 'navigate',
        'target': 'remote_actions',
    }


def test_license_commercial_readiness_suggests_reactivation_for_deactivated_license():
    license_row = make_license('lic-off', status='deactivated', max_devices=2, ends_in_days=30)

    readiness = _build_license_commercial_readiness(license_row, posture_summary(device_count=1, overall='ready', ready=1), NOW)

    assert readiness['action_bucket'] == 'urgent'
    assert readiness['suggested_actions'][0]['type'] == 'reactivate_license'
    assert readiness['suggested_actions'][0]['intent'] == 'reactivate'
    assert readiness['suggested_actions'][0]['execution'] == {
        'mode': 'direct',
        'action': 'reactivate_license',
    }


def test_license_detail_actions_prefer_regenerate_when_active_token_exists_before_device_binding():
    license_row = make_license('lic-token-gap', status='active', max_devices=2, ends_in_days=20)
    readiness = _build_license_commercial_readiness(license_row, posture_summary(device_count=0), NOW)
    active_token = SimpleNamespace(id='tok-1')

    actions = _refine_license_detail_suggested_actions(
        license_row,
        readiness,
        active_token=active_token,
        device_count=0,
    )

    assert actions[0]['type'] == 'regenerate_activation_token'
    assert actions[0]['execution'] == {
        'mode': 'direct',
        'action': 'regenerate_activation_token',
    }
    assert {item['type'] for item in actions}
    assert 'generate_activation_token' not in {item['type'] for item in actions}


def test_license_detail_actions_keep_generate_when_no_active_token_exists():
    license_row = make_license('lic-token-new', status='active', max_devices=2, ends_in_days=20)
    readiness = _build_license_commercial_readiness(license_row, posture_summary(device_count=0), NOW)

    actions = _refine_license_detail_suggested_actions(
        license_row,
        readiness,
        active_token=None,
        device_count=0,
    )

    assert actions[0]['type'] == 'generate_activation_token'
    assert actions[0]['execution'] == {
        'mode': 'direct',
        'action': 'ensure_activation_token',
    }


def test_license_token_summary_reports_active_token_state():
    summary = _summarize_license_token_state([make_token('tok-active')], NOW)

    assert summary['state'] == 'active'
    assert summary['badge_tone'] == 'blue'
    assert summary['active_token']['id'] == 'tok-active'
    assert summary['active_expires_in_days'] == 3
    assert summary['counts']['total'] == 1
    assert summary['counts']['active'] == 1


def test_license_commercial_readiness_prefers_get_token_when_active_token_exists_on_gap_license():
    license_row = make_license('lic-token-ready', status='active', max_devices=2, ends_in_days=20)
    token_summary = _summarize_license_token_state([make_token('tok-active')], NOW)

    readiness = _build_license_commercial_readiness(
        license_row,
        posture_summary(device_count=0),
        NOW,
        token_summary,
    )

    assert readiness['token_state'] == 'active'
    assert readiness['primary_message'] == 'Lizenz ist aktiv, ein Aktivierungstoken liegt bereits bereit'
    assert readiness['suggested_actions'][0]['type'] == 'get_activation_token'
    assert readiness['suggested_actions'][0]['execution'] == {
        'mode': 'direct',
        'action': 'ensure_activation_token',
    }


def test_license_commercial_readiness_prefers_regenerate_when_last_token_is_stale():
    license_row = make_license('lic-token-stale', status='active', max_devices=2, ends_in_days=20)
    token_summary = _summarize_license_token_state([make_token('tok-old', expires_in_days=-1)], NOW)

    readiness = _build_license_commercial_readiness(
        license_row,
        posture_summary(device_count=0),
        NOW,
        token_summary,
    )

    assert readiness['token_state'] == 'expired'
    assert 'activation_token_stale' in readiness['risk_flags']
    assert readiness['suggested_actions'][0]['type'] == 'regenerate_activation_token'
    assert readiness['suggested_actions'][0]['execution'] == {
        'mode': 'direct',
        'action': 'regenerate_activation_token',
    }


def test_license_portfolio_summary_builds_focus_queues_and_counts():
    licenses = [
        make_license('lic-urgent', status='blocked', max_devices=1, ends_in_days=-1),
        make_license('lic-renew', status='active', max_devices=2, ends_in_days=7),
        make_license('lic-gap', status='active', max_devices=2, ends_in_days=20),
        make_license('lic-review', status='active', max_devices=2, ends_in_days=20),
    ]
    posture_map = {
        'lic-urgent': posture_summary(device_count=1, overall='blocked', blocked=1),
        'lic-renew': posture_summary(device_count=1, overall='ready', ready=1),
        'lic-gap': posture_summary(device_count=0, overall='ready'),
        'lic-review': posture_summary(device_count=1, overall='review_required', review_required=1),
    }
    token_map = {
        'lic-gap': _summarize_license_token_state([make_token('tok-gap')], NOW),
    }

    summary = _build_license_portfolio_summary(licenses, posture_map, NOW, token_map)

    assert summary['counts']['total'] == 4
    assert summary['counts']['urgent'] == 1
    assert summary['counts']['attention'] == 3
    assert summary['counts']['renewal_due'] == 1
    assert summary['counts']['activation_gap'] == 1
    assert summary['counts']['token_ready'] == 1
    assert summary['counts']['token_attention'] == 0
    assert summary['counts']['review_required'] == 1
    assert summary['focus_queues']['urgent'][0]['license_id'] == 'lic-urgent'
    assert summary['focus_queues']['renewals'][0]['license_id'] == 'lic-renew'
    assert summary['focus_queues']['activation_gaps'][0]['license_id'] == 'lic-gap'
    assert summary['focus_queues']['activation_gaps'][0]['token_state'] == 'active'
    assert summary['focus_queues']['token_follow_up'][0]['license_id'] == 'lic-gap'
    assert summary['focus_queues']['device_review'][0]['license_id'] == 'lic-review'
