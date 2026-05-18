"""Signing helper utilities for device trust module.
Extracted from central_server/device_trust.py to improve modularity.
"""
from __future__ import annotations
import json
import os
from typing import Any, List, Dict

def _load_signing_registry_overrides() -> List[Dict[str, Any]]:
    """Load optional signing registry overrides from ENV.

    The environment variable ``CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY`` may contain
    a JSON object or list describing additional signing key metadata. This helper
    parses the variable safely and returns a list of dict entries.
    """
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

def get_signing_key_registry() -> Dict[str, Dict[str, Any]]:
    """Build a central signing‑key registry snapshot.

    The active placeholder signing profile is always included. Additional entries
    from ``_load_signing_registry_overrides`` are merged, allowing runtime
    configuration of retired or revoked keys without code changes.
    """
    from .device_trust import get_placeholder_signing_profile  # local import to avoid circular deps
    active_profile = get_placeholder_signing_profile()
    registry: Dict[str, Dict[str, Any]] = {
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
