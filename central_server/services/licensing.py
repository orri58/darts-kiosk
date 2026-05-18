from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_license_status(lic, now: datetime) -> str:
    now = aware(now)
    starts_at = aware(getattr(lic, "starts_at", None))
    ends_at = aware(getattr(lic, "ends_at", None))
    grace_until = aware(getattr(lic, "grace_until", None))
    status = (getattr(lic, "status", None) or "").lower()

    if status in {"deactivated", "archived", "blocked"}:
        return status
    if starts_at and now < starts_at:
        return "pending"
    if ends_at and now > ends_at:
        if grace_until and now <= grace_until:
            return "grace"
        return "expired"
    return status or "active"


def token_status(token, *, now: datetime | None = None) -> str:
    if getattr(token, "is_revoked", False):
        return "revoked"
    if getattr(token, "used_at", None):
        return "used"
    reference_now = aware(now or utcnow())
    expires_at = aware(getattr(token, "expires_at", None))
    if expires_at and expires_at < reference_now:
        return "expired"
    return "active"


def serialize_registration_token_summary(token, *, now: datetime | None = None) -> dict:
    return {
        "id": token.id,
        "token_preview": token.token_preview,
        "license_id": token.license_id,
        "device_name_template": token.device_name_template,
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "used_at": token.used_at.isoformat() if token.used_at else None,
        "is_revoked": token.is_revoked,
        "revoked_at": token.revoked_at.isoformat() if token.revoked_at else None,
        "created_at": token.created_at.isoformat() if token.created_at else None,
        "status": token_status(token, now=now),
    }


def summarize_license_token_state(tokens: list[Any] | None, now: datetime | None = None) -> dict:
    now = aware(now or utcnow())
    tokens = list(tokens or [])
    active_token = None
    latest_token = tokens[0] if tokens else None
    used_count = 0
    revoked_count = 0
    expired_count = 0

    for token in tokens:
        status = token_status(token, now=now)
        if status == "active" and active_token is None:
            active_token = token
        elif status == "used":
            used_count += 1
        elif status == "revoked":
            revoked_count += 1
        elif status == "expired":
            expired_count += 1

    active_expires_in_days = None
    if active_token is not None and getattr(active_token, "expires_at", None):
        active_expires_in_days = math.floor((aware(active_token.expires_at) - now).total_seconds() / 86400)

    if active_token is not None:
        state = "active"
        message = "Aktiver Aktivierungstoken liegt bereits vor"
    elif used_count > 0:
        state = "consumed"
        message = "Letzter Token wurde bereits bei einer Registrierung verbraucht"
    elif expired_count > 0:
        state = "expired"
        message = "Vorherige Aktivierungstoken sind abgelaufen"
    elif revoked_count > 0:
        state = "revoked"
        message = "Vorherige Aktivierungstoken wurden widerrufen"
    else:
        state = "missing"
        message = "Noch kein Aktivierungstoken erstellt"

    return {
        "state": state,
        "message": message,
        "badge_tone": {
            "active": "blue",
            "consumed": "emerald",
            "expired": "amber",
            "revoked": "red",
            "missing": "zinc",
        }.get(state, "zinc"),
        "active_token": serialize_registration_token_summary(active_token, now=now) if active_token else None,
        "active_expires_in_days": active_expires_in_days,
        "latest_token_created_at": latest_token.created_at.isoformat() if latest_token and getattr(latest_token, "created_at", None) else None,
        "counts": {
            "total": len(tokens),
            "active": 1 if active_token is not None else 0,
            "used": used_count,
            "revoked": revoked_count,
            "expired": expired_count,
        },
    }


def build_license_suggested_actions(license_row, readiness: dict | None = None) -> list[dict]:
    readiness = readiness or {}
    suggested_actions: list[dict] = []
    risk_flags = set(readiness.get("risk_flags") or [])
    computed_status = readiness.get("computed_status") or compute_license_status(license_row, utcnow())
    raw_status = str(getattr(license_row, "status", None) or "").lower()
    capacity_state = readiness.get("capacity_state")
    posture_status = readiness.get("posture_status")
    token_state = readiness.get("token_state")

    def add(action_type: str, label: str, *, priority: str, intent: str, reason: str, execution: dict | None = None):
        suggested_actions.append({
            "type": action_type,
            "label": label,
            "priority": priority,
            "intent": intent,
            "reason": reason,
            "execution": execution or {"mode": "navigate", "target": "license_detail"},
        })

    if "license_inactive" in risk_flags:
        if raw_status == "deactivated":
            add(
                "reactivate_license",
                "Lizenz reaktivieren",
                priority="urgent",
                intent="reactivate",
                reason="Deaktivierte Lizenz wieder fuer Betrieb freischalten",
                execution={"mode": "direct", "action": "reactivate_license"},
            )
        elif raw_status == "archived":
            add("review_archived_license", "Archivstatus pruefen", priority="urgent", intent="reactivate", reason="Archivierte Lizenz vor neuer Nutzung zuerst pruefen")
        else:
            add("review_contract_state", "Vertragsstatus klaeren", priority="urgent", intent="renew", reason="Inaktive/gesperrte Lizenz vor weiteren Rollouts klaeren")

    if "license_grace" in risk_flags or "renewal_due" in risk_flags:
        add("renew_license", "Renewal vorbereiten", priority="high" if "license_grace" in risk_flags else "medium", intent="renew", reason="Laufzeit oder Grace-Phase aktiv nachverfolgen")

    if "activation_gap" in risk_flags:
        action_type = "generate_activation_token"
        label = "Aktivierung starten"
        reason = "Aktive Lizenz ohne gebundenes Geraet"
        execution_action = "ensure_activation_token"
        if token_state == "active":
            action_type = "get_activation_token"
            label = "Token abrufen"
            reason = "Aktiver Token besteht bereits und kann direkt fuer die Inbetriebnahme genutzt werden"
        elif token_state in {"expired", "revoked"}:
            action_type = "regenerate_activation_token"
            label = "Token erneuern"
            reason = "Vorheriger Token ist nicht mehr nutzbar; frischen Token fuer die Inbetriebnahme erstellen"
            execution_action = "regenerate_activation_token"
        add(
            action_type,
            label,
            priority="high",
            intent="activate",
            reason=reason,
            execution={"mode": "direct", "action": execution_action},
        )

    if capacity_state in {"full", "over_capacity"}:
        add("upgrade_capacity", "Kapazitaet anpassen", priority="high" if capacity_state == "over_capacity" else "medium", intent="capacity", reason="Gebundene Geraete passen nicht mehr sauber zur Lizenzkapazitaet")

    if posture_status in {"review_required", "blocked"}:
        add(
            "review_bound_devices",
            "Gebundene Geraete pruefen",
            priority="high" if posture_status == "blocked" else "medium",
            intent="devices",
            reason="Advisory-Signale der gebundenen Geraete blockieren Commercial Readiness",
            execution={"mode": "navigate", "target": "remote_actions"},
        )

    if not suggested_actions:
        add("monitor_license", "Weiter beobachten", priority="low", intent="overview", reason="Aktuell kein direkter Eingriff noetig")

    return suggested_actions


def build_license_commercial_readiness(license_row, posture_summary: dict | None = None, now: datetime | None = None, token_summary: dict | None = None) -> dict:
    now = aware(now or utcnow())
    computed_status = compute_license_status(license_row, now)
    device_count = int(posture_summary.get("device_count") or 0) if posture_summary else 0
    max_devices = max(int(getattr(license_row, "max_devices", 0) or 0), 0)
    occupancy_ratio = round((device_count / max_devices), 3) if max_devices > 0 else None
    posture_state = (posture_summary or {}).get("overall_posture") or "ready"
    days_to_end = None
    ends_at = aware(getattr(license_row, "ends_at", None))
    if ends_at:
        days_to_end = math.floor((ends_at - now).total_seconds() / 86400)

    risk_flags: list[str] = []
    raw_status = str(getattr(license_row, "status", None) or "").lower()
    if computed_status in {"expired", "blocked"} or raw_status in {"deactivated", "archived"}:
        risk_flags.append("license_inactive")
    elif computed_status == "grace":
        risk_flags.append("license_grace")
    elif days_to_end is not None and days_to_end <= 14:
        risk_flags.append("renewal_due")

    if max_devices <= 0:
        capacity_state = "unconfigured"
        risk_flags.append("capacity_unconfigured")
    elif device_count == 0:
        capacity_state = "unassigned"
        risk_flags.append("activation_gap")
    elif device_count > max_devices:
        capacity_state = "over_capacity"
        risk_flags.append("capacity_over")
    elif device_count == max_devices:
        capacity_state = "full"
        risk_flags.append("capacity_full")
    elif occupancy_ratio is not None and occupancy_ratio >= 0.8:
        capacity_state = "near_capacity"
        risk_flags.append("capacity_near")
    else:
        capacity_state = "available"

    posture_counts = (posture_summary or {}).get("counts") or {}
    if posture_state == "blocked":
        risk_flags.append("device_blocked")
    elif posture_state == "review_required":
        risk_flags.append("device_review")
    elif posture_state == "degraded":
        risk_flags.append("device_degraded")

    action_bucket = "healthy"
    if any(flag in risk_flags for flag in {"license_inactive", "device_blocked", "capacity_over"}):
        action_bucket = "urgent"
    elif any(flag in risk_flags for flag in {"license_grace", "renewal_due", "device_review", "activation_gap", "capacity_full"}):
        action_bucket = "attention"
    elif any(flag in risk_flags for flag in {"device_degraded", "capacity_near"}):
        action_bucket = "watch"

    token_state = (token_summary or {}).get("state") or "unknown"
    if device_count == 0 and token_state == "active":
        risk_flags.append("activation_token_ready")
    elif device_count == 0 and token_state in {"expired", "revoked"}:
        risk_flags.append("activation_token_stale")

    if "license_inactive" in risk_flags:
        primary_message = f"Lizenzstatus ist {computed_status}"
        recommended_action = "Status oder Vertragslaufzeit in Central prüfen, bevor weitere Geräteaktionen geplant werden."
    elif "license_grace" in risk_flags:
        primary_message = "Lizenz läuft bereits in der Toleranzphase"
        recommended_action = "Verlängerung oder Vertragsklärung jetzt abschließen, damit der Standort nicht in den Ablauf kippt."
    elif "renewal_due" in risk_flags:
        primary_message = f"Verlängerung in {max(days_to_end, 0)} Tag(en) fällig"
        recommended_action = "Kundenansprache und Renewal-Plan vor Ablauf terminieren."
    elif "capacity_over" in risk_flags:
        primary_message = "Mehr Geräte gebunden als lizenzierte Kapazität"
        recommended_action = "Kapazität erhöhen oder nicht mehr benötigte Geräte entkoppeln."
    elif "capacity_full" in risk_flags:
        primary_message = "Kapazität vollständig belegt"
        recommended_action = "Für weitere Rollouts zuerst Upgrade oder zusätzliche Lizenz vorbereiten."
    elif "activation_gap" in risk_flags and token_state == "active":
        primary_message = "Lizenz ist aktiv, ein Aktivierungstoken liegt bereits bereit"
        recommended_action = "Bestehenden Token ans Gerät bringen oder bei Unsicherheit direkt frisch ausstellen."
    elif "activation_gap" in risk_flags and token_state in {"expired", "revoked"}:
        primary_message = "Lizenz ist aktiv, aber der letzte Aktivierungstoken ist nicht mehr nutzbar"
        recommended_action = "Token jetzt neu ausstellen und die Inbetriebnahme aktiv nachverfolgen."
    elif "activation_gap" in risk_flags:
        primary_message = "Lizenz ist aktiv, aber noch keinem Gerät zugeordnet"
        recommended_action = "Aktivierungstoken erzeugen und Inbetriebnahme aktiv nachverfolgen."
    elif "device_blocked" in risk_flags:
        primary_message = "Mindestens ein gebundenes Gerät ist kommerziell oder vertrauensseitig blockiert"
        recommended_action = "Gebundene Geräte im Advisory-Detail und Audit prüfen, bevor der Standort als marktreif gilt."
    elif "device_review" in risk_flags:
        primary_message = "Gebundene Geräte brauchen Operator-Review"
        recommended_action = "Offene Trust-/Commercial-Hinweise in den gebundenen Geräten durcharbeiten."
    elif "device_degraded" in risk_flags:
        primary_message = "Gebundene Geräte zeigen degradierte Advisory-Signale"
        recommended_action = "Warnungen beobachten und proaktiv vor dem nächsten Einsatz bereinigen."
    else:
        primary_message = "Lizenz, Kapazität und Geräteposture wirken betriebsbereit"
        recommended_action = "Kein direkter Eingriff nötig; normal weiter überwachen."

    readiness = {
        "computed_status": computed_status,
        "device_count": device_count,
        "max_devices": max_devices,
        "occupancy_ratio": occupancy_ratio,
        "capacity_state": capacity_state,
        "renewal_days": days_to_end,
        "posture_status": posture_state,
        "posture_counts": posture_counts,
        "action_bucket": action_bucket,
        "risk_flags": risk_flags,
        "primary_message": primary_message,
        "recommended_action": recommended_action,
        "token_state": token_state,
        "token_summary": token_summary,
    }
    readiness["suggested_actions"] = build_license_suggested_actions(license_row, readiness)
    return readiness


def refine_license_detail_suggested_actions(license_row, readiness: dict | None, *, active_token, device_count: int) -> list[dict]:
    readiness = dict(readiness or {})
    suggested_actions = [dict(item) for item in (readiness.get("suggested_actions") or [])]
    computed_status = readiness.get("computed_status") or compute_license_status(license_row, utcnow())
    is_operational = computed_status in {"active", "test", "grace"}

    if is_operational and device_count == 0 and active_token is not None:
        replaced = False
        for item in suggested_actions:
            if item.get("type") == "generate_activation_token":
                item.update({
                    "type": "regenerate_activation_token",
                    "label": "Token neu ausstellen",
                    "reason": "Aktiver Token besteht bereits; bei Weitergabe oder Unklarheit lieber frischen Token verwenden",
                    "execution": {"mode": "direct", "action": "regenerate_activation_token"},
                })
                replaced = True
                break
        if not replaced:
            suggested_actions.insert(0, {
                "type": "regenerate_activation_token",
                "label": "Token neu ausstellen",
                "priority": "medium",
                "intent": "activate",
                "reason": "Aktiver Token besteht bereits; bei Weitergabe oder Unklarheit lieber frischen Token verwenden",
                "execution": {"mode": "direct", "action": "regenerate_activation_token"},
            })

    return suggested_actions


def build_license_portfolio_summary(licenses: list, posture_summary_by_license: dict[str, dict] | None = None, now: datetime | None = None, token_summary_by_license: dict[str, dict] | None = None) -> dict:
    now = aware(now or utcnow())
    posture_summary_by_license = posture_summary_by_license or {}
    token_summary_by_license = token_summary_by_license or {}
    counts = {
        "total": len(licenses),
        "healthy": 0,
        "watch": 0,
        "attention": 0,
        "urgent": 0,
        "renewal_due": 0,
        "in_grace": 0,
        "activation_gap": 0,
        "token_ready": 0,
        "token_attention": 0,
        "near_capacity": 0,
        "full_or_over_capacity": 0,
        "review_required": 0,
        "blocked_devices": 0,
    }
    status_breakdown: dict[str, int] = defaultdict(int)
    plan_breakdown: dict[str, int] = defaultdict(int)
    portfolio_items = []

    for lic in licenses:
        readiness = build_license_commercial_readiness(lic, posture_summary_by_license.get(lic.id), now, token_summary_by_license.get(lic.id))
        counts[readiness["action_bucket"]] += 1
        status_breakdown[readiness["computed_status"]] += 1
        plan_breakdown[str(getattr(lic, "plan_type", None) or "unknown")] += 1
        if "renewal_due" in readiness["risk_flags"]:
            counts["renewal_due"] += 1
        if "license_grace" in readiness["risk_flags"]:
            counts["in_grace"] += 1
        if "activation_gap" in readiness["risk_flags"]:
            counts["activation_gap"] += 1
        if "activation_token_ready" in readiness["risk_flags"]:
            counts["token_ready"] += 1
        if "activation_token_stale" in readiness["risk_flags"] or readiness["token_state"] == "missing":
            counts["token_attention"] += 1
        if readiness["capacity_state"] in {"near_capacity", "full", "over_capacity"}:
            counts["near_capacity"] += 1
        if readiness["capacity_state"] in {"full", "over_capacity"}:
            counts["full_or_over_capacity"] += 1
        if readiness["posture_status"] == "review_required":
            counts["review_required"] += 1
        if readiness["posture_status"] == "blocked":
            counts["blocked_devices"] += 1

        portfolio_items.append({
            "license_id": lic.id,
            "plan_type": getattr(lic, "plan_type", None),
            "customer_id": getattr(lic, "customer_id", None),
            "location_id": getattr(lic, "location_id", None),
            "ends_at": lic.ends_at.isoformat() if getattr(lic, "ends_at", None) else None,
            **readiness,
        })

    action_order = {"urgent": 0, "attention": 1, "watch": 2, "healthy": 3}
    portfolio_items.sort(key=lambda item: (
        action_order.get(item["action_bucket"], 9),
        item["renewal_days"] if item["renewal_days"] is not None else 10**9,
        -(item["occupancy_ratio"] or 0),
        item["license_id"],
    ))

    return {
        "counts": counts,
        "status_breakdown": dict(status_breakdown),
        "plan_breakdown": dict(plan_breakdown),
        "focus_queues": {
            "urgent": portfolio_items[:6],
            "renewals": [
                item for item in portfolio_items
                if ("renewal_due" in item["risk_flags"] or "license_grace" in item["risk_flags"])
                and "license_inactive" not in item["risk_flags"]
            ][:6],
            "activation_gaps": [item for item in portfolio_items if "activation_gap" in item["risk_flags"]][:6],
            "token_follow_up": [
                item for item in portfolio_items
                if "activation_gap" in item["risk_flags"]
                and item.get("token_state") in {"missing", "expired", "revoked", "active"}
            ][:6],
            "capacity_pressure": [item for item in portfolio_items if item["capacity_state"] in {"near_capacity", "full", "over_capacity"}][:6],
            "device_review": [
                item for item in portfolio_items
                if item["posture_status"] in {"review_required", "blocked"}
                and "license_inactive" not in item["risk_flags"]
            ][:6],
        },
    }
