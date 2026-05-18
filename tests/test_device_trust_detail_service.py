from types import SimpleNamespace

from central_server.services.device_trust_details import (
    finalize_device_trust_detail,
    serialize_device_credential,
)


INSTALLER = SimpleNamespace(role="installer")
OWNER = SimpleNamespace(role="owner")


def _credential(**overrides):
    base = dict(
        id="cred-1",
        device_id="dev-1",
        status="active",
        credential_kind="placeholder",
        fingerprint="fp-secret",
        certificate_pem=None,
        public_key_pem=None,
        csr_pem=None,
        issued_at=None,
        expires_at=None,
        revoked_at=None,
        replacement_for_credential_id=None,
        details_json={"key_id": "kid-1", "issuer": {"status": "active"}},
        created_at=None,
        updated_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_finalize_device_trust_detail_redacts_operator_safe_fields():
    detail = finalize_device_trust_detail(
        {
            "device": {
                "id": "dev-1",
                "api_key_preview": "abcd...1234",
                "install_id": "install-secret",
                "trust_reason": "internal note",
                "credential_fingerprint": "fp-secret",
                "lease_id": "lease-secret",
                "last_error": "stacktrace-ish",
            },
            "credential": {
                "id": "cred-1",
                "fingerprint": "fp-secret",
                "metadata": {"private": True},
                "verification": {"valid": True, "issuer_inspection": {"status": "ok"}},
            },
            "lease": {
                "id": "lease-1",
                "signature": "sig",
                "metadata": {"private": True},
                "signed_bundle": {"token": "secret"},
                "verification": {"valid": True, "issuer_inspection": {"status": "ok"}},
            },
            "reconciliation": {"ok": True},
            "issuer_profiles": {},
            "signing_registry": {},
        },
        OWNER,
    )

    assert detail["detail_level"] == "operator_safe"
    assert "api_key_preview" not in detail["device"]
    assert "install_id" not in detail["device"]
    assert "fingerprint" not in detail["credential"]
    assert "metadata" not in detail["credential"]
    assert "signature" not in detail["lease"]
    assert "signed_bundle" not in detail["lease"]


def test_serialize_device_credential_preserves_internal_rotation_and_verification_for_installers():
    payload = serialize_device_credential(_credential())
    final = finalize_device_trust_detail({"device": {"id": "dev-1"}, "credential": payload}, INSTALLER)

    assert final["detail_level"] == "internal"
    assert final["credential"]["fingerprint"] == "fp-secret"
    assert final["credential"]["verification"]["detail_level"] == "internal"
    assert final["credential"]["rotation"]["detail_level"] == "internal"
