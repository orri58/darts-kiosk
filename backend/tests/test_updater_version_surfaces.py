from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import io
import json

import updater
from backend.services import backup_service as backup_module
from backend.services.system_service import SystemService


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_system_service_tail_logs_reads_root_logs(tmp_path, monkeypatch):
    root_logs = tmp_path / "logs"
    data_logs = tmp_path / "data_logs"
    root_logs.mkdir()
    data_logs.mkdir()
    (root_logs / "backend.log").write_text("line-1\nline-2\n", encoding="utf-8")

    import backend.services.system_service as system_module

    monkeypatch.setattr(system_module, "ROOT_LOGS_DIR", root_logs)
    monkeypatch.setattr(system_module, "LOGS_DIR", data_logs)

    service = SystemService()
    assert service.tail_logs(5) == ["line-1", "line-2"]

    listed = service.list_log_files()
    assert listed[0]["name"] == "backend.log"
    assert listed[0]["dir"] == str(root_logs)


def test_backup_service_list_backups_returns_datetime_created_at(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_file = backup_dir / "darts-kiosk-20260414-195000.sqlite.gz"
    backup_file.write_bytes(b"test")

    monkeypatch.setattr(backup_module, "BACKUP_DIR", backup_dir)

    backups = backup_module.backup_service.list_backups()

    assert len(backups) == 1
    assert isinstance(backups[0].created_at, datetime)
    assert backups[0].created_at.tzinfo == timezone.utc
    stats = backup_module.backup_service.get_backup_stats()
    assert isinstance(stats["latest_backup"], str)
    assert "T" in stats["latest_backup"]


def test_updater_version_check_retries_until_expected(monkeypatch, tmp_path):
    project_root = tmp_path
    (project_root / "VERSION").write_text("4.4.7\n", encoding="utf-8")

    responses = iter([
        _FakeResponse({"installed_version": "4.4.6"}),
        _FakeResponse({"installed_version": "4.4.7"}),
    ])

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(updater.time, "sleep", lambda _seconds: None)

    ok, local_version, api_version = updater.version_check(
        "http://localhost:8001/api/system/version",
        "4.4.7",
        str(project_root),
        retries=2,
        interval=0,
    )

    assert ok is True
    assert local_version == "4.4.7"
    assert api_version == "4.4.7"
