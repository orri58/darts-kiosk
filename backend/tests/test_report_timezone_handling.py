from datetime import datetime, timezone
from types import SimpleNamespace

from backend.routers import admin as admin_router


def test_parse_report_datetime_preserves_offset_and_converts_to_utc():
    parsed = admin_router._parse_report_datetime("2026-04-14T00:00:00+02:00")

    assert parsed == datetime(2026, 4, 13, 22, 0, 0, tzinfo=timezone.utc)


def test_parse_report_datetime_keeps_naive_values_as_utc():
    parsed = admin_router._parse_report_datetime("2026-04-14T20:04:00")

    assert parsed == datetime(2026, 4, 14, 20, 4, 0, tzinfo=timezone.utc)


def test_ensure_utc_marks_naive_session_timestamp_as_utc():
    value = datetime(2026, 4, 14, 18, 4, 0)

    assert admin_router._ensure_utc(value) == datetime(2026, 4, 14, 18, 4, 0, tzinfo=timezone.utc)


def test_ensure_utc_keeps_aware_value_unchanged():
    value = datetime(2026, 4, 14, 18, 4, 0, tzinfo=timezone.utc)

    assert admin_router._ensure_utc(value) is value
