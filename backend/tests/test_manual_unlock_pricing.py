from types import SimpleNamespace

from backend.models import PricingMode, SessionStatus
from backend.services.session_pricing import (
    MANUAL_UNLOCK_SENTINEL,
    apply_authoritative_start_charge,
    has_remaining_capacity,
)


def _manual_session(**overrides):
    data = {
        "status": SessionStatus.ACTIVE.value,
        "pricing_mode": PricingMode.PER_PLAYER.value,
        "credits_remaining": 0,
        "players_count": 0,
        "note": f"{MANUAL_UNLOCK_SENTINEL} Manual unlock without credits",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_manual_unlock_session_keeps_remaining_capacity():
    session = _manual_session()

    assert has_remaining_capacity(session) is True


def test_manual_unlock_session_does_not_charge_or_block_on_match_start():
    session = _manual_session()

    decision = apply_authoritative_start_charge(session, board_status="unlocked", players_count=2)

    assert decision.allowed is True
    assert decision.charged is False
    assert decision.blocked is False
    assert decision.delta_credits == 0
    assert decision.required_units == 0
    assert decision.reason == "manual_unlock"
