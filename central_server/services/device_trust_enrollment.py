from __future__ import annotations

import hashlib
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from central_server.models import (
    CentralDevice,
    DeviceCredential,
    DeviceCredentialStatus,
    DeviceLease,
    DeviceLeaseStatus,
    DeviceTrustStatus,
    RegistrationToken,
)


async def enroll_device_trust_payload(
    *,
    body: dict,
    request,
    db,
    utcnow,
    hash_token,
    aware,
    normalize_enrollment_material,
    log_audit,
    register_device,
    serialize_device,
    serialize_device_credential,
):
    raw_token = body.get("token")
    install_id = body.get("install_id")
    csr_pem = body.get("csr_pem")
    public_key_pem = body.get("public_key_pem")
    fingerprint = body.get("credential_fingerprint") or body.get("fingerprint")
    device_name = body.get("device_name")
    now = utcnow()

    if not raw_token:
        raise HTTPException(400, "Enrollment token fehlt")
    if not install_id:
        raise HTTPException(400, "install_id fehlt")
    if not csr_pem and not public_key_pem:
        raise HTTPException(400, "csr_pem oder public_key_pem erforderlich")

    enrollment_material = normalize_enrollment_material(
        csr_pem=csr_pem,
        public_key_pem=public_key_pem,
        fingerprint=fingerprint,
    )

    token_hash = hash_token(raw_token)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.token_hash == token_hash))
    token = result.scalar_one_or_none()
    if not token:
        await log_audit(db, "DEVICE_ENROLLMENT_FAILED", install_id=install_id, message="Invalid enrollment token")
        raise HTTPException(403, "Ungueltiger Enrollment-Token")
    if token.is_revoked:
        raise HTTPException(403, "Token wurde widerrufen")
    if token.expires_at and aware(token.expires_at) < now:
        raise HTTPException(403, "Token ist abgelaufen")

    existing_r = await db.execute(select(CentralDevice).where(CentralDevice.install_id == install_id))
    device = existing_r.scalar_one_or_none()
    if not device and token.used_by_device_id:
        existing_r = await db.execute(select(CentralDevice).where(CentralDevice.id == token.used_by_device_id))
        device = existing_r.scalar_one_or_none()

    if not device:
        registration_result = await register_device(
            {"token": raw_token, "install_id": install_id, "device_name": device_name},
            request,
            db,
        )
        existing_r = await db.execute(select(CentralDevice).where(CentralDevice.id == registration_result["device_id"]))
        device = existing_r.scalar_one_or_none()

    if not device:
        raise HTTPException(500, "Device could not be resolved for enrollment")

    existing_cred_r = await db.execute(
        select(DeviceCredential)
        .where(
            DeviceCredential.device_id == device.id,
            DeviceCredential.status.in_([
                DeviceCredentialStatus.PENDING.value,
                DeviceCredentialStatus.ACTIVE.value,
                DeviceCredentialStatus.ROTATING.value,
            ]),
        )
        .order_by(DeviceCredential.created_at.desc())
    )
    credential = existing_cred_r.scalars().first()
    metadata = {
        "source": "device_trust_enrollment_placeholder",
        "install_id": install_id,
        "device_name": device_name or device.device_name,
        "requested_at": now.isoformat(),
        "key_id": enrollment_material["key_id"],
        "client_ip": request.client.host if request.client else None,
        "hardware": body.get("hardware") or {},
        "runtime": body.get("runtime") or {},
    }

    if credential:
        credential.status = DeviceCredentialStatus.PENDING.value
        credential.credential_kind = body.get("credential_kind", credential.credential_kind or "x509_csr")
        credential.fingerprint = enrollment_material["fingerprint"]
        credential.csr_pem = enrollment_material["csr_pem"]
        credential.public_key_pem = enrollment_material["public_key_pem"]
        credential.details_json = metadata
    else:
        credential = DeviceCredential(
            device_id=device.id,
            status=DeviceCredentialStatus.PENDING.value,
            credential_kind=body.get("credential_kind", "x509_csr"),
            fingerprint=enrollment_material["fingerprint"],
            csr_pem=enrollment_material["csr_pem"],
            public_key_pem=enrollment_material["public_key_pem"],
            details_json=metadata,
        )
        db.add(credential)

    device.trust_status = DeviceTrustStatus.PENDING_ENROLLMENT.value
    device.trust_reason = "pending device trust enrollment"
    device.trust_last_changed_at = now
    device.credential_status = DeviceCredentialStatus.PENDING.value
    device.credential_fingerprint = enrollment_material["fingerprint"]
    device.registered_via_token_id = token.id
    device.last_sync_at = now
    device.last_sync_ip = request.client.host if request.client else None
    await db.flush()

    await log_audit(
        db,
        "DEVICE_ENROLLMENT_RECORDED",
        device_id=device.id,
        install_id=install_id,
        license_id=device.license_id,
        actor="device",
        message=f"Pending enrollment credential recorded for device {device.id}",
    )

    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": serialize_device(device),
        "credential": serialize_device_credential(credential, device=device),
        "next_action": "await_central_issuance",
    }


async def issue_device_credential_placeholder_payload(
    *,
    device_id: str,
    body: dict,
    user,
    db,
    utcnow,
    require_installer_or_above,
    get_device_with_scope_check,
    issue_placeholder_credential,
    log_audit,
    serialize_device,
    serialize_device_credential,
):
    require_installer_or_above(user)
    device = await get_device_with_scope_check(device_id, user, db)

    credential_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    existing = credential_result.scalars().all()
    credential = next((c for c in existing if c.status in [DeviceCredentialStatus.PENDING.value, DeviceCredentialStatus.ROTATING.value]), None)
    if credential is None:
        credential = next((c for c in existing if c.status == DeviceCredentialStatus.ACTIVE.value), None)

    if credential is None:
        raise HTTPException(409, "No enrollment material available for credential issuance")

    now = utcnow()
    if credential.status == DeviceCredentialStatus.ACTIVE.value:
        credential.status = DeviceCredentialStatus.ROTATING.value
        replacement = DeviceCredential(
            device_id=device.id,
            status=DeviceCredentialStatus.PENDING.value,
            credential_kind=credential.credential_kind,
            fingerprint=credential.fingerprint,
            csr_pem=credential.csr_pem,
            public_key_pem=credential.public_key_pem,
            replacement_for_credential_id=credential.id,
            details_json=dict(credential.details_json or {}),
        )
        db.add(replacement)
        await db.flush()
        credential = replacement

    validity_days = int(body.get("validity_days", 30))
    if validity_days < 1 or validity_days > 366:
        raise HTTPException(400, "validity_days out of allowed range")

    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by=user.username,
        validity_days=validity_days,
        now=now,
    )
    await db.flush()
    await log_audit(
        db,
        "DEVICE_CREDENTIAL_ISSUED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder credential issued (key_id={(credential.details_json or {}).get('key_id')})",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": serialize_device(device),
        "credential": serialize_device_credential(credential, device=device),
    }


async def issue_device_lease_placeholder_payload(
    *,
    device_id: str,
    body: dict,
    user,
    db,
    utcnow,
    require_installer_or_above,
    get_device_with_scope_check,
    attach_lease_key_metadata,
    sync_device_trust_snapshot,
    log_audit,
    serialize_device,
    serialize_device_lease,
):
    require_installer_or_above(user)
    device = await get_device_with_scope_check(device_id, user, db)
    now = utcnow()

    duration_hours = int(body.get("duration_hours", 24))
    grace_hours = int(body.get("grace_hours", 24))
    if duration_hours < 1 or duration_hours > 24 * 31:
        raise HTTPException(400, "duration_hours out of allowed range")
    if grace_hours < 0 or grace_hours > 24 * 31:
        raise HTTPException(400, "grace_hours out of allowed range")

    issued_at = now
    expires_at = now + timedelta(hours=duration_hours)
    grace_until = expires_at + timedelta(hours=grace_hours)
    lease_metadata = {
        "mode": "placeholder",
        "issued_by_role": user.role,
        "issued_by": user.username,
        "reason": body.get("reason") or "manual placeholder issuance",
        "capability_overrides": body.get("capability_overrides") or {},
        "lease_policy": {
            "duration_hours": duration_hours,
            "grace_hours": grace_hours,
            "enforcement": "disabled",
        },
    }
    signature = hashlib.sha256(f"{device.id}:{issued_at.isoformat()}:{expires_at.isoformat()}".encode()).hexdigest()

    lease = DeviceLease(
        device_id=device.id,
        central_license_id=device.license_id,
        status=DeviceLeaseStatus.ACTIVE.value,
        issued_at=issued_at,
        expires_at=expires_at,
        grace_until=grace_until,
        signature=signature,
        details_json=lease_metadata,
    )
    db.add(lease)

    credential_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    active_credential = next((c for c in credential_result.scalars().all() if c.status == DeviceCredentialStatus.ACTIVE.value), None)
    attach_lease_key_metadata(lease=lease, credential=active_credential)

    if device.credential_status == DeviceCredentialStatus.NONE.value:
        device.credential_status = DeviceCredentialStatus.PENDING.value
    sync_device_trust_snapshot(device, lease=lease, credential=active_credential, now=now)

    await db.flush()
    await log_audit(
        db,
        "DEVICE_LEASE_ISSUED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder lease issued until {expires_at.isoformat()}",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": serialize_device(device),
        "lease": serialize_device_lease(lease, device=device, credential=active_credential),
    }


async def revoke_device_credential_placeholder_payload(
    *,
    device_id: str,
    body: dict,
    user,
    db,
    utcnow,
    require_installer_or_above,
    get_device_with_scope_check,
    revoke_placeholder_credential,
    log_audit,
    serialize_device,
    serialize_device_credential,
):
    require_installer_or_above(user)
    device = await get_device_with_scope_check(device_id, user, db)
    credential_id = body.get("credential_id")

    credential_stmt = select(DeviceCredential).where(DeviceCredential.device_id == device.id)
    if credential_id:
        credential_stmt = credential_stmt.where(DeviceCredential.id == credential_id)
    credential_stmt = credential_stmt.order_by(DeviceCredential.created_at.desc())
    credential = (await db.execute(credential_stmt)).scalars().first()
    if credential is None:
        raise HTTPException(404, "Credential not found")

    revoke_placeholder_credential(
        credential=credential,
        device=device,
        reason=body.get("reason"),
        revoked_by=user.username,
        now=utcnow(),
    )
    await db.flush()
    await log_audit(
        db,
        "DEVICE_CREDENTIAL_REVOKED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder credential revoked ({credential.id})",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": serialize_device(device),
        "credential": serialize_device_credential(credential, device=device),
    }


async def revoke_device_lease_placeholder_payload(
    *,
    device_id: str,
    body: dict,
    user,
    db,
    utcnow,
    require_installer_or_above,
    get_device_with_scope_check,
    revoke_placeholder_lease,
    log_audit,
    serialize_device,
    serialize_device_lease,
):
    require_installer_or_above(user)
    device = await get_device_with_scope_check(device_id, user, db)
    lease_id = body.get("lease_id")

    lease_stmt = select(DeviceLease).where(DeviceLease.device_id == device.id)
    if lease_id:
        lease_stmt = lease_stmt.where(DeviceLease.id == lease_id)
    lease_stmt = lease_stmt.order_by(DeviceLease.created_at.desc())
    lease = (await db.execute(lease_stmt)).scalars().first()
    if lease is None:
        raise HTTPException(404, "Lease not found")

    credential_stmt = (
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    credential = next((c for c in (await db.execute(credential_stmt)).scalars().all() if c.status == DeviceCredentialStatus.ACTIVE.value), None)

    revoke_placeholder_lease(
        lease=lease,
        device=device,
        credential=credential,
        reason=body.get("reason"),
        revoked_by=user.username,
        now=utcnow(),
    )
    await db.flush()
    await log_audit(
        db,
        "DEVICE_LEASE_REVOKED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder lease revoked ({lease.lease_id})",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": serialize_device(device),
        "lease": serialize_device_lease(lease, device=device, credential=credential),
    }
