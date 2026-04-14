from pathlib import Path

import pytest

from backend.routers import admin
from backend.services.system_service import SystemService
from backend.services.update_service import UpdateService
from backend.services import version_service


@pytest.fixture
def temp_version_file(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    monkeypatch.setattr(version_service, "VERSION_FILE", version_file)
    return version_file


def test_system_service_reads_current_version_from_disk(temp_version_file):
    temp_version_file.write_text("4.4.4\n", encoding="utf-8")
    service = SystemService()

    assert service.get_system_info()["version"] == "4.4.4"

    temp_version_file.write_text("4.4.5\n", encoding="utf-8")
    assert service.get_system_info()["version"] == "4.4.5"


def test_update_service_reads_current_version_dynamically(temp_version_file):
    temp_version_file.write_text("4.4.4\n", encoding="utf-8")
    service = UpdateService()

    assert service.get_current_version() == "4.4.4"

    temp_version_file.write_text("4.4.5\n", encoding="utf-8")
    assert service.get_current_version() == "4.4.5"


@pytest.mark.asyncio
async def test_public_system_version_endpoint_reads_current_version_from_disk(temp_version_file):
    temp_version_file.write_text("4.4.4\n", encoding="utf-8")
    first = await admin.get_system_version()
    assert first["installed_version"] == "4.4.4"

    temp_version_file.write_text("4.4.5\n", encoding="utf-8")
    second = await admin.get_system_version()
    assert second["installed_version"] == "4.4.5"
