from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.models import CentralDevice, CentralLocation, ConfigHistory, ConfigProfile

VALID_SCOPE_TYPES = ("global", "customer", "location", "device")


def serialize_config_profile(profile: ConfigProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "scope_type": profile.scope_type,
        "scope_id": profile.scope_id,
        "config_data": profile.config_data or {},
        "version": profile.version,
        "updated_by": profile.updated_by,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts. override wins on conflict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict into dot-notation keys."""
    items: dict[str, Any] = {}
    if not isinstance(data, dict):
        return {prefix: data} if prefix else {}
    for key, value in data.items():
        flat_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(flatten_dict(value, flat_key))
        else:
            items[flat_key] = value
    return items


def build_config_changes(old_data: dict[str, Any], new_data: dict[str, Any]) -> list[dict[str, Any]]:
    old_flat = flatten_dict(old_data or {})
    new_flat = flatten_dict(new_data or {})
    all_keys = sorted(set(old_flat.keys()) | set(new_flat.keys()))

    changes: list[dict[str, Any]] = []
    for key in all_keys:
        old_val = old_flat.get(key)
        new_val = new_flat.get(key)
        if key not in old_flat:
            changes.append({"key": key, "status": "added", "old": None, "new": new_val})
        elif key not in new_flat:
            changes.append({"key": key, "status": "removed", "old": old_val, "new": None})
        elif old_val != new_val:
            changes.append({"key": key, "status": "changed", "old": old_val, "new": new_val})
        else:
            changes.append({"key": key, "status": "unchanged", "old": old_val, "new": new_val})
    return changes


def normalize_scope_id(scope_type: str, scope_id: str | None) -> str | None:
    return None if scope_type == "global" else scope_id


def ensure_valid_scope_type(scope_type: str) -> None:
    if scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(400, "scope_type must be global|customer|location|device")


async def ensure_config_scope_access(*, db: AsyncSession, user, scope_type: str, scope_id: str | None, can_access_customer) -> None:
    if scope_type == "global":
        if user.role != "superadmin":
            raise HTTPException(403, "Only superadmin can modify global config")
        return

    if scope_type == "customer":
        if not can_access_customer(user, scope_id):
            raise HTTPException(403, "No access to this customer")
        return

    if scope_type == "location":
        location = await db.get(CentralLocation, scope_id)
        if not location or not can_access_customer(user, location.customer_id):
            raise HTTPException(403, "No access to this location")
        return

    if scope_type == "device":
        device = await db.get(CentralDevice, scope_id)
        if device:
            location = await db.get(CentralLocation, device.location_id)
            if not location or not can_access_customer(user, location.customer_id):
                raise HTTPException(403, "No access to this device")


async def ensure_config_scope_read_access(*, db: AsyncSession, user, scope_type: str, scope_id: str | None, can_access_customer) -> None:
    if scope_type == "global":
        return
    if scope_type == "customer":
        if not can_access_customer(user, scope_id):
            raise HTTPException(403, "No access")
        return
    if scope_type == "location":
        location = await db.get(CentralLocation, scope_id)
        if not location or not can_access_customer(user, location.customer_id):
            raise HTTPException(403, "No access")
        return
    if scope_type == "device":
        device = await db.get(CentralDevice, scope_id)
        if device:
            location = await db.get(CentralLocation, device.location_id)
            if not location or not can_access_customer(user, location.customer_id):
                raise HTTPException(403, "No access")


async def fetch_config_profile(*, db: AsyncSession, scope_type: str, scope_id: str | None) -> ConfigProfile | None:
    sid = normalize_scope_id(scope_type, scope_id)
    result = await db.execute(
        select(ConfigProfile).where(
            ConfigProfile.scope_type == scope_type,
            ConfigProfile.scope_id == sid,
        )
    )
    return result.scalar_one_or_none()


async def list_config_profiles_payload(*, db: AsyncSession, scope_type: str | None) -> list[dict[str, Any]]:
    stmt = select(ConfigProfile)
    if scope_type:
        stmt = stmt.where(ConfigProfile.scope_type == scope_type)
    stmt = stmt.order_by(ConfigProfile.scope_type, ConfigProfile.updated_at.desc())
    result = await db.execute(stmt)
    return [serialize_config_profile(profile) for profile in result.scalars().all()]


async def get_config_profile_payload(*, db: AsyncSession, scope_type: str, scope_id: str | None) -> dict[str, Any]:
    profile = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)
    if not profile:
        raise HTTPException(404, f"No config for {scope_type}/{scope_id}")
    return serialize_config_profile(profile)


async def get_global_config_payload(*, db: AsyncSession) -> dict[str, Any]:
    profile = await fetch_config_profile(db=db, scope_type="global", scope_id=None)
    if not profile:
        raise HTTPException(404, "No global config found")
    return serialize_config_profile(profile)


async def upsert_config_profile_payload(
    *,
    db: AsyncSession,
    user,
    scope_type: str,
    scope_id: str,
    config_data: dict[str, Any],
    utcnow,
    log_audit,
    resolve_affected_devices,
    device_ws_hub,
) -> dict[str, Any]:
    sid = normalize_scope_id(scope_type, scope_id)
    profile = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)

    if profile:
        db.add(ConfigHistory(
            profile_id=profile.id,
            scope_type=profile.scope_type,
            scope_id=profile.scope_id,
            config_data=profile.config_data or {},
            version=profile.version or 1,
            updated_by=profile.updated_by,
        ))
        profile.config_data = config_data
        profile.version = (profile.version or 0) + 1
        profile.updated_by = user.username
        profile.updated_at = utcnow()
    else:
        profile = ConfigProfile(
            scope_type=scope_type,
            scope_id=sid,
            config_data=config_data,
            updated_by=user.username,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    await log_audit(db, "config_updated", actor=user.username, message=f"Config {scope_type}/{sid} updated (v{profile.version})")
    await db.commit()

    try:
        affected = await resolve_affected_devices(db, scope_type, scope_id)
        if affected:
            await device_ws_hub.push_to_devices(
                affected,
                "config_updated",
                {"scope_type": scope_type, "scope_id": scope_id, "version": profile.version},
            )
    except Exception:
        pass

    return serialize_config_profile(profile)


async def get_config_history_payload(*, db: AsyncSession, scope_type: str, scope_id: str) -> dict[str, Any]:
    sid = normalize_scope_id(scope_type, scope_id)
    result = await db.execute(
        select(ConfigHistory).where(
            ConfigHistory.scope_type == scope_type,
            ConfigHistory.scope_id == sid,
        ).order_by(ConfigHistory.version.desc()).limit(50)
    )
    entries = result.scalars().all()
    active = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)

    return {
        "scope_type": scope_type,
        "scope_id": sid,
        "active_version": active.version if active else None,
        "active_updated_by": active.updated_by if active else None,
        "active_updated_at": active.updated_at.isoformat() if active and active.updated_at else None,
        "history": [
            {
                "id": entry.id,
                "version": entry.version,
                "updated_by": entry.updated_by,
                "saved_at": entry.saved_at.isoformat() if entry.saved_at else None,
                "config_data": entry.config_data,
            }
            for entry in entries
        ],
    }


async def rollback_config_payload(
    *,
    db: AsyncSession,
    user,
    scope_type: str,
    scope_id: str,
    version: int,
    utcnow,
    log_audit,
    resolve_affected_devices,
    device_ws_hub,
) -> dict[str, Any]:
    sid = normalize_scope_id(scope_type, scope_id)
    history_result = await db.execute(
        select(ConfigHistory).where(
            ConfigHistory.scope_type == scope_type,
            ConfigHistory.scope_id == sid,
            ConfigHistory.version == version,
        )
    )
    history_entry = history_result.scalar_one_or_none()
    if not history_entry:
        raise HTTPException(404, f"Version {version} nicht gefunden fuer {scope_type}/{scope_id}")

    profile = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)
    if not profile:
        raise HTTPException(404, f"Kein aktives Profil fuer {scope_type}/{scope_id}")

    db.add(ConfigHistory(
        profile_id=profile.id,
        scope_type=profile.scope_type,
        scope_id=profile.scope_id,
        config_data=profile.config_data or {},
        version=profile.version or 1,
        updated_by=profile.updated_by,
    ))

    profile.config_data = history_entry.config_data
    profile.version = (profile.version or 0) + 1
    profile.updated_by = f"{user.username} (rollback v{version})"
    profile.updated_at = utcnow()

    await db.commit()

    try:
        await log_audit(
            db,
            "config_rollback",
            actor=user.username,
            message=f"Config {scope_type}/{sid} rolled back to v{version} (now v{profile.version})",
        )
        await db.commit()
    except Exception:
        pass

    try:
        affected = await resolve_affected_devices(db, scope_type, scope_id)
        if affected:
            await device_ws_hub.push_to_devices(
                affected,
                "config_updated",
                {"scope_type": scope_type, "scope_id": scope_id, "version": profile.version},
            )
    except Exception:
        pass

    return {
        "success": True,
        "new_version": profile.version,
        "rolled_back_to": version,
        "config_data": profile.config_data,
    }


async def get_config_diff_payload(*, db: AsyncSession, scope_type: str, scope_id: str, version: int) -> dict[str, Any]:
    sid = normalize_scope_id(scope_type, scope_id)
    active = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)
    if not active:
        raise HTTPException(404, f"Kein aktives Profil fuer {scope_type}/{scope_id}")

    history_result = await db.execute(
        select(ConfigHistory).where(
            ConfigHistory.scope_type == scope_type,
            ConfigHistory.scope_id == sid,
            ConfigHistory.version == version,
        )
    )
    history_entry = history_result.scalar_one_or_none()
    if not history_entry:
        raise HTTPException(404, f"Version {version} nicht gefunden")

    changes = build_config_changes(history_entry.config_data or {}, active.config_data or {})
    actual_changes = [change for change in changes if change["status"] != "unchanged"]
    return {
        "scope_type": scope_type,
        "scope_id": sid,
        "old_version": version,
        "new_version": active.version,
        "total_changes": len(actual_changes),
        "changes": changes,
    }


async def export_config_payload(*, db: AsyncSession, user, scope_type: str, scope_id: str, utcnow) -> dict[str, Any]:
    profile = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)
    if not profile:
        raise HTTPException(404, f"No config for {scope_type}/{scope_id}")
    return {
        "meta": {
            "type": "darts_kiosk_config_export",
            "format_version": 1,
            "scope_type": scope_type,
            "scope_id": scope_id if scope_type != "global" else "global",
            "version": profile.version,
            "exported_at": utcnow().isoformat(),
            "exported_by": user.username,
        },
        "config_data": profile.config_data or {},
    }


async def validate_config_import_payload(*, db: AsyncSession, user, import_data: dict[str, Any], target_scope_type: str | None, target_scope_id: str | None, mode: str, can_access_customer) -> dict[str, Any]:
    errors: list[str] = []

    if not isinstance(import_data, dict):
        return {"valid": False, "errors": ["Datei muss ein JSON-Objekt sein"], "diff": None}

    meta = import_data.get("meta", {})
    config_data = import_data.get("config_data", {})

    if not isinstance(meta, dict) or meta.get("type") != "darts_kiosk_config_export":
        errors.append("Keine gueltige Config-Export-Datei (meta.type fehlt oder ungueltig)")
    if not isinstance(config_data, dict) or not config_data:
        errors.append("config_data fehlt oder ist leer")
    if errors:
        return {"valid": False, "errors": errors, "diff": None}

    from central_server.config_schema import validate_config
    schema_errors = validate_config(config_data)
    if schema_errors:
        return {"valid": False, "errors": [f"Schema: {error}" for error in schema_errors], "diff": None}

    scope_type = target_scope_type or meta.get("scope_type", "global")
    scope_id = target_scope_id or meta.get("scope_id")
    if scope_type not in VALID_SCOPE_TYPES:
        return {"valid": False, "errors": [f"Ungueltiger Ziel-Scope: {scope_type}"], "diff": None}

    sid = normalize_scope_id(scope_type, scope_id)

    if scope_type == "customer" and not can_access_customer(user, scope_id):
        return {"valid": False, "errors": ["Kein Zugriff auf diesen Scope"], "diff": None}
    if scope_type == "global" and user.role != "superadmin":
        return {"valid": False, "errors": ["Nur Superadmin kann globale Config importieren"], "diff": None}

    current = await fetch_config_profile(db=db, scope_type=scope_type, scope_id=scope_id)
    current_data = current.config_data if current else {}
    new_data = config_data if mode == "replace" else deep_merge(current_data or {}, config_data)

    changes = build_config_changes(current_data or {}, new_data)
    actual_changes = [change for change in changes if change["status"] != "unchanged"]

    warnings: list[str] = []
    if mode == "replace" and current_data:
        removed = [change for change in actual_changes if change["status"] == "removed"]
        if removed:
            warnings.append(f"Replace-Modus: {len(removed)} bestehende Felder werden entfernt")
    if meta.get("scope_type") and meta["scope_type"] != scope_type:
        warnings.append(f"Originaler Scope war '{meta['scope_type']}', Ziel ist '{scope_type}'")

    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "mode": mode,
        "target_scope_type": scope_type,
        "target_scope_id": scope_id or "global",
        "source_meta": meta,
        "diff": {
            "total_changes": len(actual_changes),
            "changes": changes,
        },
    }


async def apply_config_import_payload(
    *,
    db: AsyncSession,
    user,
    import_data: dict[str, Any],
    target_scope_type: str,
    target_scope_id: str | None,
    mode: str,
    utcnow,
    log_audit,
    resolve_affected_devices,
    device_ws_hub,
) -> dict[str, Any]:
    config_data = import_data.get("config_data", {})
    meta = import_data.get("meta", {})

    if not isinstance(config_data, dict) or not config_data:
        raise HTTPException(400, "config_data fehlt oder ist leer")
    if target_scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(400, "Ungueltiger scope_type")

    from central_server.config_schema import validate_config
    schema_errors = validate_config(config_data)
    if schema_errors:
        raise HTTPException(422, detail={"validation_errors": schema_errors})

    sid = normalize_scope_id(target_scope_type, target_scope_id)
    profile = await fetch_config_profile(db=db, scope_type=target_scope_type, scope_id=target_scope_id)

    if profile:
        db.add(ConfigHistory(
            profile_id=profile.id,
            scope_type=profile.scope_type,
            scope_id=profile.scope_id,
            config_data=profile.config_data or {},
            version=profile.version or 1,
            updated_by=profile.updated_by,
        ))
        profile.config_data = deep_merge(profile.config_data or {}, config_data) if mode == "merge" else config_data
        profile.version = (profile.version or 0) + 1
        profile.updated_by = f"{user.username} (import-{mode})"
        profile.updated_at = utcnow()
    else:
        profile = ConfigProfile(
            scope_type=target_scope_type,
            scope_id=sid,
            config_data=config_data,
            updated_by=f"{user.username} (import-{mode})",
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)

    source_info = f"from {meta.get('scope_type', '?')}/{meta.get('scope_id', '?')} v{meta.get('version', '?')}"
    await log_audit(
        db,
        "config_import",
        actor=user.username,
        message=f"Config imported ({mode}) to {target_scope_type}/{sid} v{profile.version} {source_info}",
    )
    await db.commit()

    try:
        affected = await resolve_affected_devices(db, target_scope_type, target_scope_id or "global")
        if affected:
            await device_ws_hub.push_to_devices(
                affected,
                "config_updated",
                {"scope_type": target_scope_type, "version": profile.version},
            )
    except Exception:
        pass

    return {
        "success": True,
        "mode": mode,
        "profile": serialize_config_profile(profile),
        "source_meta": meta,
    }
