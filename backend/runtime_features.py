"""Runtime feature gates and local-core compatibility helpers.

Phase 2 goal: keep the observer-first local core stable while pushing
central/licensing surfaces behind explicit opt-in seams.
"""
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict

from backend.models import PricingMode


_TRUTHY = {"1", "true", "yes", "on"}

LOCAL_CORE_PRICING_MODES = (
    PricingMode.PER_GAME.value,
    PricingMode.PER_TIME.value,
)

AUTODARTS_MODE = (os.environ.get("AUTODARTS_MODE", "observer") or "observer").strip().lower()
ENABLE_CENTRAL_ADAPTERS = (os.environ.get("ENABLE_CENTRAL_ADAPTERS", "") or "").strip().lower() in _TRUTHY
ENABLE_PORTAL_SURFACE = (
    os.environ.get("ENABLE_PORTAL_SURFACE", "1" if ENABLE_CENTRAL_ADAPTERS else "0").strip().lower() in _TRUTHY
)
ENABLE_CALL_STAFF = (os.environ.get("ENABLE_CALL_STAFF", "") or "").strip().lower() in _TRUTHY


def central_adapters_enabled() -> bool:
    return ENABLE_CENTRAL_ADAPTERS


def portal_surface_enabled() -> bool:
    return ENABLE_CENTRAL_ADAPTERS and ENABLE_PORTAL_SURFACE


def call_staff_enabled() -> bool:
    return ENABLE_CALL_STAFF


def observer_mode_requires_target() -> bool:
    return AUTODARTS_MODE == "observer"


def supports_local_pricing_mode(mode: str | None) -> bool:
    return (mode or "").strip() in LOCAL_CORE_PRICING_MODES


def sanitize_pricing_settings(pricing: Dict[str, Any] | None) -> Dict[str, Any]:
    """Keep pricing config compatible with the stable local-core surface.

    Historical data may still contain `per_player`. We preserve that payload for
    reporting / future migration, but normalize the operator-facing default mode
    back to a supported local mode.
    """
    cleaned: Dict[str, Any] = deepcopy(pricing or {})
    if cleaned.get("mode") not in LOCAL_CORE_PRICING_MODES:
        cleaned["mode"] = PricingMode.PER_GAME.value
    return cleaned
