from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import and_, func, select

from central_server.models import (
    CentralCustomer,
    CentralDevice,
    CentralLicense,
    CentralLocation,
    DeviceCredentialStatus,
    DeviceLeaseStatus,
    DeviceTrustStatus,
    RegistrationToken,
)


async def get_or_create_license_token_payload(
    *,
    db,
    user,
    license_id: str,
    utcnow,
    aware,
    require_installer_or_above,
    can_access_customer,
    generate_reg_token,
    serialize_reg_token,
    log_audit,
    token_ttl,
):
    require_installer_or_above(user)
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")

    now = utcnow()
    tok_result = await db.execute(
        select(RegistrationToken).where(
            RegistrationToken.license_id == license_id,
            RegistrationToken.used_at.is_(None),
            RegistrationToken.is_revoked == False,
        ).order_by(RegistrationToken.created_at.desc())
    )
    for token in tok_result.scalars().all():
        if token.expires_at and aware(token.expires_at) > now:
            return {"exists": True, "token": serialize_reg_token(token), "message": "Aktiver Token vorhanden"}

    raw_token, token_hash, preview = generate_reg_token()
    token = RegistrationToken(
        token_hash=token_hash,
        token_preview=preview,
        customer_id=lic.customer_id,
        location_id=lic.location_id,
        license_id=lic.id,
        expires_at=now + token_ttl,
        created_by=user.username,
        note=f"Auto-created for license {lic.plan_type}",
    )
    db.add(token)
    await db.flush()
    await log_audit(
        db,
        "REG_TOKEN_CREATED",
        license_id=lic.id,
        actor=user.username,
        message="Activation token created for license (auto)",
    )
    result_data = serialize_reg_token(token)
    result_data["raw_token"] = raw_token
    return {"exists": False, "token": result_data, "raw_token": raw_token, "message": "Neuer Token erstellt"}


async def regenerate_license_token_payload(
    *,
    db,
    user,
    license_id: str,
    utcnow,
    require_installer_or_above,
    can_access_customer,
    generate_reg_token,
    serialize_reg_token,
    log_audit,
    token_ttl,
):
    require_installer_or_above(user)
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")

    now = utcnow()
    tok_result = await db.execute(
        select(RegistrationToken).where(
            RegistrationToken.license_id == license_id,
            RegistrationToken.used_at.is_(None),
            RegistrationToken.is_revoked == False,
        )
    )
    revoked_count = 0
    for token in tok_result.scalars().all():
        token.is_revoked = True
        token.revoked_at = now
        token.revoked_by = user.username
        revoked_count += 1

    raw_token, token_hash, preview = generate_reg_token()
    token = RegistrationToken(
        token_hash=token_hash,
        token_preview=preview,
        customer_id=lic.customer_id,
        location_id=lic.location_id,
        license_id=lic.id,
        expires_at=now + token_ttl,
        created_by=user.username,
        note=f"Regenerated (replaced {revoked_count} old tokens)",
    )
    db.add(token)
    await db.flush()
    await log_audit(
        db,
        "REG_TOKEN_REGENERATED",
        license_id=lic.id,
        actor=user.username,
        message=f"Token regenerated for license ({revoked_count} old tokens revoked)",
    )
    result_data = serialize_reg_token(token)
    result_data["raw_token"] = raw_token
    return {"token": result_data, "raw_token": raw_token, "revoked_count": revoked_count}


async def create_registration_token_payload(
    *,
    db,
    user,
    data: dict,
    utcnow,
    require_installer_or_above,
    can_access_customer,
    generate_reg_token,
    serialize_reg_token,
    log_audit,
):
    require_installer_or_above(user)
    if data.get("customer_id") and not can_access_customer(user, data["customer_id"]):
        raise HTTPException(403, "Access denied to this customer")

    raw_token, token_hash, preview = generate_reg_token()
    expires_in = int(data.get("expires_in_hours", 72))
    token = RegistrationToken(
        token_hash=token_hash,
        token_preview=preview,
        customer_id=data.get("customer_id"),
        location_id=data.get("location_id"),
        license_id=data.get("license_id"),
        device_name_template=data.get("device_name_template"),
        expires_at=utcnow() + token_ttl_hours(expires_in),
        created_by=user.username,
        note=data.get("note"),
    )
    db.add(token)
    await db.flush()
    await log_audit(
        db,
        "REG_TOKEN_CREATED",
        actor=user.username,
        message=f"Token {preview} created, expires in {expires_in}h",
    )
    result = serialize_reg_token(token)
    result["raw_token"] = raw_token
    return result


def token_ttl_hours(hours: int):
    from datetime import timedelta

    return timedelta(hours=hours)


async def list_registration_tokens_payload(*, db, user, status: str | None, serialize_reg_token):
    stmt = select(RegistrationToken).order_by(RegistrationToken.created_at.desc())
    if not user.is_superadmin:
        allowed = user.allowed_customer_ids or []
        stmt = stmt.where(RegistrationToken.customer_id.in_(allowed))
    result = await db.execute(stmt)
    tokens = [serialize_reg_token(token) for token in result.scalars().all()]
    if status:
        tokens = [token for token in tokens if token["status"] == status]
    return tokens


async def revoke_registration_token_payload(
    *,
    db,
    user,
    token_id: str,
    utcnow,
    require_installer_or_above,
    can_access_customer,
    serialize_reg_token,
    log_audit,
):
    require_installer_or_above(user)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(404, "Token not found")
    if token.customer_id and not can_access_customer(user, token.customer_id):
        raise HTTPException(403, "Access denied")
    if token.is_revoked:
        raise HTTPException(400, "Token already revoked")
    if token.used_at:
        raise HTTPException(400, "Token already used")

    token.is_revoked = True
    token.revoked_at = utcnow()
    token.revoked_by = user.username
    await db.flush()
    await log_audit(db, "REG_TOKEN_REVOKED", actor=user.username, message=f"Token {token.token_preview} revoked")
    return serialize_reg_token(token)


async def register_device_with_token_payload(
    *,
    body: dict,
    request: Request,
    db,
    logger,
    utcnow,
    aware,
    hash_token,
    log_audit,
    find_best_license,
    compute_status,
):
    raw_token = body.get("token")
    install_id = body.get("install_id")
    device_name = body.get("device_name")

    if not raw_token:
        raise HTTPException(400, "Registrierungs-Token fehlt")
    if not install_id:
        raise HTTPException(400, "install_id fehlt")

    token_hash = hash_token(raw_token)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.token_hash == token_hash))
    token = result.scalar_one_or_none()

    if not token:
        await log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id, message="Invalid token")
        raise HTTPException(403, "Ungueltiger Registrierungs-Token")
    if token.is_revoked:
        raise HTTPException(403, "Token wurde widerrufen")
    if token.used_at:
        raise HTTPException(403, "Token wurde bereits verwendet")

    now = utcnow()
    if token.expires_at and aware(token.expires_at) < now:
        raise HTTPException(403, "Token ist abgelaufen")

    existing_r = await db.execute(select(CentralDevice).where(CentralDevice.install_id == install_id))
    existing_device = existing_r.scalar_one_or_none()

    location_id = token.location_id
    customer_id = token.customer_id

    if location_id and not customer_id:
        loc_r = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
        loc = loc_r.scalar_one_or_none()
        if loc:
            customer_id = loc.customer_id

    if not location_id and not customer_id:
        raise HTTPException(400, "Token hat keinen Kunden/Standort")

    license_id = token.license_id
    resolved_license = None
    if license_id:
        lic_r = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
        resolved_license = lic_r.scalar_one_or_none()
    elif customer_id:
        conditions: list[Any] = [
            CentralLicense.customer_id == customer_id,
            CentralLicense.status.in_(["active", "test"]),
        ]
        if location_id:
            conditions.append((CentralLicense.location_id == location_id) | (CentralLicense.location_id.is_(None)))
        lic_r = await db.execute(select(CentralLicense).where(and_(*conditions)))
        licenses = lic_r.scalars().all()
        if licenses:
            best, _ = find_best_license(licenses, now)
            if best:
                resolved_license = best
                license_id = best.id

    if not location_id and resolved_license and resolved_license.location_id:
        location_id = resolved_license.location_id

    if not location_id and customer_id:
        loc_r = await db.execute(select(CentralLocation).where(CentralLocation.customer_id == customer_id).limit(1))
        existing_loc = loc_r.scalar_one_or_none()
        if existing_loc:
            location_id = existing_loc.id
        else:
            cust_r = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
            cust = cust_r.scalar_one_or_none()
            cust_name = cust.name if cust else "Kunde"
            new_loc = CentralLocation(customer_id=customer_id, name=f"{cust_name} - Hauptstandort")
            db.add(new_loc)
            await db.flush()
            location_id = new_loc.id
            logger.info(f"[REG] Auto-created default location {location_id} for customer {customer_id}")

    if not location_id:
        raise HTTPException(400, "Standort konnte nicht aufgeloest werden. Bitte Lizenz-/Token-Konfiguration pruefen.")

    if resolved_license:
        count_conditions = [CentralDevice.license_id == resolved_license.id, CentralDevice.status == "active"]
        if existing_device:
            count_conditions.append(CentralDevice.id != existing_device.id)
        bound_count_r = await db.execute(select(func.count()).where(*count_conditions))
        bound_count = bound_count_r.scalar() or 0
        if bound_count >= resolved_license.max_devices:
            await log_audit(
                db,
                "DEVICE_REGISTRATION_REJECTED",
                install_id=install_id,
                license_id=resolved_license.id,
                message=f"max_devices limit reached ({bound_count}/{resolved_license.max_devices})",
            )
            raise HTTPException(403, f"Geraete-Limit erreicht: {bound_count}/{resolved_license.max_devices} Geraete bereits aktiv")

    effective_name = device_name or token.device_name_template or f"Kiosk-{install_id[:8]}"
    trust_status = DeviceTrustStatus.LEGACY_BOUND.value
    trust_changed_at = now
    request_ip = request.client.host if request.client else None

    if existing_device:
        existing_device.location_id = location_id
        existing_device.license_id = license_id
        existing_device.device_name = effective_name
        existing_device.status = "active"
        existing_device.binding_status = "bound"
        existing_device.trust_status = trust_status
        existing_device.trust_reason = "legacy registration flow (install_id/api_key)"
        existing_device.trust_last_changed_at = trust_changed_at
        existing_device.last_sync_at = now
        existing_device.last_sync_ip = request_ip
        existing_device.registered_via_token_id = token.id
        api_key = existing_device.api_key
        device_id = existing_device.id
        await db.flush()
        logger.info(f"[REG] Re-registered existing device {device_id} (install_id={install_id})")
    else:
        api_key = f"dk_{secrets.token_urlsafe(32)}"
        new_device = CentralDevice(
            location_id=location_id,
            install_id=install_id,
            api_key=api_key,
            device_name=effective_name,
            status="active",
            binding_status="bound",
            trust_status=trust_status,
            trust_reason="legacy registration flow (install_id/api_key)",
            trust_last_changed_at=trust_changed_at,
            credential_status=DeviceCredentialStatus.NONE.value,
            lease_status=DeviceLeaseStatus.NONE.value,
            license_id=license_id,
            last_sync_at=now,
            last_sync_ip=request_ip,
            sync_count=0,
            registered_via_token_id=token.id,
        )
        db.add(new_device)
        await db.flush()
        device_id = new_device.id

    token.used_at = now
    token.used_by_install_id = install_id
    token.used_by_device_id = device_id
    await db.flush()

    license_status = "no_license"
    plan_type = None
    expiry = None
    customer_name = None

    if customer_id:
        cust_r = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
        cust = cust_r.scalar_one_or_none()
        if cust:
            customer_name = cust.name

    if resolved_license:
        license_status = compute_status(resolved_license, now)
        plan_type = resolved_license.plan_type
        expiry = resolved_license.ends_at.isoformat() if resolved_license.ends_at else None

    reg_type = "re-registered" if existing_device else "registered"
    await log_audit(
        db,
        "DEVICE_REGISTERED",
        device_id=device_id,
        install_id=install_id,
        license_id=license_id,
        actor="registration",
        message=f"Device {effective_name} {reg_type} via token {token.token_preview}",
    )
    return {
        "success": True,
        "device_id": device_id,
        "device_name": effective_name,
        "api_key": api_key,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "location_id": location_id,
        "license_id": license_id,
        "license_status": license_status,
        "plan_type": plan_type,
        "expiry": expiry,
        "binding_status": "bound",
        "re_registered": existing_device is not None,
        "server_timestamp": now.isoformat(),
    }
