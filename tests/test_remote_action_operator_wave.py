from central_server.server import _remote_action_problem_scope_payload, _remote_action_triage_priority


def _scope(group_id, group_type, *, pending_review=0, pending_delivery=0, expired=0, refused=0, failed=0, total=None):
    total = total if total is not None else pending_review + pending_delivery + expired + refused + failed
    return {
        "group_id": group_id,
        "group_type": group_type,
        "group_name": f"{group_type}-{group_id}",
        "summary": {
            "counts": {
                "pending_approval": pending_review,
                "pending_delivery": pending_delivery,
                "expired": expired,
                "refused": refused,
                "finalized_failed": failed,
                "total": total,
            },
        },
    }


def test_remote_action_problem_scopes_prioritize_pending_review_and_delivery_pressure():
    scopes = [
        _scope("loc-1", "location", pending_review=1, pending_delivery=1, total=2),
        _scope("loc-2", "location", pending_review=0, pending_delivery=5, total=5),
        _scope("dev-1", "device", pending_review=2, pending_delivery=0, total=2),
    ]

    ranked = _remote_action_problem_scope_payload(scopes, limit=3)

    assert [item["group_id"] for item in ranked] == ["dev-1", "loc-1", "loc-2"]
    assert ranked[0]["problem_counts"]["pending_review"] == 2
    assert ranked[1]["problem_counts"]["pending_delivery"] == 1


def test_remote_action_triage_priority_prefers_pending_review_then_delivery_then_expired():
    high_review = {"counts": {"pending_approval": 1, "pending_delivery": 0, "expired": 0, "refused": 0, "total": 1}}
    high_delivery = {"counts": {"pending_approval": 0, "pending_delivery": 3, "expired": 0, "refused": 0, "total": 3}}
    expired = {"counts": {"pending_approval": 0, "pending_delivery": 0, "expired": 2, "refused": 0, "total": 2}}

    ordered = sorted([expired, high_delivery, high_review], key=_remote_action_triage_priority)

    assert ordered == [high_review, high_delivery, expired]
