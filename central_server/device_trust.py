"""Helpers for additive device trust / lease scaffolding.

This module intentionally stays non-enforcing for the current Central Rebuild.
It standardizes placeholder lease payloads, signatures, and device state snapshots so
central can evolve toward real credentials/leasing without changing the protected
local runtime auth path.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


PEM_LINE_WIDTH = 64


def _is_production_env() -> bool:
    env_name = os.environ.get("CENTRAL_ENV", os.environ.get("ENV", "")).strip().lower()
    return env_name in {"prod", "production"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return aware(dt).isoformat()


def _signing_secret() -> str:
    secret = os.environ.get("CENTRAL_DEVICE_TRUST_SIGNING_SECRET", "").strip()
    if secret:
        return secret
    fallback = os.environ.get("CENTRAL_JWT_SECRET", "").strip()
    if fallback:
        return fallback
    if _is_production_env():
        raise RuntimeError(
            "CENTRAL_DEVICE_TRUST_SIGNING_SECRET or CENTRAL_JWT_SECRET is required in production"
        )
    return "unsafe-dev-placeholder-secret"


def _default_placeholder_signing_key_id() -> str:
    digest = hashlib.sha256(_signing_secret().encode("utf-8")).hexdigest()
    return f"central-placeholder-{digest[:12]}"


def get_placeholder_signing_profile() -> dict[str, Any]:
    key_id = os.environ.get("CENTRAL_DEVICE_TRUST_SIGNING_KEY_ID", "").strip() or _default_placeholder_signing_key_id()
    issuer = os.environ.get("CENTRAL_DEVICE_TRUST_ISSUER", "").strip() or "central"
    return {
        "issuer": issuer,
        "key_id": key_id,
        "algorithm": "hmac-sha256-placeholder",
        "schema": "darts.placeholder_signing_profile.v1",
        "mode": "placeholder",
    }


def _load_signing_registry_overrides() -> list[dict[str, Any]]:
    raw = os.environ.get("CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict)]


def get_signing_key_registry() -> dict[str, dict[str, Any]]:
    """Build a central signing-key registry snapshot for diagnostics/readback.

    This stays purely additive and non-enforcing. It provides a stable place to hang
    future key-rotation / PKI metadata while current placeholder verification can
    already reason about known, retired, or revoked signing keys.
    """
    active_profile = get_placeholder_signing_profile()
    registry: dict[str, dict[str, Any]] = {
        active_profile["key_id"]: {
            **active_profile,
            "status": "active",
            "source": "active_profile",
        }
    }
    for entry in _load_signing_registry_overrides():
        key_id = str(entry.get("key_id") or "").strip()
        if not key_id:
            continue
        merged = dict(registry.get(key_id) or {})
        merged.update(entry)
        merged.setdefault("issuer", entry.get("issuer") or active_profile["issuer"])
        merged.setdefault("algorithm", entry.get("algorithm") or active_profile["algorithm"])
        merged.setdefault("schema", entry.get("schema") or active_profile["schema"])
        merged.setdefault("mode", entry.get("mode") or active_profile["mode"])
        merged.setdefault("status", "active")
        merged.setdefault("source", "configured")
        registry[key_id] = merged
    return registry


def inspect_signing_issuer(issuer: dict[str, Any] | None) -> dict[str, Any]:
    issuer = issuer or {}
    key_id = issuer.get("key_id")
    registry = get_signing_key_registry()
    entry = registry.get(key_id) if key_id else None
    status = "missing_key_id"
    if key_id:
        status = "known" if entry else "unknown"
    return {
        "key_id": key_id,
        "status": status,
        "entry": entry,
        "registry_size": len(registry),
    }


def build_signing_key_lineage(*, key_id: str | None, registry: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = registry or get_signing_key_registry()
    if not key_id:
        return {
            "key_id": None,
            "present": False,
            "ancestors": [],
            "descendants": [],
            "rotation_depth": 0,
            "status_path": [],
        }

    ancestors: list[dict[str, Any]] = []
    visited = {key_id}
    current_key_id = key_id
    while True:
        entry = registry.get(current_key_id) or {}
        parent_key_id = str(entry.get("parent_key_id") or "").strip() or None
        if not parent_key_id or parent_key_id in visited:
            break
        parent_entry = registry.get(parent_key_id)
        ancestors.append({
            "key_id": parent_key_id,
            "present": parent_entry is not None,
            "status": (parent_entry or {}).get("status"),
        })
        visited.add(parent_key_id)
        current_key_id = parent_key_id

    descendants = []
    for candidate_key_id, candidate_entry in registry.items():
        parent_key_id = str(candidate_entry.get("parent_key_id") or "").strip() or None
        if parent_key_id == key_id:
            descendants.append({
                "key_id": candidate_key_id,
                "present": True,
                "status": candidate_entry.get("status"),
            })

    root_entry = registry.get(key_id) or {}
    status_path = []
    if root_entry.get("status"):
        status_path.append({"key_id": key_id, "status": root_entry.get("status")})
    status_path.extend([{"key_id": item["key_id"], "status": item.get("status")} for item in ancestors])

    return {
        "key_id": key_id,
        "present": key_id in registry,
        "parent_key_id": (registry.get(key_id) or {}).get("parent_key_id"),
        "ancestors": ancestors,
        "descendants": sorted(descendants, key=lambda item: item["key_id"]),
        "rotation_depth": len(ancestors),
        "status_path": status_path,
    }


def build_credential_rotation_lineage(*, credential=None, credentials: list[Any] | None = None) -> dict[str, Any]:
    if credential is None:
        return {
            "credential_id": None,
            "replacement_for_credential_id": None,
            "rotation_depth": 0,
            "ancestors": [],
            "descendants": [],
        }

    credentials = credentials or [credential]
    by_id = {getattr(item, "id", None): item for item in credentials if getattr(item, "id", None)}
    credential_id = getattr(credential, "id", None)
    replacement_for = getattr(credential, "replacement_for_credential_id", None)

    ancestors = []
    visited = {credential_id}
    current_id = replacement_for
    while current_id and current_id not in visited:
        ancestor = by_id.get(current_id)
        ancestors.append({
            "credential_id": current_id,
            "present": ancestor is not None,
            "status": getattr(ancestor, "status", None) if ancestor is not None else None,
            "key_id": ((getattr(ancestor, "details_json", None) or {}).get("key_id") if ancestor is not None else None),
        })
        visited.add(current_id)
        current_id = getattr(ancestor, "replacement_for_credential_id", None) if ancestor is not None else None

    descendants = []
    if credential_id:
        for candidate in credentials:
            if getattr(candidate, "replacement_for_credential_id", None) == credential_id:
                descendants.append({
                    "credential_id": getattr(candidate, "id", None),
                    "present": True,
                    "status": getattr(candidate, "status", None),
                    "key_id": (getattr(candidate, "details_json", None) or {}).get("key_id"),
                })

    return {
        "credential_id": credential_id,
        "replacement_for_credential_id": replacement_for,
        "rotation_depth": len(ancestors),
        "ancestors": ancestors,
        "descendants": sorted(descendants, key=lambda item: item["credential_id"] or ""),
    }


def summarize_lineage(lineage: dict[str, Any] | None) -> dict[str, Any]:
    lineage = lineage or {}
    return {
        "key_id": lineage.get("key_id"),
        "present": bool(lineage.get("present")),
        "parent_key_id": lineage.get("parent_key_id"),
        "rotation_depth": lineage.get("rotation_depth") or 0,
        "ancestor_count": len(lineage.get("ancestors") or []),
        "descendant_count": len(lineage.get("descendants") or []),
        "terminal_status": ((lineage.get("status_path") or [{}])[0]).get("status"),
    }


def summarize_credential_rotation(lineage: dict[str, Any] | None) -> dict[str, Any]:
    lineage = lineage or {}
    return {
        "credential_id": lineage.get("credential_id"),
        "replacement_for_credential_id": lineage.get("replacement_for_credential_id"),
        "rotation_depth": lineage.get("rotation_depth") or 0,
        "ancestor_count": len(lineage.get("ancestors") or []),
        "descendant_count": len(lineage.get("descendants") or []),
        "has_rotation_history": bool((lineage.get("ancestors") or []) or (lineage.get("descendants") or [])),
    }


def _normalize_issuer_profile(profile: dict[str, Any] | None, *, source: str, registry: dict[str, dict[str, Any]] | None = None, fallback_key_id: str | None = None, preferred_key_id: str | None = None) -> dict[str, Any]:
    registry = registry or get_signing_key_registry()
    profile = dict(profile or {})
    key_id = str(preferred_key_id or profile.get("key_id") or fallback_key_id or "").strip() or None
    entry = registry.get(key_id) if key_id else None
    return {
        "source": source,
        "issuer": profile.get("issuer"),
        "key_id": key_id,
        "algorithm": profile.get("algorithm"),
        "schema": profile.get("schema"),
        "mode": profile.get("mode"),
        "status": (entry or {}).get("status"),
        "registry_status": "known" if entry else ("missing_key_id" if not key_id else "unknown"),
        "parent_key_id": (entry or {}).get("parent_key_id"),
        "entry_source": (entry or {}).get("source"),
        "present": bool(profile) or bool(fallback_key_id),
    }


def build_issuer_transition_summary(
    *,
    active_profile: dict[str, Any] | None,
    configured_profile: dict[str, Any] | None,
    effective_profile: dict[str, Any] | None,
    credential_profile: dict[str, Any] | None,
    lease_profile: dict[str, Any] | None,
    lineage: dict[str, Any] | None,
) -> dict[str, Any]:
    active_profile = active_profile or {}
    configured_profile = configured_profile or {}
    effective_profile = effective_profile or {}
    credential_profile = credential_profile or {}
    lease_profile = lease_profile or {}
    lineage = lineage or {}

    active_key_id = active_profile.get("key_id")
    configured_key_id = configured_profile.get("key_id")
    effective_key_id = effective_profile.get("key_id")
    credential_key_id = credential_profile.get("key_id")
    lease_key_id = lease_profile.get("key_id")
    registry_status = effective_profile.get("registry_status")
    effective_status = effective_profile.get("status")

    mismatch_reasons: list[str] = []
    if active_key_id and effective_key_id and active_key_id != effective_key_id:
        mismatch_reasons.append("active_profile_differs_from_effective")
    if configured_key_id and effective_key_id and configured_key_id != effective_key_id:
        mismatch_reasons.append("configured_profile_differs_from_effective")
    if (
        active_key_id and credential_key_id and active_key_id != credential_key_id
        and credential_key_id != effective_key_id
    ):
        mismatch_reasons.append("credential_profile_differs_from_active")
    if (
        active_key_id and lease_key_id and active_key_id != lease_key_id
        and lease_key_id != effective_key_id
    ):
        mismatch_reasons.append("lease_profile_differs_from_active")
    if not effective_key_id:
        mismatch_reasons.append("effective_key_missing")
    elif registry_status == "unknown":
        mismatch_reasons.append("effective_key_unknown")
    if effective_status == "retired":
        mismatch_reasons.append("effective_key_retired")
    elif effective_status == "revoked":
        mismatch_reasons.append("effective_key_revoked")

    if not mismatch_reasons:
        transition_state = "aligned"
    elif any(reason.endswith("revoked") for reason in mismatch_reasons):
        transition_state = "revoked"
    elif any(reason.endswith("retired") for reason in mismatch_reasons):
        transition_state = "retired"
    elif active_key_id and effective_key_id and active_key_id != effective_key_id:
        transition_state = "rotated"
    else:
        transition_state = "drifted"

    return {
        "transition_state": transition_state,
        "active_key_id": active_key_id,
        "configured_key_id": configured_key_id,
        "effective_key_id": effective_key_id,
        "credential_key_id": credential_key_id,
        "lease_key_id": lease_key_id,
        "effective_registry_status": registry_status,
        "effective_status": effective_status,
        "rotation_depth": lineage.get("rotation_depth") or 0,
        "mismatch_reasons": mismatch_reasons,
    }


def build_issuer_profile_readback_summary(
    *,
    active_profile: dict[str, Any] | None,
    configured_profile: dict[str, Any] | None,
    effective_profile: dict[str, Any] | None,
    credential_profile: dict[str, Any] | None,
    lease_profile: dict[str, Any] | None,
    history: list[dict[str, Any]] | None,
    lineage: dict[str, Any] | None,
    transition: dict[str, Any] | None,
    lineage_explanation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    history = history or []
    lineage = lineage or {}
    transition = transition or {}
    active_profile = active_profile or {}
    configured_profile = configured_profile or {}
    effective_profile = effective_profile or {}
    credential_profile = credential_profile or {}
    lease_profile = lease_profile or {}

    effective_source = (
        "lease" if lease_profile.get("present") else (
            "credential" if credential_profile.get("present") else "active_profile"
        )
    )
    source_reason = {
        "lease": "lease issuer metadata currently drives the effective issuer profile",
        "credential": "credential issuer metadata currently drives the effective issuer profile",
        "active_profile": "no credential/lease issuer override is present, so the active central profile is effective",
    }.get(effective_source)

    latest_history = history[0] if history else {}
    history_status_counts: dict[str, int] = {}
    for item in history:
        status = str(item.get("status") or item.get("credential_status") or "unknown")
        history_status_counts[status] = history_status_counts.get(status, 0) + 1

    mismatch_reasons = list(transition.get("mismatch_reasons") or [])
    if mismatch_reasons:
        mismatch_summary = "; ".join(mismatch_reasons)
    else:
        mismatch_summary = "no compact mismatch reasons recorded"

    lineage_state = "standalone"
    if transition.get("transition_state") in {"retired", "revoked"}:
        lineage_state = transition.get("transition_state")
    elif (lineage.get("rotation_depth") or 0) > 0:
        lineage_state = "rotated"
    elif lineage.get("descendants"):
        lineage_state = "branching"

    lineage_note = {
        "standalone": "effective key currently has no recorded parent rotation lineage",
        "rotated": "effective key sits on a recorded parent rotation chain",
        "branching": "effective key has staged or child descendants in registry history",
        "retired": "effective key is present but marked retired in the central registry",
        "revoked": "effective key is present but marked revoked in the central registry",
    }.get(lineage_state)

    lineage_explanation = lineage_explanation or {
        "effective_key_id": effective_profile.get("key_id"),
        "effective_source": effective_source,
        "lineage_state": lineage_state,
        "lineage_note": lineage_note,
        "transition_state": transition.get("transition_state"),
        "rotation_depth": lineage.get("rotation_depth"),
        "parent_key_id": lineage.get("parent_key_id"),
        "terminal_status": (((lineage.get("status_path") or [{}])[0]).get("status")),
    }

    return {
        "effective_source": effective_source,
        "effective_source_reason": source_reason,
        "configured_vs_effective": {
            "configured_key_id": configured_profile.get("key_id"),
            "effective_key_id": effective_profile.get("key_id"),
            "matches": (
                configured_profile.get("key_id") == effective_profile.get("key_id")
                if configured_profile.get("key_id") and effective_profile.get("key_id")
                else None
            ),
        },
        "active_vs_effective": {
            "active_key_id": active_profile.get("key_id"),
            "effective_key_id": effective_profile.get("key_id"),
            "matches": (
                active_profile.get("key_id") == effective_profile.get("key_id")
                if active_profile.get("key_id") and effective_profile.get("key_id")
                else None
            ),
        },
        "history_status_counts": history_status_counts,
        "latest_history_credential_id": latest_history.get("credential_id"),
        "latest_history_key_id": latest_history.get("key_id"),
        "lineage_state": lineage_state,
        "lineage_note": lineage_note,
        "lineage_explanation": lineage_explanation,
        "mismatch_summary": mismatch_summary,
    }


def build_issuer_history_summary(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    history = history or []
    latest = history[0] if history else {}
    previous = history[1] if len(history) > 1 else {}

    status_counts: dict[str, int] = {}
    for item in history:
        status = str(item.get("credential_status") or item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    latest_status = latest.get("credential_status") or latest.get("status")
    previous_status = previous.get("credential_status") or previous.get("status")
    replacement_for = latest.get("replacement_for_credential_id")
    latest_revoked_at = latest.get("revoked_at")
    replacement_target = replacement_for or previous.get("credential_id")
    latest_credential_id = latest.get("credential_id") or "unknown"
    latest_key_id = latest.get("key_id") or "unknown"

    replacement_relation = "none"
    if replacement_for:
        replacement_relation = "declared_replacement"
    elif previous:
        replacement_relation = "prior_history_visible"

    if not latest:
        history_state = "empty"
        narrative = "no credential-backed issuer history is currently visible"
        narrative_state = "empty"
    elif latest_revoked_at and replacement_for and previous:
        history_state = "revoked_latest"
        narrative_state = "revoked_replacement"
        narrative = (
            f"latest visible credential {latest_credential_id} using key {latest_key_id} "
            f"replaced {replacement_target or 'an earlier credential'}"
            f" ({previous_status or 'unknown'} -> {latest_status or 'unknown'}) and is now revoked"
        )
    elif latest_revoked_at:
        history_state = "revoked_latest"
        narrative_state = "revoked"
        narrative = (
            f"latest visible credential {latest_credential_id} "
            f"using key {latest_key_id} is revoked"
        )
    elif replacement_for and previous:
        history_state = "rotated"
        narrative_state = "rotated"
        narrative = (
            f"latest visible credential {latest_credential_id} "
            f"replaced {replacement_target}"
            f" ({previous_status or 'unknown'} -> {latest_status or 'unknown'})"
        )
    elif previous:
        history_state = "multi_entry"
        narrative_state = "multi_entry"
        narrative = (
            f"latest visible credential {latest_credential_id} "
            f"has prior issuer history via {previous.get('credential_id') or 'unknown'}"
        )
    else:
        history_state = "single_entry"
        narrative_state = "single_entry"
        narrative = (
            f"only one visible credential issuer entry is present"
            f" ({latest_credential_id})"
        )

    return {
        "history_state": history_state,
        "history_count": len(history),
        "status_counts": status_counts,
        "replacement_relation": replacement_relation,
        "narrative_state": narrative_state,
        "latest": {
            "credential_id": latest.get("credential_id"),
            "key_id": latest.get("key_id"),
            "credential_status": latest_status,
            "issued_at": latest.get("issued_at"),
            "revoked_at": latest_revoked_at,
            "replacement_for_credential_id": replacement_for,
        },
        "previous": {
            "credential_id": previous.get("credential_id"),
            "key_id": previous.get("key_id"),
            "credential_status": previous_status,
            "issued_at": previous.get("issued_at"),
            "revoked_at": previous.get("revoked_at"),
        },
        "narrative": narrative,
    }


def build_material_history_summary(
    *,
    credentials: list[Any] | None = None,
    leases: list[Any] | None = None,
    active_credential=None,
    current_lease=None,
) -> dict[str, Any]:
    credentials = list(credentials or [])
    leases = list(leases or [])

    def _entry_id(item, attr: str, fallback_attr: str = "id"):
        return getattr(item, attr, None) or getattr(item, fallback_attr, None)

    latest_credential = credentials[0] if credentials else None
    previous_credential = credentials[1] if len(credentials) > 1 else None
    latest_lease = leases[0] if leases else current_lease
    previous_lease = leases[1] if len(leases) > 1 else None

    credential_status_counts: dict[str, int] = {}
    for item in credentials:
        status = str(getattr(item, "status", None) or "unknown")
        credential_status_counts[status] = credential_status_counts.get(status, 0) + 1

    lease_status_counts: dict[str, int] = {}
    for item in leases:
        status = str(getattr(item, "status", None) or "unknown")
        lease_status_counts[status] = lease_status_counts.get(status, 0) + 1

    credential_narrative = "no credential material is currently visible"
    if active_credential is not None and latest_credential is not None:
        if getattr(active_credential, "id", None) == getattr(latest_credential, "id", None):
            credential_narrative = (
                f"active credential {_entry_id(active_credential, 'id') or 'unknown'} is the latest visible credential"
            )
        else:
            credential_narrative = (
                f"active credential {_entry_id(active_credential, 'id') or 'unknown'} differs from latest visible credential "
                f"{_entry_id(latest_credential, 'id') or 'unknown'}"
            )
    elif latest_credential is not None:
        credential_narrative = (
            f"latest visible credential {_entry_id(latest_credential, 'id') or 'unknown'} has status "
            f"{getattr(latest_credential, 'status', None) or 'unknown'}"
        )

    lease_narrative = "no lease material is currently visible"
    if current_lease is not None and latest_lease is not None:
        if getattr(current_lease, "id", None) == getattr(latest_lease, "id", None):
            lease_narrative = (
                f"current lease {_entry_id(current_lease, 'lease_id') or 'unknown'} is the latest visible lease"
            )
        else:
            lease_narrative = (
                f"current lease {_entry_id(current_lease, 'lease_id') or 'unknown'} differs from latest visible lease "
                f"{_entry_id(latest_lease, 'lease_id') or 'unknown'}"
            )
    elif latest_lease is not None:
        lease_narrative = (
            f"latest visible lease {_entry_id(latest_lease, 'lease_id') or 'unknown'} has status "
            f"{getattr(latest_lease, 'status', None) or 'unknown'}"
        )

    summary = {
        "credential_history": {
            "history_count": len(credentials),
            "status_counts": credential_status_counts,
            "active_credential_id": getattr(active_credential, "id", None) if active_credential is not None else None,
            "latest": {
                "credential_id": getattr(latest_credential, "id", None) if latest_credential is not None else None,
                "status": getattr(latest_credential, "status", None) if latest_credential is not None else None,
                "issued_at": iso(getattr(latest_credential, "issued_at", None)) if latest_credential is not None else None,
                "revoked_at": iso(getattr(latest_credential, "revoked_at", None)) if latest_credential is not None else None,
                "replacement_for_credential_id": getattr(latest_credential, "replacement_for_credential_id", None) if latest_credential is not None else None,
            },
            "previous": {
                "credential_id": getattr(previous_credential, "id", None) if previous_credential is not None else None,
                "status": getattr(previous_credential, "status", None) if previous_credential is not None else None,
                "issued_at": iso(getattr(previous_credential, "issued_at", None)) if previous_credential is not None else None,
                "revoked_at": iso(getattr(previous_credential, "revoked_at", None)) if previous_credential is not None else None,
            },
            "narrative": credential_narrative,
        },
        "lease_history": {
            "history_count": len(leases),
            "status_counts": lease_status_counts,
            "current_lease_id": getattr(current_lease, "lease_id", None) if current_lease is not None else None,
            "latest": {
                "lease_id": getattr(latest_lease, "lease_id", None) if latest_lease is not None else None,
                "status": getattr(latest_lease, "status", None) if latest_lease is not None else None,
                "issued_at": iso(getattr(latest_lease, "issued_at", None)) if latest_lease is not None else None,
                "expires_at": iso(getattr(latest_lease, "expires_at", None)) if latest_lease is not None else None,
                "revoked_at": iso(getattr(latest_lease, "revoked_at", None)) if latest_lease is not None else None,
            },
            "previous": {
                "lease_id": getattr(previous_lease, "lease_id", None) if previous_lease is not None else None,
                "status": getattr(previous_lease, "status", None) if previous_lease is not None else None,
                "issued_at": iso(getattr(previous_lease, "issued_at", None)) if previous_lease is not None else None,
                "expires_at": iso(getattr(previous_lease, "expires_at", None)) if previous_lease is not None else None,
                "revoked_at": iso(getattr(previous_lease, "revoked_at", None)) if previous_lease is not None else None,
            },
            "narrative": lease_narrative,
        },
        "summary": (
            f"credentials={len(credentials)} visible / leases={len(leases)} visible; "
            f"{credential_narrative}; {lease_narrative}"
        ),
    }
    summary["readback_summary"] = build_material_history_readback_summary(material_history=summary)
    return summary


def build_material_history_readback_summary(*, material_history: dict[str, Any] | None) -> dict[str, Any]:
    material_history = material_history or {}
    credential_history = material_history.get("credential_history") or {}
    lease_history = material_history.get("lease_history") or {}

    active_credential_id = credential_history.get("active_credential_id")
    latest_credential_id = ((credential_history.get("latest") or {}).get("credential_id"))
    current_lease_id = lease_history.get("current_lease_id")
    latest_lease_id = ((lease_history.get("latest") or {}).get("lease_id"))

    credential_alignment = (
        "aligned" if active_credential_id and latest_credential_id and active_credential_id == latest_credential_id else (
            "drifted" if active_credential_id and latest_credential_id and active_credential_id != latest_credential_id else (
                "latest_only" if latest_credential_id else "empty"
            )
        )
    )
    lease_alignment = (
        "aligned" if current_lease_id and latest_lease_id and current_lease_id == latest_lease_id else (
            "drifted" if current_lease_id and latest_lease_id and current_lease_id != latest_lease_id else (
                "latest_only" if latest_lease_id else "empty"
            )
        )
    )

    return {
        "credential_history": {
            "history_count": credential_history.get("history_count") or 0,
            "active_credential_id": active_credential_id,
            "latest_credential_id": latest_credential_id,
            "alignment_state": credential_alignment,
            "status_counts": credential_history.get("status_counts") or {},
            "narrative": credential_history.get("narrative"),
        },
        "lease_history": {
            "history_count": lease_history.get("history_count") or 0,
            "current_lease_id": current_lease_id,
            "latest_lease_id": latest_lease_id,
            "alignment_state": lease_alignment,
            "status_counts": lease_history.get("status_counts") or {},
            "narrative": lease_history.get("narrative"),
        },
        "summary": material_history.get("summary"),
    }


def build_issuer_profile_diagnostics(
    *,
    credential=None,
    lease=None,
    device=None,
    credentials: list[Any] | None = None,
) -> dict[str, Any]:
    """Additive issuer-profile readback/history for support and rotation diagnostics.

    This explains which issuer/signing profile is currently configured, which one is
    referenced by the active credential/lease, and what prior credential issuers are
    still visible in central records. Purely diagnostic; no trust decision changes.
    """
    registry = get_signing_key_registry()
    active_profile = _normalize_issuer_profile(
        get_placeholder_signing_profile(),
        source="active_profile",
        registry=registry,
    )
    lease_metadata = dict(getattr(lease, "details_json", None) or {}) if lease is not None else {}
    credential_metadata = dict(getattr(credential, "details_json", None) or {}) if credential is not None else {}
    credential_key_id = str(credential_metadata.get("key_id") or "").strip() or None
    lease_key_id = str(
        lease_metadata.get("credential_key_id")
        or credential_key_id
        or lease_metadata.get("lease_key_id")
        or ""
    ).strip() or None
    configured_profile = _normalize_issuer_profile(
        lease_metadata.get("issuer") or credential_metadata.get("issuer") or get_placeholder_signing_profile(),
        source="configured_profile",
        registry=registry,
        fallback_key_id=lease_key_id or credential_key_id,
        preferred_key_id=lease_metadata.get("credential_key_id") or credential_key_id,
    )
    effective_profile = _normalize_issuer_profile(
        (lease_metadata.get("issuer") or credential_metadata.get("issuer") or get_placeholder_signing_profile()),
        source="effective_profile",
        registry=registry,
        fallback_key_id=lease_key_id or credential_key_id,
        preferred_key_id=lease_metadata.get("credential_key_id") or credential_key_id,
    )
    credential_profile = _normalize_issuer_profile(
        credential_metadata.get("issuer"),
        source="credential",
        registry=registry,
        fallback_key_id=credential_key_id,
    )
    lease_profile = _normalize_issuer_profile(
        lease_metadata.get("issuer"),
        source="lease",
        registry=registry,
        fallback_key_id=lease_key_id,
    )

    history: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for item in credentials or ([] if credential is None else [credential]):
        metadata = dict(getattr(item, "details_json", None) or {})
        profile = _normalize_issuer_profile(
            metadata.get("issuer"),
            source="credential_history",
            registry=registry,
            fallback_key_id=(str(metadata.get("key_id") or "").strip() or None),
        )
        signature = (getattr(item, "id", None), profile.get("key_id"), profile.get("issuer"))
        if signature in seen:
            continue
        seen.add(signature)
        history.append({
            **profile,
            "credential_id": getattr(item, "id", None),
            "credential_status": getattr(item, "status", None),
            "replacement_for_credential_id": getattr(item, "replacement_for_credential_id", None),
            "issued_at": iso(getattr(item, "issued_at", None)),
            "revoked_at": iso(getattr(item, "revoked_at", None)),
        })

    sorted_history = sorted(
        history,
        key=lambda item: (item.get("issued_at") or "", item.get("credential_id") or ""),
        reverse=True,
    )

    key_id = effective_profile.get("key_id")
    lineage = build_signing_key_lineage(key_id=key_id, registry=registry) if key_id else {
        "key_id": None,
        "present": False,
        "ancestors": [],
        "descendants": [],
        "rotation_depth": 0,
        "status_path": [],
    }
    support_summary = {
        "effective_source": (
            "lease" if lease_profile.get("present") else (
                "credential" if credential_profile.get("present") else "active_profile"
            )
        ),
        "effective_key_id": effective_profile.get("key_id"),
        "effective_registry_status": effective_profile.get("registry_status"),
        "effective_status": effective_profile.get("status"),
        "history_count": len(sorted_history),
        "history_key_ids": sorted({item.get("key_id") for item in sorted_history if item.get("key_id")}),
        "active_profile_matches_effective": (
            active_profile.get("key_id") == effective_profile.get("key_id")
            if active_profile.get("key_id") and effective_profile.get("key_id")
            else None
        ),
        "credential_profile_matches_effective": (
            credential_profile.get("key_id") == effective_profile.get("key_id")
            if credential_profile.get("key_id") and effective_profile.get("key_id")
            else None
        ),
        "lease_profile_matches_effective": (
            lease_profile.get("key_id") == effective_profile.get("key_id")
            if lease_profile.get("key_id") and effective_profile.get("key_id")
            else None
        ),
        "rotation_depth": lineage.get("rotation_depth") or 0,
    }
    support_summary["transition"] = build_issuer_transition_summary(
        active_profile=active_profile,
        configured_profile=configured_profile,
        effective_profile=effective_profile,
        credential_profile=credential_profile,
        lease_profile=lease_profile,
        lineage=lineage,
    )
    lineage_explanation = {
        "effective_key_id": effective_profile.get("key_id"),
        "effective_source": support_summary.get("effective_source"),
        "lineage_state": None,
        "lineage_note": None,
        "transition_state": support_summary["transition"].get("transition_state"),
        "rotation_depth": summarize_lineage(lineage).get("rotation_depth"),
        "parent_key_id": summarize_lineage(lineage).get("parent_key_id"),
        "terminal_status": summarize_lineage(lineage).get("terminal_status"),
    }
    readback_summary = build_issuer_profile_readback_summary(
        active_profile=active_profile,
        configured_profile=configured_profile,
        effective_profile=effective_profile,
        credential_profile=credential_profile,
        lease_profile=lease_profile,
        history=sorted_history,
        lineage=lineage,
        transition=support_summary["transition"],
        lineage_explanation=lineage_explanation,
    )
    history_summary = build_issuer_history_summary(sorted_history)
    readback_summary["lineage_explanation"] = {
        **(readback_summary.get("lineage_explanation") or {}),
        "lineage_state": readback_summary.get("lineage_state"),
        "lineage_note": readback_summary.get("lineage_note"),
    }

    return {
        "active_profile": active_profile,
        "configured_profile": configured_profile,
        "effective_profile": effective_profile,
        "credential_profile": credential_profile,
        "lease_profile": lease_profile,
        "history": sorted_history,
        "effective_lineage": lineage,
        "effective_lineage_summary": summarize_lineage(lineage),
        "support_summary": support_summary,
        "readback_summary": readback_summary,
        "history_summary": history_summary,
    }


def build_issuer_lineage_explanation(*, issuer_profiles: dict[str, Any] | None) -> dict[str, Any]:
    issuer_profiles = issuer_profiles or {}
    effective_profile = issuer_profiles.get("effective_profile") or {}
    effective_lineage_summary = issuer_profiles.get("effective_lineage_summary") or {}
    readback_summary = issuer_profiles.get("readback_summary") or {}
    support_summary = issuer_profiles.get("support_summary") or {}
    transition = support_summary.get("transition") or {}
    existing = readback_summary.get("lineage_explanation") or {}
    return {
        "effective_key_id": existing.get("effective_key_id") or effective_profile.get("key_id"),
        "effective_source": existing.get("effective_source") or support_summary.get("effective_source"),
        "lineage_state": existing.get("lineage_state") or readback_summary.get("lineage_state"),
        "lineage_note": existing.get("lineage_note") or readback_summary.get("lineage_note"),
        "transition_state": existing.get("transition_state") or transition.get("transition_state"),
        "rotation_depth": existing.get("rotation_depth") if existing.get("rotation_depth") is not None else effective_lineage_summary.get("rotation_depth"),
        "parent_key_id": existing.get("parent_key_id") or effective_lineage_summary.get("parent_key_id"),
        "terminal_status": existing.get("terminal_status") or effective_lineage_summary.get("terminal_status"),
    }


def build_support_contract_source_summary(
    *,
    issuer_profiles: dict[str, Any] | None,
    material_history: dict[str, Any] | None,
) -> dict[str, Any]:
    issuer_profiles = issuer_profiles or {}
    material_history = material_history or {}
    readback_summary = issuer_profiles.get("readback_summary") or {}
    history_summary = issuer_profiles.get("history_summary") or {}
    material_readback_present = "readback_summary" in material_history and bool(material_history.get("readback_summary"))
    material_history_present = bool(material_history)
    material_readback_summary = material_history.get("readback_summary") or build_material_history_readback_summary(material_history=material_history)

    return {
        "issuer_profile_readback": {
            "schema": "darts.issuer_profile_readback_summary.v1",
            "detail_level": "support_compact",
            "present": bool(readback_summary),
            "source_state": "present" if readback_summary else "missing",
            "lineage_state": readback_summary.get("lineage_state"),
            "effective_source": readback_summary.get("effective_source"),
            "has_lineage_explanation": bool(readback_summary.get("lineage_explanation")),
            "has_effective_source_reason": bool(readback_summary.get("effective_source_reason")),
            "has_mismatch_summary": bool(readback_summary.get("mismatch_summary")),
        },
        "issuer_history": {
            "schema": "darts.issuer_history_summary.v1",
            "detail_level": "support_compact",
            "present": bool(history_summary),
            "source_state": "present" if history_summary else "missing",
            "history_state": history_summary.get("history_state"),
            "narrative_state": history_summary.get("narrative_state"),
            "history_count": history_summary.get("history_count"),
            "replacement_relation": history_summary.get("replacement_relation"),
            "has_narrative": bool(history_summary.get("narrative")),
        },
        "material_history_readback": {
            "schema": "darts.material_history.readback_summary.v1",
            "detail_level": "support_compact",
            "present": material_readback_present,
            "source_state": "present" if material_readback_present else ("derived_from_material_history" if material_history_present else "missing"),
            "credential_alignment": ((material_readback_summary.get("credential_history") or {}).get("alignment_state")),
            "lease_alignment": ((material_readback_summary.get("lease_history") or {}).get("alignment_state")),
            "credential_history_count": ((material_readback_summary.get("credential_history") or {}).get("history_count")),
            "lease_history_count": ((material_readback_summary.get("lease_history") or {}).get("history_count")),
            "has_summary": material_readback_summary.get("summary") is not None,
        },
    }


def build_support_contract_state_summary(
    *,
    source_contracts: dict[str, Any] | None,
) -> dict[str, Any]:
    source_contracts = source_contracts or {}
    canonical_names = (
        "issuer_profile_readback",
        "issuer_history",
        "material_history_readback",
    )
    observed_names = sorted(name for name in source_contracts.keys() if isinstance(name, str))
    extra_names = sorted(name for name in observed_names if name not in canonical_names)
    missing_expected_names = [name for name in canonical_names if name not in observed_names]
    all_names = list(canonical_names) + extra_names
    state_names = ("present", "missing", "derived_from_material_history")
    state_counts = {name: 0 for name in state_names}
    source_states: dict[str, str | None] = {}
    present_names: list[str] = []
    derived_names: list[str] = []
    missing_names: list[str] = []

    for name in all_names:
        payload = source_contracts.get(name)
        if not isinstance(payload, dict):
            payload = {"present": False, "source_state": "missing"}
        source_state = payload.get("source_state")
        source_states[name] = source_state
        if source_state in state_counts:
            state_counts[source_state] += 1
        if source_state == "derived_from_material_history":
            derived_names.append(name)
        elif payload.get("present") and source_state == "present":
            present_names.append(name)
        else:
            missing_names.append(name)

    if derived_names:
        overall_state = "derived_present"
    elif present_names and not missing_names:
        overall_state = "complete"
    elif present_names:
        overall_state = "partial"
    else:
        overall_state = "missing"

    summary_parts: list[str] = []
    if present_names:
        summary_parts.append(f"present={len(present_names)}")
    if derived_names:
        summary_parts.append(f"derived={len(derived_names)}")
    if missing_names:
        summary_parts.append(f"missing={len(missing_names)}")

    present_names = sorted(present_names)
    derived_names = sorted(derived_names)
    missing_names = sorted(missing_names)
    total_contracts = len(present_names) + len(derived_names) + len(missing_names)
    expected_contract_count = len(canonical_names)
    observed_contract_count = len(observed_names)
    observed_extra_count = len(extra_names)
    missing_expected_count = len(missing_expected_names)
    coverage_state = (
        "full_set" if all(name in source_contracts for name in canonical_names) else "partial_set"
    )
    if overall_state == "complete" and not extra_names:
        verdict = "canonical_complete"
        verdict_text = "all canonical compact source contracts are present"
    elif overall_state == "derived_present" and not missing_expected_names and not extra_names:
        verdict = "canonical_derived"
        verdict_text = "canonical compact source contracts are visible with at least one derived readback"
    elif overall_state == "missing":
        verdict = "contracts_missing"
        verdict_text = "no compact source contracts are currently visible"
    elif missing_expected_names and extra_names:
        verdict = "contracts_drifted"
        verdict_text = "expected compact source contracts are missing and unexpected contracts are also present"
    elif missing_expected_names:
        verdict = "contracts_incomplete"
        verdict_text = "expected compact source contracts are missing from the observed set"
    elif extra_names:
        verdict = "contracts_extended"
        verdict_text = "all expected compact source contracts are present and additional unexpected contracts were observed"
    else:
        verdict = f"contracts_{overall_state}"
        verdict_text = f"compact source contracts are in a {overall_state} state"

    return {
        "schema": "darts.support_diagnostics.source_contract_state_summary.v1",
        "detail_level": "support_compact",
        "overall_state": overall_state,
        "coverage_state": coverage_state,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "state_counts": {
            **state_counts,
            "detail_level": "support_compact",
        },
        "total_contracts": total_contracts,
        "expected_contract_count": expected_contract_count,
        "observed_contract_count": observed_contract_count,
        "present_contract_count": len(present_names),
        "derived_contract_count": len(derived_names),
        "missing_contract_count": len(missing_names),
        "observed_extra_count": observed_extra_count,
        "missing_expected_count": missing_expected_count,
        "has_present_contracts": bool(present_names),
        "has_derived_contracts": bool(derived_names),
        "has_missing_contracts": bool(missing_names),
        "has_unexpected_contracts": bool(extra_names),
        "has_missing_expected_contracts": bool(missing_expected_names),
        "expected_names": list(canonical_names),
        "observed_names": observed_names,
        "missing_expected_names": missing_expected_names,
        "unexpected_names": extra_names,
        "source_states": {
            **source_states,
            "detail_level": "support_compact",
        },
        "present_names": present_names,
        "derived_names": derived_names,
        "missing_names": missing_names,
        "summary": ", ".join(summary_parts) if summary_parts else "no compact source contracts visible",
    }



def build_support_diagnostics_compact_summary(
    *,
    issuer_profiles: dict[str, Any] | None,
    signing_registry: dict[str, Any] | None,
    material_history: dict[str, Any] | None = None,
    credential=None,
    lease=None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a compact support-facing explanation block for trust diagnostics.

    This stays read-only and central-side. It gives support a concise, stable
    narrative for issuer/signing state without forcing them to parse the full
    issuer history, registry lineage, or verification internals.
    """
    now = aware(now) or utcnow()
    issuer_profiles = issuer_profiles or {}
    signing_registry = signing_registry or {}
    material_history = material_history or {}

    support_summary = issuer_profiles.get("support_summary") or {}
    transition = support_summary.get("transition") or {}
    readback_summary = issuer_profiles.get("readback_summary") or {}
    lineage_explanation = build_issuer_lineage_explanation(issuer_profiles=issuer_profiles)
    signing_support = signing_registry.get("support_summary") or {}
    history_summary = issuer_profiles.get("history_summary") or {}
    material_readback_summary = material_history.get("readback_summary") or build_material_history_readback_summary(material_history=material_history)
    credential_history = material_history.get("credential_history") or {}
    lease_history = material_history.get("lease_history") or {}
    source_contracts = build_support_contract_source_summary(
        issuer_profiles=issuer_profiles,
        material_history=material_history,
    )
    source_contract_state_summary = build_support_contract_state_summary(source_contracts=source_contracts)

    def _compact_summary_block(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                **value,
                "detail_level": "support_compact",
            }
        if value in (None, ""):
            return value
        return {
            "text": str(value),
            "detail_level": "support_compact",
        }

    effective_key_id = support_summary.get("effective_key_id")
    effective_source = support_summary.get("effective_source")
    effective_status = support_summary.get("effective_status") or "unknown"
    transition_state = transition.get("transition_state") or "unknown"
    lineage_state = readback_summary.get("lineage_state") or "standalone"
    mismatch_reasons = list(transition.get("mismatch_reasons") or [])

    issuer_sentence = (
        f"effective issuer comes from {effective_source or 'unknown source'}"
        f" using key {effective_key_id or 'unknown'}"
        f" ({effective_status}; transition={transition_state}; lineage={lineage_state})"
    )

    registry_sentence = (
        f"registry tracks {signing_registry.get('registry_size') or 0} keys"
        f" with statuses {signing_registry.get('status_counts') or {}}"
    )

    reference_flags: list[str] = []
    for label, names in (
        ("unknown", signing_support.get("unknown_reference_names") or []),
        ("retired", signing_support.get("retired_reference_names") or []),
        ("revoked", signing_support.get("revoked_reference_names") or []),
        ("inconsistent", signing_support.get("inconsistent_reference_names") or []),
    ):
        if names:
            reference_flags.append(f"{label}={len(names)}")

    credential_alignment = ((material_readback_summary.get("credential_history") or {}).get("alignment_state"))
    lease_alignment = ((material_readback_summary.get("lease_history") or {}).get("alignment_state"))
    contract_summary = {
        "schema": "darts.support_diagnostics.compact_summary.v1",
        "detail_level": "support_compact",
        "issuer_state": {
            "transition_state": transition_state,
            "lineage_state": lineage_state,
            "effective_status": effective_status,
            "effective_source": effective_source,
            "history_state": history_summary.get("history_state"),
            "history_narrative_state": history_summary.get("narrative_state"),
            "detail_level": "support_compact",
        },
        "material_state": {
            "credential_alignment": credential_alignment,
            "lease_alignment": lease_alignment,
            "has_credential_timestamps": any(
                value is not None
                for value in (
                    iso(getattr(credential, "issued_at", None)) if credential is not None else None,
                    iso(getattr(credential, "expires_at", None)) if credential is not None else None,
                    iso(getattr(credential, "revoked_at", None)) if credential is not None else None,
                )
            ),
            "has_lease_timestamps": any(
                value is not None
                for value in (
                    iso(getattr(lease, "issued_at", None)) if lease is not None else None,
                    iso(getattr(lease, "expires_at", None)) if lease is not None else None,
                    iso(getattr(lease, "grace_until", None)) if lease is not None else None,
                    iso(getattr(lease, "revoked_at", None)) if lease is not None else None,
                )
            ),
            "detail_level": "support_compact",
        },
        "signing_state": {
            "has_reference_flags": bool(reference_flags),
            "reference_flag_count": len(reference_flags),
            "registry_size": signing_registry.get("registry_size") or 0,
            "detail_level": "support_compact",
        },
        "provenance_state": {
            "overall_state": source_contract_state_summary.get("overall_state"),
            "coverage_state": (
                "full"
                if (credential is not None or lease is not None)
                and source_contract_state_summary.get("overall_state") == "complete"
                and source_contract_state_summary.get("coverage_state") == "full_set"
                else source_contract_state_summary.get("coverage_state")
            ),
            "verdict": source_contract_state_summary.get("verdict"),
            "verdict_text": source_contract_state_summary.get("verdict_text"),
            **({
                "total_contracts": source_contract_state_summary.get("total_contracts"),
                "expected_contract_count": source_contract_state_summary.get("expected_contract_count"),
                "observed_contract_count": source_contract_state_summary.get("observed_contract_count"),
                "expected_names": list(source_contract_state_summary.get("expected_names") or []),
                "observed_names": list(source_contract_state_summary.get("observed_names") or []),
            } if credential is None and lease is None else {}),
            "present_contract_count": source_contract_state_summary.get("present_contract_count"),
            "derived_contract_count": source_contract_state_summary.get("derived_contract_count"),
            "missing_contract_count": source_contract_state_summary.get("missing_contract_count"),
            "missing_expected_count": source_contract_state_summary.get("missing_expected_count"),
            "observed_extra_count": source_contract_state_summary.get("observed_extra_count"),
            "has_missing_expected_contracts": source_contract_state_summary.get("has_missing_expected_contracts"),
            "has_unexpected_contracts": source_contract_state_summary.get("has_unexpected_contracts"),
            "present_names": (
                ["issuer_profile_readback", "issuer_history", "material_history_readback"]
                if (credential is not None or lease is not None)
                and source_contract_state_summary.get("overall_state") == "complete"
                and not source_contract_state_summary.get("unexpected_names")
                and not source_contract_state_summary.get("missing_expected_names")
                else list(source_contract_state_summary.get("present_names") or [])
            ),
            "derived_names": list(source_contract_state_summary.get("derived_names") or []),
            "missing_names": list(source_contract_state_summary.get("missing_names") or []),
            "missing_expected_names": list(source_contract_state_summary.get("missing_expected_names") or []),
            "unexpected_names": list(source_contract_state_summary.get("unexpected_names") or []),
            "summary": source_contract_state_summary.get("summary"),
            "detail_level": "support_compact",
        },
    }

    return {
        "generated_at": iso(now),
        "contract_summary": contract_summary,
        "issuer_state": {
            "effective_source": effective_source,
            "effective_key_id": effective_key_id,
            "effective_status": effective_status,
            "transition_state": transition_state,
            "lineage_state": lineage_state,
            "mismatch_reason_count": len(mismatch_reasons),
            "history_count": support_summary.get("history_count") or 0,
            "summary": issuer_sentence,
            "detail_level": "support_compact",
        },
        "signing_state": {
            "registry_size": signing_registry.get("registry_size") or 0,
            "status_counts": {
                **(signing_registry.get("status_counts") or {}),
                "detail_level": "support_compact",
            },
            "reference_flags": reference_flags,
            "summary": registry_sentence,
            "detail_level": "support_compact",
        },
        "material_timestamps": {
            "credential_issued_at": iso(getattr(credential, "issued_at", None)) if credential is not None else None,
            "credential_expires_at": iso(getattr(credential, "expires_at", None)) if credential is not None else None,
            "credential_revoked_at": iso(getattr(credential, "revoked_at", None)) if credential is not None else None,
            "lease_issued_at": iso(getattr(lease, "issued_at", None)) if lease is not None else None,
            "lease_expires_at": iso(getattr(lease, "expires_at", None)) if lease is not None else None,
            "lease_grace_until": iso(getattr(lease, "grace_until", None)) if lease is not None else None,
            "lease_revoked_at": iso(getattr(lease, "revoked_at", None)) if lease is not None else None,
            "detail_level": "support_compact",
        },
        "support_notes": {
            "effective_source_reason": readback_summary.get("effective_source_reason"),
            "lineage_note": readback_summary.get("lineage_note"),
            "lineage_explanation": {
                **lineage_explanation,
                "detail_level": "support_compact",
            },
            "source_contracts": source_contracts,
            "source_contract_summary": source_contract_state_summary,
            "mismatch_summary": readback_summary.get("mismatch_summary"),
            "history_narrative": history_summary.get("narrative"),
        "history_state": {
            "history_state": history_summary.get("history_state"),
            "replacement_relation": history_summary.get("replacement_relation"),
            "narrative_state": history_summary.get("narrative_state"),
            "history_count": history_summary.get("history_count"),
            "status_counts": {
                **(history_summary.get("status_counts") or {}),
                "detail_level": "support_compact",
            },
            "detail_level": "support_compact",
        },
            "credential_narrative": credential_history.get("narrative"),
            "lease_narrative": lease_history.get("narrative"),
            "material_summary": _compact_summary_block(material_history.get("summary")),
            "material_alignment": {
                "credential": credential_alignment,
                "lease": lease_alignment,
                "detail_level": "support_compact",
            },
            "detail_level": "support_compact",
        },
        "history_state": {
            **history_summary,
            "status_counts": {
                **(history_summary.get("status_counts") or {}),
                "detail_level": "support_compact",
            },
            "detail_level": "support_compact",
        },
        "material_history": {
            **material_history,
            "summary": _compact_summary_block(material_history.get("summary")),
            "credential_history": {
                **(material_history.get("credential_history") or {}),
                "status_counts": {
                    **(((material_history.get("credential_history") or {}).get("status_counts")) or {}),
                    "detail_level": "support_compact",
                },
                "detail_level": "support_compact",
            },
            "lease_history": {
                **(material_history.get("lease_history") or {}),
                "status_counts": {
                    **(((material_history.get("lease_history") or {}).get("status_counts")) or {}),
                    "detail_level": "support_compact",
                },
                "detail_level": "support_compact",
            },
            "detail_level": "support_compact",
        },
        "material_readback_summary": {
            **material_readback_summary,
            "summary": _compact_summary_block(material_readback_summary.get("summary")),
            "credential_history": {
                **(material_readback_summary.get("credential_history") or {}),
                "status_counts": {
                    **(((material_readback_summary.get("credential_history") or {}).get("status_counts")) or {}),
                    "detail_level": "support_compact",
                },
                "detail_level": "support_compact",
            },
            "lease_history": {
                **(material_readback_summary.get("lease_history") or {}),
                "status_counts": {
                    **(((material_readback_summary.get("lease_history") or {}).get("status_counts")) or {}),
                    "detail_level": "support_compact",
                },
                "detail_level": "support_compact",
            },
            "detail_level": "support_compact",
        },
    }


def build_signing_registry_diagnostics(
    *,
    credential=None,
    lease=None,
    device=None,
    credentials: list[Any] | None = None,
    include_entries: bool = True,
) -> dict[str, Any]:
    """Summarize central signing registry state for admin/readback diagnostics.

    Purely additive: this does not change trust decisions. It helps operators inspect
    active vs retired/revoked keys, current placeholder issuer consistency, and which
    registry entries are referenced by credential / lease / device snapshots.
    """
    registry = get_signing_key_registry()
    status_counts: dict[str, int] = {}
    for entry in registry.values():
        status = str(entry.get("status") or "active")
        status_counts[status] = status_counts.get(status, 0) + 1

    active_profile = get_placeholder_signing_profile()
    referenced_key_ids: dict[str, str | None] = {
        "active_profile": active_profile.get("key_id"),
        "device_credential_key_id": getattr(device, "credential_key_id", None) if device is not None else None,
        "credential_key_id": ((getattr(credential, "details_json", None) or {}).get("key_id") if credential is not None else None),
        "credential_issuer_key_id": (((getattr(credential, "details_json", None) or {}).get("issuer") or {}).get("key_id") if credential is not None else None),
        "lease_key_id": ((getattr(lease, "details_json", None) or {}).get("lease_key_id") if lease is not None else None),
        "lease_issuer_key_id": (((getattr(lease, "details_json", None) or {}).get("issuer") or {}).get("key_id") if lease is not None else None),
    }
    referenced_inspections = {
        name: inspect_signing_issuer({"key_id": key_id}) if key_id else {"key_id": None, "status": "missing_key_id", "entry": None, "registry_size": len(registry)}
        for name, key_id in referenced_key_ids.items()
    }

    consistency = {
        "active_profile_matches_credential_issuer": (
            referenced_key_ids["credential_issuer_key_id"] == referenced_key_ids["active_profile"]
            if referenced_key_ids["credential_issuer_key_id"]
            else None
        ),
        "active_profile_matches_lease_issuer": (
            referenced_key_ids["lease_issuer_key_id"] == referenced_key_ids["active_profile"]
            if referenced_key_ids["lease_issuer_key_id"]
            else None
        ),
        "lease_key_matches_lease_issuer": (
            referenced_key_ids["lease_key_id"] == referenced_key_ids["lease_issuer_key_id"]
            if referenced_key_ids["lease_key_id"] or referenced_key_ids["lease_issuer_key_id"]
            else None
        ),
        "device_key_matches_credential_key": (
            referenced_key_ids["device_credential_key_id"] == referenced_key_ids["credential_key_id"]
            if referenced_key_ids["device_credential_key_id"] and referenced_key_ids["credential_key_id"]
            else None
        ),
    }

    key_lineage = {
        name: build_signing_key_lineage(key_id=key_id, registry=registry)
        for name, key_id in referenced_key_ids.items()
        if key_id
    }
    credential_rotation = build_credential_rotation_lineage(credential=credential, credentials=credentials)

    diagnostics = {
        "active_profile": active_profile,
        "registry_size": len(registry),
        "status_counts": status_counts,
        "referenced_key_ids": referenced_key_ids,
        "referenced_keys": referenced_inspections,
        "key_lineage": key_lineage,
        "key_lineage_summary": {
            name: summarize_lineage(lineage)
            for name, lineage in key_lineage.items()
        },
        "credential_rotation": credential_rotation,
        "credential_rotation_summary": summarize_credential_rotation(credential_rotation),
        "consistency": consistency,
        "support_summary": {
            "registry_size": len(registry),
            "status_counts": status_counts,
            "unknown_reference_names": sorted([
                name for name, inspection in referenced_inspections.items()
                if inspection.get("status") == "unknown"
            ]),
            "revoked_reference_names": sorted([
                name for name, inspection in referenced_inspections.items()
                if ((inspection.get("entry") or {}).get("status") == "revoked")
            ]),
            "retired_reference_names": sorted([
                name for name, inspection in referenced_inspections.items()
                if ((inspection.get("entry") or {}).get("status") == "retired")
            ]),
            "inconsistent_reference_names": sorted([
                name for name, matches in consistency.items() if matches is False
            ]),
            "rotation_depths": {
                "credential": (credential_rotation.get("rotation_depth") or 0),
                **{
                    name: (lineage.get("rotation_depth") or 0)
                    for name, lineage in key_lineage.items()
                },
            },
        },
    }
    if include_entries:
        diagnostics["entries"] = list(registry.values())
    return diagnostics


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict[str, Any]) -> str:
    digest = hmac.new(_signing_secret().encode("utf-8"), _canonical_json(payload), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _normalize_text_block(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.replace("\r", "").strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned or None


def normalize_pem_block(value: str | None) -> str | None:
    """Normalize PEM-ish input for stable fingerprinting/storage.

    Keeps BEGIN/END markers when present, removes surrounding noise, and wraps body
    to a consistent width. If the input is not PEM-shaped, returns a cleaned string.
    """
    cleaned = _normalize_text_block(value)
    if not cleaned:
        return None

    if "-----BEGIN " not in cleaned or "-----END " not in cleaned:
        return cleaned

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    begin = next((line for line in lines if line.startswith("-----BEGIN ")), None)
    end = next((line for line in reversed(lines) if line.startswith("-----END ")), None)
    if not begin or not end:
        return cleaned

    try:
        begin_index = lines.index(begin)
        end_index = len(lines) - 1 - lines[::-1].index(end)
    except ValueError:
        return cleaned

    body = "".join(lines[begin_index + 1:end_index])
    body = re.sub(r"\s+", "", body)
    if not body:
        return "\n".join([begin, end])

    wrapped = [body[i:i + PEM_LINE_WIDTH] for i in range(0, len(body), PEM_LINE_WIDTH)]
    return "\n".join([begin, *wrapped, end])


def fingerprint_text(value: str | None) -> str | None:
    normalized = normalize_pem_block(value)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def derive_key_id(*, public_key_pem: str | None = None, csr_pem: str | None = None, fingerprint: str | None = None) -> str | None:
    material = fingerprint or fingerprint_text(public_key_pem) or fingerprint_text(csr_pem)
    if not material:
        return None
    return f"kid_{material[:16]}"


def normalize_enrollment_material(
    *,
    csr_pem: str | None,
    public_key_pem: str | None,
    fingerprint: str | None,
) -> dict[str, Any]:
    normalized_csr = normalize_pem_block(csr_pem)
    normalized_public_key = normalize_pem_block(public_key_pem)
    derived_fingerprint = fingerprint or fingerprint_text(normalized_public_key) or fingerprint_text(normalized_csr)
    key_id = derive_key_id(
        public_key_pem=normalized_public_key,
        csr_pem=normalized_csr,
        fingerprint=derived_fingerprint,
    )
    return {
        "csr_pem": normalized_csr,
        "public_key_pem": normalized_public_key,
        "fingerprint": derived_fingerprint,
        "key_id": key_id,
    }


def build_placeholder_signed_lease(*, device, lease, credential=None, issued_by: str | None = None) -> dict[str, Any]:
    metadata = dict(lease.details_json or {})
    signing = get_placeholder_signing_profile()
    lease_key_id = metadata.get("lease_key_id") or signing["key_id"]
    credential_metadata = dict(getattr(credential, "details_json", None) or {}) if credential is not None else {}
    payload = {
        "schema": "darts.device_lease.v1",
        "mode": metadata.get("mode", "placeholder"),
        "device_id": device.id,
        "lease_id": lease.lease_id,
        "license_id": lease.central_license_id or device.license_id,
        "trust_status": getattr(device, "trust_status", None),
        "credential_status": getattr(device, "credential_status", None),
        "lease_status": getattr(device, "lease_status", None) or lease.status,
        "issued_at": iso(lease.issued_at),
        "expires_at": iso(lease.expires_at),
        "grace_until": iso(lease.grace_until),
        "revoked_at": iso(lease.revoked_at),
        "issued_by": issued_by or metadata.get("issued_by") or metadata.get("issued_by_role"),
        "issuer": {
            **signing,
            "key_id": lease_key_id,
        },
        "capabilities": metadata.get("capability_overrides") or {},
        "credential": {
            "fingerprint": getattr(credential, "fingerprint", None) if credential is not None else getattr(device, "credential_fingerprint", None),
            "status": getattr(credential, "status", None) if credential is not None else getattr(device, "credential_status", None),
            "issued_at": iso(getattr(credential, "issued_at", None)) if credential is not None else iso(getattr(device, "credential_issued_at", None)),
            "expires_at": iso(getattr(credential, "expires_at", None)) if credential is not None else iso(getattr(device, "credential_expires_at", None)),
            "key_id": metadata.get("credential_key_id") or credential_metadata.get("key_id") or getattr(device, "credential_key_id", None),
        },
    }
    return {
        "payload": payload,
        "signature": sign_payload(payload),
        "signature_scheme": signing["algorithm"],
        "key_id": lease_key_id,
        "issuer": payload["issuer"],
    }


def build_placeholder_certificate(*, device_id: str, fingerprint: str | None, key_id: str | None, issued_at: datetime, expires_at: datetime | None, issuer: dict[str, Any] | None = None) -> str:
    payload = {
        "schema": "darts.device_credential.placeholder.v1",
        "device_id": device_id,
        "fingerprint": fingerprint,
        "key_id": key_id,
        "issuer": issuer or get_placeholder_signing_profile(),
        "issued_at": iso(issued_at),
        "expires_at": iso(expires_at),
        "nonce": secrets.token_hex(8),
    }
    encoded = base64.b64encode(_canonical_json(payload)).decode("ascii")
    return (
        "-----BEGIN DARTS DEVICE CREDENTIAL-----\n"
        f"{encoded}\n"
        "-----END DARTS DEVICE CREDENTIAL-----"
    )


def _b64decode_loose(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def parse_placeholder_certificate(certificate_pem: str | None) -> dict[str, Any]:
    if not certificate_pem:
        return {"valid": False, "reason": "missing certificate"}

    normalized = _normalize_text_block(certificate_pem)
    if not normalized:
        return {"valid": False, "reason": "missing certificate"}

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(lines) < 3:
        return {"valid": False, "reason": "malformed certificate"}
    if lines[0] != "-----BEGIN DARTS DEVICE CREDENTIAL-----" or lines[-1] != "-----END DARTS DEVICE CREDENTIAL-----":
        return {"valid": False, "reason": "unexpected certificate envelope"}

    encoded = "".join(lines[1:-1])
    try:
        decoded = base64.b64decode(encoded.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        return {"valid": False, "reason": "certificate payload decode failed"}

    if payload.get("schema") != "darts.device_credential.placeholder.v1":
        return {"valid": False, "reason": "unexpected certificate schema", "payload": payload}

    return {"valid": True, "payload": payload}


def verify_placeholder_certificate(*, credential, device=None, now: datetime | None = None) -> dict[str, Any]:
    now = aware(now) or utcnow()
    payload_info = parse_placeholder_certificate(getattr(credential, "certificate_pem", None))
    errors: list[str] = []
    warnings: list[str] = []
    payload = payload_info.get("payload") or {}

    if not payload_info.get("valid"):
        errors.append(payload_info.get("reason") or "certificate parse failed")

    metadata = dict(getattr(credential, "details_json", None) or {})
    stored_fingerprint = getattr(credential, "fingerprint", None)
    stored_key_id = metadata.get("key_id")
    stored_issuer = metadata.get("issuer") or {}
    payload_issuer = payload.get("issuer") or {}
    issuer_inspection = inspect_signing_issuer(payload_issuer or stored_issuer)
    device_id = getattr(device, "id", None) if device is not None else None

    if payload:
        if device_id and payload.get("device_id") != device_id:
            errors.append("certificate device_id mismatch")
        if stored_fingerprint and payload.get("fingerprint") != stored_fingerprint:
            errors.append("certificate fingerprint mismatch")
        if stored_key_id and payload.get("key_id") != stored_key_id:
            errors.append("certificate key_id mismatch")
        if stored_issuer.get("key_id") and payload_issuer.get("key_id") != stored_issuer.get("key_id"):
            errors.append("certificate issuer key_id mismatch")
        if stored_issuer.get("issuer") and payload_issuer.get("issuer") != stored_issuer.get("issuer"):
            errors.append("certificate issuer mismatch")

    if issuer_inspection["status"] == "missing_key_id":
        warnings.append("certificate issuer key_id missing")
    elif issuer_inspection["status"] == "unknown":
        warnings.append("certificate issuer key_id unknown to central registry")

    registry_entry = issuer_inspection.get("entry") or {}
    if registry_entry.get("status") == "retired":
        warnings.append("certificate issuer key_id retired in central registry")
    elif registry_entry.get("status") == "revoked":
        errors.append("certificate issuer key_id revoked in central registry")

    derived_key_id = derive_key_id(
        public_key_pem=getattr(credential, "public_key_pem", None),
        csr_pem=getattr(credential, "csr_pem", None),
        fingerprint=stored_fingerprint,
    )
    if stored_key_id and derived_key_id and stored_key_id != derived_key_id:
        errors.append("credential key_id does not match enrollment material")
    if not stored_key_id:
        warnings.append("credential key_id missing")
    if not stored_fingerprint:
        warnings.append("credential fingerprint missing")

    expires_at = aware(getattr(credential, "expires_at", None))
    revoked_at = aware(getattr(credential, "revoked_at", None))
    timing_status = "active"
    if revoked_at:
        timing_status = "revoked"
    elif expires_at and now > expires_at:
        timing_status = "expired"

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "timing_status": timing_status,
        "payload": payload if payload else None,
        "derived_key_id": derived_key_id,
        "stored_key_id": stored_key_id,
        "stored_fingerprint": stored_fingerprint,
        "issuer_inspection": issuer_inspection,
    }


def verify_placeholder_signed_lease(*, bundle: dict[str, Any] | None, device=None, lease=None, credential=None, now: datetime | None = None) -> dict[str, Any]:
    now = aware(now) or utcnow()
    errors: list[str] = []
    warnings: list[str] = []
    bundle = bundle or {}
    payload = bundle.get("payload") or {}
    signature = bundle.get("signature")

    if bundle.get("signature_scheme") != "hmac-sha256-placeholder":
        errors.append("unexpected signature scheme")
    if payload.get("schema") != "darts.device_lease.v1":
        errors.append("unexpected lease schema")

    if payload:
        expected_signature = sign_payload(payload)
        if not signature or not hmac.compare_digest(signature, expected_signature):
            errors.append("lease signature mismatch")

    issuer = payload.get("issuer") or {}
    issuer_inspection = inspect_signing_issuer(issuer)
    bundle_key_id = bundle.get("key_id")
    if bundle_key_id and issuer.get("key_id") and issuer.get("key_id") != bundle_key_id:
        errors.append("lease issuer key_id mismatch")
    if issuer_inspection["status"] == "missing_key_id":
        warnings.append("lease issuer key_id missing")
    elif issuer_inspection["status"] == "unknown":
        warnings.append("lease issuer key_id unknown to central registry")

    registry_entry = issuer_inspection.get("entry") or {}
    if registry_entry.get("status") == "retired":
        warnings.append("lease issuer key_id retired in central registry")
    elif registry_entry.get("status") == "revoked":
        errors.append("lease issuer key_id revoked in central registry")

    device_id = getattr(device, "id", None) if device is not None else None
    if device_id and payload.get("device_id") != device_id:
        errors.append("lease device_id mismatch")
    if lease is not None and payload.get("lease_id") != getattr(lease, "lease_id", None):
        errors.append("lease_id mismatch")
    if device is not None and payload.get("license_id") != (getattr(lease, "central_license_id", None) or getattr(device, "license_id", None)):
        errors.append("license_id mismatch")

    metadata = dict(getattr(lease, "details_json", None) or {}) if lease is not None else {}
    credential_meta = dict(getattr(credential, "details_json", None) or {}) if credential is not None else {}
    expected_credential_key_id = metadata.get("credential_key_id") or credential_meta.get("key_id") or getattr(device, "credential_key_id", None)
    payload_credential = payload.get("credential") or {}
    payload_key_id = payload_credential.get("key_id")
    payload_fingerprint = payload_credential.get("fingerprint")
    expected_fingerprint = getattr(credential, "fingerprint", None) if credential is not None else getattr(device, "credential_fingerprint", None)

    expected_lease_key_id = metadata.get("lease_key_id") or get_placeholder_signing_profile()["key_id"]
    if expected_lease_key_id and bundle_key_id != expected_lease_key_id:
        errors.append("lease signing key_id mismatch")
    if expected_credential_key_id and payload_key_id != expected_credential_key_id:
        errors.append("lease credential key_id mismatch")
    if expected_fingerprint and payload_fingerprint != expected_fingerprint:
        errors.append("lease credential fingerprint mismatch")
    if payload_key_id and payload_fingerprint:
        derived_from_payload = derive_key_id(fingerprint=payload_fingerprint)
        if derived_from_payload and payload_key_id != derived_from_payload:
            errors.append("lease credential key_id inconsistent with fingerprint")
    if not payload_key_id:
        warnings.append("lease credential key_id missing")
    if not payload_fingerprint:
        warnings.append("lease credential fingerprint missing")

    expires_at_raw = payload.get("expires_at")
    grace_until_raw = payload.get("grace_until")
    revoked_at_raw = payload.get("revoked_at")
    expires_at = aware(datetime.fromisoformat(expires_at_raw)) if expires_at_raw else None
    grace_until = aware(datetime.fromisoformat(grace_until_raw)) if grace_until_raw else None
    revoked_at = aware(datetime.fromisoformat(revoked_at_raw)) if revoked_at_raw else None
    timing_status = "active"
    if revoked_at:
        timing_status = "revoked"
    elif expires_at and now > expires_at:
        timing_status = "grace" if grace_until and now <= grace_until else "expired"

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "timing_status": timing_status,
        "payload": payload if payload else None,
        "issuer": issuer or None,
        "issuer_inspection": issuer_inspection,
        "expected_lease_key_id": expected_lease_key_id,
        "expected_credential_key_id": expected_credential_key_id,
        "expected_fingerprint": expected_fingerprint,
    }


def compute_lease_status(lease, now: datetime | None = None) -> str:
    now = aware(now) or utcnow()
    if lease is None:
        return "none"
    if getattr(lease, "revoked_at", None):
        return "revoked"
    expires_at = aware(getattr(lease, "expires_at", None))
    grace_until = aware(getattr(lease, "grace_until", None))
    if expires_at and now > expires_at:
        if grace_until and now <= grace_until:
            return "grace"
        return "expired"
    return getattr(lease, "status", None) or "pending"


def compute_credential_status(credential, now: datetime | None = None) -> str:
    now = aware(now) or utcnow()
    if credential is None:
        return "none"
    if getattr(credential, "revoked_at", None):
        return "revoked"
    expires_at = aware(getattr(credential, "expires_at", None))
    if expires_at and now > expires_at:
        return "expired"
    return getattr(credential, "status", None) or "pending"


def derive_trust_state(*, current_trust_status: str | None, credential_status: str | None, lease_status: str | None) -> tuple[str, str]:
    if lease_status == "revoked" or credential_status == "revoked":
        return "revoked", "revoked credential or lease"
    if lease_status == "expired" or credential_status == "expired":
        return "degraded", "credential or lease expired"
    if lease_status == "grace":
        return "degraded", "lease in grace window"
    if credential_status == "pending":
        return "pending_enrollment", "credential pending issuance"
    if credential_status == "active" and lease_status == "active":
        return "trusted", "credential + lease recorded"
    return current_trust_status or "legacy_bound", "state unchanged"


def sync_device_trust_snapshot(device, lease=None, credential=None, now: datetime | None = None) -> None:
    now = aware(now) or utcnow()
    lease_status = compute_lease_status(lease, now) if lease is not None else getattr(device, "lease_status", None)
    credential_status = compute_credential_status(credential, now) if credential is not None else getattr(device, "credential_status", None)
    trust_status, trust_reason = derive_trust_state(
        current_trust_status=getattr(device, "trust_status", None),
        credential_status=credential_status,
        lease_status=lease_status,
    )
    device.lease_status = lease_status
    device.credential_status = credential_status or getattr(device, "credential_status", None)
    if credential is not None:
        device.credential_fingerprint = credential.fingerprint
        device.credential_issued_at = credential.issued_at
        device.credential_expires_at = credential.expires_at
        setattr(device, "credential_key_id", (credential.details_json or {}).get("key_id"))
    if lease is not None:
        device.lease_id = lease.lease_id
        device.lease_issued_at = lease.issued_at
        device.lease_expires_at = lease.expires_at
        device.lease_grace_until = lease.grace_until
        metadata = dict(lease.details_json or {})
        metadata["signed_bundle"] = build_placeholder_signed_lease(device=device, lease=lease, credential=credential)
        device.lease_metadata = metadata
    if getattr(device, "trust_status", None) != trust_status or getattr(device, "trust_reason", None) != trust_reason:
        device.trust_status = trust_status
        device.trust_reason = trust_reason
        device.trust_last_changed_at = now


def issue_placeholder_credential(*, credential, device, issued_by: str, validity_days: int = 30, now: datetime | None = None) -> None:
    now = aware(now) or utcnow()
    expires_at = now + timedelta(days=validity_days) if validity_days > 0 else None
    signing = get_placeholder_signing_profile()
    material = normalize_enrollment_material(
        csr_pem=getattr(credential, "csr_pem", None),
        public_key_pem=getattr(credential, "public_key_pem", None),
        fingerprint=getattr(credential, "fingerprint", None),
    )
    metadata = dict(getattr(credential, "details_json", None) or {})
    metadata.update({
        "issued_by": issued_by,
        "issued_mode": "placeholder",
        "issued_at": iso(now),
        "key_id": material["key_id"],
        "issuer": signing,
    })
    credential.csr_pem = material["csr_pem"]
    credential.public_key_pem = material["public_key_pem"]
    credential.fingerprint = material["fingerprint"]
    credential.certificate_pem = build_placeholder_certificate(
        device_id=device.id,
        fingerprint=material["fingerprint"],
        key_id=material["key_id"],
        issued_at=now,
        expires_at=expires_at,
        issuer=signing,
    )
    credential.issued_at = now
    credential.expires_at = expires_at
    credential.revoked_at = None
    credential.status = "active"
    credential.details_json = metadata
    sync_device_trust_snapshot(device, credential=credential, now=now)


def revoke_placeholder_credential(*, credential, device, reason: str | None, revoked_by: str, now: datetime | None = None) -> None:
    now = aware(now) or utcnow()
    metadata = dict(getattr(credential, "details_json", None) or {})
    metadata.update({
        "revoked_reason": reason or "manual revoke",
        "revoked_by": revoked_by,
        "revoked_at": iso(now),
    })
    credential.revoked_at = now
    credential.status = "revoked"
    credential.details_json = metadata
    sync_device_trust_snapshot(device, credential=credential, now=now)


def attach_lease_key_metadata(*, lease, credential) -> None:
    metadata = dict(getattr(lease, "details_json", None) or {})
    credential_meta = dict(getattr(credential, "details_json", None) or {}) if credential is not None else {}
    signing = get_placeholder_signing_profile()
    metadata.setdefault("lease_key_id", signing["key_id"])
    metadata.setdefault("issuer", signing)
    if credential is not None:
        metadata["credential_id"] = getattr(credential, "id", None)
    if credential_meta.get("key_id"):
        metadata["credential_key_id"] = credential_meta["key_id"]
    lease.details_json = metadata


def revoke_placeholder_lease(*, lease, device, reason: str | None, revoked_by: str, credential=None, now: datetime | None = None) -> None:
    now = aware(now) or utcnow()
    metadata = dict(getattr(lease, "details_json", None) or {})
    metadata.update({
        "revoked_reason": reason or "manual revoke",
        "revoked_by": revoked_by,
        "revoked_at": iso(now),
    })
    lease.revoked_at = now
    lease.status = "revoked"
    lease.details_json = metadata
    sync_device_trust_snapshot(device, lease=lease, credential=credential, now=now)


def get_stored_signed_lease_bundle(lease) -> dict[str, Any] | None:
    metadata = dict(getattr(lease, "details_json", None) or {}) if lease is not None else {}
    bundle = metadata.get("signed_bundle")
    return bundle if isinstance(bundle, dict) else None


def summarize_findings(findings: list[dict[str, Any]] | None) -> dict[str, Any]:
    findings = findings or []
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    source_counts: dict[str, int] = {}
    for item in findings:
        severity = item.get("severity") or "info"
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        source = item.get("source") or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
    highest = "ok"
    if severity_counts.get("error"):
        highest = "error"
    elif severity_counts.get("warning"):
        highest = "warning"
    elif findings:
        highest = "info"
    return {
        "total": len(findings),
        "highest_severity": highest,
        "severity_counts": severity_counts,
        "source_counts": source_counts,
    }


def build_reconciliation_summary(*, reconciliation: dict[str, Any] | None) -> dict[str, Any]:
    reconciliation = reconciliation or {}
    findings = reconciliation.get("findings") or []
    summary = summarize_findings(findings)
    registry_diagnostics = reconciliation.get("signing_registry") or {}
    issuer_profiles = reconciliation.get("issuer_profiles") or {}
    lineage_explanation = build_issuer_lineage_explanation(issuer_profiles=issuer_profiles)
    material_history = reconciliation.get("material_history") or {}
    material_readback_summary = material_history.get("readback_summary") or build_material_history_readback_summary(material_history=material_history)
    source_contracts = build_support_contract_source_summary(
        issuer_profiles=issuer_profiles,
        material_history=material_history,
    )
    source_contract_state_summary = build_support_contract_state_summary(source_contracts=source_contracts)
    source_contract_state_summary = {
        k: v
        for k, v in source_contract_state_summary.items()
        if k not in {"verdict", "verdict_text"}
    }
    summary.update({
        "ok": reconciliation.get("ok", summary["highest_severity"] != "error"),
        "bundle_source": reconciliation.get("bundle_source"),
        "timing_status": {
            "credential": (reconciliation.get("credential") or {}).get("timing_status"),
            "lease": (reconciliation.get("lease") or {}).get("timing_status"),
        },
        "issuer_registry_status": {
            "credential": ((reconciliation.get("credential") or {}).get("issuer_inspection") or {}).get("status"),
            "lease": ((reconciliation.get("lease") or {}).get("issuer_inspection") or {}).get("status"),
        },
        "signing_registry": {
            "registry_size": registry_diagnostics.get("registry_size"),
            "status_counts": registry_diagnostics.get("status_counts") or {},
            "rotation_depths": {
                "credential": ((registry_diagnostics.get("credential_rotation") or {}).get("rotation_depth")),
                "credential_key": ((registry_diagnostics.get("key_lineage") or {}).get("credential_key_id") or {}).get("rotation_depth"),
                "lease_key": ((registry_diagnostics.get("key_lineage") or {}).get("lease_key_id") or {}).get("rotation_depth"),
            },
        },
        "issuer_profiles": {
            "effective_key_id": ((issuer_profiles.get("effective_profile") or {}).get("key_id")),
            "effective_source": ((issuer_profiles.get("support_summary") or {}).get("effective_source")),
            "history_count": len(issuer_profiles.get("history") or []),
            "rotation_depth": ((issuer_profiles.get("effective_lineage") or {}).get("rotation_depth")),
            "transition": ((issuer_profiles.get("support_summary") or {}).get("transition") or {}),
            "lineage_explanation": lineage_explanation,
            "readback_summary": ((issuer_profiles.get("readback_summary") or {})),
            "history_summary": ((issuer_profiles.get("history_summary") or {})),
            "source_contracts": source_contracts,
            "source_contract_summary": source_contract_state_summary,
        },
        "material_history": material_history,
        "material_readback_summary": material_readback_summary,
        "support_summary": (registry_diagnostics.get("support_summary") or {}),
    })
    return summary


def reconcile_trust_material(*, device=None, credential=None, lease=None, credentials: list[Any] | None = None, leases: list[Any] | None = None, bundle: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = aware(now) or utcnow()
    findings: list[dict[str, Any]] = []

    credential_verification = None
    if credential is not None:
        credential_verification = verify_placeholder_certificate(credential=credential, device=device, now=now)
        for error in credential_verification["errors"]:
            findings.append({"severity": "error", "source": "credential", "message": error})
        for warning in credential_verification["warnings"]:
            findings.append({"severity": "warning", "source": "credential", "message": warning})

    stored_bundle = get_stored_signed_lease_bundle(lease)
    resolved_bundle = bundle or stored_bundle or (
        build_placeholder_signed_lease(device=device, lease=lease, credential=credential) if device is not None and lease is not None else None
    )

    lease_verification = None
    if lease is not None or resolved_bundle is not None:
        lease_verification = verify_placeholder_signed_lease(
            bundle=resolved_bundle,
            device=device,
            lease=lease,
            credential=credential,
            now=now,
        ) if resolved_bundle is not None else None
        if lease_verification is not None:
            for error in lease_verification["errors"]:
                findings.append({"severity": "error", "source": "lease", "message": error})
            for warning in lease_verification["warnings"]:
                findings.append({"severity": "warning", "source": "lease", "message": warning})

    if stored_bundle is not None and device is not None and lease is not None:
        expected_bundle = build_placeholder_signed_lease(device=device, lease=lease, credential=credential)
        if stored_bundle != expected_bundle:
            findings.append({
                "severity": "warning",
                "source": "lease",
                "message": "stored signed lease bundle drifted from current central reconstruction",
            })

    if credential_verification is not None:
        credential_registry_entry = (credential_verification.get("issuer_inspection") or {}).get("entry") or {}
        credential_registry_status = (credential_verification.get("issuer_inspection") or {}).get("status")
        if credential_registry_status == "unknown":
            findings.append({
                "severity": "warning",
                "source": "credential",
                "message": "credential issuer key_id not present in central signing registry",
            })
        elif credential_registry_entry.get("status") == "retired":
            findings.append({
                "severity": "warning",
                "source": "credential",
                "message": "credential issued by retired central signing key",
            })
        elif credential_registry_entry.get("status") == "revoked":
            findings.append({
                "severity": "error",
                "source": "credential",
                "message": "credential issued by revoked central signing key",
            })

    if lease_verification is not None:
        lease_registry_entry = (lease_verification.get("issuer_inspection") or {}).get("entry") or {}
        lease_registry_status = (lease_verification.get("issuer_inspection") or {}).get("status")
        if lease_registry_status == "unknown":
            findings.append({
                "severity": "warning",
                "source": "lease",
                "message": "lease issuer key_id not present in central signing registry",
            })
        elif lease_registry_entry.get("status") == "retired":
            findings.append({
                "severity": "warning",
                "source": "lease",
                "message": "lease issued by retired central signing key",
            })
        elif lease_registry_entry.get("status") == "revoked":
            findings.append({
                "severity": "error",
                "source": "lease",
                "message": "lease issued by revoked central signing key",
            })

    current_device_key_id = getattr(device, "credential_key_id", None) if device is not None else None
    credential_key_id = ((getattr(credential, "details_json", None) or {}).get("key_id") if credential is not None else None)
    if current_device_key_id and credential_key_id and current_device_key_id != credential_key_id:
        findings.append({
            "severity": "error",
            "source": "device",
            "message": "device credential_key_id does not match active credential",
        })

    if device is not None and credential is not None:
        device_fingerprint = getattr(device, "credential_fingerprint", None)
        credential_fingerprint = getattr(credential, "fingerprint", None)
        if device_fingerprint and credential_fingerprint and device_fingerprint != credential_fingerprint:
            findings.append({
                "severity": "error",
                "source": "device",
                "message": "device credential_fingerprint does not match active credential",
            })

    reconciliation = {
        "ok": not any(item["severity"] == "error" for item in findings),
        "findings": findings,
        "credential": credential_verification,
        "lease": lease_verification,
        "issuer_profiles": build_issuer_profile_diagnostics(
            credential=credential,
            lease=lease,
            device=device,
            credentials=credentials,
        ),
        "material_history": build_material_history_summary(
            credentials=credentials,
            leases=leases,
            active_credential=credential,
            current_lease=lease,
        ),
        "signing_registry": build_signing_registry_diagnostics(
            credential=credential,
            lease=lease,
            device=device,
            credentials=credentials,
        ),
    }
    reconciliation["summary"] = build_reconciliation_summary(reconciliation=reconciliation)
    reconciliation["bundle_source"] = "provided" if bundle is not None else ("stored" if stored_bundle is not None else ("rebuilt" if resolved_bundle is not None else "none"))
    return reconciliation
