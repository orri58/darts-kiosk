from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.models import (
    CentralCustomer,
    CentralDevice,
    CentralLicense,
    CentralLocation,
    CentralUser,
    LicenseStatus,
    RegistrationToken,
)


async def ensure_customer_access(*, user, customer_id: str, can_access_customer) -> None:
    if not can_access_customer(user, customer_id):
        raise HTTPException(403, "Access denied")


async def ensure_location_access(*, user, location_id: str, db: AsyncSession, can_access_location, detail: str = "Access denied") -> None:
    if not await can_access_location(user, location_id, db):
        raise HTTPException(403, detail)


async def list_customers_payload(*, db: AsyncSession, user, apply_customer_scope, serialize_customer):
    stmt = select(CentralCustomer).order_by(CentralCustomer.name)
    stmt = apply_customer_scope(stmt, user, CentralCustomer.id)
    result = await db.execute(stmt)
    return [serialize_customer(row) for row in result.scalars().all()]


async def create_customer_payload(*, db: AsyncSession, user, data: dict, log_audit, serialize_customer):
    customer = CentralCustomer(name=data["name"], contact_email=data.get("contact_email"))
    db.add(customer)
    await db.flush()
    if not user.is_superadmin:
        u_result = await db.execute(select(CentralUser).where(CentralUser.id == user.id))
        db_user = u_result.scalar_one_or_none()
        if db_user:
            ids = list(db_user.allowed_customer_ids or [])
            ids.append(customer.id)
            db_user.allowed_customer_ids = ids
            await db.flush()
    await log_audit(db, "CUSTOMER_CREATED", actor=user.username, message=f"Customer '{customer.name}' created")
    return serialize_customer(customer)


async def update_customer_payload(*, db: AsyncSession, user, customer_id: str, data: dict, can_access_customer, log_audit, serialize_customer):
    await ensure_customer_access(user=user, customer_id=customer_id, can_access_customer=can_access_customer)
    result = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")
    old_status = customer.status
    for field in ("name", "contact_email", "contact_phone", "notes", "status"):
        if field in data:
            setattr(customer, field, data[field])
    await db.flush()
    if "status" in data and data["status"] != old_status:
        await log_audit(
            db,
            "CUSTOMER_STATUS_CHANGED",
            actor=user.username,
            message=f"Customer '{customer.name}' status: {old_status} -> {data['status']}",
        )
    return serialize_customer(customer)


async def list_locations_payload(*, db: AsyncSession, user, customer_id: str | None, can_access_customer, apply_customer_scope, serialize_location):
    stmt = select(CentralLocation).order_by(CentralLocation.name)
    if customer_id:
        await ensure_customer_access(user=user, customer_id=customer_id, can_access_customer=can_access_customer)
        stmt = stmt.where(CentralLocation.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLocation.customer_id)
    result = await db.execute(stmt)
    return [serialize_location(row) for row in result.scalars().all()]


async def create_location_payload(*, db: AsyncSession, user, data: dict, can_access_customer, log_audit, serialize_location):
    await ensure_customer_access(user=user, customer_id=data["customer_id"], can_access_customer=can_access_customer)
    location = CentralLocation(customer_id=data["customer_id"], name=data["name"], address=data.get("address"))
    db.add(location)
    await db.flush()
    await log_audit(db, "LOCATION_CREATED", actor=user.username, message=f"Location '{location.name}' created")
    return serialize_location(location)


async def update_location_payload(*, db: AsyncSession, user, location_id: str, data: dict, can_access_location, log_audit, serialize_location):
    await ensure_location_access(user=user, location_id=location_id, db=db, can_access_location=can_access_location)
    result = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(404, "Location not found")
    for field in ("name", "address", "status"):
        if field in data:
            setattr(location, field, data[field])
    await db.flush()
    await log_audit(db, "LOCATION_UPDATED", actor=user.username, message=f"Location '{location.name}' updated")
    return serialize_location(location)


async def list_devices_payload(*, db: AsyncSession, user, location_id: str | None, customer_id: str | None, async_session_local, can_access_location, can_access_customer, apply_customer_scope, build_device_advisory_posture_map, compact_advisory_posture, can_view_internal_device_detail, finalize_device_summary, serialize_device, logger):
    if location_id:
        await ensure_location_access(user=user, location_id=location_id, db=db, can_access_location=can_access_location)
        stmt = select(CentralDevice).where(CentralDevice.location_id == location_id)
    elif customer_id:
        await ensure_customer_access(user=user, customer_id=customer_id, can_access_customer=can_access_customer)
        loc_ids_r = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id == customer_id))
        loc_ids = [r[0] for r in loc_ids_r.fetchall()]
        stmt = select(CentralDevice).where(CentralDevice.location_id.in_(loc_ids)) if loc_ids else select(CentralDevice).where(False)
    else:
        if user.is_superadmin:
            stmt = select(CentralDevice)
        else:
            stmt = select(CentralDevice).join(CentralLocation, CentralDevice.location_id == CentralLocation.id)
            stmt = apply_customer_scope(stmt, user, CentralLocation.customer_id)
    stmt = stmt.order_by(CentralDevice.created_at.desc())

    devices = []
    try:
        result = await db.execute(stmt)
        all_devs = result.scalars().all()
        advisory_map = await build_device_advisory_posture_map(db, all_devs)
        for device in all_devs:
            try:
                base = serialize_device(device)
                base["advisory_posture"] = compact_advisory_posture(
                    advisory_map.get(device.id),
                    detail_level="internal" if can_view_internal_device_detail(user) else "operator_safe",
                )
                devices.append(finalize_device_summary(base, user))
            except Exception as exc:
                logger.warning(f"[DEVICES-LIST] Serialization failed for device: {exc}")
                devices.append(finalize_device_summary({"id": str(getattr(device, 'id', '?')), "device_name": str(getattr(device, 'device_name', 'Fehler')), "status": "error", "_error": str(exc)}, user))
    except Exception as exc:
        logger.warning(f"[DEVICES-LIST] ORM execute failed: {type(exc).__name__}: {exc} — fresh-session raw SQL fallback")
        try:
            await db.rollback()
        except Exception:
            pass
        from sqlalchemy import text as _t
        try:
            async with async_session_local() as fresh_db:
                raw_rows = (await fresh_db.execute(_t(
                    "SELECT id, location_id, install_id, api_key, device_name, status, binding_status, license_id, reported_version, sync_count FROM devices"
                ))).mappings().all()
                for row in raw_rows:
                    devices.append(finalize_device_summary({
                        "id": row["id"],
                        "location_id": row.get("location_id"),
                        "install_id": row.get("install_id"),
                        "api_key_preview": (f"{row.get('api_key')[:8]}...{row.get('api_key')[-4:]}" if row.get("api_key") and len(row.get("api_key")) > 12 else ("****" if row.get("api_key") else None)),
                        "device_name": row.get("device_name"),
                        "status": row.get("status", "unknown"),
                        "binding_status": row.get("binding_status", "unknown"),
                        "license_id": row.get("license_id"),
                        "reported_version": row.get("reported_version"),
                        "sync_count": row.get("sync_count", 0) or 0,
                        "last_sync_at": None,
                        "last_heartbeat_at": None,
                        "created_at": None,
                        "ws_connected": False,
                        "advisory_posture": None,
                    }, user))
        except Exception as fallback_exc:
            logger.error(f"[DEVICES-LIST] Even fresh-session raw SQL failed: {fallback_exc}")
            devices = []
    return devices


async def create_device_payload(*, db: AsyncSession, user, data: dict, can_access_location, log_audit, serialize_device, secrets_module):
    await ensure_location_access(user=user, location_id=data["location_id"], db=db, can_access_location=can_access_location, detail="Access denied to this location")
    api_key = data.get("api_key") or f"dk_{secrets_module.token_urlsafe(32)}"
    device = CentralDevice(location_id=data["location_id"], device_name=data.get("device_name"), api_key=api_key, install_id=data.get("install_id"))
    db.add(device)
    await db.flush()
    await log_audit(db, "DEVICE_CREATED", device_id=device.id, actor=user.username, message=f"Device '{device.device_name}' created")
    return serialize_device(device, include_api_key=True)


async def update_device_payload(*, db: AsyncSession, user, device_id: str, data: dict, can_access_location, log_audit, serialize_device):
    result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    await ensure_location_access(user=user, location_id=device.location_id, db=db, can_access_location=can_access_location)
    old_status = device.status
    for field in ("device_name", "status"):
        if field in data:
            setattr(device, field, data[field])
    await db.flush()
    if "status" in data and data["status"] != old_status:
        await log_audit(db, "DEVICE_STATUS_CHANGED", device_id=device.id, actor=user.username, message=f"Device '{device.device_name}' status: {old_status} -> {data['status']}")
    return serialize_device(device)


async def list_licenses_payload(*, db: AsyncSession, user, customer_id: str | None, status: str | None, can_access_customer, apply_customer_scope, utcnow, summarize_license_token_state, compute_status, build_device_advisory_posture_map, summarize_posture_collection, build_license_commercial_readiness, serialize_license):
    now = utcnow()
    stmt = select(CentralLicense).order_by(CentralLicense.created_at.desc())
    if customer_id:
        await ensure_customer_access(user=user, customer_id=customer_id, can_access_customer=can_access_customer)
        stmt = stmt.where(CentralLicense.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLicense.customer_id)
    if status:
        stmt = stmt.where(CentralLicense.status == status)
    result = await db.execute(stmt)
    licenses = result.scalars().all()
    customer_ids = set(lic.customer_id for lic in licenses if lic.customer_id)
    customer_map = {}
    if customer_ids:
        cr = await db.execute(select(CentralCustomer).where(CentralCustomer.id.in_(customer_ids)))
        customer_map = {row.id: row.name for row in cr.scalars().all()}
    license_ids = [lic.id for lic in licenses]
    posture_summary_by_license = {}
    token_summary_by_license = {}
    if license_ids:
        license_devices_result = await db.execute(select(CentralDevice).where(CentralDevice.license_id.in_(license_ids)))
        license_devices = license_devices_result.scalars().all()
        device_postures = await build_device_advisory_posture_map(db, license_devices)
        devices_by_license: dict[str, list[dict]] = defaultdict(list)
        for device in license_devices:
            devices_by_license[device.license_id].append(device_postures.get(device.id))
        for lic_id, postures in devices_by_license.items():
            posture_summary_by_license[lic_id] = summarize_posture_collection(postures)
        token_result = await db.execute(select(RegistrationToken).where(RegistrationToken.license_id.in_(license_ids)).order_by(RegistrationToken.created_at.desc()))
        tokens_by_license: dict[str, list[RegistrationToken]] = defaultdict(list)
        for token in token_result.scalars().all():
            tokens_by_license[token.license_id].append(token)
        for lic_id, tokens in tokens_by_license.items():
            token_summary_by_license[lic_id] = summarize_license_token_state(tokens, now)
    items = []
    for lic in licenses:
        payload = serialize_license(lic)
        payload["customer_name"] = customer_map.get(lic.customer_id)
        dc = await db.execute(select(func.count()).where(CentralDevice.license_id == lic.id))
        payload["device_count"] = dc.scalar() or 0
        payload["computed_status"] = compute_status(lic, now)
        payload["device_advisory_summary"] = posture_summary_by_license.get(lic.id) or summarize_posture_collection([])
        payload["token_summary"] = token_summary_by_license.get(lic.id) or summarize_license_token_state([], now)
        payload["commercial_readiness"] = build_license_commercial_readiness(lic, payload["device_advisory_summary"], now, payload["token_summary"])
        items.append(payload)
    return items


async def license_portfolio_summary_payload(*, db: AsyncSession, user, customer_id: str | None, status: str | None, can_access_customer, apply_customer_scope, utcnow, build_device_advisory_posture_map, summarize_posture_collection, summarize_license_token_state, build_license_portfolio_summary):
    now = utcnow()
    stmt = select(CentralLicense).order_by(CentralLicense.created_at.desc())
    if customer_id:
        await ensure_customer_access(user=user, customer_id=customer_id, can_access_customer=can_access_customer)
        stmt = stmt.where(CentralLicense.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLicense.customer_id)
    if status:
        stmt = stmt.where(CentralLicense.status == status)
    result = await db.execute(stmt)
    licenses = result.scalars().all()
    license_ids = [lic.id for lic in licenses]
    posture_summary_by_license = {}
    token_summary_by_license = {}
    if license_ids:
        license_devices_result = await db.execute(select(CentralDevice).where(CentralDevice.license_id.in_(license_ids)))
        license_devices = license_devices_result.scalars().all()
        device_postures = await build_device_advisory_posture_map(db, license_devices)
        devices_by_license: dict[str, list[dict]] = defaultdict(list)
        for device in license_devices:
            devices_by_license[device.license_id].append(device_postures.get(device.id))
        for lic_id, postures in devices_by_license.items():
            posture_summary_by_license[lic_id] = summarize_posture_collection(postures)
        token_result = await db.execute(select(RegistrationToken).where(RegistrationToken.license_id.in_(license_ids)).order_by(RegistrationToken.created_at.desc()))
        tokens_by_license: dict[str, list[RegistrationToken]] = defaultdict(list)
        for token in token_result.scalars().all():
            tokens_by_license[token.license_id].append(token)
        for lic_id, tokens in tokens_by_license.items():
            token_summary_by_license[lic_id] = summarize_license_token_state(tokens, now)
    return build_license_portfolio_summary(licenses, posture_summary_by_license, now, token_summary_by_license)


async def create_license_payload(*, db: AsyncSession, user, data: dict, can_access_customer, utcnow, log_audit, serialize_license):
    await ensure_customer_access(user=user, customer_id=data["customer_id"], can_access_customer=can_access_customer)
    ends_at = None
    grace_until = None
    if data.get("ends_at"):
        ends_at = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
        grace_days = data.get("grace_days", 7)
        grace_until = ends_at + timedelta(days=grace_days)
    license_row = CentralLicense(
        customer_id=data["customer_id"],
        location_id=data.get("location_id"),
        plan_type=data.get("plan_type", "standard"),
        max_devices=data.get("max_devices", 1),
        status=data.get("status", LicenseStatus.ACTIVE.value),
        starts_at=datetime.fromisoformat(data["starts_at"].replace("Z", "+00:00")) if data.get("starts_at") else utcnow(),
        ends_at=ends_at,
        grace_days=data.get("grace_days", 7),
        grace_until=grace_until,
        notes=data.get("notes"),
    )
    db.add(license_row)
    await db.flush()
    await log_audit(db, "LICENSE_CREATED", license_id=license_row.id, actor=user.username, message=f"License {license_row.plan_type} created for customer {data['customer_id']}")
    return serialize_license(license_row)


async def update_license_payload(*, db: AsyncSession, user, license_id: str, data: dict, can_access_customer, log_audit, serialize_license):
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    license_row = result.scalar_one_or_none()
    if not license_row:
        raise HTTPException(404, "License not found")
    await ensure_customer_access(user=user, customer_id=license_row.customer_id, can_access_customer=can_access_customer)
    for field in ("plan_type", "max_devices", "status", "notes", "grace_days"):
        if field in data:
            setattr(license_row, field, data[field])
    if "ends_at" in data:
        if data["ends_at"]:
            license_row.ends_at = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
            license_row.grace_until = license_row.ends_at + timedelta(days=license_row.grace_days or 7)
        else:
            license_row.ends_at = None
            license_row.grace_until = None
    await db.flush()
    await log_audit(db, "LICENSE_UPDATED", license_id=license_row.id, actor=user.username, message=f"License updated: status={license_row.status}")
    return serialize_license(license_row)


async def get_license_detail_payload(*, db: AsyncSession, user, license_id: str, can_access_customer, utcnow, aware, compute_status, build_license_commercial_readiness, refine_license_detail_suggested_actions, summarize_license_token_state, summarize_posture_collection, finalize_device_summary, serialize_device, serialize_license, serialize_reg_token_summary, finalize_reg_token_summary):
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    license_row = result.scalar_one_or_none()
    if not license_row:
        raise HTTPException(404, "License not found")
    await ensure_customer_access(user=user, customer_id=license_row.customer_id, can_access_customer=can_access_customer)

    dev_result = await db.execute(select(CentralDevice).where(CentralDevice.license_id == license_id).order_by(CentralDevice.created_at.desc()))
    devices = [finalize_device_summary(serialize_device(device), user) for device in dev_result.scalars().all()]

    tok_result = await db.execute(select(RegistrationToken).where(RegistrationToken.license_id == license_id).order_by(RegistrationToken.created_at.desc()))
    tokens = tok_result.scalars().all()
    active_token = None
    now = utcnow()
    for token in tokens:
        if not token.used_at and not token.is_revoked and (aware(token.expires_at) > now if token.expires_at else True):
            active_token = token
            break

    customer_name = None
    location_name = None
    if license_row.customer_id:
        cr = await db.execute(select(CentralCustomer).where(CentralCustomer.id == license_row.customer_id))
        customer = cr.scalar_one_or_none()
        if customer:
            customer_name = customer.name
    if license_row.location_id:
        lr = await db.execute(select(CentralLocation).where(CentralLocation.id == license_row.location_id))
        location = lr.scalar_one_or_none()
        if location:
            location_name = location.name

    computed_status = compute_status(license_row, now)
    advisory_summary = summarize_posture_collection([d.get("advisory_posture") for d in devices if isinstance(d, dict)])
    token_summary = summarize_license_token_state(tokens, now)
    commercial_readiness = build_license_commercial_readiness(license_row, advisory_summary, now, token_summary)
    commercial_readiness["suggested_actions"] = refine_license_detail_suggested_actions(
        license_row,
        commercial_readiness,
        active_token=active_token,
        device_count=len(devices),
    )

    detail = serialize_license(license_row)
    detail["computed_status"] = computed_status
    detail["customer_name"] = customer_name
    detail["location_name"] = location_name
    detail["devices"] = devices
    detail["device_count"] = len(devices)
    detail["device_advisory_summary"] = advisory_summary
    detail["token_summary"] = token_summary
    detail["commercial_readiness"] = commercial_readiness
    detail["active_token"] = finalize_reg_token_summary(serialize_reg_token_summary(active_token), user) if active_token else None
    detail["token_history"] = [finalize_reg_token_summary(serialize_reg_token_summary(token), user) for token in tokens]
    return detail
