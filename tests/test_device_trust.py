from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from central_server.device_trust import (
    attach_lease_key_metadata,
    build_credential_rotation_lineage,
    build_issuer_history_summary,
    build_issuer_profile_diagnostics,
    build_material_history_readback_summary,
    build_material_history_summary,
    build_placeholder_certificate,
    build_placeholder_signed_lease,
    build_reconciliation_summary,
    build_signing_registry_diagnostics,
    build_signing_key_lineage,
    build_support_contract_source_summary,
    build_support_contract_state_summary,
    build_support_diagnostics_compact_summary,
    derive_key_id,
    get_placeholder_signing_profile,
    issue_placeholder_credential,
    reconcile_trust_material,
    summarize_credential_rotation,
    summarize_lineage,
    verify_placeholder_certificate,
    verify_placeholder_signed_lease,
)
from central_server.server import (
    _finalize_device_trust_detail,
    _finalize_endpoint_summary,
    _to_operator_safe_issuer_profiles,
    _to_operator_safe_signing_registry,
)


UTC = timezone.utc


def _device(**overrides):
    base = dict(
        id="dev-1",
        license_id="lic-1",
        trust_status="pending_enrollment",
        trust_reason=None,
        trust_last_changed_at=None,
        credential_status="none",
        credential_fingerprint=None,
        credential_issued_at=None,
        credential_expires_at=None,
        credential_key_id=None,
        lease_status="none",
        lease_id=None,
        lease_issued_at=None,
        lease_expires_at=None,
        lease_grace_until=None,
        lease_metadata=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _credential(**overrides):
    base = dict(
        id="cred-1",
        device_id="dev-1",
        status="pending",
        credential_kind="placeholder",
        fingerprint=None,
        public_key_pem="-----BEGIN PUBLIC KEY-----\nQUJDREVGRw==\n-----END PUBLIC KEY-----",
        certificate_pem=None,
        csr_pem=None,
        issued_at=None,
        expires_at=None,
        revoked_at=None,
        replacement_for_credential_id=None,
        details_json={},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _lease(**overrides):
    now = datetime(2026, 4, 13, 12, 0, tzinfo=UTC)
    base = dict(
        id="lease-db-1",
        device_id="dev-1",
        central_license_id="lic-1",
        lease_id="lease-1",
        status="active",
        issued_at=now,
        expires_at=now,
        grace_until=now,
        revoked_at=None,
        signature="sig",
        details_json={"mode": "placeholder"},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_issue_placeholder_credential_records_richer_issuer_metadata():
    device = _device()
    credential = _credential()
    now = datetime(2026, 4, 13, 12, 0, tzinfo=UTC)

    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by="jarvis",
        validity_days=30,
        now=now,
    )

    issuer = (credential.details_json or {}).get("issuer")
    assert issuer
    assert issuer["schema"] == "darts.placeholder_signing_profile.v1"
    assert issuer["algorithm"] == "hmac-sha256-placeholder"
    assert verify_placeholder_certificate(credential=credential, device=device)["valid"] is True


def test_signed_lease_carries_consistent_issuer_and_key_id():
    credential_key_id = derive_key_id(fingerprint="abc123")
    device = _device(
        credential_status="active",
        credential_fingerprint="abc123",
        credential_key_id=credential_key_id,
    )
    credential = _credential(
        status="active",
        fingerprint="abc123",
        details_json={"key_id": credential_key_id},
    )
    lease = _lease()
    attach_lease_key_metadata(lease=lease, credential=credential)

    bundle = build_placeholder_signed_lease(device=device, lease=lease)
    verification = verify_placeholder_signed_lease(
        bundle=bundle,
        device=device,
        lease=lease,
        credential=credential,
    )

    assert bundle["issuer"]["key_id"] == bundle["key_id"]
    assert bundle["payload"]["issuer"]["key_id"] == bundle["key_id"]
    assert verification["valid"] is True
    assert verification["expected_lease_key_id"] == bundle["key_id"]


def test_reconciliation_reports_mismatched_device_key_id():
    profile = get_placeholder_signing_profile()
    device = _device(
        credential_status="active",
        credential_fingerprint="abc123",
        credential_key_id="kid_wrongwrongwrong",
    )
    credential = _credential(
        status="active",
        fingerprint="abc123",
        details_json={
            "key_id": "kid_abc123abc123abcd",
            "issuer": profile,
        },
        certificate_pem=None,
    )
    lease = _lease(details_json={"mode": "placeholder"})
    attach_lease_key_metadata(lease=lease, credential=credential)
    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by="jarvis",
        validity_days=30,
        now=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )
    device.credential_key_id = "kid_wrongwrongwrong"

    reconciliation = reconcile_trust_material(device=device, credential=credential, lease=lease)

    assert reconciliation["ok"] is False
    assert reconciliation["summary"]["highest_severity"] == "error"
    assert any(
        finding["message"] == "device credential_key_id does not match active credential"
        for finding in reconciliation["findings"]
    )


def test_reconciliation_reports_stored_bundle_drift_as_warning():
    device = _device(
        credential_status="active",
        credential_fingerprint="abc123",
    )
    credential = _credential(status="active", fingerprint="abc123")
    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by="jarvis",
        validity_days=30,
        now=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )
    lease = _lease(details_json={"mode": "placeholder"})
    attach_lease_key_metadata(lease=lease, credential=credential)
    stored_bundle = build_placeholder_signed_lease(device=device, lease=lease)
    stored_bundle["payload"]["credential"]["fingerprint"] = "drifted"
    lease.details_json["signed_bundle"] = stored_bundle

    reconciliation = reconcile_trust_material(device=device, credential=credential, lease=lease)

    assert reconciliation["ok"] is False
    assert reconciliation["bundle_source"] == "stored"
    assert any(
        finding["message"] == "stored signed lease bundle drifted from current central reconstruction"
        for finding in reconciliation["findings"]
    )


def test_build_reconciliation_summary_counts_severities_and_sources():
    summary = build_reconciliation_summary(
        reconciliation={
            "ok": False,
            "findings": [
                {"severity": "warning", "source": "lease", "message": "a"},
                {"severity": "error", "source": "device", "message": "b"},
                {"severity": "warning", "source": "lease", "message": "c"},
            ],
            "credential": {"timing_status": "active"},
            "lease": {"timing_status": "expired"},
        }
    )

    assert summary == {
        "ok": False,
        "total": 3,
        "highest_severity": "error",
        "severity_counts": {"error": 1, "warning": 2, "info": 0},
        "source_counts": {"lease": 2, "device": 1},
        "bundle_source": None,
        "timing_status": {"credential": "active", "lease": "expired"},
        "issuer_registry_status": {"credential": None, "lease": None},
        "signing_registry": {
            "registry_size": None,
            "status_counts": {},
            "rotation_depths": {"credential": None, "credential_key": None, "lease_key": None},
        },
        "issuer_profiles": {
            "effective_key_id": None,
            "effective_source": None,
            "history_count": 0,
            "rotation_depth": None,
            "transition": {},
            "lineage_explanation": {
                "effective_key_id": None,
                "effective_source": None,
                "lineage_state": None,
                "lineage_note": None,
                "transition_state": None,
                "rotation_depth": None,
                "parent_key_id": None,
                "terminal_status": None,
            },
            "readback_summary": {},
            "history_summary": {},
            "source_contracts": {
                "issuer_profile_readback": {
                    "schema": "darts.issuer_profile_readback_summary.v1",
                    "detail_level": "support_compact",
                    "present": False,
                    "source_state": "missing",
                    "lineage_state": None,
                    "effective_source": None,
                    "has_lineage_explanation": False,
                    "has_effective_source_reason": False,
                    "has_mismatch_summary": False,
                },
                "issuer_history": {
                    "schema": "darts.issuer_history_summary.v1",
                    "detail_level": "support_compact",
                    "present": False,
                    "source_state": "missing",
                    "history_state": None,
                    "narrative_state": None,
                    "history_count": None,
                    "replacement_relation": None,
                    "has_narrative": False,
                },
                "material_history_readback": {
                    "schema": "darts.material_history.readback_summary.v1",
                    "detail_level": "support_compact",
                    "present": False,
                    "source_state": "missing",
                    "credential_alignment": "empty",
                    "lease_alignment": "empty",
                    "credential_history_count": 0,
                    "lease_history_count": 0,
                    "has_summary": False,
                },
            },
            "source_contract_summary": {
                "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
                "detail_level": "support_compact",
                "overall_state": "missing",
                "coverage_state": "full_set",
                "state_counts": {
                    "present": 0,
                    "missing": 3,
                    "derived_from_material_history": 0,
                    "detail_level": "support_compact",
                },
                "total_contracts": 3,
                "expected_contract_count": 3,
                "observed_contract_count": 3,
                "present_contract_count": 0,
                "derived_contract_count": 0,
                "missing_contract_count": 3,
                "observed_extra_count": 0,
                "missing_expected_count": 0,
                "has_present_contracts": False,
                "has_derived_contracts": False,
                "has_missing_contracts": True,
                "has_unexpected_contracts": False,
                "has_missing_expected_contracts": False,
                "expected_names": [
                    "issuer_profile_readback",
                    "issuer_history",
                    "material_history_readback",
                ],
                "observed_names": [
                    "issuer_history",
                    "issuer_profile_readback",
                    "material_history_readback",
                ],
                "missing_expected_names": [],
                "unexpected_names": [],
                "source_states": {
                    "issuer_profile_readback": "missing",
                    "issuer_history": "missing",
                    "material_history_readback": "missing",
                    "detail_level": "support_compact",
                },
                "present_names": [],
                "derived_names": [],
                "missing_names": [
                    "issuer_history",
                    "issuer_profile_readback",
                    "material_history_readback",
                ],
                "summary": "missing=3",
            },
        },
        "material_history": {},
        "material_readback_summary": {
            "credential_history": {
                "history_count": 0,
                "active_credential_id": None,
                "latest_credential_id": None,
                "alignment_state": "empty",
                "status_counts": {},
                "narrative": None,
            },
            "lease_history": {
                "history_count": 0,
                "current_lease_id": None,
                "latest_lease_id": None,
                "alignment_state": "empty",
                "status_counts": {},
                "narrative": None,
            },
            "summary": None,
        },
        "support_summary": {},
    }


def test_build_signing_key_lineage_tracks_parent_and_child_keys(monkeypatch):
    monkeypatch.setenv(
        "CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY",
        '[{"key_id":"kid_root","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"retired"},'
        '{"key_id":"kid_active","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"active","parent_key_id":"kid_root"},'
        '{"key_id":"kid_future","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"staged","parent_key_id":"kid_active"}]',
    )

    lineage = build_signing_key_lineage(key_id="kid_active")

    assert lineage["parent_key_id"] == "kid_root"
    assert lineage["rotation_depth"] == 1
    assert lineage["ancestors"] == [{"key_id": "kid_root", "present": True, "status": "retired"}]
    assert lineage["descendants"] == [{"key_id": "kid_future", "present": True, "status": "staged"}]


def test_build_credential_rotation_lineage_tracks_replacement_chain():
    root = _credential(id="cred-root", status="retired", details_json={"key_id": "kid_root"})
    current = _credential(
        id="cred-current",
        status="active",
        replacement_for_credential_id="cred-root",
        details_json={"key_id": "kid_current"},
    )
    pending = _credential(
        id="cred-pending",
        status="pending",
        replacement_for_credential_id="cred-current",
        details_json={"key_id": "kid_pending"},
    )

    lineage = build_credential_rotation_lineage(credential=current, credentials=[root, current, pending])

    assert lineage == {
        "credential_id": "cred-current",
        "replacement_for_credential_id": "cred-root",
        "rotation_depth": 1,
        "ancestors": [{
            "credential_id": "cred-root",
            "present": True,
            "status": "retired",
            "key_id": "kid_root",
        }],
        "descendants": [{
            "credential_id": "cred-pending",
            "present": True,
            "status": "pending",
            "key_id": "kid_pending",
        }],
    }


def test_certificate_verification_reports_retired_signing_key(monkeypatch):
    monkeypatch.setenv(
        "CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY",
        '[{"key_id":"kid_retired123456","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"retired"}]',
    )
    device = _device()
    credential = _credential()
    now = datetime(2026, 4, 13, 12, 0, tzinfo=UTC)

    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by="jarvis",
        validity_days=30,
        now=now,
    )
    retired_issuer = {
        **(credential.details_json or {}).get("issuer", {}),
        "key_id": "kid_retired123456",
    }
    credential.details_json["issuer"] = retired_issuer
    credential.certificate_pem = build_placeholder_certificate(
        device_id=device.id,
        fingerprint=credential.fingerprint,
        key_id=(credential.details_json or {}).get("key_id"),
        issued_at=credential.issued_at,
        expires_at=credential.expires_at,
        issuer=retired_issuer,
    )
    parsed = verify_placeholder_certificate(credential=credential, device=device)

    assert parsed["valid"] is True
    assert "certificate issuer key_id retired in central registry" in parsed["warnings"]
    assert parsed["issuer_inspection"]["status"] == "known"
    assert parsed["issuer_inspection"]["entry"]["status"] == "retired"


def test_reconciliation_reports_revoked_signing_key_as_error(monkeypatch):
    monkeypatch.setenv(
        "CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY",
        '[{"key_id":"kid_revoked123456","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"revoked"}]',
    )
    device = _device(
        credential_status="active",
        credential_fingerprint="abc123",
        credential_key_id=derive_key_id(fingerprint="abc123"),
    )
    credential = _credential(status="active", fingerprint="abc123")
    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by="jarvis",
        validity_days=30,
        now=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )
    revoked_issuer = {
        **(credential.details_json or {}).get("issuer", {}),
        "key_id": "kid_revoked123456",
    }
    credential.details_json["issuer"] = revoked_issuer
    credential.certificate_pem = build_placeholder_certificate(
        device_id=device.id,
        fingerprint=credential.fingerprint,
        key_id=(credential.details_json or {}).get("key_id"),
        issued_at=credential.issued_at,
        expires_at=credential.expires_at,
        issuer=revoked_issuer,
    )
    lease = _lease(details_json={
        "mode": "placeholder",
        "lease_key_id": "kid_revoked123456",
        "issuer": {
            "issuer": "central",
            "key_id": "kid_revoked123456",
            "algorithm": "hmac-sha256-placeholder",
            "schema": "darts.placeholder_signing_profile.v1",
        },
    })
    attach_lease_key_metadata(lease=lease, credential=credential)
    lease.details_json["lease_key_id"] = "kid_revoked123456"
    lease.details_json["issuer"] = {
        "issuer": "central",
        "key_id": "kid_revoked123456",
        "algorithm": "hmac-sha256-placeholder",
        "schema": "darts.placeholder_signing_profile.v1",
    }

    reconciliation = reconcile_trust_material(device=device, credential=credential, lease=lease)

    assert reconciliation["ok"] is False
    assert any(
        finding["message"] == "credential issued by revoked central signing key"
        for finding in reconciliation["findings"]
    )
    assert any(
        finding["message"] == "lease issued by revoked central signing key"
        for finding in reconciliation["findings"]
    )
    assert reconciliation["summary"]["issuer_registry_status"] == {"credential": "known", "lease": "known"}
    assert reconciliation["summary"]["signing_registry"] == {
        "registry_size": 2,
        "status_counts": {"active": 1, "revoked": 1},
        "rotation_depths": {"credential": 0, "credential_key": 0, "lease_key": 0},
    }


def test_issuer_profile_diagnostics_exposes_effective_profile_and_history(monkeypatch):
    monkeypatch.setenv(
        "CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY",
        '[{"key_id":"kid_root","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"retired"},'
        '{"key_id":"kid_active","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"active","parent_key_id":"kid_root"}]',
    )
    device = _device(credential_key_id="kid_active")
    root = _credential(
        id="cred-root",
        status="retired",
        replacement_for_credential_id=None,
        details_json={
            "key_id": "kid_root_leaf",
            "issuer": {
                "issuer": "central",
                "key_id": "kid_root",
                "algorithm": "hmac-sha256-placeholder",
                "schema": "darts.placeholder_signing_profile.v1",
            },
        },
        issued_at=datetime(2026, 4, 12, 12, 0, tzinfo=UTC),
    )
    current = _credential(
        id="cred-current",
        status="active",
        replacement_for_credential_id="cred-root",
        details_json={
            "key_id": "kid_current_leaf",
            "issuer": {
                "issuer": "central",
                "key_id": "kid_active",
                "algorithm": "hmac-sha256-placeholder",
                "schema": "darts.placeholder_signing_profile.v1",
            },
        },
        issued_at=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )
    lease = _lease(details_json={
        "mode": "placeholder",
        "lease_key_id": "kid_active",
        "issuer": {
            "issuer": "central",
            "key_id": "kid_active",
            "algorithm": "hmac-sha256-placeholder",
            "schema": "darts.placeholder_signing_profile.v1",
        },
    })

    diagnostics = build_issuer_profile_diagnostics(
        device=device,
        credential=current,
        lease=lease,
        credentials=[root, current],
    )

    assert diagnostics["effective_profile"]["key_id"] == "kid_current_leaf"
    assert diagnostics["support_summary"] == {
        "effective_source": "lease",
        "effective_key_id": "kid_current_leaf",
        "effective_registry_status": "unknown",
        "effective_status": None,
        "history_count": 2,
        "history_key_ids": ["kid_active", "kid_root"],
        "active_profile_matches_effective": False,
        "credential_profile_matches_effective": False,
        "lease_profile_matches_effective": False,
        "rotation_depth": 0,
        "transition": {
            "transition_state": "rotated",
            "active_key_id": get_placeholder_signing_profile()["key_id"],
            "configured_key_id": "kid_current_leaf",
            "effective_key_id": "kid_current_leaf",
            "credential_key_id": "kid_active",
            "lease_key_id": "kid_active",
            "effective_registry_status": "unknown",
            "effective_status": None,
            "rotation_depth": 0,
            "mismatch_reasons": [
                "active_profile_differs_from_effective",
                "credential_profile_differs_from_active",
                "lease_profile_differs_from_active",
                "effective_key_unknown",
            ],
        },
    }
    assert [item["credential_id"] for item in diagnostics["history"]] == ["cred-current", "cred-root"]
    assert diagnostics["effective_lineage_summary"]["parent_key_id"] is None
    assert diagnostics["readback_summary"] == {
        "effective_source": "lease",
        "effective_source_reason": "lease issuer metadata currently drives the effective issuer profile",
        "configured_vs_effective": {
            "configured_key_id": "kid_current_leaf",
            "effective_key_id": "kid_current_leaf",
            "matches": True,
        },
        "active_vs_effective": {
            "active_key_id": get_placeholder_signing_profile()["key_id"],
            "effective_key_id": "kid_current_leaf",
            "matches": False,
        },
        "history_status_counts": {"active": 1, "retired": 1},
        "latest_history_credential_id": "cred-current",
        "latest_history_key_id": "kid_active",
        "lineage_state": "standalone",
        "lineage_note": "effective key currently has no recorded parent rotation lineage",
        "lineage_explanation": {
            "effective_key_id": "kid_current_leaf",
            "effective_source": "lease",
            "lineage_state": "standalone",
            "lineage_note": "effective key currently has no recorded parent rotation lineage",
            "transition_state": "rotated",
            "rotation_depth": 0,
            "parent_key_id": None,
            "terminal_status": None,
        },
        "mismatch_summary": "active_profile_differs_from_effective; credential_profile_differs_from_active; lease_profile_differs_from_active; effective_key_unknown",
    }
    assert diagnostics["history_summary"] == {
        "history_state": "rotated",
        "history_count": 2,
        "status_counts": {"active": 1, "retired": 1},
        "replacement_relation": "declared_replacement",
        "narrative_state": "rotated",
        "latest": {
            "credential_id": "cred-current",
            "key_id": "kid_active",
            "credential_status": "active",
            "issued_at": "2026-04-13T12:00:00+00:00",
            "revoked_at": None,
            "replacement_for_credential_id": "cred-root",
        },
        "previous": {
            "credential_id": "cred-root",
            "key_id": "kid_root",
            "credential_status": "retired",
            "issued_at": "2026-04-12T12:00:00+00:00",
            "revoked_at": None,
        },
        "narrative": "latest visible credential cred-current replaced cred-root (retired -> active)",
    }


def test_build_issuer_history_summary_describes_rotation_and_revocation():
    history = [
        {
            "credential_id": "cred-current",
            "credential_status": "revoked",
            "key_id": "kid-current",
            "issued_at": "2026-04-13T12:00:00+00:00",
            "revoked_at": "2026-04-14T12:00:00+00:00",
            "replacement_for_credential_id": "cred-root",
        },
        {
            "credential_id": "cred-root",
            "credential_status": "retired",
            "key_id": "kid-root",
            "issued_at": "2026-04-12T12:00:00+00:00",
            "revoked_at": None,
        },
    ]

    assert build_issuer_history_summary(history) == {
        "history_state": "revoked_latest",
        "history_count": 2,
        "status_counts": {"revoked": 1, "retired": 1},
        "replacement_relation": "declared_replacement",
        "narrative_state": "revoked_replacement",
        "latest": {
            "credential_id": "cred-current",
            "key_id": "kid-current",
            "credential_status": "revoked",
            "issued_at": "2026-04-13T12:00:00+00:00",
            "revoked_at": "2026-04-14T12:00:00+00:00",
            "replacement_for_credential_id": "cred-root",
        },
        "previous": {
            "credential_id": "cred-root",
            "key_id": "kid-root",
            "credential_status": "retired",
            "issued_at": "2026-04-12T12:00:00+00:00",
            "revoked_at": None,
        },
        "narrative": "latest visible credential cred-current using key kid-current replaced cred-root (retired -> revoked) and is now revoked",
    }


def test_build_material_history_summary_describes_current_vs_latest_material():
    active_credential = _credential(
        id="cred-active",
        status="active",
        issued_at=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )
    latest_credential = _credential(
        id="cred-revoked",
        status="revoked",
        issued_at=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
        revoked_at=datetime(2026, 4, 14, 14, 0, tzinfo=UTC),
        replacement_for_credential_id="cred-active",
    )
    previous_lease = _lease(
        id="lease-db-0",
        lease_id="lease-0",
        status="revoked",
        issued_at=datetime(2026, 4, 12, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
        revoked_at=datetime(2026, 4, 13, 10, 0, tzinfo=UTC),
    )
    current_lease = _lease(
        id="lease-db-1",
        lease_id="lease-1",
        status="active",
        issued_at=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )

    summary = build_material_history_summary(
        credentials=[latest_credential, active_credential],
        leases=[current_lease, previous_lease],
        active_credential=active_credential,
        current_lease=current_lease,
    )

    assert summary == {
        "credential_history": {
            "history_count": 2,
            "status_counts": {"revoked": 1, "active": 1},
            "active_credential_id": "cred-active",
            "latest": {
                "credential_id": "cred-revoked",
                "status": "revoked",
                "issued_at": "2026-04-14T12:00:00+00:00",
                "revoked_at": "2026-04-14T14:00:00+00:00",
                "replacement_for_credential_id": "cred-active",
            },
            "previous": {
                "credential_id": "cred-active",
                "status": "active",
                "issued_at": "2026-04-13T12:00:00+00:00",
                "revoked_at": None,
            },
            "narrative": "active credential cred-active differs from latest visible credential cred-revoked",
        },
        "lease_history": {
            "history_count": 2,
            "status_counts": {"active": 1, "revoked": 1},
            "current_lease_id": "lease-1",
            "latest": {
                "lease_id": "lease-1",
                "status": "active",
                "issued_at": "2026-04-13T12:00:00+00:00",
                "expires_at": "2026-04-14T12:00:00+00:00",
                "revoked_at": None,
            },
            "previous": {
                "lease_id": "lease-0",
                "status": "revoked",
                "issued_at": "2026-04-12T12:00:00+00:00",
                "expires_at": "2026-04-13T12:00:00+00:00",
                "revoked_at": "2026-04-13T10:00:00+00:00",
            },
            "narrative": "current lease lease-1 is the latest visible lease",
        },
        "summary": "credentials=2 visible / leases=2 visible; active credential cred-active differs from latest visible credential cred-revoked; current lease lease-1 is the latest visible lease",
        "readback_summary": {
            "credential_history": {
                "history_count": 2,
                "active_credential_id": "cred-active",
                "latest_credential_id": "cred-revoked",
                "alignment_state": "drifted",
                "status_counts": {"revoked": 1, "active": 1},
                "narrative": "active credential cred-active differs from latest visible credential cred-revoked",
            },
            "lease_history": {
                "history_count": 2,
                "current_lease_id": "lease-1",
                "latest_lease_id": "lease-1",
                "alignment_state": "aligned",
                "status_counts": {"active": 1, "revoked": 1},
                "narrative": "current lease lease-1 is the latest visible lease",
            },
            "summary": "credentials=2 visible / leases=2 visible; active credential cred-active differs from latest visible credential cred-revoked; current lease lease-1 is the latest visible lease",
        },
    }



def test_build_material_history_readback_summary_compacts_alignment_and_narrative():
    material_history = {
        "credential_history": {
            "history_count": 1,
            "status_counts": {"active": 1},
            "active_credential_id": "cred-1",
            "latest": {"credential_id": "cred-1"},
            "narrative": "active credential cred-1 is the latest visible credential",
        },
        "lease_history": {
            "history_count": 2,
            "status_counts": {"active": 1, "revoked": 1},
            "current_lease_id": "lease-1",
            "latest": {"lease_id": "lease-2"},
            "narrative": "current lease lease-1 differs from latest visible lease lease-2",
        },
        "summary": "credentials=1 visible / leases=2 visible",
    }

    assert build_material_history_readback_summary(material_history=material_history) == {
        "credential_history": {
            "history_count": 1,
            "active_credential_id": "cred-1",
            "latest_credential_id": "cred-1",
            "alignment_state": "aligned",
            "status_counts": {"active": 1},
            "narrative": "active credential cred-1 is the latest visible credential",
        },
        "lease_history": {
            "history_count": 2,
            "current_lease_id": "lease-1",
            "latest_lease_id": "lease-2",
            "alignment_state": "drifted",
            "status_counts": {"active": 1, "revoked": 1},
            "narrative": "current lease lease-1 differs from latest visible lease lease-2",
        },
        "summary": "credentials=1 visible / leases=2 visible",
    }



def test_signing_registry_diagnostics_exposes_support_summary(monkeypatch):
    monkeypatch.setenv(
        "CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY",
        '[{"key_id":"kid_root","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"retired"},'
        '{"key_id":"kid_revoked","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"revoked","parent_key_id":"kid_root"}]',
    )
    device = _device(credential_key_id="kid_revoked")
    credential = _credential(
        id="cred-current",
        fingerprint="abc123",
        replacement_for_credential_id="cred-root",
        details_json={
            "key_id": derive_key_id(fingerprint="abc123"),
            "issuer": {
                "issuer": "central",
                "key_id": "kid_revoked",
                "algorithm": "hmac-sha256-placeholder",
                "schema": "darts.placeholder_signing_profile.v1",
            },
        },
    )
    root = _credential(id="cred-root", status="retired", details_json={"key_id": "kid_root"})
    lease = _lease(details_json={
        "mode": "placeholder",
        "lease_key_id": "kid_revoked",
        "issuer": {
            "issuer": "central",
            "key_id": "kid_root",
            "algorithm": "hmac-sha256-placeholder",
            "schema": "darts.placeholder_signing_profile.v1",
        },
    })

    diagnostics = build_signing_registry_diagnostics(device=device, credential=credential, lease=lease, credentials=[root, credential])

    assert diagnostics["support_summary"] == {
        "registry_size": 3,
        "status_counts": {"active": 1, "retired": 1, "revoked": 1},
        "unknown_reference_names": ["credential_key_id"],
        "revoked_reference_names": ["credential_issuer_key_id", "device_credential_key_id", "lease_key_id"],
        "retired_reference_names": ["lease_issuer_key_id"],
        "inconsistent_reference_names": [
            "active_profile_matches_credential_issuer",
            "active_profile_matches_lease_issuer",
            "device_key_matches_credential_key",
            "lease_key_matches_lease_issuer",
        ],
        "rotation_depths": {
            "credential": 1,
            "device_credential_key_id": 1,
            "credential_key_id": 0,
            "credential_issuer_key_id": 1,
            "lease_key_id": 1,
            "lease_issuer_key_id": 0,
            "active_profile": 0,
        },
    }


def test_reconciliation_summary_carries_issuer_profile_summary_and_support_summary():
    summary = build_reconciliation_summary(
        reconciliation={
            "ok": False,
            "findings": [{"severity": "warning", "source": "lease", "message": "retired key"}],
            "credential": {"timing_status": "active", "issuer_inspection": {"status": "known"}},
            "lease": {"timing_status": "grace", "issuer_inspection": {"status": "unknown"}},
            "issuer_profiles": {
                "effective_profile": {"key_id": "kid_active"},
                "effective_lineage": {"rotation_depth": 1},
                "history": [{"credential_id": "cred-1"}, {"credential_id": "cred-0"}],
                "support_summary": {
                    "effective_source": "lease",
                    "transition": {"transition_state": "rotated", "mismatch_reasons": ["active_profile_differs_from_effective"]},
                },
            },
            "signing_registry": {
                "registry_size": 2,
                "status_counts": {"active": 1, "retired": 1},
                "key_lineage": {"lease_key_id": {"rotation_depth": 1}},
                "credential_rotation": {"rotation_depth": 2},
                "support_summary": {"retired_reference_names": ["lease_key_id"]},
            },
        }
    )

    assert summary["support_summary"] == {"retired_reference_names": ["lease_key_id"]}
    assert summary["issuer_profiles"] == {
        "effective_key_id": "kid_active",
        "effective_source": "lease",
        "history_count": 2,
        "rotation_depth": 1,
        "transition": {"transition_state": "rotated", "mismatch_reasons": ["active_profile_differs_from_effective"]},
        "lineage_explanation": {
            "effective_key_id": "kid_active",
            "effective_source": "lease",
            "lineage_state": None,
            "lineage_note": None,
            "transition_state": "rotated",
            "rotation_depth": None,
            "parent_key_id": None,
            "terminal_status": None,
        },
        "readback_summary": {},
        "history_summary": {},
        "source_contracts": {
            "issuer_profile_readback": {
                "schema": "darts.issuer_profile_readback_summary.v1",
                "detail_level": "support_compact",
                "present": False,
                "source_state": "missing",
                "lineage_state": None,
                "effective_source": None,
                "has_lineage_explanation": False,
                "has_effective_source_reason": False,
                "has_mismatch_summary": False,
            },
            "issuer_history": {
                "schema": "darts.issuer_history_summary.v1",
                "detail_level": "support_compact",
                "present": False,
                "source_state": "missing",
                "history_state": None,
                "narrative_state": None,
                "history_count": None,
                "replacement_relation": None,
                "has_narrative": False,
            },
            "material_history_readback": {
                "schema": "darts.material_history.readback_summary.v1",
                "detail_level": "support_compact",
                "present": False,
                "source_state": "missing",
                "credential_alignment": "empty",
                "lease_alignment": "empty",
                "credential_history_count": 0,
                "lease_history_count": 0,
                "has_summary": False,
            },
        },
        "source_contract_summary": {
            "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
            "detail_level": "support_compact",
            "overall_state": "missing",
            "coverage_state": "full_set",
            "state_counts": {
                "present": 0,
                "missing": 3,
                "derived_from_material_history": 0,
                "detail_level": "support_compact",
            },
            "total_contracts": 3,
            "expected_contract_count": 3,
            "observed_contract_count": 3,
            "present_contract_count": 0,
            "derived_contract_count": 0,
            "missing_contract_count": 3,
            "observed_extra_count": 0,
            "missing_expected_count": 0,
            "has_present_contracts": False,
            "has_derived_contracts": False,
            "has_missing_contracts": True,
            "has_unexpected_contracts": False,
            "has_missing_expected_contracts": False,
            "expected_names": [
                "issuer_profile_readback",
                "issuer_history",
                "material_history_readback",
            ],
            "observed_names": [
                "issuer_history",
                "issuer_profile_readback",
                "material_history_readback",
            ],
            "missing_expected_names": [],
            "unexpected_names": [],
            "source_states": {
                "issuer_profile_readback": "missing",
                "issuer_history": "missing",
                "material_history_readback": "missing",
                "detail_level": "support_compact",
            },
            "present_names": [],
            "derived_names": [],
            "missing_names": ["issuer_history", "issuer_profile_readback", "material_history_readback"],
            "summary": "missing=3",
        },
    }
    assert summary["material_history"] == {}
    assert summary["material_readback_summary"] == {
        "credential_history": {
            "history_count": 0,
            "active_credential_id": None,
            "latest_credential_id": None,
            "alignment_state": "empty",
            "status_counts": {},
            "narrative": None,
        },
        "lease_history": {
            "history_count": 0,
            "current_lease_id": None,
            "latest_lease_id": None,
            "alignment_state": "empty",
            "status_counts": {},
            "narrative": None,
        },
        "summary": None,
    }
    assert summary["timing_status"] == {"credential": "active", "lease": "grace"}
    assert summary["issuer_registry_status"] == {"credential": "known", "lease": "unknown"}


def test_lineage_helpers_build_compact_support_summaries():
    key_lineage = {
        "key_id": "kid_active",
        "present": True,
        "parent_key_id": "kid_root",
        "ancestors": [{"key_id": "kid_root", "present": True, "status": "retired"}],
        "descendants": [{"key_id": "kid_future", "present": True, "status": "staged"}],
        "rotation_depth": 1,
        "status_path": [{"key_id": "kid_active", "status": "active"}],
    }
    credential_lineage = {
        "credential_id": "cred-current",
        "replacement_for_credential_id": "cred-root",
        "rotation_depth": 1,
        "ancestors": [{"credential_id": "cred-root"}],
        "descendants": [{"credential_id": "cred-next"}],
    }

    assert summarize_lineage(key_lineage) == {
        "key_id": "kid_active",
        "present": True,
        "parent_key_id": "kid_root",
        "rotation_depth": 1,
        "ancestor_count": 1,
        "descendant_count": 1,
        "terminal_status": "active",
    }
    assert summarize_credential_rotation(credential_lineage) == {
        "credential_id": "cred-current",
        "replacement_for_credential_id": "cred-root",
        "rotation_depth": 1,
        "ancestor_count": 1,
        "descendant_count": 1,
        "has_rotation_history": True,
    }


def test_signing_registry_diagnostics_reports_reference_consistency(monkeypatch):
    monkeypatch.setenv(
        "CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY",
        '[{"key_id":"kid_retired123456","issuer":"central","algorithm":"hmac-sha256-placeholder","schema":"darts.placeholder_signing_profile.v1","status":"retired"}]',
    )
    active_key_id = get_placeholder_signing_profile()["key_id"]
    device = _device(credential_key_id="kid_retired123456")
    credential = _credential(
        fingerprint="abc123",
        details_json={
            "key_id": derive_key_id(fingerprint="abc123"),
            "issuer": {
                "issuer": "central",
                "key_id": active_key_id,
                "algorithm": "hmac-sha256-placeholder",
                "schema": "darts.placeholder_signing_profile.v1",
            },
        },
    )
    lease = _lease(details_json={
        "mode": "placeholder",
        "lease_key_id": active_key_id,
        "issuer": {
            "issuer": "central",
            "key_id": "kid_retired123456",
            "algorithm": "hmac-sha256-placeholder",
            "schema": "darts.placeholder_signing_profile.v1",
        },
    })

    diagnostics = build_signing_registry_diagnostics(device=device, credential=credential, lease=lease)

    assert diagnostics["registry_size"] == 2
    assert diagnostics["status_counts"] == {"active": 1, "retired": 1}
    assert diagnostics["referenced_keys"]["lease_issuer_key_id"]["entry"]["status"] == "retired"
    assert diagnostics["credential_rotation"]["rotation_depth"] == 0
    assert diagnostics["key_lineage"]["lease_issuer_key_id"]["rotation_depth"] == 0
    assert diagnostics["consistency"] == {
        "active_profile_matches_credential_issuer": True,
        "active_profile_matches_lease_issuer": False,
        "lease_key_matches_lease_issuer": False,
        "device_key_matches_credential_key": False,
    }


def test_operator_safe_signing_registry_keeps_compact_rotation_and_terminal_status():
    payload = _to_operator_safe_signing_registry({
        "registry_size": 3,
        "status_counts": {"active": 1, "retired": 1, "revoked": 1},
        "consistency": {"lease_key_matches_lease_issuer": False},
        "credential_rotation": {
            "credential_id": "cred-current",
            "replacement_for_credential_id": "cred-root",
            "rotation_depth": 1,
            "ancestors": [{"credential_id": "cred-root"}],
            "descendants": [{"credential_id": "cred-next"}],
        },
        "key_lineage": {
            "lease_key_id": {
                "key_id": "kid-active",
                "present": True,
                "parent_key_id": "kid-root",
                "rotation_depth": 1,
                "status_path": [{"key_id": "kid-active", "status": "active"}],
            }
        },
        "support_summary": {"revoked_reference_names": ["device_credential_key_id"]},
    })

    assert payload == {
        "registry_size": 3,
        "status_counts": {"active": 1, "retired": 1, "revoked": 1},
        "consistency": {"lease_key_matches_lease_issuer": False},
        "credential_rotation": {
            "credential_id": "cred-current",
            "replacement_for_credential_id": "cred-root",
            "rotation_depth": 1,
            "ancestor_count": 1,
            "descendant_count": 1,
            "detail_level": "operator_safe",
        },
        "key_lineage": {
            "lease_key_id": {
                "key_id": "kid-active",
                "present": True,
                "terminal_status": "active",
                "rotation_depth": 1,
                "parent_key_id": "kid-root",
                "detail_level": "operator_safe",
            }
        },
        "support_summary": {
            "revoked_reference_names": ["device_credential_key_id"],
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }


def test_operator_safe_issuer_profiles_keeps_transition_summary():
    payload = _to_operator_safe_issuer_profiles({
        "active_profile": {"key_id": "kid-current"},
        "configured_profile": {"key_id": "kid-next"},
        "effective_profile": {"key_id": "kid-next"},
        "effective_lineage_summary": {"rotation_depth": 1},
        "history": [{
            "credential_id": "cred-current",
            "credential_status": "active",
            "replacement_for_credential_id": "cred-root",
            "issued_at": "2026-04-13T12:00:00+00:00",
            "revoked_at": None,
            "key_id": "kid-next",
            "issuer": "central",
            "status": "active",
            "registry_status": "known",
            "parent_key_id": "kid-root",
        }],
        "support_summary": {
            "effective_source": "lease",
            "transition": {
                "transition_state": "rotated",
                "mismatch_reasons": ["active_profile_differs_from_effective"],
            },
        },
    })

    assert payload["support_summary"] == {
        "effective_source": "lease",
        "transition": {
            "transition_state": "rotated",
            "mismatch_reasons": ["active_profile_differs_from_effective"],
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }
    assert payload["readback_summary"] == {
        "lineage_explanation": {
            "effective_key_id": "kid-next",
            "effective_source": "lease",
            "lineage_state": None,
            "lineage_note": None,
            "transition_state": "rotated",
            "rotation_depth": 1,
            "parent_key_id": None,
            "terminal_status": None,
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }
    assert payload["history_summary"] == {"detail_level": "operator_safe"}


def test_operator_safe_issuer_profiles_backfills_lineage_explanation_when_missing():
    payload = _to_operator_safe_issuer_profiles({
        "effective_profile": {"key_id": "kid-next"},
        "effective_lineage_summary": {
            "rotation_depth": 2,
            "parent_key_id": "kid-parent",
            "terminal_status": "retired",
        },
        "support_summary": {
            "effective_source": "credential",
            "transition": {"transition_state": "retired"},
        },
        "readback_summary": {
            "effective_source": "credential",
            "lineage_state": "retired",
            "lineage_note": "effective key is present but marked retired in the central registry",
        },
    })

    assert payload["readback_summary"]["lineage_explanation"] == {
        "effective_key_id": "kid-next",
        "effective_source": "credential",
        "lineage_state": "retired",
        "lineage_note": "effective key is present but marked retired in the central registry",
        "transition_state": "retired",
        "rotation_depth": 2,
        "parent_key_id": "kid-parent",
        "terminal_status": "retired",
        "detail_level": "operator_safe",
    }


def test_build_issuer_lineage_explanation_prefers_existing_compact_contract():
    assert build_support_diagnostics_compact_summary(
        issuer_profiles={
            "effective_profile": {"key_id": "kid-fallback"},
            "effective_lineage_summary": {
                "rotation_depth": 1,
                "parent_key_id": "kid-parent",
                "terminal_status": "retired",
            },
            "support_summary": {
                "effective_source": "lease",
                "transition": {"transition_state": "rotated"},
            },
            "readback_summary": {
                "lineage_state": "rotated",
                "lineage_note": "fallback note",
                "lineage_explanation": {
                    "effective_key_id": "kid-compact",
                    "effective_source": "credential",
                    "lineage_state": "revoked",
                    "lineage_note": "compact note",
                    "transition_state": "revoked",
                    "rotation_depth": 3,
                    "parent_key_id": "kid-compact-parent",
                    "terminal_status": "revoked",
                },
            },
        },
        signing_registry={},
        now=datetime(2026, 4, 13, 22, 34, tzinfo=UTC),
    )["support_notes"]["lineage_explanation"] == {
        "effective_key_id": "kid-compact",
        "effective_source": "credential",
        "lineage_state": "revoked",
        "lineage_note": "compact note",
        "transition_state": "revoked",
        "rotation_depth": 3,
        "parent_key_id": "kid-compact-parent",
        "terminal_status": "revoked",
        "detail_level": "support_compact",
    }


def test_build_support_contract_source_summary_publishes_upstream_compact_contracts():
    payload = build_support_contract_source_summary(
        issuer_profiles={
            "readback_summary": {
                "lineage_state": "rotated",
                "effective_source": "lease",
                "lineage_explanation": {"effective_key_id": "kid-1"},
            },
            "history_summary": {
                "history_state": "single_entry",
                "narrative_state": "single_entry",
                "history_count": 1,
            },
        },
        material_history={
            "readback_summary": {
                "credential_history": {"alignment_state": "aligned"},
                "lease_history": {"alignment_state": "drifted"},
                "summary": "credentials=1 / leases=2",
            },
        },
    )

    assert payload == {
        "issuer_profile_readback": {
            "schema": "darts.issuer_profile_readback_summary.v1",
            "detail_level": "support_compact",
            "present": True,
            "source_state": "present",
            "lineage_state": "rotated",
            "effective_source": "lease",
            "has_lineage_explanation": True,
            "has_effective_source_reason": False,
            "has_mismatch_summary": False,
        },
        "issuer_history": {
            "schema": "darts.issuer_history_summary.v1",
            "detail_level": "support_compact",
            "present": True,
            "source_state": "present",
            "history_state": "single_entry",
            "narrative_state": "single_entry",
            "history_count": 1,
            "replacement_relation": None,
            "has_narrative": False,
        },
        "material_history_readback": {
            "schema": "darts.material_history.readback_summary.v1",
            "detail_level": "support_compact",
            "present": True,
            "source_state": "present",
            "credential_alignment": "aligned",
            "lease_alignment": "drifted",
            "credential_history_count": None,
            "lease_history_count": None,
            "has_summary": True,
        },
    }



def test_build_support_contract_state_summary_classifies_present_missing_and_derived_contracts():
    payload = build_support_contract_state_summary(
        source_contracts={
            "issuer_profile_readback": {
                "present": True,
                "source_state": "present",
            },
            "issuer_history": {
                "present": False,
                "source_state": "missing",
            },
            "material_history_readback": {
                "present": False,
                "source_state": "derived_from_material_history",
            },
        }
    )

    assert payload == {
        "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
        "detail_level": "support_compact",
        "overall_state": "derived_present",
        "coverage_state": "full_set",
        "verdict": "canonical_derived",
        "verdict_text": "canonical compact source contracts are visible with at least one derived readback",
        "state_counts": {
            "present": 1,
            "missing": 1,
            "derived_from_material_history": 1,
            "detail_level": "support_compact",
        },
        "total_contracts": 3,
        "expected_contract_count": 3,
        "observed_contract_count": 3,
        "present_contract_count": 1,
        "derived_contract_count": 1,
        "missing_contract_count": 1,
        "observed_extra_count": 0,
        "missing_expected_count": 0,
        "has_present_contracts": True,
        "has_derived_contracts": True,
        "has_missing_contracts": True,
        "has_unexpected_contracts": False,
        "has_missing_expected_contracts": False,
        "expected_names": [
            "issuer_profile_readback",
            "issuer_history",
            "material_history_readback",
        ],
        "observed_names": [
            "issuer_history",
            "issuer_profile_readback",
            "material_history_readback",
        ],
        "missing_expected_names": [],
        "unexpected_names": [],
        "source_states": {
            "issuer_profile_readback": "present",
            "issuer_history": "missing",
            "material_history_readback": "derived_from_material_history",
            "detail_level": "support_compact",
        },
        "present_names": ["issuer_profile_readback"],
        "derived_names": ["material_history_readback"],
        "missing_names": ["issuer_history"],
        "summary": "present=1, derived=1, missing=1",
    }


def test_support_contract_state_summary_marks_partial_observed_contract_sets():
    payload = build_support_contract_state_summary(
        source_contracts={
            "issuer_profile_readback": {
                "present": True,
                "source_state": "present",
            },
        }
    )

    assert payload == {
        "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
        "detail_level": "support_compact",
        "overall_state": "partial",
        "coverage_state": "partial_set",
        "verdict": "contracts_incomplete",
        "verdict_text": "expected compact source contracts are missing from the observed set",
        "state_counts": {
            "present": 1,
            "missing": 2,
            "derived_from_material_history": 0,
            "detail_level": "support_compact",
        },
        "total_contracts": 3,
        "expected_contract_count": 3,
        "observed_contract_count": 1,
        "present_contract_count": 1,
        "derived_contract_count": 0,
        "missing_contract_count": 2,
        "observed_extra_count": 0,
        "missing_expected_count": 2,
        "has_present_contracts": True,
        "has_derived_contracts": False,
        "has_missing_contracts": True,
        "has_unexpected_contracts": False,
        "has_missing_expected_contracts": True,
        "expected_names": [
            "issuer_profile_readback",
            "issuer_history",
            "material_history_readback",
        ],
        "observed_names": ["issuer_profile_readback"],
        "missing_expected_names": ["issuer_history", "material_history_readback"],
        "unexpected_names": [],
        "source_states": {
            "issuer_profile_readback": "present",
            "issuer_history": "missing",
            "material_history_readback": "missing",
            "detail_level": "support_compact",
        },
        "present_names": ["issuer_profile_readback"],
        "derived_names": [],
        "missing_names": ["issuer_history", "material_history_readback"],
        "summary": "present=1, missing=2",
    }


def test_support_contract_state_summary_tracks_unexpected_extra_contracts():
    payload = build_support_contract_state_summary(
        source_contracts={
            "issuer_profile_readback": {
                "present": True,
                "source_state": "present",
            },
            "issuer_history": {
                "present": True,
                "source_state": "present",
            },
            "material_history_readback": {
                "present": False,
                "source_state": "missing",
            },
            "issuer_transition_bridge": {
                "present": True,
                "source_state": "present",
            },
        }
    )

    assert payload == {
        "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
        "detail_level": "support_compact",
        "overall_state": "partial",
        "coverage_state": "full_set",
        "verdict": "contracts_extended",
        "verdict_text": "all expected compact source contracts are present and additional unexpected contracts were observed",
        "state_counts": {
            "present": 3,
            "missing": 1,
            "derived_from_material_history": 0,
            "detail_level": "support_compact",
        },
        "total_contracts": 4,
        "expected_contract_count": 3,
        "observed_contract_count": 4,
        "present_contract_count": 3,
        "derived_contract_count": 0,
        "missing_contract_count": 1,
        "observed_extra_count": 1,
        "missing_expected_count": 0,
        "has_present_contracts": True,
        "has_derived_contracts": False,
        "has_missing_contracts": True,
        "has_unexpected_contracts": True,
        "has_missing_expected_contracts": False,
        "expected_names": [
            "issuer_profile_readback",
            "issuer_history",
            "material_history_readback",
        ],
        "observed_names": [
            "issuer_history",
            "issuer_profile_readback",
            "issuer_transition_bridge",
            "material_history_readback",
        ],
        "missing_expected_names": [],
        "unexpected_names": ["issuer_transition_bridge"],
        "source_states": {
            "issuer_profile_readback": "present",
            "issuer_history": "present",
            "material_history_readback": "missing",
            "issuer_transition_bridge": "present",
            "detail_level": "support_compact",
        },
        "present_names": ["issuer_history", "issuer_profile_readback", "issuer_transition_bridge"],
        "derived_names": [],
        "missing_names": ["material_history_readback"],
        "summary": "present=3, missing=1",
    }



def test_support_contract_state_summary_marks_missing_plus_extra_as_drifted():
    payload = build_support_contract_state_summary(
        source_contracts={
            "issuer_profile_readback": {
                "present": True,
                "source_state": "present",
            },
            "issuer_transition_bridge": {
                "present": True,
                "source_state": "present",
            },
        }
    )

    assert payload["verdict"] == "contracts_drifted"
    assert payload["verdict_text"] == (
        "expected compact source contracts are missing and unexpected contracts are also present"
    )
    assert payload["missing_expected_names"] == ["issuer_history", "material_history_readback"]
    assert payload["unexpected_names"] == ["issuer_transition_bridge"]



def test_support_contract_source_summary_exposes_compact_presence_markers():
    payload = build_support_contract_source_summary(
        issuer_profiles={
            "readback_summary": {
                "lineage_state": "rotated",
                "effective_source": "lease",
                "lineage_explanation": {"effective_key_id": "kid-1"},
                "effective_source_reason": "lease issuer metadata currently drives the effective issuer profile",
                "mismatch_summary": "active_profile_differs_from_effective",
            },
            "history_summary": {
                "history_state": "rotated",
                "narrative_state": "rotated",
                "history_count": 2,
                "replacement_relation": "declared_replacement",
                "narrative": "latest visible credential cred-2 replaced cred-1",
            },
        },
        material_history={
            "readback_summary": {
                "credential_history": {"alignment_state": "aligned", "history_count": 2},
                "lease_history": {"alignment_state": "drifted", "history_count": 3},
                "summary": "credentials=2 / leases=3",
            },
        },
    )

    assert payload == {
        "issuer_profile_readback": {
            "schema": "darts.issuer_profile_readback_summary.v1",
            "detail_level": "support_compact",
            "present": True,
            "source_state": "present",
            "lineage_state": "rotated",
            "effective_source": "lease",
            "has_lineage_explanation": True,
            "has_effective_source_reason": True,
            "has_mismatch_summary": True,
        },
        "issuer_history": {
            "schema": "darts.issuer_history_summary.v1",
            "detail_level": "support_compact",
            "present": True,
            "source_state": "present",
            "history_state": "rotated",
            "narrative_state": "rotated",
            "history_count": 2,
            "replacement_relation": "declared_replacement",
            "has_narrative": True,
        },
        "material_history_readback": {
            "schema": "darts.material_history.readback_summary.v1",
            "detail_level": "support_compact",
            "present": True,
            "source_state": "present",
            "credential_alignment": "aligned",
            "lease_alignment": "drifted",
            "credential_history_count": 2,
            "lease_history_count": 3,
            "has_summary": True,
        },
    }


def test_support_contract_source_summary_marks_material_readback_fallback_origin():
    payload = build_support_contract_source_summary(
        issuer_profiles={},
        material_history={
            "credential_history": {
                "history_count": 1,
                "active_credential_id": "cred-1",
                "latest": {"credential_id": "cred-1"},
            },
            "lease_history": {
                "history_count": 1,
                "current_lease_id": "lease-1",
                "latest": {"lease_id": "lease-1"},
            },
            "summary": "credentials=1 / leases=1",
        },
    )

    assert payload == {
        "issuer_profile_readback": {
            "schema": "darts.issuer_profile_readback_summary.v1",
            "detail_level": "support_compact",
            "present": False,
            "source_state": "missing",
            "lineage_state": None,
            "effective_source": None,
            "has_lineage_explanation": False,
            "has_effective_source_reason": False,
            "has_mismatch_summary": False,
        },
        "issuer_history": {
            "schema": "darts.issuer_history_summary.v1",
            "detail_level": "support_compact",
            "present": False,
            "source_state": "missing",
            "history_state": None,
            "narrative_state": None,
            "history_count": None,
            "replacement_relation": None,
            "has_narrative": False,
        },
        "material_history_readback": {
            "schema": "darts.material_history.readback_summary.v1",
            "detail_level": "support_compact",
            "present": False,
            "source_state": "derived_from_material_history",
            "credential_alignment": "aligned",
            "lease_alignment": "aligned",
            "credential_history_count": 1,
            "lease_history_count": 1,
            "has_summary": True,
        },
    }



def test_support_diagnostics_contract_summary_carries_stable_classification_markers():
    payload = build_support_diagnostics_compact_summary(
        issuer_profiles={
            "support_summary": {
                "effective_source": "credential",
                "effective_key_id": "kid_active",
                "effective_status": "retired",
                "history_count": 1,
                "transition": {
                    "transition_state": "retired",
                    "mismatch_reasons": [],
                },
            },
            "readback_summary": {
                "lineage_state": "retired",
                "effective_source_reason": "credential issuer metadata currently drives the effective issuer profile",
                "lineage_note": "effective key is present but marked retired in the central registry",
            },
            "history_summary": {
                "history_state": "single_entry",
                "narrative_state": "single_entry",
            },
        },
        signing_registry={
            "registry_size": 1,
            "status_counts": {"retired": 1},
            "support_summary": {},
        },
        material_history={
            "readback_summary": {
                "credential_history": {"alignment_state": "latest_only"},
                "lease_history": {"alignment_state": "empty"},
            },
        },
        now=datetime(2026, 4, 13, 22, 34, tzinfo=UTC),
    )

    assert payload["contract_summary"] == {
        "schema": "darts.support_diagnostics.compact_summary.v1",
        "detail_level": "support_compact",
        "issuer_state": {
            "transition_state": "retired",
            "lineage_state": "retired",
            "effective_status": "retired",
            "effective_source": "credential",
            "history_state": "single_entry",
            "history_narrative_state": "single_entry",
            "detail_level": "support_compact",
        },
        "material_state": {
            "credential_alignment": "latest_only",
            "lease_alignment": "empty",
            "has_credential_timestamps": False,
            "has_lease_timestamps": False,
            "detail_level": "support_compact",
        },
        "signing_state": {
            "has_reference_flags": False,
            "reference_flag_count": 0,
            "registry_size": 1,
            "detail_level": "support_compact",
        },
        "provenance_state": {
            "overall_state": "complete",
            "coverage_state": "full_set",
            "verdict": "canonical_complete",
            "verdict_text": "all canonical compact source contracts are present",
            "total_contracts": 3,
            "expected_contract_count": 3,
            "observed_contract_count": 3,
            "present_contract_count": 3,
            "derived_contract_count": 0,
            "missing_contract_count": 0,
            "missing_expected_count": 0,
            "observed_extra_count": 0,
            "has_missing_expected_contracts": False,
            "has_unexpected_contracts": False,
            "expected_names": [
                "issuer_profile_readback",
                "issuer_history",
                "material_history_readback",
            ],
            "observed_names": [
                "issuer_history",
                "issuer_profile_readback",
                "material_history_readback",
            ],
            "present_names": [
                "issuer_history",
                "issuer_profile_readback",
                "material_history_readback",
            ],
            "derived_names": [],
            "missing_names": [],
            "missing_expected_names": [],
            "unexpected_names": [],
            "summary": "present=3",
            "detail_level": "support_compact",
        },
    }


def test_finalize_endpoint_summary_stamps_compact_contract_subblocks():
    payload = _finalize_endpoint_summary(
        {
            "contract_summary": {
                "schema": "darts.support_diagnostics.compact_summary.v1",
                "detail_level": "support_compact",
                "issuer_state": {"transition_state": "rotated"},
                "material_state": {"credential_alignment": "aligned"},
                "signing_state": {"registry_size": 2},
                "provenance_state": {
                    "overall_state": "partial",
                    "verdict": "contracts_incomplete",
                    "verdict_text": "expected compact source contracts are missing from the observed set",
                    "missing_expected_count": 1,
                    "observed_extra_count": 0,
                    "present_names": ["issuer_profile_readback", "issuer_history"],
                    "derived_names": [],
                    "missing_names": ["material_history_readback"],
                    "missing_expected_names": ["material_history_readback"],
                    "unexpected_names": [],
                    "summary": "present=2, missing=1",
                },
            },
            "support_notes": {
                "history_state": {"history_state": "single_entry"},
                "material_alignment": {"credential": "aligned"},
                "lineage_explanation": {"effective_key_id": "kid-1"},
                "source_contracts": {
                    "issuer_profile_readback": {"schema": "darts.issuer_profile_readback_summary.v1"},
                },
                "source_contract_summary": {
                    "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
                    "overall_state": "partial",
                },
            },
        },
        detail_level="operator_safe",
    )

    assert payload == {
        "contract_summary": {
            "schema": "darts.support_diagnostics.compact_summary.v1",
            "detail_level": "operator_safe",
            "issuer_state": {"transition_state": "rotated", "detail_level": "operator_safe"},
            "material_state": {"credential_alignment": "aligned", "detail_level": "operator_safe"},
            "signing_state": {"registry_size": 2, "detail_level": "operator_safe"},
            "provenance_state": {
                "overall_state": "partial",
                "missing_expected_count": 1,
                "observed_extra_count": 0,
                "present_names": ["issuer_profile_readback", "issuer_history"],
                "derived_names": [],
                "missing_names": ["material_history_readback"],
                "missing_expected_names": ["material_history_readback"],
                "unexpected_names": [],
                "summary": "present=2, missing=1",
                "detail_level": "operator_safe",
            },
        },
        "support_notes": {
            "history_state": {"history_state": "single_entry", "detail_level": "operator_safe"},
            "material_alignment": {"credential": "aligned", "detail_level": "operator_safe"},
            "lineage_explanation": {"effective_key_id": "kid-1", "detail_level": "operator_safe"},
            "source_contracts": {
                "issuer_profile_readback": {
                    "schema": "darts.issuer_profile_readback_summary.v1",
                    "detail_level": "operator_safe",
                },
            },
            "source_contract_summary": {
                "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
                "overall_state": "partial",
                "detail_level": "operator_safe",
            },
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
        "issuer_state": None,
        "signing_state": None,
        "material_timestamps": None,
        "history_state": None,
        "material_history": None,
        "material_readback_summary": None,
    }



def test_compact_support_summary_provenance_state_mirrors_name_lists():
    payload = build_support_diagnostics_compact_summary(
        issuer_profiles={
            "readback_summary": {
                "lineage_state": "rotated",
                "effective_source": "lease",
                "lineage_explanation": {"effective_key_id": "kid-1"},
            },
        },
        signing_registry={},
        material_history={
            "credential_history": {
                "history_count": 1,
                "active_credential_id": "cred-1",
                "latest": {"credential_id": "cred-1"},
            },
            "lease_history": {
                "history_count": 1,
                "current_lease_id": "lease-1",
                "latest": {"lease_id": "lease-1"},
            },
            "summary": "credentials=1 / leases=1",
        },
        now=datetime(2026, 4, 13, 22, 34, tzinfo=UTC),
    )

    assert payload["contract_summary"]["provenance_state"] == {
        "overall_state": "derived_present",
        "coverage_state": "full_set",
        "verdict": "canonical_derived",
        "verdict_text": "canonical compact source contracts are visible with at least one derived readback",
        "total_contracts": 3,
        "expected_contract_count": 3,
        "observed_contract_count": 3,
        "present_contract_count": 1,
        "derived_contract_count": 1,
        "missing_contract_count": 1,
        "missing_expected_count": 0,
        "observed_extra_count": 0,
        "has_missing_expected_contracts": False,
        "has_unexpected_contracts": False,
        "expected_names": [
            "issuer_profile_readback",
            "issuer_history",
            "material_history_readback",
        ],
        "observed_names": [
            "issuer_history",
            "issuer_profile_readback",
            "material_history_readback",
        ],
        "present_names": ["issuer_profile_readback"],
        "derived_names": ["material_history_readback"],
        "missing_names": ["issuer_history"],
        "missing_expected_names": [],
        "unexpected_names": [],
        "summary": "present=1, derived=1, missing=1",
        "detail_level": "support_compact",
    }


def test_compact_reconciliation_summary_stamps_nested_transition_and_lineage_contracts():
    payload = _finalize_device_trust_detail(
        {
            "device": {"id": "dev-1", "device_name": "Board 1", "status": "active"},
            "reconciliation_summary": {
                "ok": True,
                "status_counts": {"warning": 1},
                "issuer_profiles": {
                    "effective_key_id": "kid-active",
                    "effective_source": "lease",
                    "transition": {
                        "transition_state": "rotated",
                        "mismatch_reasons": ["active_profile_differs_from_effective"],
                    },
                    "lineage_explanation": {
                        "effective_key_id": "kid-active",
                        "effective_source": "lease",
                    },
                    "readback_summary": {
                        "effective_source": "lease",
                        "lineage_explanation": {
                            "effective_key_id": "kid-active",
                            "effective_source": "lease",
                        },
                    },
                    "history_summary": {
                        "history_state": "rotated",
                        "history_count": 2,
                    },
                    "source_contracts": {
                        "issuer_profile_readback": {
                            "schema": "darts.issuer_profile_readback_summary.v1",
                        },
                        "issuer_history": {
                            "schema": "darts.issuer_history_summary.v1",
                        },
                    },
                    "source_contract_summary": {
                        "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
                        "overall_state": "partial",
                    },
                },
                "material_readback_summary": {
                    "credential_history": {
                        "alignment_state": "aligned",
                        "history_count": 1,
                    },
                    "lease_history": {
                        "alignment_state": "drifted",
                        "history_count": 2,
                    },
                },
                "support_summary": {"retired_reference_names": ["lease_key_id"]},
            },
        },
        SimpleNamespace(role="owner", role_level=3),
    )

    issuer_profiles = payload["reconciliation_summary"]["issuer_profiles"]
    assert issuer_profiles == {
        "effective_key_id": "kid-active",
        "effective_source": "lease",
        "transition": {
            "transition_state": "rotated",
            "mismatch_reasons": ["active_profile_differs_from_effective"],
        },
        "lineage_explanation": {
            "effective_key_id": "kid-active",
            "effective_source": "lease",
        },
        "readback_summary": {
            "effective_source": "lease",
            "lineage_explanation": {
                "effective_key_id": "kid-active",
                "effective_source": "lease",
            },
        },
        "history_summary": {
            "history_state": "rotated",
            "history_count": 2,
        },
        "source_contracts": {
            "issuer_profile_readback": {
                "schema": "darts.issuer_profile_readback_summary.v1",
            },
            "issuer_history": {
                "schema": "darts.issuer_history_summary.v1",
            },
        },
        "source_contract_summary": {
            "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
            "overall_state": "partial",
        },
    }
    assert payload["reconciliation_summary"]["material_readback_summary"] == {
        "credential_history": {
            "alignment_state": "aligned",
            "history_count": 1,
        },
        "lease_history": {
            "alignment_state": "drifted",
            "history_count": 2,
        },
    }
    assert payload["reconciliation_summary"]["support_summary"] == {
        "retired_reference_names": ["lease_key_id"],
    }


def test_support_diagnostics_compact_summary_explains_rotation_and_timestamps():
    now = datetime(2026, 4, 13, 22, 34, tzinfo=UTC)
    credential = _credential(
        status="active",
        issued_at=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    lease = _lease(
        issued_at=datetime(2026, 4, 13, 13, 0, tzinfo=UTC),
        expires_at=datetime(2026, 4, 14, 13, 0, tzinfo=UTC),
        grace_until=datetime(2026, 4, 15, 13, 0, tzinfo=UTC),
    )

    payload = build_support_diagnostics_compact_summary(
        issuer_profiles={
            "support_summary": {
                "effective_source": "lease",
                "effective_key_id": "kid_active",
                "effective_status": "active",
                "history_count": 2,
                "transition": {
                    "transition_state": "rotated",
                    "mismatch_reasons": ["active_profile_differs_from_effective"],
                },
            },
            "readback_summary": {
                "lineage_state": "rotated",
                "effective_source_reason": "lease issuer metadata currently drives the effective issuer profile",
                "lineage_note": "effective key sits on a recorded parent rotation chain",
                "mismatch_summary": "active_profile_differs_from_effective",
            },
        },
        signing_registry={
            "registry_size": 3,
            "status_counts": {"active": 1, "retired": 1, "revoked": 1},
            "support_summary": {
                "unknown_reference_names": ["credential_key_id"],
                "retired_reference_names": ["lease_issuer_key_id"],
                "revoked_reference_names": ["lease_key_id"],
                "inconsistent_reference_names": ["lease_key_matches_lease_issuer"],
            },
        },
        credential=credential,
        lease=lease,
        now=now,
    )

    assert payload["generated_at"] == "2026-04-13T22:34:00+00:00"
    assert payload["contract_summary"] == {
        "schema": "darts.support_diagnostics.compact_summary.v1",
        "detail_level": "support_compact",
        "issuer_state": {
            "transition_state": "rotated",
            "lineage_state": "rotated",
            "effective_status": "active",
            "effective_source": "lease",
            "history_state": None,
            "history_narrative_state": None,
            "detail_level": "support_compact",
        },
        "material_state": {
            "credential_alignment": "empty",
            "lease_alignment": "empty",
            "has_credential_timestamps": True,
            "has_lease_timestamps": True,
            "detail_level": "support_compact",
        },
        "signing_state": {
            "has_reference_flags": True,
            "reference_flag_count": 4,
            "registry_size": 3,
            "detail_level": "support_compact",
        },
        "provenance_state": {
            "overall_state": "partial",
            "coverage_state": "full_set",
            "verdict": "contracts_partial",
            "verdict_text": "compact source contracts are in a partial state",
            "present_contract_count": 1,
            "derived_contract_count": 0,
            "missing_contract_count": 2,
            "missing_expected_count": 0,
            "observed_extra_count": 0,
            "has_missing_expected_contracts": False,
            "has_unexpected_contracts": False,
            "present_names": ["issuer_profile_readback"],
            "derived_names": [],
            "missing_names": ["issuer_history", "material_history_readback"],
            "missing_expected_names": [],
            "unexpected_names": [],
            "summary": "present=1, missing=2",
            "detail_level": "support_compact",
        },
    }
    assert payload["issuer_state"]["effective_key_id"] == "kid_active"
    assert payload["issuer_state"]["detail_level"] == "support_compact"
    assert payload["support_notes"]["lineage_explanation"]["effective_key_id"] is None
    assert payload["support_notes"]["source_contracts"]["issuer_profile_readback"]["present"] is True
    assert payload["support_notes"]["source_contract_summary"]["state_counts"] == {
        "present": 1,
        "missing": 2,
        "derived_from_material_history": 0,
        "detail_level": "support_compact",
    }
    assert payload["material_readback_summary"]["credential_history"]["status_counts"] == {
        "detail_level": "support_compact"
    }
    assert payload["material_history"]["credential_history"]["status_counts"] == {
        "detail_level": "support_compact"
    }
