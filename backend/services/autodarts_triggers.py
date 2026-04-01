from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


class TriggerAuthority(str, Enum):
    AUTHORITATIVE = "authoritative"
    ASSISTIVE = "assistive"
    DIAGNOSTIC = "diagnostic"
    IGNORED = "ignored"


class TriggerAction(str, Enum):
    START = "start"
    FINISH = "finish"
    ABORT = "abort"
    RESET = "reset"
    DIAGNOSTIC = "diagnostic"
    NONE = "none"


@dataclass(frozen=True)
class TriggerDecision:
    interpretation: str
    action: TriggerAction
    authority: TriggerAuthority
    reason: str

    @property
    def is_authoritative(self) -> bool:
        return self.authority == TriggerAuthority.AUTHORITATIVE

    @property
    def is_assistive(self) -> bool:
        return self.authority == TriggerAuthority.ASSISTIVE


@dataclass(frozen=True)
class TriggerPolicy:
    authoritative_start: frozenset[str]
    authoritative_finish: frozenset[str]
    authoritative_abort: frozenset[str]
    assistive_finish: frozenset[str]
    diagnostic_interpretations: frozenset[str]
    delete_channel_prefixes: tuple[str, ...]
    delete_channel_suffixes: tuple[str, ...]
    require_prior_active_for_finish: bool
    require_prior_active_for_abort: bool
    allow_console_finish_authority: bool
    allow_dom_finish_authority: bool

    def is_qualified_delete_channel(self, channel: str | None) -> bool:
        value = (channel or "").strip().lower()
        if not value:
            return False
        return value.startswith(self.delete_channel_prefixes) and value.endswith(self.delete_channel_suffixes)

    def classify_ws(self, interpretation: str, channel: str | None = None) -> TriggerDecision:
        if interpretation in self.authoritative_start:
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.START,
                authority=TriggerAuthority.AUTHORITATIVE,
                reason="authoritative_start_signal",
            )
        if interpretation in self.authoritative_finish:
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.FINISH,
                authority=TriggerAuthority.AUTHORITATIVE,
                reason="authoritative_finish_signal",
            )
        if interpretation in self.authoritative_abort:
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.ABORT,
                authority=TriggerAuthority.AUTHORITATIVE,
                reason="authoritative_abort_signal",
            )
        if interpretation == "match_reset_delete":
            if self.is_qualified_delete_channel(channel):
                return TriggerDecision(
                    interpretation=interpretation,
                    action=TriggerAction.ABORT,
                    authority=TriggerAuthority.AUTHORITATIVE,
                    reason="qualified_delete_abort_signal",
                )
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.DIAGNOSTIC,
                authority=TriggerAuthority.DIAGNOSTIC,
                reason="delete_channel_not_qualified",
            )
        if interpretation in self.assistive_finish:
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.FINISH,
                authority=TriggerAuthority.ASSISTIVE,
                reason="assistive_finish_hint",
            )
        if interpretation in self.diagnostic_interpretations:
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.DIAGNOSTIC,
                authority=TriggerAuthority.DIAGNOSTIC,
                reason="diagnostic_signal",
            )
        if interpretation == "irrelevant":
            return TriggerDecision(
                interpretation=interpretation,
                action=TriggerAction.NONE,
                authority=TriggerAuthority.IGNORED,
                reason="ignored_signal",
            )
        return TriggerDecision(
            interpretation=interpretation,
            action=TriggerAction.DIAGNOSTIC,
            authority=TriggerAuthority.DIAGNOSTIC,
            reason="unmapped_signal",
        )

    def export(self) -> dict[str, Any]:
        return {
            "authoritative_start": sorted(self.authoritative_start),
            "authoritative_finish": sorted(self.authoritative_finish),
            "authoritative_abort": sorted(self.authoritative_abort),
            "assistive_finish": sorted(self.assistive_finish),
            "diagnostic_interpretations": sorted(self.diagnostic_interpretations),
            "delete_channel_prefixes": list(self.delete_channel_prefixes),
            "delete_channel_suffixes": list(self.delete_channel_suffixes),
            "require_prior_active_for_finish": self.require_prior_active_for_finish,
            "require_prior_active_for_abort": self.require_prior_active_for_abort,
            "allow_console_finish_authority": self.allow_console_finish_authority,
            "allow_dom_finish_authority": self.allow_dom_finish_authority,
        }


def _as_frozenset(value: Any, fallback: tuple[str, ...]) -> frozenset[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(fallback)
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return frozenset(cleaned or fallback)


def _as_tuple(value: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return fallback
    cleaned = tuple(str(item).strip().lower() for item in value if str(item).strip())
    return cleaned or fallback


DEFAULT_TRIGGER_POLICY = {
    "authoritative_start": ["match_start_throw", "match_start_turn_start"],
    "authoritative_finish": ["match_end_state_finished", "match_end_game_finished"],
    "authoritative_abort": ["match_abort_delete"],
    "assistive_finish": ["match_end_gameshot_match", "match_finished_matchshot"],
    "diagnostic_interpretations": ["round_transition_gameshot", "subscription", "match_other", "match_reset_delete"],
    "delete_channel_prefixes": ["autodarts.matches.", "autodarts.boards."],
    "delete_channel_suffixes": [".state", ".matches", ".game-events"],
    "require_prior_active_for_finish": True,
    "require_prior_active_for_abort": True,
    "allow_console_finish_authority": False,
    "allow_dom_finish_authority": False,
}

TRIGGER_SIGNAL_GROUPS = {
    "authoritative_start": [
        {
            "interpretation": "match_start_throw",
            "label": "First throw detected",
            "description": "Zuverlässiger Match-Start über den ersten echten Throw.",
            "source": "autodarts websocket",
            "role": "authoritative",
            "action": "start",
            "group": "authoritative_start",
        },
        {
            "interpretation": "match_start_turn_start",
            "label": "Turn start signal",
            "description": "Fallback-Startsignal, wenn der Match-Throw nicht sauber ankommt.",
            "source": "autodarts websocket",
            "role": "authoritative",
            "action": "start",
            "group": "authoritative_start",
        },
    ],
    "authoritative_finish": [
        {
            "interpretation": "match_end_state_finished",
            "label": "State switched to finished",
            "description": "Harter Finish-Zustand aus der Match-State-Subscription.",
            "source": "autodarts websocket",
            "role": "authoritative",
            "action": "finish",
            "group": "authoritative_finish",
        },
        {
            "interpretation": "match_end_game_finished",
            "label": "Game finished event",
            "description": "Direktes Game-Ende-Event aus den Spielereignissen.",
            "source": "autodarts websocket",
            "role": "authoritative",
            "action": "finish",
            "group": "authoritative_finish",
        },
    ],
    "authoritative_abort": [
        {
            "interpretation": "match_abort_delete",
            "label": "Qualified delete abort",
            "description": "Nur gültig zusammen mit geschützten Delete-Channel-Regeln serverseitig.",
            "source": "qualified websocket delete",
            "role": "authoritative",
            "action": "abort",
            "group": "authoritative_abort",
        },
    ],
    "assistive_finish": [
        {
            "interpretation": "match_end_gameshot_match",
            "label": "Game shot hint",
            "description": "Früher Finish-Hinweis. Darf allein keine Credits verbrauchen.",
            "source": "autodarts websocket",
            "role": "assistive",
            "action": "finish",
            "group": "assistive_finish",
        },
        {
            "interpretation": "match_finished_matchshot",
            "label": "Match shot hint",
            "description": "Assistiver Matchshot-Hinweis aus der Observer-Interpretation.",
            "source": "observer derived hint",
            "role": "assistive",
            "action": "finish",
            "group": "assistive_finish",
        },
    ],
    "diagnostic_interpretations": [
        {
            "interpretation": "round_transition_gameshot",
            "label": "Round transition",
            "description": "Nur fürs Debugging bei Rundenwechseln und Game-Shot-Kantenfällen.",
            "source": "observer derived hint",
            "role": "diagnostic",
            "action": "diagnostic",
            "group": "diagnostic_interpretations",
        },
        {
            "interpretation": "subscription",
            "label": "Subscription lifecycle",
            "description": "Verbindungsdiagnostik der aktiven WS-Subscriptions.",
            "source": "autodarts websocket",
            "role": "diagnostic",
            "action": "diagnostic",
            "group": "diagnostic_interpretations",
        },
        {
            "interpretation": "match_other",
            "label": "Unclassified match signal",
            "description": "Sammelt nicht eindeutig zuordenbare Match-Events für spätere Analyse.",
            "source": "observer classification",
            "role": "diagnostic",
            "action": "diagnostic",
            "group": "diagnostic_interpretations",
        },
        {
            "interpretation": "match_reset_delete",
            "label": "Delete without qualification",
            "description": "Delete-Hinweis bleibt diagnostisch, solange Kanal/Scope nicht qualifiziert ist.",
            "source": "autodarts websocket",
            "role": "diagnostic",
            "action": "diagnostic",
            "group": "diagnostic_interpretations",
        },
    ],
}

TRIGGER_POLICY_PRESETS = [
    {
        "id": "strict_ws",
        "label": "WS strict",
        "description": "Empfohlen für produktive lokale Setups. Nur saubere WS-Signale bekommen echte Authority.",
        "recommended": True,
        "risk": "low",
        "risk_label": "Empfohlen",
        "config": {
            **DEFAULT_TRIGGER_POLICY,
        },
    },
    {
        "id": "console_recovery",
        "label": "Console recovery",
        "description": "Behält WS-Signale bei, erlaubt aber Konsole als zusätzlichen Finish-Fallback für instabile Venues.",
        "recommended": False,
        "risk": "medium",
        "risk_label": "Fallback",
        "config": {
            **DEFAULT_TRIGGER_POLICY,
            "allow_console_finish_authority": True,
        },
    },
    {
        "id": "dom_last_resort",
        "label": "DOM last resort",
        "description": "Nur für hartnäckige Recovery-Fälle. Ergänzt Console + DOM als letzte Finish-Authority.",
        "recommended": False,
        "risk": "high",
        "risk_label": "Letzter Fallback",
        "config": {
            **DEFAULT_TRIGGER_POLICY,
            "allow_console_finish_authority": True,
            "allow_dom_finish_authority": True,
        },
    },
]

KNOWN_TRIGGER_INTERPRETATIONS = frozenset(
    item["interpretation"]
    for items in TRIGGER_SIGNAL_GROUPS.values()
    for item in items
)

_EDITABLE_SIGNAL_GROUPS = (
    "authoritative_start",
    "authoritative_finish",
    "authoritative_abort",
    "assistive_finish",
    "diagnostic_interpretations",
)

_BOOLEAN_TRIGGER_FIELDS = (
    "require_prior_active_for_finish",
    "require_prior_active_for_abort",
    "allow_console_finish_authority",
    "allow_dom_finish_authority",
)


def _sanitize_signal_group(group_key: str, raw_value: Any) -> list[str]:
    fallback = tuple(DEFAULT_TRIGGER_POLICY[group_key])
    values = _as_frozenset(raw_value, fallback)
    unknown = sorted(values - KNOWN_TRIGGER_INTERPRETATIONS)
    if unknown:
        raise ValueError(f"Unknown trigger interpretations for {group_key}: {', '.join(unknown)}")
    if not values:
        raise ValueError(f"{group_key} must contain at least one known interpretation")
    return sorted(values)


def sanitize_trigger_policy_config(config: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    merged = dict(DEFAULT_TRIGGER_POLICY)
    if config:
        merged.update({k: v for k, v in dict(config).items() if v is not None})

    sanitized: dict[str, Any] = {
        "version": 1,
    }

    for field in _EDITABLE_SIGNAL_GROUPS:
        sanitized[field] = _sanitize_signal_group(field, merged.get(field))

    sanitized["delete_channel_prefixes"] = list(DEFAULT_TRIGGER_POLICY["delete_channel_prefixes"])
    sanitized["delete_channel_suffixes"] = list(DEFAULT_TRIGGER_POLICY["delete_channel_suffixes"])

    for field in _BOOLEAN_TRIGGER_FIELDS:
        sanitized[field] = bool(merged.get(field, DEFAULT_TRIGGER_POLICY[field]))

    return sanitized


def export_trigger_policy_metadata() -> dict[str, Any]:
    return {
        "presets": [
            {
                **preset,
                "config": sanitize_trigger_policy_config(preset["config"]),
            }
            for preset in TRIGGER_POLICY_PRESETS
        ],
        "signal_catalog": [
            signal
            for group in _EDITABLE_SIGNAL_GROUPS
            for signal in TRIGGER_SIGNAL_GROUPS[group]
        ],
        "locked_fields": {
            "delete_channel_prefixes": list(DEFAULT_TRIGGER_POLICY["delete_channel_prefixes"]),
            "delete_channel_suffixes": list(DEFAULT_TRIGGER_POLICY["delete_channel_suffixes"]),
        },
    }


def build_trigger_policy(config: Optional[Mapping[str, Any]] = None) -> TriggerPolicy:
    merged = sanitize_trigger_policy_config(config)
    return TriggerPolicy(
        authoritative_start=_as_frozenset(
            merged.get("authoritative_start"),
            tuple(DEFAULT_TRIGGER_POLICY["authoritative_start"]),
        ),
        authoritative_finish=_as_frozenset(
            merged.get("authoritative_finish"),
            tuple(DEFAULT_TRIGGER_POLICY["authoritative_finish"]),
        ),
        authoritative_abort=_as_frozenset(
            merged.get("authoritative_abort"),
            tuple(DEFAULT_TRIGGER_POLICY["authoritative_abort"]),
        ),
        assistive_finish=_as_frozenset(
            merged.get("assistive_finish"),
            tuple(DEFAULT_TRIGGER_POLICY["assistive_finish"]),
        ),
        diagnostic_interpretations=_as_frozenset(
            merged.get("diagnostic_interpretations"),
            tuple(DEFAULT_TRIGGER_POLICY["diagnostic_interpretations"]),
        ),
        delete_channel_prefixes=_as_tuple(
            merged.get("delete_channel_prefixes"),
            tuple(DEFAULT_TRIGGER_POLICY["delete_channel_prefixes"]),
        ),
        delete_channel_suffixes=_as_tuple(
            merged.get("delete_channel_suffixes"),
            tuple(DEFAULT_TRIGGER_POLICY["delete_channel_suffixes"]),
        ),
        require_prior_active_for_finish=bool(merged.get("require_prior_active_for_finish", True)),
        require_prior_active_for_abort=bool(merged.get("require_prior_active_for_abort", True)),
        allow_console_finish_authority=bool(merged.get("allow_console_finish_authority", False)),
        allow_dom_finish_authority=bool(merged.get("allow_dom_finish_authority", False)),
    )
