from pathlib import Path

from backend.database import PROJECT_ROOT, sqlite_path_from_url
from backend.services import setup_wizard
from backend.services.update_service import UpdateService


def test_sqlite_path_from_url_resolves_relative_path():
    path = sqlite_path_from_url('sqlite+aiosqlite:///./data/db/darts.sqlite')
    assert path == (PROJECT_ROOT / 'data' / 'db' / 'darts.sqlite').resolve()


def test_setup_wizard_local_urls_include_setup_endpoint(monkeypatch):
    monkeypatch.setenv('PORT', '8001')
    monkeypatch.setenv('FRONTEND_PORT', '3000')
    monkeypatch.setenv('BOARD_ID', 'BOARD-99')

    urls = setup_wizard._build_local_urls()

    assert urls['backend'] == 'http://localhost:8001'
    assert urls['admin_login'] == 'http://localhost:3000/admin/login'
    assert urls['setup'] == 'http://localhost:3000/setup'
    assert urls['kiosk'].endswith('/BOARD-99')


def test_downloaded_assets_include_filename_and_path(monkeypatch, tmp_path):
    downloads_dir = tmp_path / 'downloads'
    downloads_dir.mkdir()
    asset = downloads_dir / 'darts-kiosk-win.zip'
    asset.write_bytes(b'zip-bytes')

    monkeypatch.setattr('backend.services.update_service.DOWNLOADS_DIR', downloads_dir)

    service = UpdateService()
    items = service.list_downloaded_assets()

    assert len(items) == 1
    assert items[0]['name'] == 'darts-kiosk-win.zip'
    assert items[0]['filename'] == 'darts-kiosk-win.zip'
    assert items[0]['path'] == str(asset)
    assert items[0]['size_bytes'] == len(b'zip-bytes')
