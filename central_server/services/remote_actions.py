from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from central_server.remote_action_policy import get_remote_action_policy, list_remote_action_types


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


VALID_ACTIONS = set(list_remote_action_types())
FINAL_REMOTE_ACTION_STATUSES = {"acked", "failed", "expired"}


def normalize_remote_action_request_state(action) -> str:
    request_state = getattr(action, "request_state", None)
    if request_state:
        return request_state
    approval_state = getattr(action, "approval_state", None)
    status = getattr(action, "status", None)
    if approval_state == "pending":
        return "pending_approval"
    if approval_state == "refused":
        return "refused"
    if status in FINAL_REMOTE_ACTION_STATUSES:
        return "finalized" if status in {"acked", "failed"} else "expired"
    return "queued"


def derive_remote_action_outcome(action) -> tuple[str | None, str | None]:
    outcome_code = getattr(action, "outcome_code", None)
    outcome_detail = getattr(action, "outcome_detail", None)
    if outcome_code:
        return outcome_code, outcome_detail

    request_state = normalize_remote_action_request_state(action)
    status = getattr(action, "status", None)
    approval_state = getattr(action, "approval_state", None)
    if approval_state == "refused" or request_state == "refused":
        return "refused", "manual_review"
    if request_state == "pending_approval":
        return "accepted", "awaiting_review"
    if status == "pending":
        return "accepted", "queued"
    if status == "acked":
        return "succeeded", "device_ack"
    if status == "failed":
        return "failed", "device_reported_failure"
    if status == "expired":
        message = (getattr(action, "result_message", "") or "").lower()
        if "blocked" in message:
            return "blocked", "central_policy"
        return "expired", "ttl_elapsed"
    return None, None


def build_remote_action_review_fields(policy, user, body: dict) -> dict:
    approval_required = bool(policy.approval_required)
    request_note = body.get("request_note") or body.get("note")
    return {
        "request_state": "pending_approval" if approval_required else "queued",
        "approval_state": "pending" if approval_required else "not_required",
        "outcome_code": "accepted",
        "outcome_detail": "awaiting_review" if approval_required else "queued",
        "request_note": request_note,
        "requested_at": utcnow(),
        "reviewed_at": None,
        "reviewed_by": None,
        "review_note": None,
        "delivered_at": None,
        "finalized_at": None,
        "finalized_by": None,
    }


def remote_action_summary_payload(actions: list) -> dict:
    counts = {
        "total": len(actions),
        "pending_delivery": 0,
        "pending_approval": 0,
        "approved": 0,
        "refused": 0,
        "finalized_success": 0,
        "finalized_failed": 0,
        "expired": 0,
    }
    by_outcome: dict[str, int] = defaultdict(int)
    by_action_type: dict[str, int] = defaultdict(int)
    by_request_state: dict[str, int] = defaultdict(int)
    by_approval_state: dict[str, int] = defaultdict(int)
    oldest_pending_approval_at = None
    latest_issued_at = None
    latest_finalized_at = None
    for action in actions:
        state = normalize_remote_action_request_state(action)
        outcome_code, _ = derive_remote_action_outcome(action)
        by_action_type[action.action_type] += 1
        by_request_state[state] += 1
        approval_state = getattr(action, "approval_state", None) or ("pending" if state == "pending_approval" else "not_required")
        by_approval_state[approval_state] += 1
        issued_at = aware(getattr(action, "issued_at", None))
        finalized_at = aware(getattr(action, "finalized_at", None) or getattr(action, "acked_at", None))
        if issued_at and (latest_issued_at is None or issued_at > latest_issued_at):
            latest_issued_at = issued_at
        if finalized_at and (latest_finalized_at is None or finalized_at > latest_finalized_at):
            latest_finalized_at = finalized_at
        if state == "pending_approval" and issued_at and (oldest_pending_approval_at is None or issued_at < oldest_pending_approval_at):
            oldest_pending_approval_at = issued_at
        if outcome_code:
            by_outcome[outcome_code] += 1
        if state == "pending_approval":
            counts["pending_approval"] += 1
        elif state == "approved":
            counts["approved"] += 1
        elif state == "refused":
            counts["refused"] += 1
        elif state == "expired":
            counts["expired"] += 1
        elif state in {"finalized", "delivered"}:
            if getattr(action, "status", None) == "acked":
                counts["finalized_success"] += 1
            elif getattr(action, "status", None) == "failed":
                counts["finalized_failed"] += 1
        else:
            counts["pending_delivery"] += 1
    return {
        "schema": "darts.remote_action_summary.v1",
        "counts": counts,
        "by_outcome": dict(sorted(by_outcome.items())),
        "by_action_type": dict(sorted(by_action_type.items())),
        "by_request_state": dict(sorted(by_request_state.items())),
        "by_approval_state": dict(sorted(by_approval_state.items())),
        "latest_issued_at": latest_issued_at.isoformat() if latest_issued_at else None,
        "latest_finalized_at": latest_finalized_at.isoformat() if latest_finalized_at else None,
        "oldest_pending_approval_at": oldest_pending_approval_at.isoformat() if oldest_pending_approval_at else None,
        "has_pending_review": counts["pending_approval"] > 0,
    }


def remote_action_scope_snapshot(action, *, device=None, location=None, customer=None, license_row=None) -> dict:
    getv = action.get if isinstance(action, dict) else lambda name, default=None: getattr(action, name, default)
    return {
        "device_id": getv("device_id"),
        "device_name": getattr(device, "device_name", None) if device is not None else None,
        "location_id": getattr(device, "location_id", None) if device is not None else getv("location_id"),
        "location_name": getattr(location, "name", None) if location is not None else None,
        "customer_id": getattr(location, "customer_id", None) if location is not None else getv("customer_id"),
        "customer_name": getattr(customer, "name", None) if customer is not None else None,
        "license_id": getattr(device, "license_id", None) if device is not None else getv("license_id"),
        "license_plan_type": getattr(license_row, "plan_type", None) if license_row is not None else None,
    }


def remote_action_triage_priority(summary: dict) -> tuple:
    counts = (summary or {}).get("counts") or {}
    return (
        -(counts.get("pending_approval") or 0),
        -(counts.get("pending_delivery") or 0),
        -(counts.get("expired") or 0),
        -(counts.get("refused") or 0),
        -(counts.get("total") or 0),
    )


def remote_action_problem_scope_payload(entries: list[dict], *, limit: int = 8) -> list[dict]:
    ranked = []
    for entry in entries or []:
        summary = entry.get("summary") or {}
        counts = summary.get("counts") or {}
        ranked.append({
            **entry,
            "problem_counts": {
                "pending_review": counts.get("pending_approval") or 0,
                "pending_delivery": counts.get("pending_delivery") or 0,
                "expired": counts.get("expired") or 0,
                "refused": counts.get("refused") or 0,
                "failed": counts.get("finalized_failed") or 0,
            },
            "problem_score": (
                ((counts.get("pending_approval") or 0) * 100)
                + ((counts.get("pending_delivery") or 0) * 40)
                + ((counts.get("expired") or 0) * 25)
                + ((counts.get("refused") or 0) * 15)
                + ((counts.get("finalized_failed") or 0) * 10)
                + (counts.get("total") or 0)
            ),
        })
    ranked.sort(key=lambda item: remote_action_triage_priority(item.get("summary") or {}) + (-int(item.get("problem_score") or 0),))
    return ranked[: max(1, min(limit, 24))]


def remote_action_queue_metrics(actions: list) -> dict:
    summary = remote_action_summary_payload(actions)
    counts = summary.get("counts") or {}
    pending_review = counts.get("pending_approval") or 0
    pending_delivery = counts.get("pending_delivery") or 0
    expired = counts.get("expired") or 0
    refused = counts.get("refused") or 0
    finalized_failed = counts.get("finalized_failed") or 0
    needs_triage = pending_review + expired + refused + finalized_failed
    return {
        "schema": "darts.remote_action_queue_metrics.v1",
        "summary": summary,
        "totals": {
            "needs_triage": needs_triage,
            "pending_review": pending_review,
            "pending_delivery": pending_delivery,
            "expired": expired,
            "refused": refused,
            "finalized_failed": finalized_failed,
        },
        "sla": {
            "oldest_pending_approval_at": summary.get("oldest_pending_approval_at"),
            "has_pending_review": summary.get("has_pending_review") is True,
        },
    }


def remote_action_lifecycle_details(action, *, event: str, actor: str | None = None, extra: dict | None = None) -> dict:
    getv = action.get if isinstance(action, dict) else lambda name, default=None: getattr(action, name, default)
    details = {
        "schema": "darts.remote_action_audit.v1",
        "event": event,
        "action_id": getv("id"),
        "device_id": getv("device_id"),
        "action_type": getv("action_type"),
        "status": getv("status"),
        "request_state": getv("request_state") or normalize_remote_action_request_state(action),
        "approval_state": getv("approval_state"),
        "outcome_code": getv("outcome_code"),
        "outcome_detail": getv("outcome_detail"),
        "issued_by": getv("issued_by"),
        "actor": actor,
        "issued_at": aware(getv("issued_at")).isoformat() if aware(getv("issued_at")) else None,
        "requested_at": aware(getv("requested_at")).isoformat() if aware(getv("requested_at")) else None,
        "reviewed_at": aware(getv("reviewed_at")).isoformat() if aware(getv("reviewed_at")) else None,
        "reviewed_by": getv("reviewed_by"),
        "delivered_at": aware(getv("delivered_at")).isoformat() if aware(getv("delivered_at")) else None,
        "finalized_at": aware(getv("finalized_at") or getv("acked_at")).isoformat() if aware(getv("finalized_at") or getv("acked_at")) else None,
        "finalized_by": getv("finalized_by"),
        "expires_at": None,
        "params_present": getv("params") is not None,
        "request_note_present": bool(getv("request_note")),
        "review_note_present": bool(getv("review_note")),
    }
    try:
        policy = get_remote_action_policy(getv("action_type"))
        expires_at = policy.expires_at(getv("issued_at"))
        details.update({
            "category": policy.category,
            "risk_level": policy.risk_level,
            "approval_required": policy.approval_required,
            "ttl_seconds": policy.ttl_seconds,
            "queue_allowed": policy.queue_allowed,
            "expires_at": expires_at.isoformat() if expires_at else None,
        })
    except Exception:
        pass
    if extra:
        details.update(extra)
    return details
