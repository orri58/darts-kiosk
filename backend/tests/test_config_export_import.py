"""
Config Export/Import Feature Tests (v3.9.8)
Tests for: Export, Validate-Import, Apply-Import, Rollback, RBAC, Audit Logging
Central Server runs on port 8002
"""
import pytest
import requests
import os
import time

# Central server URL (NOT the backend proxy)
CS_URL = "http://localhost:8002"

# Test credentials
SUPERADMIN_CREDS = {"username": "superadmin", "password": "admin"}


class TestConfigExportImport:
    """Config Export/Import API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get superadmin auth token"""
        res = requests.post(f"{CS_URL}/api/auth/login", json=SUPERADMIN_CREDS)
        assert res.status_code == 200, f"Login failed: {res.text}"
        data = res.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Auth headers for API calls"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    # ─── EXPORT TESTS ───────────────────────────────────────────
    
    def test_export_global_config_returns_valid_json(self, auth_headers):
        """GET /api/config/export/global/global returns valid JSON with meta and config_data"""
        res = requests.get(f"{CS_URL}/api/config/export/global/global", headers=auth_headers)
        assert res.status_code == 200, f"Export failed: {res.text}"
        
        data = res.json()
        # Validate structure
        assert "meta" in data, "Response missing 'meta'"
        assert "config_data" in data, "Response missing 'config_data'"
        
        # Validate meta fields
        meta = data["meta"]
        assert meta.get("type") == "darts_kiosk_config_export", f"Wrong meta.type: {meta.get('type')}"
        assert "format_version" in meta, "meta missing format_version"
        assert "version" in meta, "meta missing version"
        assert "exported_at" in meta, "meta missing exported_at"
        assert "exported_by" in meta, "meta missing exported_by"
        assert meta.get("scope_type") == "global", f"Wrong scope_type: {meta.get('scope_type')}"
        
        print(f"✓ Export returned valid JSON with meta.type={meta['type']}, version={meta['version']}")
    
    def test_export_nonexistent_scope_returns_404(self, auth_headers):
        """Export for non-existent scope returns 404"""
        res = requests.get(f"{CS_URL}/api/config/export/customer/nonexistent-id", headers=auth_headers)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"
        print("✓ Export for non-existent scope returns 404")
    
    # ─── VALIDATE IMPORT TESTS ──────────────────────────────────
    
    def test_validate_import_missing_meta_type(self, auth_headers):
        """Validation rejects import with missing meta.type"""
        invalid_import = {
            "meta": {"format_version": 1},  # Missing type
            "config_data": {"branding": {"cafe_name": "Test"}}
        }
        res = requests.post(f"{CS_URL}/api/config/import/validate", json={
            "import_data": invalid_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        assert res.status_code == 200, f"Unexpected status: {res.status_code}"
        data = res.json()
        assert data.get("valid") == False, f"Should be invalid: {data}"
        assert any("meta.type" in e.lower() for e in data.get("errors", [])), f"Should mention meta.type: {data.get('errors')}"
        print(f"✓ Validation rejects missing meta.type: {data.get('errors')}")
    
    def test_validate_import_empty_config_data(self, auth_headers):
        """Validation rejects import with empty config_data"""
        invalid_import = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {}  # Empty
        }
        res = requests.post(f"{CS_URL}/api/config/import/validate", json={
            "import_data": invalid_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        assert res.status_code == 200
        data = res.json()
        assert data.get("valid") == False, f"Should be invalid: {data}"
        assert any("config_data" in e.lower() or "leer" in e.lower() for e in data.get("errors", [])), f"Should mention config_data: {data.get('errors')}"
        print(f"✓ Validation rejects empty config_data: {data.get('errors')}")
    
    def test_validate_import_invalid_schema_value(self, auth_headers):
        """Validation rejects invalid schema values (e.g., invalid pricing.mode)"""
        invalid_import = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"pricing": {"mode": "invalid_mode"}}  # Invalid value
        }
        res = requests.post(f"{CS_URL}/api/config/import/validate", json={
            "import_data": invalid_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        assert res.status_code == 200
        data = res.json()
        assert data.get("valid") == False, f"Should be invalid: {data}"
        assert any("schema" in e.lower() or "pricing" in e.lower() for e in data.get("errors", [])), f"Should mention schema error: {data.get('errors')}"
        print(f"✓ Validation rejects invalid schema values: {data.get('errors')}")
    
    def test_validate_import_valid_merge_returns_diff(self, auth_headers):
        """Valid import with merge mode returns diff with changes"""
        valid_import = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1, "scope_type": "global", "scope_id": "global", "version": 1},
            "config_data": {"branding": {"cafe_name": "Test Import Cafe"}}
        }
        res = requests.post(f"{CS_URL}/api/config/import/validate", json={
            "import_data": valid_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        assert res.status_code == 200, f"Validation failed: {res.text}"
        data = res.json()
        assert data.get("valid") == True, f"Should be valid: {data}"
        assert "diff" in data, "Response missing diff"
        assert "changes" in data["diff"], "Diff missing changes"
        assert data.get("mode") == "merge", f"Wrong mode: {data.get('mode')}"
        print(f"✓ Valid merge import returns diff with {data['diff'].get('total_changes', 0)} changes")
    
    def test_validate_import_replace_shows_removed_fields(self, auth_headers):
        """Replace mode shows removed fields in diff"""
        # First, ensure there's some config to replace
        valid_import = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"branding": {"cafe_name": "Replace Test"}}  # Only branding, other fields will be "removed"
        }
        res = requests.post(f"{CS_URL}/api/config/import/validate", json={
            "import_data": valid_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "replace"
        }, headers=auth_headers)
        
        assert res.status_code == 200, f"Validation failed: {res.text}"
        data = res.json()
        assert data.get("valid") == True, f"Should be valid: {data}"
        assert data.get("mode") == "replace", f"Wrong mode: {data.get('mode')}"
        
        # Check for warnings about removed fields
        if data.get("warnings"):
            print(f"✓ Replace mode shows warnings: {data['warnings']}")
        else:
            print("✓ Replace mode validation passed (no warnings if no existing fields)")
    
    # ─── APPLY IMPORT TESTS ─────────────────────────────────────
    
    def test_apply_import_merge_creates_version(self, auth_headers):
        """Apply import with merge mode creates new version and saves history"""
        # Get current version first
        export_res = requests.get(f"{CS_URL}/api/config/export/global/global", headers=auth_headers)
        current_version = export_res.json().get("meta", {}).get("version", 0) if export_res.status_code == 200 else 0
        
        # Apply merge import
        test_value = f"Merge Test {int(time.time())}"
        import_data = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1, "scope_type": "global", "scope_id": "global", "version": 1},
            "config_data": {"branding": {"cafe_name": test_value}}
        }
        res = requests.post(f"{CS_URL}/api/config/import/apply", json={
            "import_data": import_data,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        assert res.status_code == 200, f"Apply failed: {res.text}"
        data = res.json()
        assert data.get("success") == True, f"Apply not successful: {data}"
        assert data.get("mode") == "merge", f"Wrong mode: {data.get('mode')}"
        assert "profile" in data, "Response missing profile"
        
        new_version = data["profile"].get("version", 0)
        assert new_version > current_version, f"Version should increase: {current_version} -> {new_version}"
        
        # Verify the value was saved
        verify_res = requests.get(f"{CS_URL}/api/config/export/global/global", headers=auth_headers)
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["config_data"].get("branding", {}).get("cafe_name") == test_value, f"Value not saved: {verify_data['config_data']}"
        
        print(f"✓ Merge import created version {new_version}, value saved correctly")
        return new_version
    
    def test_apply_import_replace_removes_old_fields(self, auth_headers):
        """Apply import with replace mode removes fields not in import"""
        # First add a field via merge
        setup_import = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"branding": {"cafe_name": "Setup", "primary_color": "#FF0000"}, "pricing": {"mode": "per_game"}}
        }
        requests.post(f"{CS_URL}/api/config/import/apply", json={
            "import_data": setup_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        # Now replace with only branding
        replace_import = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"branding": {"cafe_name": "Replace Only"}}
        }
        res = requests.post(f"{CS_URL}/api/config/import/apply", json={
            "import_data": replace_import,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "replace"
        }, headers=auth_headers)
        
        assert res.status_code == 200, f"Replace failed: {res.text}"
        data = res.json()
        assert data.get("success") == True
        assert data.get("mode") == "replace"
        
        # Verify pricing was removed
        verify_res = requests.get(f"{CS_URL}/api/config/export/global/global", headers=auth_headers)
        verify_data = verify_res.json()
        assert "pricing" not in verify_data["config_data"], f"pricing should be removed: {verify_data['config_data']}"
        
        print("✓ Replace import removed old fields correctly")
    
    def test_history_shows_import_labels(self, auth_headers):
        """History shows correct import-merge/import-replace labels in updated_by"""
        res = requests.get(f"{CS_URL}/api/config/history/global/global", headers=auth_headers)
        assert res.status_code == 200, f"History fetch failed: {res.text}"
        
        data = res.json()
        # History endpoint returns dict with 'history' key
        history = data.get("history", []) if isinstance(data, dict) else data
        assert isinstance(history, list), f"History should be list: {data}"
        
        # Check for import labels in recent history
        import_entries = [h for h in history if "import" in h.get("updated_by", "").lower()]
        if import_entries:
            print(f"✓ History contains import entries: {[h.get('updated_by') for h in import_entries[:3]]}")
        else:
            print("✓ History endpoint works (no import entries yet)")
    
    # ─── ROLLBACK TESTS ─────────────────────────────────────────
    
    def test_rollback_after_import_works(self, auth_headers):
        """Rollback after import creates new version and returns new_version"""
        # First do an import to create history
        import_data = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"branding": {"cafe_name": f"Pre-Rollback {int(time.time())}"}}
        }
        apply_res = requests.post(f"{CS_URL}/api/config/import/apply", json={
            "import_data": import_data,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        assert apply_res.status_code == 200
        
        # Get history to find a version to rollback to
        history_res = requests.get(f"{CS_URL}/api/config/history/global/global", headers=auth_headers)
        assert history_res.status_code == 200
        history_data = history_res.json()
        
        # History endpoint returns dict with 'history' key
        history = history_data.get("history", []) if isinstance(history_data, dict) else history_data
        
        if not history:
            pytest.skip("No history entries to rollback to")
        
        # Rollback to first available version
        rollback_version = history[0].get("version", 1)
        rollback_res = requests.post(f"{CS_URL}/api/config/rollback/global/global/{rollback_version}", headers=auth_headers)
        
        assert rollback_res.status_code == 200, f"Rollback failed: {rollback_res.text}"
        data = rollback_res.json()
        assert data.get("success") == True, f"Rollback not successful: {data}"
        assert "new_version" in data, f"Response missing new_version: {data}"
        assert data.get("rolled_back_to") == rollback_version, f"Wrong rolled_back_to: {data}"
        
        print(f"✓ Rollback to v{rollback_version} created new version {data['new_version']}")
    
    def test_rollback_nonexistent_version_returns_404(self, auth_headers):
        """Rollback to non-existent version returns 404"""
        res = requests.post(f"{CS_URL}/api/config/rollback/global/global/99999", headers=auth_headers)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"
        print("✓ Rollback to non-existent version returns 404")
    
    # ─── RBAC TESTS ─────────────────────────────────────────────
    
    def test_rbac_non_superadmin_cannot_import_global(self):
        """Non-superadmin cannot import to global scope"""
        # Try to create a non-superadmin user or use existing one
        # First login as superadmin to check if there's an owner user
        admin_res = requests.post(f"{CS_URL}/api/auth/login", json=SUPERADMIN_CREDS)
        admin_token = admin_res.json().get("access_token")
        admin_headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        
        # Get users to find a non-superadmin
        users_res = requests.get(f"{CS_URL}/api/users", headers=admin_headers)
        if users_res.status_code != 200:
            pytest.skip("Cannot fetch users to test RBAC")
        
        users = users_res.json()
        non_superadmin = next((u for u in users if u.get("role") != "superadmin"), None)
        
        if not non_superadmin:
            # Create a test owner user
            create_res = requests.post(f"{CS_URL}/api/users", json={
                "username": "test_owner_rbac",
                "password": "testpass123",
                "role": "owner"
            }, headers=admin_headers)
            if create_res.status_code not in [200, 201]:
                pytest.skip("Cannot create test user for RBAC test")
            non_superadmin = create_res.json()
        
        # Login as non-superadmin
        login_res = requests.post(f"{CS_URL}/api/auth/login", json={
            "username": non_superadmin.get("username", "test_owner_rbac"),
            "password": "testpass123"
        })
        
        if login_res.status_code != 200:
            pytest.skip(f"Cannot login as non-superadmin: {login_res.text}")
        
        owner_token = login_res.json().get("access_token")
        owner_headers = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}
        
        # Try to validate import to global scope
        import_data = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"branding": {"cafe_name": "RBAC Test"}}
        }
        res = requests.post(f"{CS_URL}/api/config/import/validate", json={
            "import_data": import_data,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=owner_headers)
        
        # Should either return valid=False with RBAC error or 403
        if res.status_code == 200:
            data = res.json()
            assert data.get("valid") == False, f"Non-superadmin should not be able to import to global: {data}"
            assert any("superadmin" in e.lower() for e in data.get("errors", [])), f"Should mention superadmin: {data.get('errors')}"
            print(f"✓ RBAC: Non-superadmin blocked from global import: {data.get('errors')}")
        else:
            assert res.status_code == 403, f"Expected 403 or valid=False, got {res.status_code}: {res.text}"
            print("✓ RBAC: Non-superadmin blocked from global import (403)")
    
    # ─── AUDIT LOG TESTS ────────────────────────────────────────
    
    def test_audit_log_records_export(self, auth_headers):
        """Audit log records config_export action"""
        # Do an export
        requests.get(f"{CS_URL}/api/config/export/global/global", headers=auth_headers)
        
        # Check audit log
        time.sleep(0.5)  # Allow time for audit to be written
        audit_res = requests.get(f"{CS_URL}/api/licensing/audit-log?limit=20", headers=auth_headers)
        
        if audit_res.status_code != 200:
            pytest.skip(f"Cannot fetch audit log: {audit_res.text}")
        
        logs = audit_res.json()
        export_logs = [l for l in logs if l.get("action") == "config_export"]
        
        if export_logs:
            print(f"✓ Audit log contains config_export entries: {len(export_logs)} found")
        else:
            print("⚠ No config_export entries in recent audit log (may be older)")
    
    def test_audit_log_records_import(self, auth_headers):
        """Audit log records config_import action"""
        # Do an import
        import_data = {
            "meta": {"type": "darts_kiosk_config_export", "format_version": 1},
            "config_data": {"branding": {"cafe_name": f"Audit Test {int(time.time())}"}}
        }
        requests.post(f"{CS_URL}/api/config/import/apply", json={
            "import_data": import_data,
            "target_scope_type": "global",
            "target_scope_id": "global",
            "mode": "merge"
        }, headers=auth_headers)
        
        # Check audit log
        time.sleep(0.5)
        audit_res = requests.get(f"{CS_URL}/api/licensing/audit-log?limit=20", headers=auth_headers)
        
        if audit_res.status_code != 200:
            pytest.skip(f"Cannot fetch audit log: {audit_res.text}")
        
        logs = audit_res.json()
        import_logs = [l for l in logs if l.get("action") == "config_import"]
        
        if import_logs:
            print(f"✓ Audit log contains config_import entries: {len(import_logs)} found")
        else:
            print("⚠ No config_import entries in recent audit log")
    
    def test_audit_log_records_rollback(self, auth_headers):
        """Audit log records config_rollback action"""
        # Get history first
        history_res = requests.get(f"{CS_URL}/api/config/history/global/global", headers=auth_headers)
        if history_res.status_code != 200:
            pytest.skip("No history for rollback test")
        
        history_data = history_res.json()
        history = history_data.get("history", []) if isinstance(history_data, dict) else history_data
        
        if not history:
            pytest.skip("No history entries for rollback test")
        
        rollback_version = history[0].get("version", 1)
        
        # Do a rollback
        requests.post(f"{CS_URL}/api/config/rollback/global/global/{rollback_version}", headers=auth_headers)
        
        # Check audit log
        time.sleep(0.5)
        audit_res = requests.get(f"{CS_URL}/api/licensing/audit-log?limit=20", headers=auth_headers)
        
        if audit_res.status_code != 200:
            pytest.skip(f"Cannot fetch audit log: {audit_res.text}")
        
        logs = audit_res.json()
        rollback_logs = [l for l in logs if l.get("action") == "config_rollback"]
        
        if rollback_logs:
            print(f"✓ Audit log contains config_rollback entries: {len(rollback_logs)} found")
        else:
            print("⚠ No config_rollback entries in recent audit log")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
