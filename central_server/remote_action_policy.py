from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


class RemoteActionPolicyError(ValueError):
    """Raised when a remote action violates central policy."""


@dataclass(frozen=True)
class RemoteActionPolicy:
    action_type: str
    category: str
    risk_level: str
    queue_allowed: bool
    min_role: str
    approval_required: bool = False
    ttl_seconds: int = 300
    params_kind: str = "any_json"  # any_json | object_only | none_only
    notes: str | None = None

    def expires_at(self, issued_at: datetime | None) -> datetime | None:
        if issued_at is None:
            return None
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=timezone.utc)
        return issued_at + timedelta(seconds=self.ttl_seconds)

    def serialize_metadata(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "risk_level": self.risk_level,
            "queue_allowed": self.queue_allowed,
            "min_role": self.min_role,
            "approval_required": self.approval_required,
            "ttl_seconds": self.ttl_seconds,
            "params_kind": self.params_kind,
            "notes": self.notes,
        }


ROLE_HIERARCHY = {
    "staff": 1,
    "owner": 2,
    "installer": 3,
    "superadmin": 4,
}


REMOTE_ACTION_POLICIES: dict[str, RemoteActionPolicy] = {
    "force_sync": RemoteActionPolicy(
        action_type="force_sync",
        category="maintenance",
        risk_level="low",
        queue_allowed=True,
        min_role="owner",
        ttl_seconds=300,
        params_kind="none_only",
        notes="Refreshes central sync state without mutating live local gameplay state.",
    ),
    "reload_ui": RemoteActionPolicy(
        action_type="reload_ui",
        category="maintenance",
        risk_level="medium",
        queue_allowed=True,
        min_role="owner",
        ttl_seconds=180,
        params_kind="none_only",
        notes="UI refresh only; additive maintenance action.",
    ),
    "restart_backend": RemoteActionPolicy(
        action_type="restart_backend",
        category="maintenance",
        risk_level="high",
        queue_allowed=True,
        min_role="installer",
        approval_required=True,
        ttl_seconds=180,
        params_kind="none_only",
        notes="Strictly controlled operational restart; narrowed to installer+.",
    ),
    "unlock_board": RemoteActionPolicy(
        action_type="unlock_board",
        category="board_control",
        risk_level="critical",
        queue_allowed=False,
        min_role="installer",
        approval_required=True,
        params_kind="object_only",
        notes="Blocked centrally in V1: revenue/board state mutation should remain local-authoritative.",
    ),
    "lock_board": RemoteActionPolicy(
        action_type="lock_board",
        category="board_control",
        risk_level="critical",
        queue_allowed=False,
        min_role="installer",
        approval_required=True,
        params_kind="object_only",
        notes="Blocked centrally in V1: revenue/board state mutation should remain local-authoritative.",
    ),
    "start_session": RemoteActionPolicy(
        action_type="start_session",
        category="session_control",
        risk_level="critical",
        queue_allowed=False,
        min_role="installer",
        approval_required=True,
        params_kind="object_only",
        notes="Blocked centrally in V1: central must not become authoritative over live session lifecycle.",
    ),
    "stop_session": RemoteActionPolicy(
        action_type="stop_session",
        category="session_control",
        risk_level="critical",
        queue_allowed=False,
        min_role="installer",
        approval_required=True,
        params_kind="object_only",
        notes="Blocked centrally in V1: central must not become authoritative over live session lifecycle.",
    ),
}


def get_remote_action_policy(action_type: str) -> RemoteActionPolicy:
    policy = REMOTE_ACTION_POLICIES.get((action_type or "").strip())
    if not policy:
        raise RemoteActionPolicyError(f"Unknown remote action_type: {action_type}")
    return policy


def list_remote_action_types() -> list[str]:
    return sorted(REMOTE_ACTION_POLICIES.keys())


def validate_remote_action_request(*, action_type: str, params: Any, user_role: str) -> RemoteActionPolicy:
    policy = get_remote_action_policy(action_type)

    if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY.get(policy.min_role, 999):
        raise RemoteActionPolicyError(
            f"Action '{policy.action_type}' requires role {policy.min_role}+ (got {user_role})"
        )

    if not policy.queue_allowed:
        raise RemoteActionPolicyError(
            f"Action '{policy.action_type}' is blocked by central policy in V1 ({policy.category}, risk={policy.risk_level})"
        )

    if policy.params_kind == "none_only" and params not in (None, "", {}, []):
        raise RemoteActionPolicyError(f"Action '{policy.action_type}' does not accept params")
    if policy.params_kind == "object_only" and params is not None and not isinstance(params, dict):
        raise RemoteActionPolicyError(f"Action '{policy.action_type}' requires params to be a JSON object")

    return policy


def is_remote_action_expired(action_type: str, issued_at: datetime | None, now: datetime | None = None) -> bool:
    if issued_at is None:
        return False
    policy = get_remote_action_policy(action_type)
    expires_at = policy.expires_at(issued_at)
    if expires_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now >= expires_at


def can_deliver_remote_action(action_type: str) -> bool:
    return get_remote_action_policy(action_type).queue_allowed
