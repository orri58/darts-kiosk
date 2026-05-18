"""Telemetry utilities for central server.
Provides device connectivity computation based on heartbeat timestamps.
"""
from datetime import datetime, timezone
from .server import _utcnow  # reuse utcnow helper

# Thresholds (seconds)
ONLINE_THRESHOLD_SECONDS = 300  # 5 minutes
DEGRADED_THRESHOLD_SECONDS = 900  # 15 minutes — online > degraded > offline

def compute_device_connectivity(last_heartbeat_at) -> str:
    """Compute device connectivity status.
    Returns one of "online", "degraded", "offline".
    """
    if last_heartbeat_at is None:
        return "offline"
    now = _utcnow()
    try:
        if isinstance(last_heartbeat_at, str):
            try:
                last_heartbeat_at = datetime.fromisoformat(last_heartbeat_at.replace("Z", "+00:00"))
            except Exception:
                return "offline"
        if hasattr(last_heartbeat_at, "tzinfo") and last_heartbeat_at.tzinfo is None:
            last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
        diff = (now - last_heartbeat_at).total_seconds()
        if diff < ONLINE_THRESHOLD_SECONDS:
            return "online"
        elif diff < DEGRADED_THRESHOLD_SECONDS:
            return "degraded"
        else:
            return "offline"
    except Exception:
        return "offline"
