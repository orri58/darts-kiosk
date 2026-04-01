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
    "diagnostic_interpretations": ["round_transition_gameshot", "subscription", "match_other"],
    "delete_channel_prefixes": ["autodarts.matches.", "autodarts.boards."],
    "delete_channel_suffixes": [".state", ".matches", ".game-events"],
    "require_prior_active_for_finish": True,
    "require_prior_active_for_abort": True,
    "allow_console_finish_authority": False,
    "allow_dom_finish_authority": False,
}


def build_trigger_policy(config: Optional[Mapping[str, Any]] = None) -> TriggerPolicy:
    merged = dict(DEFAULT_TRIGGER_POLICY)
    if config:
        merged.update({k: v for k, v in dict(config).items() if v is not None})
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
