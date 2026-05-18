from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.auth import AuthUser, get_current_user, require_owner_or_above
from central_server.database import get_db
from central_server.device_trust import (
    build_issuer_profile_diagnostics,
    build_reconciliation_summary,
    build_signing_registry_diagnostics,
    build_support_diagnostics_compact_summary,
    reconcile_trust_material,
    sync_device_trust_snapshot,
)
from central_server.models import DeviceCredential, DeviceCredentialStatus, DeviceLease, DeviceLeaseStatus, DeviceTrustStatus
from central_server.services.device_trust_details import finalize_device_trust_detail, to_device_safe_current_lease_payload
from central_server.services.device_trust_enrollment import (
    enroll_device_trust_payload,
    issue_device_credential_placeholder_payload,
    issue_device_lease_placeholder_payload,
    revoke_device_credential_placeholder_payload,
    revoke_device_lease_placeholder_payload,
)


def build_device_trust_router(
    *,
    utcnow,
    aware,
    authenticate_device,
    get_device_with_scope_check,
    build_device_advisory_posture,
    serialize_device,
    serialize_device_credential,
    serialize_device_credential_summary,
    serialize_device_lease,
    serialize_device_lease_summary,
    hash_token,
    normalize_enrollment_material,
    log_audit,
    register_device,
    require_installer_or_above,
    attach_lease_key_metadata,
    issue_placeholder_credential,
    revoke_placeholder_credential,
    revoke_placeholder_lease,
) -> APIRouter:
    router = APIRouter(tags=["device-trust"])

    async def _load_device_trust_materials(device_id: str, db: AsyncSession):
        cred_result = await db.execute(
            select(DeviceCredential)
            .where(DeviceCredential.device_id == device_id)
            .order_by(DeviceCredential.created_at.desc())
        )
        lease_result = await db.execute(
            select(DeviceLease)
            .where(DeviceLease.device_id == device_id)
            .order_by(DeviceLease.created_at.desc())
        )
        credentials = cred_result.scalars().all()
        credentials_by_id = {c.id: c for c in credentials}
        active_credential = next((c for c in credentials if c.status == DeviceCredentialStatus.ACTIVE.value), None)
        leases = lease_result.scalars().all()
        current_lease = leases[0] if leases else None
        lease_credential = active_credential
        if current_lease is not None:
            credential_id = (current_lease.details_json or {}).get("credential_id")
            lease_credential = credentials_by_id.get(credential_id) or active_credential
        return credentials, credentials_by_id, active_credential, leases, current_lease, lease_credential

    async def _build_readback_payload(device, db: AsyncSession, *, now, credential, lease, credentials, leases):
        reconciliation = reconcile_trust_material(
            device=device,
            credential=credential,
            lease=lease,
            credentials=credentials,
            leases=leases,
        )
        issuer_profiles = build_issuer_profile_diagnostics(
            credential=credential,
            lease=lease,
            device=device,
            credentials=credentials,
        )
        signing_registry = build_signing_registry_diagnostics(
            credential=credential,
            lease=lease,
            device=device,
            credentials=credentials,
        )
        advisory_posture = await build_device_advisory_posture(
            db,
            device=device,
            credential=credential,
            lease=lease,
            now=now,
        )
        return {
            "device": serialize_device(device),
            "diagnostics_timestamp": now.isoformat(),
            "advisory_posture": advisory_posture,
            "reconciliation": reconciliation,
            "reconciliation_summary": reconciliation.get("summary") or build_reconciliation_summary(reconciliation=reconciliation),
            "issuer_profiles": issuer_profiles,
            "signing_registry": signing_registry,
            "endpoint_summary": build_support_diagnostics_compact_summary(
                issuer_profiles=issuer_profiles,
                signing_registry=signing_registry,
                material_history=reconciliation.get("material_history"),
                credential=credential,
                lease=lease,
                now=now,
            ),
        }

    @router.post("/api/device-trust/enroll")
    async def enroll_device_trust(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
        return await enroll_device_trust_payload(
            body=body,
            request=request,
            db=db,
            utcnow=utcnow,
            hash_token=hash_token,
            aware=aware,
            normalize_enrollment_material=normalize_enrollment_material,
            log_audit=log_audit,
            register_device=register_device,
            serialize_device=serialize_device,
            serialize_device_credential=serialize_device_credential,
        )

    @router.get("/api/device-trust/devices/{device_id}")
    async def get_device_trust_detail(device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        require_owner_or_above(user)
        device = await get_device_with_scope_check(device_id, user, db)
        now = utcnow()
        credentials, credentials_by_id, active_credential, leases, current_lease, effective_credential = await _load_device_trust_materials(device.id, db)
        payload = await _build_readback_payload(
            device,
            db,
            now=now,
            credential=effective_credential,
            lease=current_lease,
            credentials=credentials,
            leases=leases,
        )
        payload["credentials"] = [serialize_device_credential_summary(c, device=device) for c in credentials]
        payload["leases"] = [
            serialize_device_lease_summary(
                lease,
                device=device,
                credential=credentials_by_id.get((lease.details_json or {}).get("credential_id")) or active_credential,
            )
            for lease in leases
        ]
        return finalize_device_trust_detail(payload, user)

    @router.get("/api/device-trust/devices/{device_id}/support-diagnostics")
    async def get_device_trust_support_diagnostics(device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        require_owner_or_above(user)
        device = await get_device_with_scope_check(device_id, user, db)
        now = utcnow()
        credentials, _credentials_by_id, _active_credential, leases, current_lease, lease_credential = await _load_device_trust_materials(device.id, db)
        payload = await _build_readback_payload(
            device,
            db,
            now=now,
            credential=lease_credential,
            lease=current_lease,
            credentials=credentials,
            leases=leases,
        )
        payload.update({
            "credential": serialize_device_credential(lease_credential, device=device) if lease_credential else None,
            "lease": serialize_device_lease(current_lease, device=device, credential=lease_credential) if current_lease else None,
            "mode": "support_diagnostics_read_only",
            "enforcement": "disabled",
        })
        return finalize_device_trust_detail(payload, user)

    @router.post("/api/device-trust/devices/{device_id}/issue-credential")
    async def issue_device_credential_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        return await issue_device_credential_placeholder_payload(
            device_id=device_id,
            body=body,
            user=user,
            db=db,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            get_device_with_scope_check=get_device_with_scope_check,
            issue_placeholder_credential=issue_placeholder_credential,
            log_audit=log_audit,
            serialize_device=serialize_device,
            serialize_device_credential=serialize_device_credential,
        )

    @router.post("/api/device-trust/devices/{device_id}/issue-lease")
    async def issue_device_lease_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        return await issue_device_lease_placeholder_payload(
            device_id=device_id,
            body=body,
            user=user,
            db=db,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            get_device_with_scope_check=get_device_with_scope_check,
            attach_lease_key_metadata=attach_lease_key_metadata,
            sync_device_trust_snapshot=sync_device_trust_snapshot,
            log_audit=log_audit,
            serialize_device=serialize_device,
            serialize_device_lease=serialize_device_lease,
        )

    @router.post("/api/device-trust/devices/{device_id}/revoke-credential")
    async def revoke_device_credential_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        return await revoke_device_credential_placeholder_payload(
            device_id=device_id,
            body=body,
            user=user,
            db=db,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            get_device_with_scope_check=get_device_with_scope_check,
            revoke_placeholder_credential=revoke_placeholder_credential,
            log_audit=log_audit,
            serialize_device=serialize_device,
            serialize_device_credential=serialize_device_credential,
        )

    @router.post("/api/device-trust/devices/{device_id}/revoke-lease")
    async def revoke_device_lease_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        return await revoke_device_lease_placeholder_payload(
            device_id=device_id,
            body=body,
            user=user,
            db=db,
            utcnow=utcnow,
            require_installer_or_above=require_installer_or_above,
            get_device_with_scope_check=get_device_with_scope_check,
            revoke_placeholder_lease=revoke_placeholder_lease,
            log_audit=log_audit,
            serialize_device=serialize_device,
            serialize_device_lease=serialize_device_lease,
        )

    @router.get("/api/device-trust/lease/current")
    async def get_current_device_lease(request: Request, db: AsyncSession = Depends(get_db)):
        device = await authenticate_device(request, db)
        now = utcnow()
        credentials, credentials_by_id, active_credential, leases, lease, lease_credential = await _load_device_trust_materials(device.id, db)

        if lease:
            sync_device_trust_snapshot(device, lease=lease, now=now)
            await db.flush()

        payload = await _build_readback_payload(
            device,
            db,
            now=now,
            credential=lease_credential,
            lease=lease,
            credentials=credentials,
            leases=leases,
        )
        return to_device_safe_current_lease_payload({
            "device_id": device.id,
            "diagnostics_timestamp": now.isoformat(),
            "trust_status": getattr(device, "trust_status", DeviceTrustStatus.LEGACY_UNBOUND.value),
            "credential_status": getattr(device, "credential_status", DeviceCredentialStatus.NONE.value),
            "lease_status": getattr(device, "lease_status", DeviceLeaseStatus.NONE.value),
            "advisory_posture": payload.get("advisory_posture"),
            "credential": serialize_device_credential(lease_credential, device=device) if lease_credential else None,
            "lease": serialize_device_lease(lease, device=device, credential=credentials_by_id.get((lease.details_json or {}).get("credential_id")) or active_credential) if lease else None,
            "reconciliation": payload.get("reconciliation"),
            "reconciliation_summary": payload.get("reconciliation_summary"),
            "issuer_profiles": payload.get("issuer_profiles"),
            "signing_registry": payload.get("signing_registry"),
            "endpoint_summary": payload.get("endpoint_summary"),
            "enforcement": "disabled",
            "mode": "read_only_placeholder",
        })

    return router
