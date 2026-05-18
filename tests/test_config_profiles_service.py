import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from central_server.services.config_profiles import (
    build_config_changes,
    deep_merge,
    get_config_diff_payload,
    validate_config_import_payload,
)


class _ScalarOneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarListResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class SequencedDB:
    def __init__(self, values):
        self._values = list(values)

    async def execute(self, _stmt):
        value = self._values.pop(0)
        if isinstance(value, list):
            return _ScalarListResult(value)
        return _ScalarOneResult(value)


def test_deep_merge_and_build_config_changes_cover_nested_profile_diff():
    merged = deep_merge(
        {"theme": {"mode": "dark"}, "feature": {"alpha": True}, "keep": 1},
        {"theme": {"mode": "light", "accent": "blue"}, "feature": {"alpha": False}},
    )

    assert merged == {
        "theme": {"mode": "light", "accent": "blue"},
        "feature": {"alpha": False},
        "keep": 1,
    }

    changes = build_config_changes(
        {"theme": {"mode": "dark"}, "remove": 1},
        {"theme": {"mode": "light", "accent": "blue"}, "add": 2},
    )
    by_key = {item["key"]: item for item in changes}

    assert by_key["theme.mode"]["status"] == "changed"
    assert by_key["theme.accent"]["status"] == "added"
    assert by_key["remove"]["status"] == "removed"
    assert by_key["add"]["status"] == "added"


def test_get_config_diff_payload_compares_history_version_to_active_profile():
    db = SequencedDB([
        SimpleNamespace(config_data={"theme": {"mode": "light"}, "keep": True}, version=9),
        SimpleNamespace(config_data={"theme": {"mode": "dark"}, "old": 1}, version=4),
    ])

    payload = asyncio.run(get_config_diff_payload(
        db=db,
        scope_type="device",
        scope_id="dev-1",
        version=4,
    ))

    assert payload["scope_type"] == "device"
    assert payload["scope_id"] == "dev-1"
    assert payload["old_version"] == 4
    assert payload["new_version"] == 9
    assert payload["total_changes"] == 3
    assert {item["key"] for item in payload["changes"] if item["status"] != "unchanged"} == {"theme.mode", "old", "keep"}


def test_validate_config_import_payload_reports_scope_warning_and_replace_removals():
    db = SequencedDB([
        SimpleNamespace(config_data={"theme": {"mode": "dark"}, "obsolete": True}, version=2),
    ])
    user = SimpleNamespace(role="owner", username="owner")

    payload = asyncio.run(validate_config_import_payload(
        db=db,
        user=user,
        import_data={
            "meta": {
                "type": "darts_kiosk_config_export",
                "scope_type": "customer",
                "scope_id": "cust-1",
                "version": 2,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "config_data": {"theme": {"mode": "light"}},
        },
        target_scope_type="device",
        target_scope_id="dev-1",
        mode="replace",
        can_access_customer=lambda _user, _customer_id: True,
    ))

    assert payload["valid"] is True
    assert any("Replace-Modus" in warning for warning in payload["warnings"])
    assert any("Originaler Scope war 'customer'" in warning for warning in payload["warnings"])
    assert payload["diff"]["total_changes"] == 2
