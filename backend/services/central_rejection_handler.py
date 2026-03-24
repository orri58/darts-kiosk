"""
Central Rejection Handler — v3.13.0

Shared handler for when the central server rejects a device (HTTP 403).
Updates the local license cache to 'suspended' and logs the event.
This ensures that when a device is deactivated/blocked centrally,
the local kiosk immediately enters a restricted state.

Called by: telemetry_sync_client, config_sync_client, action_poller.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def handle_central_rejection(source: str, status_code: int, detail: str = ""):
    """
    Called when any sync service receives a 403 from the central server.
    Updates the local license cache to 'suspended' so the kiosk blocks all operations.

    Args:
        source: Which service triggered this (e.g., "heartbeat", "config_sync", "action_poller")
        status_code: The HTTP status code received
        detail: Any detail message from the response body
    """
    if status_code != 403:
        return

    logger.warning(
        f"[CENTRAL-REJECTION] Device rejected by central server! "
        f"source={source} status={status_code} detail={detail}"
    )

    try:
        from backend.services.license_service import license_service
        from backend.services.device_log_buffer import device_logs

        # Update the license cache to 'suspended'
        suspended_status = {
            "status": "suspended",
            "source": "central_rejection",
            "rejection_source": source,
            "rejection_detail": detail,
            "checked_at": _utcnow().isoformat(),
            "registration_status": "registered",
        }

        # Preserve existing customer/license info from cache if available
        existing = license_service.load_from_cache()
        if existing:
            for key in ("customer_name", "license_id", "plan_type"):
                if existing.get(key):
                    suspended_status[key] = existing[key]

        license_service.save_to_cache(suspended_status)

        device_logs.warn(
            "central_rejection",
            "device_suspended",
            f"Device suspended by central server ({source}: {detail})",
        )

        logger.warning(
            f"[CENTRAL-REJECTION] License cache updated to 'suspended' (source={source})"
        )
    except Exception as e:
        logger.error(f"[CENTRAL-REJECTION] Failed to update license cache: {e}")


async def handle_central_reactivation(source: str):
    """
    v3.15.3: REMOVED auto-reactivation.
    
    Central server status is AUTHORITATIVE. Only the central server
    can change a device from suspended → active. No local flow
    may override a suspended/blocked state.
    
    This function now ONLY logs that the central server accepted
    the device again. The actual status change happens via the
    next license check that the central server returns.
    """
    try:
        from backend.services.license_service import license_service

        cached = license_service.load_from_cache()
        if cached and cached.get("source") == "central_rejection":
            # Central is accepting us again — but DO NOT change cache.
            # Let the next license check (with real status from central) update it.
            logger.info(
                f"[CENTRAL-REJECTION] Central accepting device again (source={source}). "
                f"Cache remains suspended — waiting for authoritative license check."
            )
            # Log for observability, but do NOT write to cache
            try:
                from backend.services.device_log_buffer import device_logs
                device_logs.info(
                    "central_rejection",
                    "central_accepting_again",
                    f"Central accepted ({source}), cache still suspended pending license check",
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[CENTRAL-REJECTION] Reactivation handler error: {e}")
