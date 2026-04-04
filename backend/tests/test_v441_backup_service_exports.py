import importlib


def test_backup_service_exports_lifespan_hooks_and_router_contract():
    module = importlib.import_module("backend.services.backup_service")

    assert hasattr(module, "start_backup_service")
    assert hasattr(module, "stop_backup_service")
    assert hasattr(module, "backup_service")

    service = module.backup_service
    assert hasattr(service, "list_backups")
    assert hasattr(service, "create_backup")
    assert hasattr(service, "restore_backup")
    assert hasattr(service, "get_backup_path")
    assert hasattr(service, "delete_backup")
    assert hasattr(service, "get_backup_stats")
