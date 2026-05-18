from __future__ import annotations

from central_server.device_trust import (
    build_credential_rotation_lineage,
    build_placeholder_signed_lease,
    build_reconciliation_summary,
    build_signing_key_lineage,
    compute_lease_status,
    get_stored_signed_lease_bundle,
    summarize_credential_rotation,
    summarize_lineage,
    verify_placeholder_certificate,
    verify_placeholder_signed_lease,
)
from central_server.models import CentralDevice, DeviceCredential, DeviceLease


def can_view_internal_device_detail(user) -> bool:
    return getattr(user, "role", None) in {"installer", "superadmin"}


def _can_view_internal_device_detail(user) -> bool:
    return can_view_internal_device_detail(user)


def safe_iso(dt):
    if not dt:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def serialize_device_credential(credential: DeviceCredential, device: CentralDevice = None) -> dict:
    payload = {
        "id": credential.id,
        "device_id": credential.device_id,
        "status": credential.status,
        "credential_kind": credential.credential_kind,
        "fingerprint": credential.fingerprint,
        "issued_at": safe_iso(credential.issued_at),
        "expires_at": safe_iso(credential.expires_at),
        "revoked_at": safe_iso(credential.revoked_at),
        "replacement_for_credential_id": credential.replacement_for_credential_id,
        "metadata": credential.details_json or {},
        "key_id": (credential.details_json or {}).get("key_id"),
        "created_at": safe_iso(credential.created_at),
        "updated_at": safe_iso(credential.updated_at),
    }
    payload["verification"] = verify_placeholder_certificate(credential=credential, device=device)
    payload["rotation"] = build_credential_rotation_lineage(credential=credential)
    payload["rotation_summary"] = summarize_credential_rotation(payload["rotation"])
    payload["signing_key_lineage"] = build_signing_key_lineage(key_id=(credential.details_json or {}).get("key_id"))
    payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


def serialize_device_credential_summary(credential: DeviceCredential, device: CentralDevice = None) -> dict:
    payload = {
        "id": credential.id,
        "device_id": credential.device_id,
        "status": credential.status,
        "credential_kind": credential.credential_kind,
        "fingerprint": credential.fingerprint,
        "issued_at": safe_iso(credential.issued_at),
        "expires_at": safe_iso(credential.expires_at),
        "revoked_at": safe_iso(credential.revoked_at),
        "replacement_for_credential_id": credential.replacement_for_credential_id,
        "key_id": (credential.details_json or {}).get("key_id"),
        "created_at": safe_iso(credential.created_at),
        "updated_at": safe_iso(credential.updated_at),
    }
    payload["verification"] = verify_placeholder_certificate(credential=credential, device=device)
    payload["rotation"] = build_credential_rotation_lineage(credential=credential)
    payload["rotation_summary"] = summarize_credential_rotation(payload["rotation"])
    payload["signing_key_lineage"] = build_signing_key_lineage(key_id=(credential.details_json or {}).get("key_id"))
    payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


def serialize_device_lease(lease: DeviceLease, device: CentralDevice = None, credential: DeviceCredential = None) -> dict:
    payload = {
        "id": lease.id,
        "device_id": lease.device_id,
        "central_license_id": lease.central_license_id,
        "lease_id": lease.lease_id,
        "status": lease.status,
        "computed_status": compute_lease_status(lease),
        "issued_at": safe_iso(lease.issued_at),
        "expires_at": safe_iso(lease.expires_at),
        "grace_until": safe_iso(lease.grace_until),
        "revoked_at": safe_iso(lease.revoked_at),
        "signature": lease.signature,
        "metadata": lease.details_json or {},
        "created_at": safe_iso(lease.created_at),
        "updated_at": safe_iso(lease.updated_at),
    }
    stored_bundle = get_stored_signed_lease_bundle(lease)
    bundle = stored_bundle
    if bundle is None and device is not None:
        bundle = build_placeholder_signed_lease(device=device, lease=lease, credential=credential)
    if bundle is not None:
        payload["signed_bundle"] = bundle
        payload["signed_bundle_source"] = "stored" if stored_bundle is not None else "rebuilt"
        payload["verification"] = verify_placeholder_signed_lease(bundle=bundle, device=device, lease=lease, credential=credential)
        payload["signing_key_lineage"] = build_signing_key_lineage(key_id=bundle.get("key_id"))
        payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


def serialize_device_lease_summary(lease: DeviceLease, device: CentralDevice = None, credential: DeviceCredential = None) -> dict:
    payload = {
        "id": lease.id,
        "device_id": lease.device_id,
        "central_license_id": lease.central_license_id,
        "lease_id": lease.lease_id,
        "status": lease.status,
        "computed_status": compute_lease_status(lease),
        "issued_at": safe_iso(lease.issued_at),
        "expires_at": safe_iso(lease.expires_at),
        "grace_until": safe_iso(lease.grace_until),
        "revoked_at": safe_iso(lease.revoked_at),
        "created_at": safe_iso(lease.created_at),
        "updated_at": safe_iso(lease.updated_at),
    }
    stored_bundle = get_stored_signed_lease_bundle(lease)
    bundle = stored_bundle
    if bundle is None and device is not None:
        bundle = build_placeholder_signed_lease(device=device, lease=lease, credential=credential)
    if bundle is not None:
        payload["verification"] = verify_placeholder_signed_lease(bundle=bundle, device=device, lease=lease, credential=credential)
        payload["signed_bundle_source"] = "stored" if stored_bundle is not None else "rebuilt"
        payload["signing_key_lineage"] = build_signing_key_lineage(key_id=bundle.get("key_id"))
        payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


_OPERATOR_SAFE_DEVICE_SUMMARY_INTERNAL_KEYS = {
    "api_key_preview",
    "install_id",
    "trust_reason",
    "credential_fingerprint",
    "lease_id",
    "last_error",
}

_OPERATOR_SAFE_DEVICE_DETAIL_INTERNAL_KEYS = {
    "health_snapshot",
    "device_logs",
    "lease_metadata",
}


def _apply_operator_safe_device_summary(device_summary: dict) -> dict:
    payload = dict(device_summary)
    for key in _OPERATOR_SAFE_DEVICE_SUMMARY_INTERNAL_KEYS:
        payload.pop(key, None)
    payload["detail_level"] = "operator_safe"
    return payload


def finalize_device_summary(device_summary: dict, user) -> dict:
    payload = dict(device_summary)
    payload.setdefault("detail_level", "internal" if can_view_internal_device_detail(user) else "operator_safe")
    if can_view_internal_device_detail(user):
        return payload
    return _apply_operator_safe_device_summary(payload)


def to_operator_safe_warning(warning: dict) -> dict:
    payload = dict(warning)
    if payload.get("type") == "error":
        payload["message"] = "Gerät meldet einen Fehler"
    return payload


def to_operator_safe_recent_event(event: dict) -> dict:
    return {
        "event_type": event.get("event_type"),
        "timestamp": event.get("timestamp"),
        "has_data": bool(event.get("data")),
    }


def to_operator_safe_recent_action(action: dict) -> dict:
    payload = {
        "id": action.get("id"),
        "device_id": action.get("device_id"),
        "action_type": action.get("action_type"),
        "status": action.get("status"),
        "request_state": action.get("request_state"),
        "approval_state": action.get("approval_state"),
        "outcome_code": action.get("outcome_code"),
        "outcome_detail": action.get("outcome_detail"),
        "issued_at": action.get("issued_at"),
        "acked_at": action.get("acked_at"),
        "has_result_message": action.get("result_message") not in (None, ""),
        "has_params": "params" in action and action.get("params") not in (None, "", {}, []),
        "detail_level": "operator_safe",
    }
    if action.get("scope") is not None:
        payload["scope"] = action.get("scope")
    return payload


def to_operator_safe_recent_credential(credential: dict) -> dict:
    payload = dict(credential)
    payload.pop("fingerprint", None)
    payload["detail_level"] = "operator_safe"
    return payload


def to_operator_safe_recent_lease(lease: dict) -> dict:
    payload = dict(lease)
    payload.pop("lease_id", None)
    payload["detail_level"] = "operator_safe"
    return payload


def finalize_device_detail(detail: dict, user) -> dict:
    payload = dict(detail)
    payload.setdefault("detail_level", "internal" if can_view_internal_device_detail(user) else "operator_safe")
    if can_view_internal_device_detail(user):
        return payload
    for key in _OPERATOR_SAFE_DEVICE_DETAIL_INTERNAL_KEYS:
        payload.pop(key, None)
    payload["recent_events"] = [to_operator_safe_recent_event(event) for event in (detail.get("recent_events") or [])]
    payload["recent_actions"] = [to_operator_safe_recent_action(action) for action in (detail.get("recent_actions") or [])]
    payload["recent_credentials"] = [to_operator_safe_recent_credential(item) for item in (detail.get("recent_credentials") or [])]
    payload["recent_leases"] = [to_operator_safe_recent_lease(item) for item in (detail.get("recent_leases") or [])]
    payload["detail_level"] = "operator_safe"
    return payload


def to_operator_safe_trust_verification(verification: dict | None) -> dict | None:
    if not verification:
        return verification
    return {
        "valid": verification.get("valid"),
        "errors": list(verification.get("errors") or []),
        "warnings": list(verification.get("warnings") or []),
        "timing_status": verification.get("timing_status"),
        "issuer_status": ((verification.get("issuer_inspection") or {}).get("status")),
    }


def stamp_detail_level(block, detail_level: str):
    if not isinstance(block, dict):
        return block
    stamped = dict(block)
    stamped["detail_level"] = detail_level
    return stamped


def to_internal_trust_credential(credential: dict | None) -> dict | None:
    if credential is None:
        return None
    payload = stamp_detail_level(credential, "internal")
    payload["verification"] = stamp_detail_level(payload.get("verification"), "internal")
    payload["rotation"] = stamp_detail_level(payload.get("rotation"), "internal")
    payload["rotation_summary"] = stamp_detail_level(payload.get("rotation_summary"), "internal")
    payload["signing_key_lineage"] = stamp_detail_level(payload.get("signing_key_lineage"), "internal")
    payload["signing_key_lineage_summary"] = stamp_detail_level(payload.get("signing_key_lineage_summary"), "internal")
    return payload


def to_internal_trust_lease(lease: dict | None) -> dict | None:
    if lease is None:
        return None
    payload = stamp_detail_level(lease, "internal")
    payload["verification"] = stamp_detail_level(payload.get("verification"), "internal")
    payload["signing_key_lineage"] = stamp_detail_level(payload.get("signing_key_lineage"), "internal")
    payload["signing_key_lineage_summary"] = stamp_detail_level(payload.get("signing_key_lineage_summary"), "internal")
    return payload


def to_operator_safe_trust_credential(credential: dict) -> dict:
    payload = dict(credential)
    payload.pop("fingerprint", None)
    payload.pop("metadata", None)
    payload["verification"] = to_operator_safe_trust_verification(payload.get("verification"))
    payload["detail_level"] = "operator_safe"
    return payload


def to_operator_safe_trust_lease(lease: dict) -> dict:
    payload = dict(lease)
    payload.pop("signature", None)
    payload.pop("metadata", None)
    payload.pop("signed_bundle", None)
    payload["verification"] = to_operator_safe_trust_verification(payload.get("verification"))
    payload["detail_level"] = "operator_safe"
    return payload


def to_operator_safe_reconciliation(reconciliation: dict | None) -> dict:
    reconciliation = reconciliation or {}
    return {
        "ok": reconciliation.get("ok"),
        "summary": reconciliation.get("summary") or build_reconciliation_summary(reconciliation=reconciliation),
        "bundle_source": reconciliation.get("bundle_source"),
        "detail_level": "operator_safe",
    }


def to_operator_safe_signing_registry(signing_registry: dict | None) -> dict:
    signing_registry = signing_registry or {}
    credential_rotation = signing_registry.get("credential_rotation") or {}
    key_lineage = signing_registry.get("key_lineage") or {}
    return {
        "registry_size": signing_registry.get("registry_size"),
        "status_counts": dict(signing_registry.get("status_counts") or {}),
        "consistency": signing_registry.get("consistency") or {},
        "credential_rotation": {
            "credential_id": credential_rotation.get("credential_id"),
            "replacement_for_credential_id": credential_rotation.get("replacement_for_credential_id"),
            "rotation_depth": credential_rotation.get("rotation_depth"),
            "ancestor_count": len(credential_rotation.get("ancestors") or []),
            "descendant_count": len(credential_rotation.get("descendants") or []),
            "detail_level": "operator_safe",
        },
        "key_lineage": {
            name: {
                "key_id": (lineage or {}).get("key_id"),
                "present": (lineage or {}).get("present"),
                "terminal_status": (((lineage or {}).get("status_path") or [{}])[0]).get("status"),
                "rotation_depth": (lineage or {}).get("rotation_depth"),
                "parent_key_id": (lineage or {}).get("parent_key_id"),
                "detail_level": "operator_safe",
            }
            for name, lineage in key_lineage.items()
        },
        "support_summary": {
            **(signing_registry.get("support_summary") or {}),
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }


def to_operator_safe_issuer_profiles(issuer_profiles: dict | None) -> dict:
    issuer_profiles = issuer_profiles or {}

    def _stamp_profile_block(block: dict | None) -> dict:
        return {**(block or {}), "detail_level": "operator_safe"}

    raw_support_summary = issuer_profiles.get("support_summary") or {}
    support_summary = {**raw_support_summary, "detail_level": "operator_safe"}
    transition = raw_support_summary.get("transition")
    if isinstance(transition, dict):
        support_summary["transition"] = {**transition, "detail_level": "operator_safe"}

    readback_summary = issuer_profiles.get("readback_summary") or {}
    effective_lineage_summary = issuer_profiles.get("effective_lineage_summary") or {}
    lineage_explanation = readback_summary.get("lineage_explanation") or {
        "effective_key_id": ((issuer_profiles.get("effective_profile") or {}).get("key_id")),
        "effective_source": support_summary.get("effective_source"),
        "lineage_state": readback_summary.get("lineage_state"),
        "lineage_note": readback_summary.get("lineage_note"),
        "transition_state": ((support_summary.get("transition") or {}).get("transition_state")),
        "rotation_depth": effective_lineage_summary.get("rotation_depth"),
        "parent_key_id": effective_lineage_summary.get("parent_key_id"),
        "terminal_status": effective_lineage_summary.get("terminal_status"),
    }
    return {
        "active_profile": _stamp_profile_block(issuer_profiles.get("active_profile")),
        "configured_profile": _stamp_profile_block(issuer_profiles.get("configured_profile")),
        "effective_profile": _stamp_profile_block(issuer_profiles.get("effective_profile")),
        "effective_lineage_summary": {**effective_lineage_summary, "detail_level": "operator_safe"},
        "history": [
            {
                "credential_id": item.get("credential_id"),
                "credential_status": item.get("credential_status"),
                "replacement_for_credential_id": item.get("replacement_for_credential_id"),
                "issued_at": item.get("issued_at"),
                "revoked_at": item.get("revoked_at"),
                "key_id": item.get("key_id"),
                "issuer": item.get("issuer"),
                "status": item.get("status"),
                "registry_status": item.get("registry_status"),
                "parent_key_id": item.get("parent_key_id"),
                "detail_level": "operator_safe",
            }
            for item in (issuer_profiles.get("history") or [])
        ],
        "support_summary": support_summary,
        "readback_summary": {
            **readback_summary,
            "lineage_explanation": {**lineage_explanation, "detail_level": "operator_safe"},
            "detail_level": "operator_safe",
        },
        "history_summary": {**(issuer_profiles.get("history_summary") or {}), "detail_level": "operator_safe"},
        "detail_level": "operator_safe",
    }


def finalize_endpoint_summary(endpoint_summary: dict | None, *, detail_level: str) -> dict | None:
    if endpoint_summary is None:
        return None

    def _stamp(block):
        if not isinstance(block, dict):
            return block
        stamped = dict(block)
        stamped["detail_level"] = detail_level
        for nested_name in (
            "issuer_state",
            "material_state",
            "signing_state",
            "provenance_state",
            "history_state",
            "material_alignment",
            "lineage_explanation",
            "credential_history",
            "lease_history",
            "summary",
            "material_summary",
            "source_contract_summary",
            "state_counts",
            "source_states",
            "status_counts",
        ):
            nested = stamped.get(nested_name)
            if isinstance(nested, dict):
                stamped_nested = {**nested, "detail_level": detail_level}
                nested_status_counts = stamped_nested.get("status_counts")
                if isinstance(nested_status_counts, dict):
                    stamped_nested["status_counts"] = {**nested_status_counts, "detail_level": detail_level}
                if nested_name == "source_contract_summary":
                    for child_name in ("state_counts", "source_states"):
                        child = stamped_nested.get(child_name)
                        if isinstance(child, dict):
                            stamped_nested[child_name] = {**child, "detail_level": detail_level}
                elif nested_name == "signing_state":
                    status_counts = stamped_nested.get("status_counts")
                    if isinstance(status_counts, dict):
                        stamped_nested["status_counts"] = {**status_counts, "detail_level": detail_level}
                if nested_name == "provenance_state":
                    stamped_nested = {
                        key: stamped_nested.get(key)
                        for key in (
                            "overall_state",
                            "missing_expected_count",
                            "observed_extra_count",
                            "present_names",
                            "derived_names",
                            "missing_names",
                            "missing_expected_names",
                            "unexpected_names",
                            "summary",
                            "detail_level",
                        )
                        if key in stamped_nested
                    }
                stamped[nested_name] = stamped_nested
        source_contracts = stamped.get("source_contracts")
        if isinstance(source_contracts, dict):
            stamped["source_contracts"] = {
                name: {**value, "detail_level": detail_level} if isinstance(value, dict) else value
                for name, value in source_contracts.items()
            }
        return stamped

    payload = dict(endpoint_summary)
    payload["detail_level"] = detail_level
    for block_name in (
        "issuer_state",
        "signing_state",
        "material_timestamps",
        "support_notes",
        "contract_summary",
        "history_state",
        "material_history",
        "material_readback_summary",
    ):
        payload[block_name] = _stamp(payload.get(block_name))
    return payload


def _build_compact_reconciliation_readback_summary(payload: dict) -> dict:
    raw_summary = payload.get("reconciliation_summary") or build_reconciliation_summary(
        reconciliation={
            "summary": payload.get("reconciliation_summary") or payload.get("reconciliation") or {},
            "issuer_profiles": payload.get("issuer_profiles") or {},
            "signing_registry": payload.get("signing_registry") or {},
        }
    )

    issuer_profiles = dict(raw_summary.get("issuer_profiles") or {})
    lineage_explanation = issuer_profiles.get("lineage_explanation")
    if isinstance(lineage_explanation, dict):
        issuer_profiles["lineage_explanation"] = {**lineage_explanation, "detail_level": "operator_safe"}
    transition = issuer_profiles.get("transition")
    if isinstance(transition, dict):
        issuer_profiles["transition"] = {**transition, "detail_level": "operator_safe"}
    readback_summary = issuer_profiles.get("readback_summary")
    if isinstance(readback_summary, dict):
        stamped_readback_summary = {**readback_summary, "detail_level": "operator_safe"}
        nested_lineage_explanation = stamped_readback_summary.get("lineage_explanation")
        if isinstance(nested_lineage_explanation, dict):
            stamped_readback_summary["lineage_explanation"] = {**nested_lineage_explanation, "detail_level": "operator_safe"}
        issuer_profiles["readback_summary"] = stamped_readback_summary
    history_summary = issuer_profiles.get("history_summary")
    if isinstance(history_summary, dict):
        stamped_history_summary = {**history_summary, "detail_level": "operator_safe"}
        if isinstance(stamped_history_summary.get("status_counts"), dict):
            stamped_history_summary["status_counts"] = {**(stamped_history_summary.get("status_counts") or {}), "detail_level": "operator_safe"}
        issuer_profiles["history_summary"] = stamped_history_summary
    source_contracts = issuer_profiles.get("source_contracts")
    if isinstance(source_contracts, dict):
        issuer_profiles["source_contracts"] = {
            name: {**value, "detail_level": "operator_safe"} if isinstance(value, dict) else value
            for name, value in source_contracts.items()
        }
    source_contract_summary = issuer_profiles.get("source_contract_summary")
    if isinstance(source_contract_summary, dict):
        stamped_source_contract_summary = {**source_contract_summary, "detail_level": "operator_safe"}
        for nested_name in ("state_counts", "source_states"):
            nested = stamped_source_contract_summary.get(nested_name)
            if isinstance(nested, dict):
                stamped_source_contract_summary[nested_name] = {**nested, "detail_level": "operator_safe"}
        issuer_profiles["source_contract_summary"] = stamped_source_contract_summary

    material_readback_summary = dict(raw_summary.get("material_readback_summary") or {})
    for nested_name in ("summary", "credential_history", "lease_history"):
        nested = material_readback_summary.get(nested_name)
        if isinstance(nested, dict):
            material_readback_summary[nested_name] = {**nested, "detail_level": "operator_safe"}

    return {
        "ok": raw_summary.get("ok"),
        "status_counts": {**(raw_summary.get("status_counts") or {}), "detail_level": "operator_safe"},
        "bundle_source": (payload.get("reconciliation") or {}).get("bundle_source") or raw_summary.get("bundle_source"),
        "timing": {**(raw_summary.get("timing_status") or raw_summary.get("timing") or {}), "detail_level": "operator_safe"},
        "support_summary": {**(raw_summary.get("support_summary") or {}), "detail_level": "operator_safe"},
        "issuer_profiles": {**issuer_profiles, "detail_level": "operator_safe"},
        "material_readback_summary": {**material_readback_summary, "detail_level": "operator_safe"},
        "detail_level": "operator_safe",
    }


def to_internal_reconciliation(reconciliation: dict | None) -> dict | None:
    if reconciliation is None:
        return None
    payload = stamp_detail_level(reconciliation, "internal")
    payload["summary"] = stamp_detail_level(payload.get("summary"), "internal")
    return payload


def to_internal_signing_registry(signing_registry: dict | None) -> dict | None:
    if signing_registry is None:
        return None
    payload = stamp_detail_level(signing_registry, "internal")
    payload["status_counts"] = stamp_detail_level(payload.get("status_counts"), "internal")
    payload["support_summary"] = stamp_detail_level(payload.get("support_summary"), "internal")
    payload["consistency"] = stamp_detail_level(payload.get("consistency"), "internal")
    payload["credential_rotation"] = stamp_detail_level(payload.get("credential_rotation"), "internal")
    key_lineage = payload.get("key_lineage")
    if isinstance(key_lineage, dict):
        payload["key_lineage"] = {name: stamp_detail_level(lineage, "internal") for name, lineage in key_lineage.items()}
    return payload


def to_internal_issuer_profiles(issuer_profiles: dict | None) -> dict | None:
    if issuer_profiles is None:
        return None
    payload = stamp_detail_level(issuer_profiles, "internal")
    for name in (
        "active_profile",
        "configured_profile",
        "effective_profile",
        "effective_lineage_summary",
        "support_summary",
        "readback_summary",
        "history_summary",
    ):
        value = payload.get(name)
        if name == "support_summary" and not isinstance(value, dict):
            value = {}
        payload[name] = stamp_detail_level(value, "internal")
    history = payload.get("history")
    if isinstance(history, list):
        payload["history"] = [stamp_detail_level(item, "internal") for item in history]
    transition = (payload.get("support_summary") or {}).get("transition")
    if isinstance(transition, dict):
        payload["support_summary"] = {**payload.get("support_summary"), "transition": stamp_detail_level(transition, "internal")}
    lineage_explanation = (payload.get("readback_summary") or {}).get("lineage_explanation")
    if isinstance(lineage_explanation, dict):
        payload["readback_summary"] = {**payload.get("readback_summary"), "lineage_explanation": stamp_detail_level(lineage_explanation, "internal")}
    source_contracts = payload.get("source_contracts")
    if isinstance(source_contracts, dict):
        payload["source_contracts"] = {name: stamp_detail_level(value, "internal") for name, value in source_contracts.items()}
    source_contract_summary = payload.get("source_contract_summary")
    if isinstance(source_contract_summary, dict):
        payload["source_contract_summary"] = {
            **stamp_detail_level(source_contract_summary, "internal"),
            "state_counts": stamp_detail_level(source_contract_summary.get("state_counts"), "internal"),
            "source_states": stamp_detail_level(source_contract_summary.get("source_states"), "internal"),
        }
    return payload


def to_internal_material_readback_summary(material_readback_summary: dict | None) -> dict | None:
    if material_readback_summary is None:
        return None
    payload = stamp_detail_level(material_readback_summary, "internal")
    for name in ("summary", "credential_history", "lease_history"):
        payload[name] = stamp_detail_level(payload.get(name), "internal")
        nested = payload.get(name)
        if isinstance(nested, dict) and isinstance(nested.get("status_counts"), dict):
            payload[name] = {**nested, "status_counts": stamp_detail_level(nested.get("status_counts"), "internal")}
    return payload


def to_internal_reconciliation_summary(reconciliation_summary: dict | None) -> dict | None:
    if reconciliation_summary is None:
        return None
    payload = stamp_detail_level(reconciliation_summary, "internal")
    payload["status_counts"] = stamp_detail_level(payload.get("status_counts") or payload.get("severity_counts"), "internal")
    payload["severity_counts"] = stamp_detail_level(payload.get("severity_counts") or payload.get("status_counts"), "internal")
    payload["source_counts"] = stamp_detail_level(payload.get("source_counts"), "internal")
    payload["timing"] = stamp_detail_level(payload.get("timing") or payload.get("timing_status"), "internal")
    payload["timing_status"] = stamp_detail_level(payload.get("timing_status") or payload.get("timing"), "internal")
    payload["support_summary"] = stamp_detail_level(payload.get("support_summary"), "internal")
    payload["issuer_profiles"] = to_internal_issuer_profiles(payload.get("issuer_profiles"))
    payload["material_readback_summary"] = to_internal_material_readback_summary(payload.get("material_readback_summary"))
    return payload


def to_device_safe_current_lease_payload(payload: dict | None) -> dict:
    payload = dict(payload or {})
    payload["advisory_posture"] = stamp_detail_level(payload.get("advisory_posture"), "operator_safe")
    payload["credential"] = to_operator_safe_trust_credential(payload.get("credential") or {}) if payload.get("credential") else None
    payload["lease"] = to_operator_safe_trust_lease(payload.get("lease") or {}) if payload.get("lease") else None
    payload["reconciliation"] = to_operator_safe_reconciliation(payload.get("reconciliation"))
    payload["reconciliation_summary"] = _build_compact_reconciliation_readback_summary(payload)
    payload["issuer_profiles"] = to_operator_safe_issuer_profiles(payload.get("issuer_profiles"))
    payload["signing_registry"] = to_operator_safe_signing_registry(payload.get("signing_registry"))
    payload["endpoint_summary"] = finalize_endpoint_summary(payload.get("endpoint_summary"), detail_level="operator_safe")
    payload["detail_level"] = "device_safe"
    return payload


def finalize_device_trust_detail(detail: dict, user) -> dict:
    payload = dict(detail)
    payload.setdefault("detail_level", "internal" if can_view_internal_device_detail(user) else "operator_safe")
    payload["device"] = finalize_device_summary(payload.get("device") or {}, user)
    if can_view_internal_device_detail(user):
        payload["advisory_posture"] = stamp_detail_level(payload.get("advisory_posture"), "internal")
        payload["credentials"] = [to_internal_trust_credential(item) for item in (payload.get("credentials") or [])]
        payload["leases"] = [to_internal_trust_lease(item) for item in (payload.get("leases") or [])]
        if payload.get("credential"):
            payload["credential"] = to_internal_trust_credential(payload.get("credential"))
        if payload.get("lease"):
            payload["lease"] = to_internal_trust_lease(payload.get("lease"))
        payload["reconciliation"] = to_internal_reconciliation(payload.get("reconciliation"))
        payload["reconciliation_summary"] = to_internal_reconciliation_summary(payload.get("reconciliation_summary"))
        payload["issuer_profiles"] = to_internal_issuer_profiles(payload.get("issuer_profiles"))
        payload["signing_registry"] = to_internal_signing_registry(payload.get("signing_registry"))
        payload["endpoint_summary"] = finalize_endpoint_summary(payload.get("endpoint_summary"), detail_level="internal")
        return payload
    payload["advisory_posture"] = stamp_detail_level(payload.get("advisory_posture"), "operator_safe")
    payload["credentials"] = [to_operator_safe_trust_credential(item) for item in (payload.get("credentials") or [])]
    payload["leases"] = [to_operator_safe_trust_lease(item) for item in (payload.get("leases") or [])]
    if payload.get("credential"):
        payload["credential"] = to_operator_safe_trust_credential(payload.get("credential") or {})
    if payload.get("lease"):
        payload["lease"] = to_operator_safe_trust_lease(payload.get("lease") or {})
    payload["reconciliation"] = to_operator_safe_reconciliation(payload.get("reconciliation"))
    if (detail or {}).get("reconciliation") is None and (detail or {}).get("issuer_profiles") is None and (detail or {}).get("signing_registry") is None and (detail or {}).get("reconciliation_summary") is not None:
        payload["reconciliation_summary"] = payload.get("reconciliation_summary")
    else:
        payload["reconciliation_summary"] = _build_compact_reconciliation_readback_summary(payload)
    payload["issuer_profiles"] = to_operator_safe_issuer_profiles(payload.get("issuer_profiles"))
    payload["signing_registry"] = to_operator_safe_signing_registry(payload.get("signing_registry"))
    if isinstance((payload.get("signing_registry") or {}).get("status_counts"), dict):
        payload["signing_registry"] = {
            **payload["signing_registry"],
            "status_counts": stamp_detail_level((payload["signing_registry"] or {}).get("status_counts"), "operator_safe"),
        }
    payload["endpoint_summary"] = finalize_endpoint_summary(payload.get("endpoint_summary"), detail_level="operator_safe")
    payload["detail_level"] = "operator_safe"
    return payload
