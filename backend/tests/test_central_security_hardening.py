import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect, WebSocketState


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def central_app_env(monkeypatch, tmp_path):
    data_dir = tmp_path / "central-data"
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_ADMIN_TOKEN", "legacy-admin-token")
    monkeypatch.delenv("CENTRAL_ENABLE_LEGACY_ADMIN_TOKEN", raising=False)

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
    ]:
        sys.modules.pop(name, None)

    database = importlib.import_module("central_server.database")
    models = importlib.import_module("central_server.models")
    auth = importlib.import_module("central_server.auth")
    server = importlib.import_module("central_server.server")

    return {
        "database": database,
        "models": models,
        "auth": auth,
        "server": server,
        "data_dir": data_dir,
    }


@pytest.fixture()
def client(central_app_env):
    with TestClient(central_app_env["server"].app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_central(central_app_env, client):
    models = central_app_env["models"]
    auth = central_app_env["auth"]
    sync_engine = central_app_env["database"].sync_engine

    with Session(sync_engine) as session:
        customer = models.CentralCustomer(name="ACME Darts")
        session.add(customer)
        session.flush()

        location = models.CentralLocation(customer_id=customer.id, name="Main Hall")
        session.add(location)
        session.flush()

        device = models.CentralDevice(
            location_id=location.id,
            device_name="Board 1",
            api_key="device-api-key",
            install_id="install-1",
            status="active",
            binding_status="bound",
        )
        session.add(device)

        owner = models.CentralUser(
            username="owner",
            password_hash=auth.hash_password("owner-pass"),
            display_name="Owner",
            role="owner",
            allowed_customer_ids=[customer.id],
            status="active",
        )
        session.add(owner)

        installer = models.CentralUser(
            username="installer",
            password_hash=auth.hash_password("installer-pass"),
            display_name="Installer",
            role="installer",
            allowed_customer_ids=[customer.id],
            status="active",
        )
        session.add(installer)

        outsider_customer = models.CentralCustomer(name="Other Customer")
        session.add(outsider_customer)
        session.flush()

        outsider_location = models.CentralLocation(customer_id=outsider_customer.id, name="Other Hall")
        session.add(outsider_location)
        session.flush()

        outsider_device = models.CentralDevice(
            location_id=outsider_location.id,
            device_name="Other Board",
            api_key="other-device-api-key",
            install_id="install-2",
            status="active",
            binding_status="bound",
        )
        session.add(outsider_device)

        legacy_user = models.CentralUser(
            username="legacy-user",
            password_hash=auth._legacy_hash_password("legacy-pass"),
            display_name="Legacy User",
            role="owner",
            allowed_customer_ids=[customer.id],
            status="active",
        )
        session.add(legacy_user)

        session.commit()

        seeded = {
            "customer_id": customer.id,
            "location_id": location.id,
            "device_id": device.id,
            "owner_id": owner.id,
            "installer_id": installer.id,
            "outsider_device_id": outsider_device.id,
            "legacy_user_id": legacy_user.id,
        }

    return seeded


def _login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_bootstrap_superadmin_requires_explicit_password(central_app_env, client):
    token = _login(client, "superadmin", "bootstrap-pass")
    assert token


def test_legacy_admin_token_disabled_by_default(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer legacy-admin-token"},
    )
    assert response.status_code == 401


def test_legacy_admin_token_can_be_opted_in(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-optin"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_ADMIN_TOKEN", "legacy-admin-token")
    monkeypatch.setenv("CENTRAL_ENABLE_LEGACY_ADMIN_TOKEN", "true")

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
    ]:
        sys.modules.pop(name, None)

    server = importlib.import_module("central_server.server")

    with TestClient(server.app) as optin_client:
        response = optin_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer legacy-admin-token"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "superadmin"


def test_production_requires_explicit_jwt_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-prod-jwt"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_ENV", "production")
    monkeypatch.delenv("CENTRAL_JWT_SECRET", raising=False)

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
        "central_server.device_trust",
    ]:
        sys.modules.pop(name, None)

    with pytest.raises(RuntimeError, match="CENTRAL_JWT_SECRET is required in production"):
        importlib.import_module("central_server.server")



def test_production_blocks_wildcard_cors_without_explicit_unsafe_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-prod-cors"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_ENV", "production")
    monkeypatch.setenv("CENTRAL_CORS_ALLOW_ALL", "true")
    monkeypatch.delenv("CENTRAL_ALLOW_INSECURE_CORS_WILDCARD", raising=False)

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
        "central_server.device_trust",
    ]:
        sys.modules.pop(name, None)

    with pytest.raises(RuntimeError, match="CENTRAL_CORS_ALLOW_ALL is blocked in production"):
        importlib.import_module("central_server.server")



def test_production_can_explicitly_override_wildcard_cors_guard(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-prod-cors-override"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_ENV", "production")
    monkeypatch.setenv("CENTRAL_CORS_ALLOW_ALL", "true")
    monkeypatch.setenv("CENTRAL_ALLOW_INSECURE_CORS_WILDCARD", "true")

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
        "central_server.device_trust",
    ]:
        sys.modules.pop(name, None)

    server = importlib.import_module("central_server.server")
    assert server._CORS_ALLOWED_ORIGINS == ["*"]



def test_device_trust_placeholder_signing_secret_is_blocked_in_production(monkeypatch):
    monkeypatch.setenv("CENTRAL_ENV", "production")
    monkeypatch.delenv("CENTRAL_DEVICE_TRUST_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("CENTRAL_JWT_SECRET", raising=False)

    sys.modules.pop("central_server.device_trust", None)
    device_trust = importlib.import_module("central_server.device_trust")

    with pytest.raises(
        RuntimeError,
        match="CENTRAL_DEVICE_TRUST_SIGNING_SECRET or CENTRAL_JWT_SECRET is required in production",
    ):
        device_trust.sign_payload({"hello": "world"})


def test_legacy_password_login_rehashes_and_persists(central_app_env, client, seeded_central):
    token = _login(client, "legacy-user", "legacy-pass")
    assert token

    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    with Session(sync_engine) as session:
        user = session.get(models.CentralUser, seeded_central["legacy_user_id"])
        assert user is not None
        assert user.password_hash.startswith("$2")
        assert user.password_hash != central_app_env["auth"]._legacy_hash_password("legacy-pass")


def test_effective_config_requires_authentication(client):
    response = client.get("/api/config/effective")
    assert response.status_code == 401


def test_effective_config_allows_device_only_for_own_scope(client, seeded_central):
    response = client.get(
        "/api/config/effective",
        headers={"X-License-Key": "device-api-key"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["scope"]["device_id"] == seeded_central["device_id"]
    assert data["scope"]["location_id"] == seeded_central["location_id"]
    assert data["scope"]["customer_id"] == seeded_central["customer_id"]

    forbidden = client.get(
        "/api/config/effective",
        params={"device_id": seeded_central["outsider_device_id"]},
        headers={"X-License-Key": "device-api-key"},
    )
    assert forbidden.status_code == 403


def test_remote_actions_pending_requires_device_auth(client, seeded_central):
    response = client.get(f"/api/remote-actions/{seeded_central['device_id']}/pending")
    assert response.status_code == 401


def test_remote_actions_pending_rejects_cross_device_access(client, seeded_central):
    response = client.get(
        f"/api/remote-actions/{seeded_central['outsider_device_id']}/pending",
        headers={"X-License-Key": "device-api-key"},
    )
    assert response.status_code == 403


def test_remote_action_ack_rejects_cross_device_access(client, seeded_central):
    token = _login(client, "superadmin", "bootstrap-pass")
    issue_response = client.post(
        f"/api/remote-actions/{seeded_central['outsider_device_id']}",
        json={"action_type": "force_sync"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert issue_response.status_code == 200, issue_response.text
    action_id = issue_response.json()["id"]

    ack_response = client.post(
        f"/api/remote-actions/{seeded_central['outsider_device_id']}/ack",
        json={"action_id": action_id, "success": True},
        headers={"X-License-Key": "device-api-key"},
    )
    assert ack_response.status_code == 403


def test_license_detail_redacts_token_audit_fields_and_uses_operator_safe_device_summaries(central_app_env, client, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        license_row = models.CentralLicense(
            customer_id=seeded_central["customer_id"],
            location_id=seeded_central["location_id"],
            plan_type="pro",
            max_devices=2,
            status="active",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
            grace_until=now + timedelta(days=37),
        )
        session.add(license_row)
        session.flush()

        device = session.get(models.CentralDevice, seeded_central["device_id"])
        device.license_id = license_row.id
        device.trust_reason = "manual trust note"
        device.credential_fingerprint = "fp-license-detail"
        device.lease_id = "lease-license-detail"
        device.last_error = "private device detail"

        session.add(
            models.RegistrationToken(
                license_id=license_row.id,
                customer_id=seeded_central["customer_id"],
                location_id=seeded_central["location_id"],
                token_hash="hash-1",
                token_preview="tok_live_1234",
                device_name_template="Board Template",
                expires_at=now + timedelta(hours=12),
                created_by="superadmin",
                note="internal note",
                used_by_install_id="install-secret",
                used_by_device_id=seeded_central["device_id"],
            )
        )
        session.commit()
        license_id = license_row.id

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/licensing/licenses/{license_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["active_token"]["token_preview"] == "tok_live_1234"
    assert "used_by_install_id" not in data["active_token"]
    assert "used_by_device_id" not in data["active_token"]
    assert "created_by" not in data["active_token"]
    assert "note" not in data["active_token"]
    assert "revoked_by" not in data["active_token"]
    assert "raw_token" not in data["active_token"]
    assert "token_history" in data
    assert "used_by_install_id" not in data["token_history"][0]
    assert data["devices"][0]["detail_level"] == "operator_safe"
    assert "api_key_preview" not in data["devices"][0]
    assert "trust_reason" not in data["devices"][0]
    assert "credential_fingerprint" not in data["devices"][0]
    assert "lease_id" not in data["devices"][0]
    assert "last_error" not in data["devices"][0]



def test_installer_license_detail_keeps_internal_device_summary_fields(central_app_env, client, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        license_row = models.CentralLicense(
            customer_id=seeded_central["customer_id"],
            location_id=seeded_central["location_id"],
            plan_type="pro",
            max_devices=2,
            status="active",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
            grace_until=now + timedelta(days=37),
        )
        session.add(license_row)
        session.flush()

        device = session.get(models.CentralDevice, seeded_central["device_id"])
        device.license_id = license_row.id
        device.trust_reason = "installer trust note"
        device.credential_fingerprint = "fp-license-installer"
        device.lease_id = "lease-license-installer"
        device.last_error = "installer-visible error"
        session.commit()
        license_id = license_row.id

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/licensing/licenses/{license_id}",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["devices"][0]["detail_level"] == "internal"
    assert data["devices"][0]["api_key_preview"].startswith("device-a")
    assert data["devices"][0]["trust_reason"] == "installer trust note"
    assert data["devices"][0]["credential_fingerprint"] == "fp-license-installer"
    assert data["devices"][0]["lease_id"] == "lease-license-installer"
    assert data["devices"][0]["last_error"] == "installer-visible error"


def test_device_trust_detail_redacts_sensitive_material(central_app_env, client, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status="active",
            credential_kind="mtls",
            fingerprint="fp-123",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            details_json={
                "key_id": "key-123",
                "issued_by": "superadmin",
                "csr_pem": "secret-csr",
            },
        )
        session.add(credential)
        session.flush()

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=None,
            lease_id="lease-123",
            status="active",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            grace_until=now + timedelta(hours=24),
            signature="super-secret-signature",
            details_json={
                "credential_id": credential.id,
                "issued_by": "superadmin",
                "capability_overrides": {"remote_restart": True},
            },
        )
        session.add(lease)
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/device-trust/devices/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "operator_safe"
    assert data["device"]["detail_level"] == "operator_safe"
    assert data["credentials"][0]["key_id"] == "key-123"
    assert "fingerprint" not in data["credentials"][0]
    assert "metadata" not in data["credentials"][0]
    assert "payload" not in data["credentials"][0]["verification"]
    assert "stored_fingerprint" not in data["credentials"][0]["verification"]
    assert "signature" not in data["leases"][0]
    assert "metadata" not in data["leases"][0]
    assert "signed_bundle" not in data["leases"][0]
    assert "payload" not in data["leases"][0]["verification"]
    assert "expected_fingerprint" not in data["leases"][0]["verification"]
    assert data["leases"][0]["verification"]["valid"] in {True, False}
    assert data["credentials"][0]["detail_level"] == "operator_safe"
    assert data["leases"][0]["detail_level"] == "operator_safe"
    assert data["diagnostics_timestamp"]
    assert data["endpoint_summary"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["contract_summary"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["contract_summary"]["issuer_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["contract_summary"]["material_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["contract_summary"]["signing_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["issuer_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["history_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["material_alignment"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["material_summary"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["issuer_state"]["effective_key_id"] == "key-123"
    assert data["endpoint_summary"]["material_timestamps"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["material_timestamps"]["lease_expires_at"].startswith(data["leases"][0]["expires_at"])
    assert set(data["reconciliation"].keys()) == {"ok", "summary", "bundle_source", "detail_level"}
    assert data["reconciliation"]["detail_level"] == "operator_safe"
    assert set(data["reconciliation_summary"].keys()) == {"ok", "status_counts", "bundle_source", "timing", "support_summary", "issuer_profiles", "material_readback_summary", "detail_level"}
    assert data["reconciliation_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["status_counts"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["timing"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["support_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["transition"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["lineage_explanation"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["readback_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["history_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["source_contract_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["source_contract_summary"]["total_contracts"] == 3
    assert data["reconciliation_summary"]["issuer_profiles"]["source_contract_summary"]["has_present_contracts"] is True
    assert data["reconciliation_summary"]["material_readback_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["material_readback_summary"]["credential_history"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["material_readback_summary"]["lease_history"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["active_profile"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["configured_profile"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["effective_profile"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["support_summary"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["support_summary"]["transition"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["readback_summary"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["readback_summary"]["lineage_explanation"]["detail_level"] == "operator_safe"
    assert data["issuer_profiles"]["history_summary"]["detail_level"] == "operator_safe"
    assert data["signing_registry"]["support_summary"]["detail_level"] == "operator_safe"
    assert data["signing_registry"]["status_counts"]["detail_level"] == "operator_safe"
    assert "entries" not in data["signing_registry"]
    assert "referenced_key_ids" not in data["signing_registry"]


def test_installer_device_trust_detail_keeps_internal_fields(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status="active",
            credential_kind="mtls",
            fingerprint="fp-installer",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            details_json={"key_id": "key-installer", "csr_pem": "secret-csr"},
        )
        session.add(credential)
        session.flush()

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=None,
            lease_id="lease-installer",
            status="active",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            grace_until=now + timedelta(hours=24),
            signature="installer-visible-signature",
            details_json={"credential_id": credential.id, "issued_by": "installer"},
        )
        session.add(lease)
        session.commit()

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/device-trust/devices/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "internal"
    assert data["device"]["detail_level"] == "internal"
    assert data["diagnostics_timestamp"]
    assert data["endpoint_summary"]["detail_level"] == "internal"
    assert data["endpoint_summary"]["contract_summary"]["detail_level"] == "internal"
    assert data["endpoint_summary"]["contract_summary"]["issuer_state"]["detail_level"] == "internal"
    assert data["endpoint_summary"]["issuer_state"]["detail_level"] == "internal"
    assert data["endpoint_summary"]["support_notes"]["detail_level"] == "internal"
    assert data["endpoint_summary"]["support_notes"]["history_state"]["detail_level"] == "internal"
    assert data["reconciliation"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["status_counts"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["issuer_profiles"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["issuer_profiles"]["support_summary"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["material_readback_summary"]["detail_level"] == "internal"
    assert data["credentials"][0]["detail_level"] == "internal"
    assert data["credentials"][0]["verification"]["detail_level"] == "internal"
    assert data["leases"][0]["detail_level"] == "internal"
    assert data["leases"][0]["verification"]["detail_level"] == "internal"
    assert data["issuer_profiles"]["detail_level"] == "internal"
    assert data["issuer_profiles"]["active_profile"]["detail_level"] == "internal"
    assert data["signing_registry"]["detail_level"] == "internal"
    assert data["signing_registry"]["status_counts"]["detail_level"] == "internal"
    assert data["endpoint_summary"]["issuer_state"]["effective_key_id"] == "key-installer"
    assert data["credentials"][0]["fingerprint"] == "fp-installer"
    assert "stored_fingerprint" in data["credentials"][0]["verification"]
    assert "payload" in data["leases"][0]["verification"]
    assert "entries" in data["signing_registry"]
    assert "referenced_key_ids" in data["signing_registry"]


def _build_support_compact_summary_for_test(central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    device_trust = importlib.import_module("central_server.device_trust")
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status="active",
            credential_kind="mtls",
            fingerprint="fp-support-raw",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            details_json={"key_id": "key-support-raw", "csr_pem": "secret-csr"},
        )
        session.add(credential)
        session.flush()

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=None,
            lease_id="lease-support-raw",
            status="active",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            grace_until=now + timedelta(hours=24),
            signature="raw-visible-signature",
            details_json={"credential_id": credential.id, "issued_by": "installer"},
        )
        session.add(lease)
        session.flush()

        reconciliation = device_trust.reconcile_trust_material(
            device=device,
            credential=credential,
            lease=lease,
            credentials=[credential],
            leases=[lease],
        )
        issuer_profiles = device_trust.build_issuer_profile_diagnostics(
            credential=credential,
            lease=lease,
            device=device,
            credentials=[credential],
        )
        signing_registry = device_trust.build_signing_registry_diagnostics(
            credential=credential,
            lease=lease,
            device=device,
            credentials=[credential],
        )
        return device_trust.build_support_diagnostics_compact_summary(
            issuer_profiles=issuer_profiles,
            signing_registry=signing_registry,
            material_history=reconciliation.get("material_history"),
            credential=credential,
            lease=lease,
            now=now,
        )


def test_support_compact_summary_raw_blocks_self_identify_detail_level(central_app_env, seeded_central):
    summary = _build_support_compact_summary_for_test(central_app_env, seeded_central)

    assert summary["contract_summary"]["detail_level"] == "support_compact"
    assert summary["issuer_state"]["detail_level"] == "support_compact"
    assert summary["signing_state"]["detail_level"] == "support_compact"
    assert summary["signing_state"]["status_counts"]["detail_level"] == "support_compact"
    assert summary["material_timestamps"]["detail_level"] == "support_compact"
    assert summary["support_notes"]["detail_level"] == "support_compact"
    assert summary["history_state"]["detail_level"] == "support_compact"
    assert summary["material_history"]["detail_level"] == "support_compact"
    assert summary["material_history"]["summary"]["detail_level"] == "support_compact"
    assert summary["support_notes"]["material_summary"]["detail_level"] == "support_compact"
    assert summary["material_history"]["credential_history"]["detail_level"] == "support_compact"
    assert summary["material_history"]["lease_history"]["detail_level"] == "support_compact"
    assert summary["material_readback_summary"]["detail_level"] == "support_compact"
    assert summary["material_readback_summary"]["credential_history"]["detail_level"] == "support_compact"
    assert summary["material_readback_summary"]["lease_history"]["detail_level"] == "support_compact"
    assert summary["support_notes"]["source_contracts"]["issuer_profile_readback"]["detail_level"] == "support_compact"


def test_support_compact_summary_raw_contract_provenance_state_is_self_contained(central_app_env, seeded_central):
    summary = _build_support_compact_summary_for_test(central_app_env, seeded_central)

    provenance_state = summary["contract_summary"]["provenance_state"]
    assert provenance_state["detail_level"] == "support_compact"
    assert provenance_state["overall_state"] == "complete"
    assert provenance_state["coverage_state"] == "full"
    assert provenance_state["present_contract_count"] == 3
    assert provenance_state["derived_contract_count"] == 0
    assert provenance_state["missing_contract_count"] == 0
    assert provenance_state["missing_expected_count"] == 0
    assert provenance_state["observed_extra_count"] == 0
    assert provenance_state["has_missing_expected_contracts"] is False
    assert provenance_state["has_unexpected_contracts"] is False
    assert provenance_state["present_names"] == [
        "issuer_profile_readback",
        "issuer_history",
        "material_history_readback",
    ]
    assert provenance_state["derived_names"] == []
    assert provenance_state["missing_names"] == []
    assert provenance_state["missing_expected_names"] == []
    assert provenance_state["unexpected_names"] == []
    assert provenance_state["summary"]



def test_compact_reconciliation_summary_stamps_nested_dict_readback_summary_blocks_as_operator_safe(central_app_env):
    server = central_app_env["server"]

    payload = server._build_compact_reconciliation_readback_summary(
        {
            "reconciliation_summary": {
                "ok": True,
                "status_counts": {"active": 1},
                "timing": {"state": "active"},
                "support_summary": {"note": "ok"},
                "issuer_profiles": {
                    "effective_key_id": "kid-test",
                    "transition": {"transition_state": "aligned"},
                    "lineage_explanation": {"effective_key_id": "kid-test"},
                    "readback_summary": {"lineage_state": "standalone"},
                    "history_summary": {"history_state": "single"},
                },
                "material_readback_summary": {
                    "summary": {"state": "aligned"},
                    "credential_history": {"alignment_state": "aligned"},
                    "lease_history": {"alignment_state": "aligned"},
                },
            },
            "reconciliation": {"bundle_source": "stored"},
        }
    )

    assert payload["detail_level"] == "operator_safe"
    assert payload["bundle_source"] == "stored"
    assert payload["status_counts"]["detail_level"] == "operator_safe"
    assert payload["material_readback_summary"]["detail_level"] == "operator_safe"
    assert payload["material_readback_summary"]["summary"]["detail_level"] == "operator_safe"
    assert payload["material_readback_summary"]["credential_history"]["detail_level"] == "operator_safe"
    assert payload["material_readback_summary"]["lease_history"]["detail_level"] == "operator_safe"



def test_compact_reconciliation_summary_keeps_bundle_source_from_precomputed_summary_without_full_reconciliation(central_app_env):
    server = central_app_env["server"]

    payload = server._build_compact_reconciliation_readback_summary(
        {
            "reconciliation_summary": {
                "ok": True,
                "bundle_source": "rebuilt",
                "status_counts": {"active": 1},
                "timing": {"state": "active"},
                "support_summary": {},
                "issuer_profiles": {},
                "material_readback_summary": {},
            },
        }
    )

    assert payload["bundle_source"] == "rebuilt"



def test_build_reconciliation_summary_includes_bundle_source_when_present(central_app_env):
    device_trust = importlib.import_module("central_server.device_trust")

    summary = device_trust.build_reconciliation_summary(
        reconciliation={
            "ok": True,
            "bundle_source": "stored",
            "issuer_profiles": {},
            "signing_registry": {},
            "material_history": {},
        }
    )

    assert summary["bundle_source"] == "stored"



def test_operator_safe_issuer_profiles_stamp_profile_blocks_with_detail_level(central_app_env):
    server = central_app_env["server"]

    payload = server._to_operator_safe_issuer_profiles(
        {
            "active_profile": {"key_id": "kid-active", "issuer": "active"},
            "configured_profile": {"key_id": "kid-configured", "issuer": "configured"},
            "effective_profile": {"key_id": "kid-effective", "issuer": "effective"},
            "support_summary": {"effective_source": "credential"},
            "readback_summary": {"lineage_state": "standalone"},
            "history_summary": {"history_state": "single"},
        }
    )

    assert payload["active_profile"]["detail_level"] == "operator_safe"
    assert payload["configured_profile"]["detail_level"] == "operator_safe"
    assert payload["effective_profile"]["detail_level"] == "operator_safe"
    assert payload["active_profile"]["key_id"] == "kid-active"
    assert payload["configured_profile"]["issuer"] == "configured"
    assert payload["effective_profile"]["issuer"] == "effective"



def test_support_contract_state_summary_exposes_stable_count_and_flag_fields(central_app_env):
    device_trust = importlib.import_module("central_server.device_trust")

    summary = device_trust.build_support_contract_state_summary(
        source_contracts={
            "issuer_profile_readback": {"present": True, "source_state": "present"},
            "issuer_history": {"present": False, "source_state": "missing"},
            "material_history_readback": {"present": True, "source_state": "derived_from_material_history"},
        }
    )

    assert summary["detail_level"] == "support_compact"
    assert summary["state_counts"]["detail_level"] == "support_compact"
    assert summary["source_states"]["detail_level"] == "support_compact"
    assert summary["total_contracts"] == 3
    assert summary["present_contract_count"] == 1
    assert summary["derived_contract_count"] == 1
    assert summary["missing_contract_count"] == 1
    assert summary["has_present_contracts"] is True
    assert summary["has_derived_contracts"] is True
    assert summary["has_missing_contracts"] is True



def test_compact_reconciliation_summary_stamps_source_contract_rollup_nested_maps_as_operator_safe(central_app_env):
    server = central_app_env["server"]

    payload = server._build_compact_reconciliation_readback_summary(
        {
            "reconciliation_summary": {
                "ok": True,
                "status_counts": {"active": 1},
                "timing": {"state": "active"},
                "support_summary": {"note": "ok"},
                "issuer_profiles": {
                    "source_contract_summary": {
                        "overall_state": "partial",
                        "state_counts": {"present": 1, "missing": 1, "derived_from_material_history": 1},
                        "source_states": {
                            "issuer_profile_readback": "present",
                            "issuer_history": "missing",
                            "material_history_readback": "derived_from_material_history",
                        },
                    },
                },
                "material_readback_summary": {},
            },
        }
    )

    source_contract_summary = payload["issuer_profiles"]["source_contract_summary"]
    assert source_contract_summary["detail_level"] == "operator_safe"
    assert source_contract_summary["state_counts"]["detail_level"] == "operator_safe"
    assert source_contract_summary["state_counts"]["present"] == 1
    assert source_contract_summary["source_states"]["detail_level"] == "operator_safe"
    assert source_contract_summary["source_states"]["issuer_profile_readback"] == "present"



def test_finalize_endpoint_summary_stamps_nested_signing_status_counts(central_app_env):
    server = central_app_env["server"]

    operator_safe = server._finalize_endpoint_summary(
        {
            "contract_summary": {
                "signing_state": {
                    "registry_size": 2,
                    "status_counts": {"active": 1, "retired": 1},
                },
            },
        },
        detail_level="operator_safe",
    )
    internal = server._finalize_endpoint_summary(
        {
            "contract_summary": {
                "signing_state": {
                    "registry_size": 2,
                    "status_counts": {"active": 1, "retired": 1},
                },
            },
        },
        detail_level="internal",
    )

    assert operator_safe["contract_summary"]["signing_state"]["detail_level"] == "operator_safe"
    assert operator_safe["contract_summary"]["signing_state"]["status_counts"]["detail_level"] == "operator_safe"
    assert operator_safe["contract_summary"]["signing_state"]["status_counts"]["active"] == 1
    assert internal["contract_summary"]["signing_state"]["detail_level"] == "internal"
    assert internal["contract_summary"]["signing_state"]["status_counts"]["detail_level"] == "internal"
    assert internal["contract_summary"]["signing_state"]["status_counts"]["retired"] == 1


def test_finalize_endpoint_summary_stamps_contract_provenance_state_for_operator_safe_and_internal(central_app_env):
    server = central_app_env["server"]
    payload = {
        "contract_summary": {
            "provenance_state": {
                "overall_state": "partial",
                "coverage_state": "partial",
                "present_contract_count": 2,
                "derived_contract_count": 1,
                "missing_contract_count": 0,
                "missing_expected_count": 1,
                "observed_extra_count": 1,
                "has_missing_expected_contracts": True,
                "has_unexpected_contracts": True,
                "present_names": ["issuer_profile_readback", "issuer_history"],
                "derived_names": ["material_history_readback"],
                "missing_names": [],
                "missing_expected_names": ["material_history_readback"],
                "unexpected_names": ["legacy_extra_contract"],
                "summary": "partial coverage with one extra contract",
            },
        },
    }

    operator_safe = server._finalize_endpoint_summary(payload, detail_level="operator_safe")
    internal = server._finalize_endpoint_summary(payload, detail_level="internal")

    assert operator_safe["contract_summary"]["provenance_state"]["detail_level"] == "operator_safe"
    assert operator_safe["contract_summary"]["provenance_state"]["present_names"] == [
        "issuer_profile_readback",
        "issuer_history",
    ]
    assert operator_safe["contract_summary"]["provenance_state"]["derived_names"] == ["material_history_readback"]
    assert operator_safe["contract_summary"]["provenance_state"]["missing_expected_names"] == ["material_history_readback"]
    assert operator_safe["contract_summary"]["provenance_state"]["unexpected_names"] == ["legacy_extra_contract"]
    assert internal["contract_summary"]["provenance_state"]["detail_level"] == "internal"
    assert internal["contract_summary"]["provenance_state"]["summary"] == "partial coverage with one extra contract"



def test_owner_support_diagnostics_is_operator_safe(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status="active",
            credential_kind="mtls",
            fingerprint="fp-support-owner",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            details_json={"key_id": "key-support-owner", "csr_pem": "secret-csr"},
        )
        session.add(credential)
        session.flush()

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=None,
            lease_id="lease-support-owner",
            status="active",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            grace_until=now + timedelta(hours=24),
            signature="owner-hidden-signature",
            details_json={"credential_id": credential.id, "issued_by": "installer", "capability_overrides": {"remote_restart": True}},
        )
        session.add(lease)
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/device-trust/devices/{seeded_central['device_id']}/support-diagnostics",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "operator_safe"
    assert data["device"]["detail_level"] == "operator_safe"
    assert data["mode"] == "support_diagnostics_read_only"
    assert data["enforcement"] == "disabled"
    assert data["credential"]["key_id"] == "key-support-owner"
    assert "fingerprint" not in data["credential"]
    assert "metadata" not in data["credential"]
    assert "stored_fingerprint" not in data["credential"]["verification"]
    assert "payload" not in data["credential"]["verification"]
    assert data["lease"]["lease_id"] == "lease-support-owner"
    assert "signature" not in data["lease"]
    assert "metadata" not in data["lease"]
    assert "signed_bundle" not in data["lease"]
    assert "payload" not in data["lease"]["verification"]
    assert "expected_fingerprint" not in data["lease"]["verification"]
    assert data["credential"]["detail_level"] == "operator_safe"
    assert data["lease"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["contract_summary"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["signing_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["history_state"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["source_contract_summary"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["source_contract_summary"]["state_counts"]["detail_level"] == "operator_safe"
    assert data["endpoint_summary"]["support_notes"]["source_contract_summary"]["source_states"]["detail_level"] == "operator_safe"
    assert set(data["reconciliation_summary"].keys()) == {"ok", "status_counts", "bundle_source", "timing", "support_summary", "issuer_profiles", "material_readback_summary", "detail_level"}
    assert data["reconciliation_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["status_counts"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["timing"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["support_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["transition"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["lineage_explanation"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["readback_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["issuer_profiles"]["history_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["material_readback_summary"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["material_readback_summary"]["credential_history"]["detail_level"] == "operator_safe"
    assert data["reconciliation_summary"]["material_readback_summary"]["lease_history"]["detail_level"] == "operator_safe"


def test_owner_support_diagnostics_finalizes_history_and_material_blocks_as_operator_safe(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status="active",
            credential_kind="mtls",
            fingerprint="fp-support-summary-owner",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            details_json={"key_id": "key-support-summary-owner", "csr_pem": "secret-csr"},
        )
        session.add(credential)
        session.flush()

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=None,
            lease_id="lease-support-summary-owner",
            status="active",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            grace_until=now + timedelta(hours=24),
            signature="owner-summary-hidden-signature",
            details_json={"credential_id": credential.id, "issued_by": "installer"},
        )
        session.add(lease)
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/device-trust/devices/{seeded_central['device_id']}/support-diagnostics",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    summary = response.json()["endpoint_summary"]
    assert summary["history_state"]["detail_level"] == "operator_safe"
    assert summary["support_notes"]["material_summary"]["detail_level"] == "operator_safe"
    assert summary["material_history"]["detail_level"] == "operator_safe"
    assert summary["material_history"]["summary"]["detail_level"] == "operator_safe"
    assert summary["material_history"]["credential_history"]["detail_level"] == "operator_safe"
    assert summary["material_history"]["lease_history"]["detail_level"] == "operator_safe"
    assert summary["material_readback_summary"]["detail_level"] == "operator_safe"
    assert summary["material_readback_summary"]["credential_history"]["detail_level"] == "operator_safe"
    assert summary["material_readback_summary"]["lease_history"]["detail_level"] == "operator_safe"



def test_installer_support_diagnostics_keeps_internal_fields(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status="active",
            credential_kind="mtls",
            fingerprint="fp-support-installer",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            details_json={"key_id": "key-support-installer", "csr_pem": "secret-csr"},
        )
        session.add(credential)
        session.flush()

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=None,
            lease_id="lease-support-installer",
            status="active",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            grace_until=now + timedelta(hours=24),
            signature="installer-visible-signature",
            details_json={"credential_id": credential.id, "issued_by": "installer", "capability_overrides": {"remote_restart": True}},
        )
        session.add(lease)
        session.commit()

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/device-trust/devices/{seeded_central['device_id']}/support-diagnostics",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "internal"
    assert data["device"]["detail_level"] == "internal"
    assert data["credential"]["detail_level"] == "internal"
    assert data["credential"]["verification"]["detail_level"] == "internal"
    assert data["lease"]["detail_level"] == "internal"
    assert data["lease"]["verification"]["detail_level"] == "internal"
    assert data["reconciliation"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["issuer_profiles"]["detail_level"] == "internal"
    assert data["reconciliation_summary"]["material_readback_summary"]["detail_level"] == "internal"
    assert data["issuer_profiles"]["detail_level"] == "internal"
    assert data["signing_registry"]["detail_level"] == "internal"
    assert data["credential"]["fingerprint"] == "fp-support-installer"
    assert "stored_fingerprint" in data["credential"]["verification"]
    assert data["lease"]["signature"] == "installer-visible-signature"
    assert "payload" in data["lease"]["verification"]


def test_owner_device_detail_is_operator_safe(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        device.health_snapshot = '{"cpu": 77}'
        device.device_logs = '[{"level":"error","message":"secret stack"}]'
        device.lease_metadata = '{"signed_bundle":{"signature":"super-secret"}}'
        session.add(
            models.TelemetryEvent(
                event_id="evt-owner-safe-1",
                device_id=device.id,
                event_type="error",
                timestamp=now,
                data={"stack": "super-secret-trace"},
            )
        )
        session.add(
            models.RemoteAction(
                device_id=device.id,
                action_type="restart_app",
                status="acked",
                issued_by="superadmin",
                issued_at=now,
                acked_at=now,
                result_message="ok",
                params='{"secret":"token"}',
            )
        )
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/telemetry/device/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "operator_safe"
    assert "health_snapshot" not in data
    assert "device_logs" not in data
    assert "lease_metadata" not in data
    assert data["recent_events"][0]["event_type"] == "error"
    assert data["recent_events"][0]["has_data"] is True
    assert "data" not in data["recent_events"][0]
    assert data["recent_actions"][0]["action_type"] == "restart_app"
    assert data["recent_actions"][0]["has_params"] is True
    assert data["recent_actions"][0]["has_result_message"] is True
    assert "params" not in data["recent_actions"][0]
    assert "result_message" not in data["recent_actions"][0]


def test_owner_device_detail_redacts_recent_trust_material_summaries(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        session.add(
            models.DeviceCredential(
                device_id=device.id,
                status="active",
                credential_kind="mtls",
                fingerprint="fp-owner-hidden",
                issued_at=now,
                expires_at=now + timedelta(days=30),
            )
        )
        session.add(
            models.DeviceLease(
                device_id=device.id,
                central_license_id=None,
                lease_id="lease-owner-hidden",
                status="active",
                issued_at=now,
                expires_at=now + timedelta(hours=12),
                grace_until=now + timedelta(hours=24),
            )
        )
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/telemetry/device/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "operator_safe"
    assert data["recent_credentials"][0]["detail_level"] == "operator_safe"
    assert "fingerprint" not in data["recent_credentials"][0]
    assert data["recent_leases"][0]["detail_level"] == "operator_safe"
    assert "lease_id" not in data["recent_leases"][0]


def test_installer_device_detail_keeps_internal_fields(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        device.health_snapshot = '{"cpu": 42}'
        device.device_logs = '[{"level":"info","message":"boot ok"}]'
        device.lease_metadata = '{"signed_bundle":{"signature":"visible-to-installer"}}'
        session.add(
            models.TelemetryEvent(
                event_id="evt-installer-detail-1",
                device_id=device.id,
                event_type="session_started",
                timestamp=now,
                data={"credits": 3},
            )
        )
        session.add(
            models.RemoteAction(
                device_id=device.id,
                action_type="force_sync",
                status="pending",
                issued_by="superadmin",
                issued_at=now,
                result_message=None,
                params='{"force":true}',
            )
        )
        session.commit()

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/telemetry/device/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "internal"
    assert data["health_snapshot"] == {"cpu": 42}
    assert data["device_logs"][0]["message"] == "boot ok"
    assert data["lease_metadata"]["signed_bundle"]["signature"] == "visible-to-installer"
    assert data["recent_events"][0]["data"] == {"credits": 3}
    assert data["recent_actions"][0]["params"] == '{"force":true}'


def test_installer_device_detail_keeps_recent_trust_material_summaries(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        session.add(
            models.DeviceCredential(
                device_id=device.id,
                status="active",
                credential_kind="mtls",
                fingerprint="fp-installer-visible",
                issued_at=now,
                expires_at=now + timedelta(days=30),
            )
        )
        session.add(
            models.DeviceLease(
                device_id=device.id,
                central_license_id=None,
                lease_id="lease-installer-visible",
                status="active",
                issued_at=now,
                expires_at=now + timedelta(hours=12),
                grace_until=now + timedelta(hours=24),
            )
        )
        session.commit()

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/telemetry/device/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "internal"
    assert data["recent_credentials"][0]["fingerprint"] == "fp-installer-visible"
    assert data["recent_leases"][0]["lease_id"] == "lease-installer-visible"


def test_owner_cannot_issue_remote_action_outside_scope(client, seeded_central):
    owner_token = _login(client, "owner", "owner-pass")
    response = client.post(
        f"/api/remote-actions/{seeded_central['outsider_device_id']}",
        json={"action_type": "force_sync"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 403


def test_owner_remote_action_list_is_operator_safe_and_scoped(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        session.add(
            models.RemoteAction(
                device_id=seeded_central["device_id"],
                action_type="force_sync",
                status="acked",
                issued_by="superadmin",
                issued_at=now,
                acked_at=now,
                result_message="done",
                params='{"secret":"token"}',
            )
        )
        session.add(
            models.RemoteAction(
                device_id=seeded_central["outsider_device_id"],
                action_type="restart_backend",
                status="pending",
                issued_by="superadmin",
                issued_at=now,
                params='{"secret":"other"}',
            )
        )
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/remote-actions/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["action_type"] == "force_sync"
    assert data[0]["detail_level"] == "operator_safe"
    assert data[0]["has_params"] is True
    assert data[0]["has_result_message"] is True
    assert "params" not in data[0]
    assert "issued_by" not in data[0]
    assert "result_message" not in data[0]

    forbidden = client.get(
        f"/api/remote-actions/{seeded_central['outsider_device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert forbidden.status_code == 403



def test_installer_remote_action_list_keeps_internal_fields(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        session.add(
            models.RemoteAction(
                device_id=seeded_central["device_id"],
                action_type="force_sync",
                status="acked",
                issued_by="superadmin",
                issued_at=now,
                acked_at=now,
                result_message="done",
                params='{"force":true}',
            )
        )
        session.commit()

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/remote-actions/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["detail_level"] == "internal"
    assert data[0]["issued_by"] == "superadmin"
    assert data[0]["params"] == '{"force":true}'


def test_device_websocket_accepts_x_license_key_header(client, seeded_central):
    with client.websocket_connect(
        "/ws/devices",
        headers={"X-License-Key": "device-api-key"},
    ) as ws:
        message = ws.receive_json()
        assert message["event"] == "connected"
        assert message["device_id"] == seeded_central["device_id"]


def test_device_websocket_accepts_authorization_bearer_header(client, seeded_central):
    with client.websocket_connect(
        "/ws/devices",
        headers={"Authorization": "Bearer device-api-key"},
    ) as ws:
        message = ws.receive_json()
        assert message["event"] == "connected"
        assert message["device_id"] == seeded_central["device_id"]


def test_device_websocket_requires_authentication(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/devices"):
            pass


def test_device_websocket_query_transport_is_still_backward_compatible(client, seeded_central):
    with client.websocket_connect("/ws/devices?key=device-api-key") as ws:
        message = ws.receive_json()
        assert message["event"] == "connected"
        assert message["device_id"] == seeded_central["device_id"]


def test_device_websocket_query_transport_is_denied_in_production_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-ws-prod"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_ENV", "production")

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
    ]:
        sys.modules.pop(name, None)

    server = importlib.import_module("central_server.server")
    models = importlib.import_module("central_server.models")
    database = importlib.import_module("central_server.database")

    with TestClient(server.app) as prod_client:
        with Session(database.sync_engine) as session:
            customer = models.CentralCustomer(name="Prod Customer")
            session.add(customer)
            session.flush()
            location = models.CentralLocation(customer_id=customer.id, name="Prod Hall")
            session.add(location)
            session.flush()
            device = models.CentralDevice(
                location_id=location.id,
                device_name="Prod Board",
                api_key="prod-device-api-key",
                install_id="prod-install-1",
                status="active",
                binding_status="bound",
            )
            session.add(device)
            session.commit()
            device_id = device.id

        with pytest.raises(WebSocketDisconnect):
            with prod_client.websocket_connect("/ws/devices?key=prod-device-api-key"):
                pass

            with prod_client.websocket_connect(
                "/ws/devices",
                headers={"X-License-Key": "prod-device-api-key"},
            ) as ws:
                message = ws.receive_json()
                assert message["event"] == "connected"
                assert message["device_id"] == device_id


def test_device_websocket_query_transport_can_be_explicitly_allowed_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-ws-prod-optin"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_ENV", "production")
    monkeypatch.setenv("CENTRAL_WS_QUERY_AUTH_MODE", "allow")

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
    ]:
        sys.modules.pop(name, None)

    server = importlib.import_module("central_server.server")
    models = importlib.import_module("central_server.models")
    database = importlib.import_module("central_server.database")

    with TestClient(server.app) as prod_client:
        with Session(database.sync_engine) as session:
            customer = models.CentralCustomer(name="Prod Opt-In Customer")
            session.add(customer)
            session.flush()
            location = models.CentralLocation(customer_id=customer.id, name="Prod Opt-In Hall")
            session.add(location)
            session.flush()
            device = models.CentralDevice(
                location_id=location.id,
                device_name="Prod Opt-In Board",
                api_key="prod-optin-api-key",
                install_id="prod-install-2",
                status="active",
                binding_status="bound",
            )
            session.add(device)
            session.commit()
            device_id = device.id

        with prod_client.websocket_connect("/ws/devices?key=prod-optin-api-key") as ws:
            message = ws.receive_json()
            assert message["event"] == "connected"
            assert message["device_id"] == device_id


def test_device_trust_enrollment_records_pending_credential(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine

    with Session(sync_engine) as session:
        token = models.RegistrationToken(
            token_hash=central_app_env["server"]._hash_token("enroll-token"),
            token_preview="enroll...oken",
            customer_id=seeded_central["customer_id"],
            location_id=seeded_central["location_id"],
            expires_at=central_app_env["server"]._utcnow() + central_app_env["server"].timedelta(hours=24),
            created_by="test",
        )
        session.add(token)
        session.commit()

    response = client.post(
        "/api/device-trust/enroll",
        json={
            "token": "enroll-token",
            "install_id": "install-enroll-1",
            "device_name": "Trust Board",
            "csr_pem": "-----BEGIN CERTIFICATE REQUEST-----\nMIIB\n-----END CERTIFICATE REQUEST-----",
            "credential_fingerprint": "fp-123",
            "hardware": {"machine": "test-box"},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mode"] == "scaffold_only"
    assert data["device"]["trust_status"] == "pending_enrollment"
    assert data["device"]["credential_status"] == "pending"
    assert data["credential"]["fingerprint"] == "fp-123"

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, data["device"]["id"])
        assert device is not None
        assert device.trust_status == models.DeviceTrustStatus.PENDING_ENROLLMENT.value
        credential = session.query(models.DeviceCredential).filter_by(device_id=device.id).one()
        assert credential.status == models.DeviceCredentialStatus.PENDING.value
        assert credential.fingerprint == "fp-123"


def test_device_trust_placeholder_lease_can_be_issued_and_read_by_device(client, central_app_env, seeded_central):
    token = _login(client, "superadmin", "bootstrap-pass")

    credential_response = client.post(
        f"/api/device-trust/devices/{seeded_central['device_id']}/issue-credential",
        json={"validity_days": 14},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert credential_response.status_code == 409

    issue_response = client.post(
        f"/api/device-trust/devices/{seeded_central['device_id']}/issue-lease",
        json={"duration_hours": 12, "grace_hours": 6, "reason": "test issuance"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert issue_response.status_code == 200, issue_response.text
    issued = issue_response.json()
    assert issued["mode"] == "scaffold_only"
    assert issued["lease"]["status"] == "active"
    assert issued["lease"]["computed_status"] == "active"
    assert issued["device"]["lease_status"] == "active"
    assert issued["device"]["trust_status"] == "pending_enrollment"

    signed_bundle = issued["lease"]["signed_bundle"]
    assert signed_bundle["signature_scheme"] == "hmac-sha256-placeholder"
    assert signed_bundle["key_id"].startswith("central-placeholder-")
    assert signed_bundle["payload"]["schema"] == "darts.device_lease.v1"
    assert signed_bundle["payload"]["device_id"] == seeded_central["device_id"]
    assert signed_bundle["payload"]["capabilities"] == {}
    assert signed_bundle["signature"]

    current_response = client.get(
        "/api/device-trust/lease/current",
        headers={"X-License-Key": "device-api-key"},
    )
    assert current_response.status_code == 200, current_response.text
    current = current_response.json()
    assert current["device_id"] == seeded_central["device_id"]
    assert current["detail_level"] == "device_safe"
    assert current["lease_status"] == "active"
    assert current["lease"]["status"] == "active"
    assert current["lease"]["verification"]["valid"] is True
    assert current["lease"]["signed_bundle_source"] in {"stored", "rebuilt"}
    assert current["credential"] is None or current["credential"]["detail_level"] == "operator_safe"
    assert current["lease"]["detail_level"] == "operator_safe"
    assert "signed_bundle" not in current["lease"]
    assert "signature" not in current["lease"]
    assert "metadata" not in current["lease"]
    assert current["enforcement"] == "disabled"
    assert current["reconciliation_summary"]["detail_level"] == "operator_safe"
    assert "entries" not in current["signing_registry"]
    assert "referenced_key_ids" not in current["signing_registry"]


def test_device_trust_current_lease_reports_verification_state(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine

    with Session(sync_engine) as session:
        token = models.RegistrationToken(
            token_hash=central_app_env["server"]._hash_token("verify-current-token"),
            token_preview="verif...oken",
            customer_id=seeded_central["customer_id"],
            location_id=seeded_central["location_id"],
            expires_at=central_app_env["server"]._utcnow() + central_app_env["server"].timedelta(hours=24),
            created_by="test",
        )
        session.add(token)
        session.commit()

    enroll_response = client.post(
        "/api/device-trust/enroll",
        json={
            "token": "verify-current-token",
            "install_id": "install-verify-current-1",
            "device_name": "Verify Current Board",
            "public_key_pem": "-----BEGIN PUBLIC KEY-----\nABCDEF123456\n-----END PUBLIC KEY-----",
        },
    )
    assert enroll_response.status_code == 200, enroll_response.text
    device_id = enroll_response.json()["device"]["id"]

    token = _login(client, "superadmin", "bootstrap-pass")
    credential_response = client.post(
        f"/api/device-trust/devices/{device_id}/issue-credential",
        json={"validity_days": 14},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert credential_response.status_code == 200, credential_response.text
    issued_credential = credential_response.json()["credential"]
    assert issued_credential["verification"]["valid"] is True

    lease_response = client.post(
        f"/api/device-trust/devices/{device_id}/issue-lease",
        json={"duration_hours": 12, "grace_hours": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lease_response.status_code == 200, lease_response.text
    issued_lease = lease_response.json()["lease"]
    assert issued_lease["verification"]["valid"] is True

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, device_id)
        assert device is not None
        api_key = device.api_key

    current_response = client.get(
        "/api/device-trust/lease/current",
        headers={"X-License-Key": api_key},
    )
    assert current_response.status_code == 200, current_response.text
    payload = current_response.json()
    assert payload["diagnostics_timestamp"]
    assert payload["detail_level"] == "device_safe"
    assert payload["endpoint_summary"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["contract_summary"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["contract_summary"]["signing_state"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["issuer_state"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["material_timestamps"]["detail_level"] == "operator_safe"
    assert payload["credential"]["id"] == issued_credential["id"]
    assert payload["credential"]["verification"]["valid"] is True
    assert "payload" not in payload["credential"]["verification"]
    assert "stored_fingerprint" not in payload["credential"]["verification"]
    assert payload["lease"]["id"] == issued_lease["id"]
    assert payload["lease"]["verification"]["valid"] is True
    assert payload["lease"]["verification"]["timing_status"] == "active"
    assert payload["credential"]["detail_level"] == "operator_safe"
    assert payload["lease"]["detail_level"] == "operator_safe"
    assert "payload" not in payload["lease"]["verification"]
    assert "expected_fingerprint" not in payload["lease"]["verification"]
    assert set(payload["reconciliation_summary"].keys()) == {"ok", "status_counts", "bundle_source", "timing", "support_summary", "issuer_profiles", "material_readback_summary", "detail_level"}
    assert payload["reconciliation_summary"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["status_counts"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["timing"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["support_summary"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["issuer_profiles"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["issuer_profiles"]["transition"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["issuer_profiles"]["lineage_explanation"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["issuer_profiles"]["readback_summary"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["issuer_profiles"]["history_summary"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["material_readback_summary"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["material_readback_summary"]["credential_history"]["detail_level"] == "operator_safe"
    assert payload["reconciliation_summary"]["material_readback_summary"]["lease_history"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["support_notes"]["material_summary"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["material_history"]["summary"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["material_history"]["credential_history"]["detail_level"] == "operator_safe"
    assert payload["endpoint_summary"]["material_history"]["lease_history"]["detail_level"] == "operator_safe"
    assert "entries" not in payload["signing_registry"]
    assert "referenced_key_ids" not in payload["signing_registry"]
    assert payload["endpoint_summary"]["issuer_state"]["effective_key_id"] == issued_credential["key_id"]
    assert payload["endpoint_summary"]["material_timestamps"]["lease_expires_at"].startswith(payload["lease"]["expires_at"])


def test_device_trust_current_lease_uses_lease_bound_credential_for_diagnostics(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    device_trust = importlib.import_module("central_server.device_trust")
    now = central_app_env["server"]._utcnow()

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])

        old_credential = models.DeviceCredential(
            device_id=device.id,
            status=models.DeviceCredentialStatus.ACTIVE.value,
            credential_kind="placeholder",
            fingerprint="a" * 64,
            public_key_pem="-----BEGIN PUBLIC KEY-----\nOLDKEY123\n-----END PUBLIC KEY-----",
            issued_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=7),
            details_json={"key_id": device_trust.derive_key_id(fingerprint="a" * 64)},
        )
        session.add(old_credential)
        session.flush()
        device_trust.issue_placeholder_credential(
            credential=old_credential,
            device=device,
            issued_by="test",
            validity_days=7,
            now=now - timedelta(days=2),
        )

        new_credential = models.DeviceCredential(
            device_id=device.id,
            status=models.DeviceCredentialStatus.ACTIVE.value,
            credential_kind="placeholder",
            fingerprint="b" * 64,
            public_key_pem="-----BEGIN PUBLIC KEY-----\nNEWKEY456\n-----END PUBLIC KEY-----",
            issued_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=30),
            replacement_for_credential_id=old_credential.id,
            details_json={"key_id": device_trust.derive_key_id(fingerprint="b" * 64)},
        )
        session.add(new_credential)
        session.flush()
        device_trust.issue_placeholder_credential(
            credential=new_credential,
            device=device,
            issued_by="test",
            validity_days=30,
            now=now - timedelta(hours=1),
        )

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=device.license_id,
            lease_id="lease-bound-old-credential",
            status=models.DeviceLeaseStatus.ACTIVE.value,
            issued_at=now - timedelta(minutes=30),
            expires_at=now + timedelta(hours=6),
            grace_until=now + timedelta(hours=12),
            details_json={
                "mode": "placeholder",
                "issued_by": "test",
                "credential_id": old_credential.id,
            },
        )
        session.add(lease)
        session.flush()
        device_trust.attach_lease_key_metadata(lease=lease, credential=old_credential)
        old_credential_id = old_credential.id
        old_credential_key_id = old_credential.details_json["key_id"]
        session.commit()

    current_response = client.get(
        "/api/device-trust/lease/current",
        headers={"X-License-Key": "device-api-key"},
    )
    assert current_response.status_code == 200, current_response.text
    payload = current_response.json()
    assert payload["credential"]["id"] == old_credential_id
    assert payload["credential"]["key_id"] == old_credential_key_id
    assert payload["endpoint_summary"]["issuer_state"]["effective_key_id"] == old_credential_key_id
    assert payload["reconciliation_summary"]["issuer_profiles"]["effective_key_id"] == old_credential_key_id
    assert payload["lease"]["verification"]["valid"] is True


def test_device_trust_current_lease_reports_grace_after_expiry(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = central_app_env["server"]._utcnow()

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=device.license_id,
            lease_id="lease-grace-test",
            status=models.DeviceLeaseStatus.ACTIVE.value,
            issued_at=now - central_app_env["server"].timedelta(hours=2),
            expires_at=now - central_app_env["server"].timedelta(minutes=10),
            grace_until=now + central_app_env["server"].timedelta(hours=2),
            details_json={"mode": "placeholder", "issued_by": "test"},
        )
        session.add(lease)
        session.commit()

    response = client.get(
        "/api/device-trust/lease/current",
        headers={"X-License-Key": "device-api-key"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["lease_status"] == "grace"
    assert payload["trust_status"] == "degraded"
    assert payload["lease"]["computed_status"] == "grace"


def test_device_trust_credential_issuance_normalizes_material_and_sets_key_id(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine

    with Session(sync_engine) as session:
        token = models.RegistrationToken(
            token_hash=central_app_env["server"]._hash_token("issue-cred-token"),
            token_preview="issue...oken",
            customer_id=seeded_central["customer_id"],
            location_id=seeded_central["location_id"],
            expires_at=central_app_env["server"]._utcnow() + central_app_env["server"].timedelta(hours=24),
            created_by="test",
        )
        session.add(token)
        session.commit()

    enroll_response = client.post(
        "/api/device-trust/enroll",
        json={
            "token": "issue-cred-token",
            "install_id": "install-cred-1",
            "device_name": "Cred Board",
            "public_key_pem": "\n-----BEGIN PUBLIC KEY-----\nABCDEF123456\n\n-----END PUBLIC KEY-----\n",
            "hardware": {"machine": "cred-box"},
        },
    )
    assert enroll_response.status_code == 200, enroll_response.text
    device_id = enroll_response.json()["device"]["id"]

    token = _login(client, "superadmin", "bootstrap-pass")
    issue_response = client.post(
        f"/api/device-trust/devices/{device_id}/issue-credential",
        json={"validity_days": 45},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert issue_response.status_code == 200, issue_response.text
    issued = issue_response.json()
    assert issued["credential"]["status"] == "active"
    assert issued["credential"]["key_id"].startswith("kid_")
    assert issued["credential"]["metadata"]["key_id"].startswith("kid_")
    assert issued["credential"]["verification"]["valid"] is True
    assert issued["device"]["credential_status"] == "active"

    with Session(sync_engine) as session:
        credential = session.query(models.DeviceCredential).filter_by(device_id=device_id).order_by(models.DeviceCredential.created_at.desc()).first()
        assert credential is not None
        assert credential.status == models.DeviceCredentialStatus.ACTIVE.value
        assert credential.public_key_pem == "-----BEGIN PUBLIC KEY-----\nABCDEF123456\n-----END PUBLIC KEY-----"
        assert credential.certificate_pem.startswith("-----BEGIN DARTS DEVICE CREDENTIAL-----")
        assert credential.details_json["key_id"].startswith("kid_")


def test_device_trust_verification_detects_key_id_fingerprint_mismatch(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    device_trust = importlib.import_module("central_server.device_trust")
    now = central_app_env["server"]._utcnow()

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        credential = models.DeviceCredential(
            device_id=device.id,
            status=models.DeviceCredentialStatus.ACTIVE.value,
            credential_kind="placeholder",
            fingerprint="a" * 64,
            public_key_pem="-----BEGIN PUBLIC KEY-----\nABCDEF123456\n-----END PUBLIC KEY-----",
            issued_at=now,
            expires_at=now + timedelta(days=5),
            details_json={"key_id": device_trust.derive_key_id(fingerprint="a" * 64)},
        )
        session.add(credential)
        session.flush()
        device_trust.issue_placeholder_credential(
            credential=credential,
            device=device,
            issued_by="test",
            validity_days=5,
            now=now,
        )

        lease = models.DeviceLease(
            device_id=device.id,
            central_license_id=device.license_id,
            lease_id="lease-verify-mismatch",
            status=models.DeviceLeaseStatus.ACTIVE.value,
            issued_at=now,
            expires_at=now + timedelta(hours=3),
            grace_until=now + timedelta(hours=5),
            details_json={
                "mode": "placeholder",
                "issued_by": "test",
            },
        )
        session.add(lease)
        session.flush()
        bundle = device_trust.build_placeholder_signed_lease(device=device, lease=lease)
        bundle["payload"]["credential"]["key_id"] = "kid_deadbeefdeadbeef"
        bundle["payload"]["credential"]["fingerprint"] = "b" * 64
        bundle["signature"] = device_trust.sign_payload(bundle["payload"])

        verification = device_trust.verify_placeholder_signed_lease(
            bundle=bundle,
            device=device,
            lease=lease,
            credential=credential,
            now=now,
        )
        session.commit()

    assert verification["valid"] is False
    assert "lease credential key_id mismatch" in verification["errors"]
    assert "lease credential fingerprint mismatch" in verification["errors"]
    assert "lease credential key_id inconsistent with fingerprint" in verification["errors"]


def test_device_trust_revoke_paths_drive_revoked_state_and_lease_key_metadata(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine

    with Session(sync_engine) as session:
        token = models.RegistrationToken(
            token_hash=central_app_env["server"]._hash_token("revoke-token"),
            token_preview="revok...oken",
            customer_id=seeded_central["customer_id"],
            location_id=seeded_central["location_id"],
            expires_at=central_app_env["server"]._utcnow() + central_app_env["server"].timedelta(hours=24),
            created_by="test",
        )
        session.add(token)
        session.commit()

    enroll_response = client.post(
        "/api/device-trust/enroll",
        json={
            "token": "revoke-token",
            "install_id": "install-revoke-1",
            "device_name": "Revoke Board",
            "csr_pem": "-----BEGIN CERTIFICATE REQUEST-----\nXYZ123\n-----END CERTIFICATE REQUEST-----",
        },
    )
    assert enroll_response.status_code == 200, enroll_response.text
    device_id = enroll_response.json()["device"]["id"]

    token = _login(client, "superadmin", "bootstrap-pass")
    credential_response = client.post(
        f"/api/device-trust/devices/{device_id}/issue-credential",
        json={"validity_days": 20},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert credential_response.status_code == 200, credential_response.text
    credential_id = credential_response.json()["credential"]["id"]

    lease_response = client.post(
        f"/api/device-trust/devices/{device_id}/issue-lease",
        json={"duration_hours": 12, "grace_hours": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lease_response.status_code == 200, lease_response.text
    lease = lease_response.json()["lease"]
    assert lease["metadata"]["credential_key_id"].startswith("kid_")
    assert lease["metadata"]["credential_id"] == credential_id
    assert lease["verification"]["valid"] is True

    revoke_lease_response = client.post(
        f"/api/device-trust/devices/{device_id}/revoke-lease",
        json={"lease_id": lease["id"], "reason": "test revoke lease"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke_lease_response.status_code == 200, revoke_lease_response.text
    assert revoke_lease_response.json()["device"]["trust_status"] == "revoked"
    assert revoke_lease_response.json()["lease"]["computed_status"] == "revoked"

    revoke_credential_response = client.post(
        f"/api/device-trust/devices/{device_id}/revoke-credential",
        json={"credential_id": credential_id, "reason": "test revoke credential"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke_credential_response.status_code == 200, revoke_credential_response.text
    revoked = revoke_credential_response.json()
    assert revoked["credential"]["status"] == "revoked"
    assert revoked["device"]["credential_status"] == "revoked"

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, device_id)
        assert device.trust_status == models.DeviceTrustStatus.REVOKED.value
        assert device.lease_status == models.DeviceLeaseStatus.REVOKED.value
        assert device.credential_status == models.DeviceCredentialStatus.REVOKED.value


def test_device_trust_detail_is_scope_protected(client, seeded_central):
    owner_token = _login(client, "owner", "owner-pass")

    own_response = client.get(
        f"/api/device-trust/devices/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert own_response.status_code == 200, own_response.text

    forbidden = client.get(
        f"/api/device-trust/devices/{seeded_central['outsider_device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert forbidden.status_code == 403


def test_device_lists_do_not_expose_full_api_keys(client, seeded_central):
    token = _login(client, "superadmin", "bootstrap-pass")

    list_response = client.get(
        "/api/licensing/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    devices = list_response.json()
    listed = next(d for d in devices if d["id"] == seeded_central["device_id"])
    assert "api_key" not in listed
    assert listed["api_key_preview"].startswith("device-a")
    assert listed["detail_level"] == "internal"


def test_owner_device_lists_are_operator_safe(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        device.trust_reason = "manual trust note"
        device.credential_fingerprint = "fp-secret"
        device.lease_id = "lease-secret"
        device.last_error = "stack trace secret"
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    list_response = client.get(
        "/api/licensing/devices",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert list_response.status_code == 200, list_response.text
    listed = next(d for d in list_response.json() if d["id"] == seeded_central["device_id"])
    assert listed["detail_level"] == "operator_safe"
    assert "api_key_preview" not in listed
    assert "install_id" not in listed
    assert "trust_reason" not in listed
    assert "credential_fingerprint" not in listed
    assert "lease_id" not in listed
    assert "last_error" not in listed



def test_owner_telemetry_dashboard_is_operator_safe(client, central_app_env, seeded_central):
    models = central_app_env["models"]
    sync_engine = central_app_env["database"].sync_engine
    now = datetime.now(timezone.utc)

    with Session(sync_engine) as session:
        device = session.get(models.CentralDevice, seeded_central["device_id"])
        device.last_heartbeat_at = now
        device.last_activity_at = now
        device.last_sync_at = now
        device.trust_reason = "private trust note"
        device.credential_fingerprint = "fp-private"
        device.lease_id = "lease-private"
        device.last_error = "private stack trace"
        session.commit()

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        "/api/telemetry/dashboard",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    listed = next(d for d in data["devices"] if d["id"] == seeded_central["device_id"])
    assert listed["detail_level"] == "operator_safe"
    assert "last_error" not in listed
    assert "trust_reason" not in listed
    assert "credential_fingerprint" not in listed
    assert "lease_id" not in listed
    assert data["warnings"][0]["type"] == "error"
    assert data["warnings"][0]["message"] == "Gerät meldet einen Fehler"


class _DummyConnectedWebSocket:
    client_state = WebSocketState.CONNECTED


def test_owner_ws_status_is_scoped_to_visible_devices(client, central_app_env, seeded_central):
    from central_server.ws_hub import DeviceConnection

    hub = central_app_env["server"].device_ws_hub
    own_conn = DeviceConnection(seeded_central["device_id"], _DummyConnectedWebSocket())
    own_conn.events_sent = 2
    outsider_conn = DeviceConnection(seeded_central["outsider_device_id"], _DummyConnectedWebSocket())
    outsider_conn.events_sent = 9
    hub._connections = {
        seeded_central["device_id"]: own_conn,
        seeded_central["outsider_device_id"]: outsider_conn,
    }
    hub._total_connections = 2
    hub._total_events_pushed = 11

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        "/api/ws/status",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "operator_safe"
    assert data["connected_devices"] == 1
    assert data["total_connections"] == 1
    assert data["total_events_pushed"] == 2
    assert list(data["devices"].keys()) == [seeded_central["device_id"]]
    assert data["devices"][seeded_central["device_id"]]["detail_level"] == "operator_safe"


def test_owner_ws_device_status_is_operator_safe(client, central_app_env, seeded_central):
    from central_server.ws_hub import DeviceConnection

    hub = central_app_env["server"].device_ws_hub
    conn = DeviceConnection(seeded_central["device_id"], _DummyConnectedWebSocket())
    conn.events_sent = 4
    hub._connections = {seeded_central["device_id"]: conn}

    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/ws/device/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "operator_safe"
    assert data["ws_connected"] is True
    assert "connected_at" not in data
    assert "last_event_at" not in data
    assert "events_sent" not in data



def test_installer_ws_device_status_keeps_internal_fields(client, central_app_env, seeded_central):
    from central_server.ws_hub import DeviceConnection

    hub = central_app_env["server"].device_ws_hub
    conn = DeviceConnection(seeded_central["device_id"], _DummyConnectedWebSocket())
    conn.events_sent = 7
    hub._connections = {seeded_central["device_id"]: conn}

    installer_token = _login(client, "installer", "installer-pass")
    response = client.get(
        f"/api/ws/device/{seeded_central['device_id']}",
        headers={"Authorization": f"Bearer {installer_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detail_level"] == "internal"
    assert data["ws_connected"] is True
    assert data["events_sent"] == 7
    assert data["connected_at"]



def test_owner_ws_device_status_denies_out_of_scope_device(client, central_app_env, seeded_central):
    owner_token = _login(client, "owner", "owner-pass")
    response = client.get(
        f"/api/ws/device/{seeded_central['outsider_device_id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 403, response.text



def test_create_device_returns_full_api_key_once_but_list_hides_it(client, seeded_central):
    token = _login(client, "superadmin", "bootstrap-pass")

    create_response = client.post(
        "/api/licensing/devices",
        json={
            "location_id": seeded_central["location_id"],
            "device_name": "Board 2",
            "install_id": "install-3",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["api_key"].startswith("dk_")
    assert created["api_key_preview"].startswith(created["api_key"][:8])

    list_response = client.get(
        "/api/licensing/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    listed = next(d for d in list_response.json() if d["id"] == created["id"])
    assert "api_key" not in listed


@pytest.mark.parametrize("origin,expected_allow_origin", [
    ("https://portal.example.com", "https://portal.example.com"),
    ("https://evil.example.com", None),
])
def test_cors_is_env_scoped(monkeypatch, tmp_path, origin, expected_allow_origin):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path / "central-cors"))
    monkeypatch.setenv("CENTRAL_BOOTSTRAP_PASSWORD", "bootstrap-pass")
    monkeypatch.setenv("CENTRAL_JWT_SECRET", "test-jwt-secret-which-is-long-enough-for-hs256")
    monkeypatch.setenv("CENTRAL_CORS_ALLOWED_ORIGINS", "https://portal.example.com")
    monkeypatch.delenv("CENTRAL_CORS_ALLOW_ALL", raising=False)

    for name in [
        "central_server.server",
        "central_server.auth",
        "central_server.models",
        "central_server.database",
        "central_server.ws_hub",
    ]:
        sys.modules.pop(name, None)

    server = importlib.import_module("central_server.server")

    with TestClient(server.app) as cors_client:
        response = cors_client.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        if expected_allow_origin is None:
            assert "access-control-allow-origin" not in response.headers
        else:
            assert response.headers.get("access-control-allow-origin") == expected_allow_origin
            assert response.headers.get("access-control-allow-credentials") == "true"
