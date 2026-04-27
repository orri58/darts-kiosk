from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from central_server.server import _build_license_commercial_readiness, _build_license_portfolio_summary


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


def test_license_commercial_readiness_flags_activation_gap_and_renewal_due():
    license_row = make_license('lic-gap', max_devices=3, ends_in_days=10)

    readiness = _build_license_commercial_readiness(license_row, posture_summary(device_count=0), NOW)

    assert readiness['action_bucket'] == 'attention'
    assert 'activation_gap' in readiness['risk_flags']
    assert 'renewal_due' in readiness['risk_flags']
    assert readiness['capacity_state'] == 'unassigned'
    assert readiness['renewal_days'] == 10


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

    summary = _build_license_portfolio_summary(licenses, posture_map, NOW)

    assert summary['counts']['total'] == 4
    assert summary['counts']['urgent'] == 1
    assert summary['counts']['attention'] == 3
    assert summary['counts']['renewal_due'] == 1
    assert summary['counts']['activation_gap'] == 1
    assert summary['counts']['review_required'] == 1
    assert summary['focus_queues']['urgent'][0]['license_id'] == 'lic-urgent'
    assert summary['focus_queues']['renewals'][0]['license_id'] == 'lic-renew'
    assert summary['focus_queues']['activation_gaps'][0]['license_id'] == 'lic-gap'
    assert summary['focus_queues']['device_review'][0]['license_id'] == 'lic-review'
