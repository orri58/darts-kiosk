import pytest

from backend.services.autodarts_observer import AutodartsObserver, ObserverState
from backend.services.autodarts_triggers import (
    TriggerAuthority,
    build_trigger_policy,
    export_trigger_policy_metadata,
    sanitize_trigger_policy_config,
)


@pytest.fixture
def observer():
    obs = AutodartsObserver("BOARD-T1")
    obs.set_trigger_policy()
    return obs


def test_trigger_policy_classifies_authoritative_and_assistive_finish_signals():
    policy = build_trigger_policy()

    start_state = policy.classify_ws("match_start_state_active", "autodarts.lobbies.abc.state")
    confirmed = policy.classify_ws("match_end_state_finished", "autodarts.matches.abc.state")
    assistive = policy.classify_ws("match_end_gameshot_match", "autodarts.matches.abc.game-events")

    assert start_state.authority == TriggerAuthority.AUTHORITATIVE
    assert confirmed.authority == TriggerAuthority.AUTHORITATIVE
    assert assistive.authority == TriggerAuthority.ASSISTIVE


def test_state_active_is_classified_as_authoritative_match_start(observer):
    interpretation = observer._classify_frame(
        '{"state":"active"}',
        "autodarts.lobbies.match-1.state",
        {"state": "active"},
    )

    assert interpretation == "match_start_state_active"


def test_extract_match_id_falls_back_to_payload_match_id(observer):
    payload = {
        "channel": "autodarts.matches",
        "topic": "019d4f60-fa34-7130-b354-5fb5b5a7c718.game-events",
        "data": {
            "event": "throw",
            "matchId": "019d4f60-fa34-7130-b354-5fb5b5a7c718",
        },
    }

    match_id = observer._extract_match_id('autodarts.matches","topic":"019d4f60-fa34-7130-b354-5fb5b5a7c718.game-events', payload)

    assert match_id == "019d4f60-fa34-7130-b354-5fb5b5a7c718"


def test_match_not_found_state_error_is_classified_as_abort(observer):
    payload = {
        "channel": "autodarts.matches",
        "topic": "019d4fa3-bbb9-7619-a0ca-6375e523b044.state",
        "error": "match not found",
        "type": "error",
    }

    interpretation = observer._classify_frame(
        '{"channel":"autodarts.matches","topic":"019d4fa3-bbb9-7619-a0ca-6375e523b044.state","error":"match not found","type":"error"}',
        "autodarts.matches",
        payload,
    )

    assert interpretation == "match_abort_delete"


def test_assistive_finish_signal_is_pending_only(observer, monkeypatch):
    scheduled = []
    monkeypatch.setattr(observer, "_schedule_immediate_finalize", lambda trigger, match_id: scheduled.append((trigger, match_id)))
    monkeypatch.setattr(observer, "_schedule_finalize_safety", lambda trigger, match_id: scheduled.append((f"safety:{trigger}", match_id)))

    observer._ws_state.match_active = True
    observer._ws_state.last_match_id = "match-1"

    observer._update_ws_state(
        "match_end_gameshot_match",
        "autodarts.matches.match-1.game-events",
        {"event": "game_shot", "body": {"type": "match"}},
        '{"event":"game_shot"}',
    )

    assert observer._ws_state.finish_pending is True
    assert observer._ws_state.match_finished is False
    assert observer._ws_state.pending_finish_trigger == "match_end_gameshot_match"
    assert scheduled == []


def test_confirmed_finish_upgrades_pending_signal(observer, monkeypatch):
    scheduled = []
    monkeypatch.setattr(observer, "_schedule_immediate_finalize", lambda trigger, match_id: scheduled.append((trigger, match_id)))
    monkeypatch.setattr(observer, "_schedule_finalize_safety", lambda trigger, match_id: scheduled.append((f"safety:{trigger}", match_id)))

    observer._ws_state.match_active = True
    observer._ws_state.last_match_id = "match-2"
    observer._ws_state.finish_pending = True
    observer._ws_state.pending_finish_trigger = "match_end_gameshot_match"

    observer._update_ws_state(
        "match_end_state_finished",
        "autodarts.matches.match-2.state",
        {"finished": True},
        '{"finished":true}',
    )

    assert observer._ws_state.match_finished is True
    assert observer._ws_state.finish_pending is False
    assert observer._ws_state.finish_trigger == "match_end_state_finished"
    assert scheduled == [
        ("match_end_state_finished", "match-2"),
        ("safety:match_end_state_finished", "match-2"),
    ]


def test_unqualified_delete_is_diagnostic_only(observer):
    observer._ws_state.match_active = True
    observer._ws_state.last_match_id = "match-3"

    observer._update_ws_state(
        "match_reset_delete",
        "system.notifications.global",
        {"event": "delete"},
        '{"event":"delete"}',
    )

    assert observer._ws_state.match_active is True
    assert observer._abort_detected is False
    assert observer._ws_state.finish_trigger is None


def test_console_and_dom_finish_hints_stay_non_authoritative(observer):
    observer._stable_state = ObserverState.IN_GAME
    merged = observer._merge_detection(None, ObserverState.FINISHED, ObserverState.FINISHED)

    assert merged == ObserverState.IDLE
    assert observer.export_trigger_policy()["allow_console_finish_authority"] is False
    assert observer.export_trigger_policy()["allow_dom_finish_authority"] is False


def test_sanitize_trigger_policy_locks_delete_channels_and_keeps_known_groups():
    sanitized = sanitize_trigger_policy_config(
        {
            "authoritative_start": ["match_start_throw"],
            "authoritative_finish": ["match_end_state_finished"],
            "authoritative_abort": ["match_abort_delete"],
            "assistive_finish": ["match_end_gameshot_match"],
            "diagnostic_interpretations": ["match_other", "match_reset_delete"],
            "delete_channel_prefixes": ["unsafe.channel."],
            "delete_channel_suffixes": [".raw"],
            "allow_console_finish_authority": True,
        }
    )

    assert sanitized["delete_channel_prefixes"] == ["autodarts.matches.", "autodarts.boards."]
    assert sanitized["delete_channel_suffixes"] == [".state", ".matches", ".game-events"]
    assert sanitized["allow_console_finish_authority"] is True
    assert sanitized["authoritative_abort"] == ["match_abort_delete"]


def test_sanitize_trigger_policy_rejects_unknown_interpretations():
    with pytest.raises(ValueError, match="Unknown trigger interpretations"):
        sanitize_trigger_policy_config(
            {
                "authoritative_start": ["match_start_throw", "totally_new_signal"],
            }
        )


def test_trigger_policy_metadata_exposes_presets_and_catalog():
    metadata = export_trigger_policy_metadata()

    assert {preset["id"] for preset in metadata["presets"]} == {"strict_ws", "console_recovery", "dom_last_resort"}
    assert any(item["interpretation"] == "match_start_throw" for item in metadata["signal_catalog"])
    assert metadata["locked_fields"]["delete_channel_prefixes"] == ["autodarts.matches.", "autodarts.boards."]


def test_payload_player_snapshot_extracts_players_from_match_payload(observer):
    count, players = observer._payload_player_snapshot(
        {
            "data": {
                "match": {
                    "players": [
                        {"id": "p1", "nickname": "Alice"},
                        {"id": "p2", "nickname": "Bob"},
                        {"id": "p3", "nickname": "Cara"},
                    ]
                }
            }
        }
    )

    assert count == 3
    assert players == ["Alice", "Bob", "Cara"]


def test_payload_player_snapshot_extracts_players_from_team_lobby_payload(observer):
    count, players = observer._payload_player_snapshot(
        {
            "lobby": {
                "teams": [
                    {"players": [{"user": {"id": "u1", "nickname": "Alice"}}]},
                    {"players": [{"user": {"id": "u2", "nickname": "Bob"}}, {"user": {"id": "u3", "nickname": "Cara"}}]},
                ]
            }
        }
    )

    assert count == 3
    assert players == ["Alice", "Bob", "Cara"]
