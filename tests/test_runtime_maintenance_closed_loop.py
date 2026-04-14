from __future__ import annotations

import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "release" / "runtime_windows" / "runtime_maintenance.py"
SPEC = importlib.util.spec_from_file_location("runtime_maintenance", MODULE_PATH)
runtime_maintenance = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = runtime_maintenance
SPEC.loader.exec_module(runtime_maintenance)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_runtime_root(root: Path, version: str = "4.4.3") -> None:
    for rel in [
        "app/backend/.env",
        "app/frontend/build/index.html",
        "app/agent/darts_agent.py",
        "app/bin/runtime_maintenance.py",
        "config/backend.env.example",
        "config/frontend.env.example",
        "data/.keep",
    ]:
        _write(root / rel)
    _write(root / "config/VERSION", version)


def _build_runtime_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("darts-kiosk-v4.4.4-windows-runtime/app/backend/server.py", "print('ok')\n")
        zf.writestr("darts-kiosk-v4.4.4-windows-runtime/app/frontend/build/index.html", "<html></html>\n")
        zf.writestr("darts-kiosk-v4.4.4-windows-runtime/app/agent/darts_agent.py", "print('agent')\n")
        zf.writestr("darts-kiosk-v4.4.4-windows-runtime/app/bin/run_backend.py", "print('bin')\n")


def test_prepare_closed_loop_rehearsal_writes_update_and_rollback_manifests(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    zip_path = tmp_path / "runtime-update.zip"
    _build_runtime_zip(zip_path)

    result = runtime_maintenance.prepare_closed_loop_rehearsal(
        root=root,
        runtime_zip=zip_path,
        target_version="4.4.4",
    )

    assert result["backup"]["files_written"] > 0
    assert result["stage"]["missing_app_entries"] == []
    assert Path(result["update_manifest_path"]).exists()
    assert Path(result["rollback_manifest_path"]).exists()
    assert result["update_validation"]["action"] == "install_update"
    assert result["rollback_validation"]["action"] == "rollback"
    assert result["rollback_validation"]["backup_payload"]["missing_app_entries"] == []
    assert all(item["ok"] for item in result["rehearsal"]["checklist"])

    update_manifest = json.loads(Path(result["update_manifest_path"]).read_text(encoding="utf-8"))
    rollback_manifest = json.loads(Path(result["rollback_manifest_path"]).read_text(encoding="utf-8"))
    assert update_manifest["backup_path"] == rollback_manifest["backup_path"]
    assert rollback_manifest["action"] == "rollback"


def test_validate_update_payload_rejects_non_app_only_rollback_backup(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    bad_backup = root / "data" / "app_backups" / "bad.zip"
    bad_backup.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bad_backup, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config/backend.env.example", "nope\n")
        zf.writestr("app/backend/server.py", "print('ok')\n")

    manifest = runtime_maintenance.build_runtime_rollback_manifest(root=root, backup_path=bad_backup)
    manifest_path = root / "data" / "update_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    validation = runtime_maintenance.validate_update_payload(root, manifest_path)

    assert validation["action"] == "rollback"
    assert validation["backup_exists"] is True
    assert validation["backup_payload"]["unexpected_top_level"] == ["config"]
    assert "app/frontend/build" in validation["backup_payload"]["missing_app_entries"]


def test_paired_summary_can_live_inside_wave13_drill_folder(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    workspace = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")

    update_leg_path = Path(workspace["workspace"]["update_leg_summary"])
    rollback_leg_path = Path(workspace["workspace"]["rollback_leg_summary"])
    update_leg_path.write_text(json.dumps({
        "label": "board-pc-drill",
        "leg": "update",
        "summary_path": str(update_leg_path),
        "comparison": {"before_version": "4.4.3", "after_version": "4.4.4", "updater_manifest_action_after": "install_update", "updater_exit_code_after": 0},
        "status": {"passed": True, "checks": [{"name": "ok", "ok": True}]},
    }, indent=2) + "\n", encoding="utf-8")
    rollback_leg_path.write_text(json.dumps({
        "label": "board-pc-drill",
        "leg": "rollback",
        "summary_path": str(rollback_leg_path),
        "comparison": {"before_version": "4.4.4", "after_version": "4.4.3", "updater_manifest_action_after": "rollback", "updater_exit_code_after": 0},
        "status": {"passed": True, "checks": [{"name": "ok", "ok": True}]},
    }, indent=2) + "\n", encoding="utf-8")

    paired = runtime_maintenance.build_paired_drill_summary(
        root,
        update_leg_path=update_leg_path,
        rollback_leg_path=rollback_leg_path,
        label="board-pc-drill",
        summary_json_path=Path(workspace["workspace"]["paired_summary_json"]),
        summary_md_path=Path(workspace["workspace"]["paired_summary_md"]),
    )
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")
    bundle = runtime_maintenance.build_support_bundle(
        root,
        label="board-pc-drill",
        bundle_path=Path(workspace["workspace"]["paired_bundle"]),
        before=Path(workspace["workspace"]["update_before"]),
        after=Path(workspace["workspace"]["rollback_after"]),
        report=Path(workspace["workspace"]["paired_summary_md"]),
    )

    assert paired["closed_loop_passed"] is True
    assert Path(paired["summary_json_path"]).exists()
    assert Path(paired["summary_md_path"]).exists()
    assert Path(bundle["bundle_path"]).exists()
    with zipfile.ZipFile(bundle["bundle_path"]) as zf:
        names = set(zf.namelist())
        assert "support/drills/board-pc-drill/DRILL_CHECKLIST.md" in names
        assert "support/drills/board-pc-drill/DRILL_HANDOFF.json" in names
        assert "support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt" in names
        assert "support/drills/board-pc-drill/DRILL_TICKET_COMMENT.md" in names
        assert "support/drills/board-pc-drill/ATTACHMENT_READINESS_REVIEW.json" in names
        assert "support/drills/board-pc-drill/ATTACHMENT_READINESS_REVIEW.txt" in names


def _mark_complete_drill_workspace(workspace: dict[str, str]) -> None:
    for key in [
        "update_before",
        "update_after",
        "update_report",
        "update_leg_summary",
        "update_bundle",
        "rollback_before",
        "rollback_after",
        "rollback_report",
        "rollback_leg_summary",
        "rollback_bundle",
        "paired_summary_json",
        "paired_summary_md",
        "paired_bundle",
    ]:
        path = Path(workspace[key])
        if key in {"update_leg_summary", "rollback_leg_summary"}:
            _write(path, json.dumps({"status": {"passed": True}}))
        elif key == "paired_summary_json":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "closed_loop_passed": True,
                "rollback_restored_start_version": True,
            }, indent=2) + "\n", encoding="utf-8")
        else:
            _write(path, "ok")


def test_refresh_drill_workspace_downgrades_stale_closed_loop_to_manual_review(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)

    stale_epoch = Path(workspace["paired_summary_json"]).stat().st_mtime - ((runtime_maintenance.FRESHNESS_STALE_HOURS + 2) * 3600)
    for key in ["paired_summary_json", "paired_summary_md", "paired_bundle"]:
        os.utime(Path(workspace[key]), (stale_epoch, stale_epoch))

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    assert handoff["complete"] is True
    assert handoff["freshness"]["ok"] is False
    assert handoff["recommendation"]["status"] == "needs_manual_review"
    assert any("paired_summary_json is older than" in reason for reason in handoff["recommendation"]["reasons"])


def test_refresh_drill_workspace_flags_misaligned_paired_bundle_timestamp(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)

    paired_summary = Path(workspace["paired_summary_json"])
    paired_bundle = Path(workspace["paired_bundle"])
    older = paired_summary.stat().st_mtime - 120
    os.utime(paired_bundle, (older, older))

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    assert handoff["freshness"]["ok"] is False
    assert "paired bundle predates paired summary" in handoff["freshness"]["warnings"]
    assert handoff["recommendation"]["status"] == "needs_manual_review"


def test_refresh_drill_workspace_emits_ticket_comment_exports(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
    )
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    txt_path = Path(handoff["support_exports"]["ticket_comment_txt"])
    md_path = Path(handoff["support_exports"]["ticket_comment_md"])
    json_path = Path(handoff["support_exports"]["ticket_comment_json"])

    assert txt_path.exists()
    assert md_path.exists()
    assert json_path.exists()
    assert "TICKET-2048" in txt_path.read_text(encoding="utf-8")
    assert "paired_bundle" in txt_path.read_text(encoding="utf-8")
    ticket_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert ticket_json["recommendation"]["status"] == "ship"
    assert ticket_json["drill_context"]["device_id"] == "BOARD-17"
    assert any(item["key"] == "paired_bundle" for item in ticket_json["attachments"])
    assert ticket_json["attachment_readiness"]["ready_to_attach"] is True
    assert any(item["key"] == "handoff_manifest_md" for item in ticket_json["attachment_readiness"]["attach_now"])
    assert ticket_json["attachment_readiness"]["missing_required"] == []


def test_finalize_drill_handoff_refreshes_final_artifacts_and_paths(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
    )
    workspace = payload["workspace"]

    update_leg_path = Path(workspace["update_leg_summary"])
    rollback_leg_path = Path(workspace["rollback_leg_summary"])
    update_leg_path.write_text(json.dumps({
        "label": "board-pc-drill",
        "leg": "update",
        "summary_path": str(update_leg_path),
        "comparison": {"before_version": "4.4.3", "after_version": "4.4.4", "updater_manifest_action_after": "install_update", "updater_exit_code_after": 0},
        "status": {"passed": True, "checks": [{"name": "ok", "ok": True}]},
    }, indent=2) + "\n", encoding="utf-8")
    rollback_leg_path.write_text(json.dumps({
        "label": "board-pc-drill",
        "leg": "rollback",
        "summary_path": str(rollback_leg_path),
        "comparison": {"before_version": "4.4.4", "after_version": "4.4.3", "updater_manifest_action_after": "rollback", "updater_exit_code_after": 0},
        "status": {"passed": True, "checks": [{"name": "ok", "ok": True}]},
    }, indent=2) + "\n", encoding="utf-8")

    for key, content in {
        "update_before": json.dumps({"ok": True}),
        "update_after": json.dumps({"ok": True}),
        "update_report": "update report",
        "update_bundle": "bundle",
        "rollback_before": json.dumps({"ok": True}),
        "rollback_after": json.dumps({"ok": True}),
        "rollback_report": "rollback report",
        "rollback_bundle": "bundle",
    }.items():
        _write(Path(workspace[key]), content)

    older = min(Path(workspace["update_leg_summary"]).stat().st_mtime, Path(workspace["rollback_leg_summary"]).stat().st_mtime) - 2
    os.utime(Path(workspace["update_after"]), (older, older))
    os.utime(Path(workspace["rollback_after"]), (older, older))

    result = runtime_maintenance.finalize_drill_handoff(
        root,
        label="board-pc-drill",
        notes="Rollback looked clean; launcher reopened without operator intervention.",
    )

    assert result["handoff"]["recommendation"]["status"] == "ship"
    assert Path(result["paths"]["paired_summary_json"]).exists()
    assert Path(result["paths"]["paired_bundle"]).exists()
    assert Path(result["paths"]["handoff_md"]).exists()
    assert Path(result["paths"]["ticket_comment_txt"]).exists()
    ticket_text = Path(result["paths"]["ticket_comment_txt"]).read_text(encoding="utf-8")
    handoff_md = Path(result["paths"]["handoff_md"]).read_text(encoding="utf-8")
    assert "TICKET-2048" in ticket_text
    assert "operator_notes:" in ticket_text
    assert "launcher reopened without operator intervention" in ticket_text
    assert "Operator notes:" in handoff_md
    checklist = json.loads((Path(workspace["base"]) / "drill-checklist.json").read_text(encoding="utf-8"))
    assert checklist["drill_context"]["notes"].startswith("Rollback looked clean")
    assert result["handoff"]["attachment_readiness"]["ready_to_attach"] is True


def test_refresh_drill_workspace_marks_missing_required_attachments_before_ship(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)

    Path(workspace["paired_bundle"]).unlink()

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    assert handoff["attachment_readiness"]["ready_to_attach"] is False
    assert any(item["key"] == "paired_bundle" for item in handoff["attachment_readiness"]["missing_required"])
    ticket_comment = json.loads((Path(workspace["base"]) / "DRILL_TICKET_COMMENT.json").read_text(encoding="utf-8"))
    assert any(item["key"] == "paired_bundle" for item in ticket_comment["attachment_readiness"]["missing_required"])


def test_acknowledge_drill_handoff_persists_post_attach_metadata(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
    )
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    result = runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        ticket_status="attachments_uploaded",
        ticket_reference="TICKET-2048",
        ticket_url="https://tickets.example/TICKET-2048",
        note="Paired bundle and handoff attached to ticket.",
    )

    assert result["ticket_acknowledgment"]["acknowledged"] is True
    assert result["handoff"]["attachment_readiness"]["acknowledged"] is True
    assert result["handoff"]["attachment_readiness"]["acknowledgment_current"] is True
    assert result["handoff"]["ticket_acknowledgment"]["attached_by"] == "orri"
    assert result["handoff"]["ticket_acknowledgment"]["ticket_reference"] == "TICKET-2048"
    ticket_comment = json.loads((Path(workspace["base"]) / "DRILL_TICKET_COMMENT.json").read_text(encoding="utf-8"))
    attachment_review = json.loads((Path(workspace["base"]) / "ATTACHMENT_READINESS_REVIEW.json").read_text(encoding="utf-8"))
    assert ticket_comment["attachment_readiness"]["acknowledged"] is True
    assert ticket_comment["attachment_readiness"]["acknowledgment_current"] is True
    assert ticket_comment["attachment_readiness"]["ticket_acknowledgment"]["ticket_status"] == "attachments_uploaded"
    assert ticket_comment["attachment_readiness"]["ticket_acknowledgment"]["ticket_url"] == "https://tickets.example/TICKET-2048"
    destination_summary = ticket_comment["attachment_readiness"]["destination_summary"]
    assert destination_summary["kind"] == "reference_and_url"
    assert destination_summary["stored_destination_ready"] is True
    assert destination_summary["verdict"] == "stored_destination_ready"
    assert "direct re-acknowledge reuse" in destination_summary["verdict_text"]
    assert destination_summary["display"] == "TICKET-2048 | https://tickets.example/TICKET-2048"
    action_verdict = ticket_comment["attachment_readiness"]["action_verdict"]
    assert action_verdict["verdict"] == "current_no_action"
    assert "no re-attach is needed" in action_verdict["summary"]
    fingerprint_summary = ticket_comment["attachment_readiness"]["fingerprint_summary"]
    assert fingerprint_summary["snapshot_available"] is True
    assert fingerprint_summary["matches_current_acknowledgment"] is True
    assert fingerprint_summary["verdict"] == "match"
    assert "matches the current paired files" in fingerprint_summary["verdict_text"]
    assert fingerprint_summary["mismatch_summary"] == "All acknowledged paired artifact fingerprints still match the current files."
    assert {item["key"] for item in fingerprint_summary["current"]["items"]} == {"paired_bundle", "paired_summary_json", "paired_summary_md"}
    timeline = ticket_comment["attachment_readiness"]["attachment_timeline"]
    assert timeline["verdict"] == "current_after_ack"
    assert "still current" in timeline["summary"]
    assert timeline["attached_at"]
    assert timeline["paired_summary_built_at"]
    assert timeline["paired_bundle_built_at"]
    assert timeline["latest_regenerated_at"]
    assert ticket_comment["attachment_readiness"]["ticket_acknowledgment"]["paired_artifact_snapshot"]["items"]
    assert [item["key"] for item in ticket_comment["attachment_readiness"]["attach_now_minimal"]] == ["paired_bundle", "handoff_manifest_md"]
    assert attachment_review["contract"]["schema"] == "runtime_attachment_review_v1"
    assert attachment_review["contract"]["detail_level"] == "reviewer_safe"
    assert attachment_review["attachment_readiness"]["action_verdict"]["verdict"] == "current_no_action"
    assert attachment_review["attachment_timeline"]["verdict"] == "current_after_ack"
    assert attachment_review["acknowledgment_history"]["count"] == 1
    assert attachment_review["acknowledgment_history"]["reacknowledge_count"] == 0
    assert attachment_review["acknowledgment_history"]["same_destination_reuse_count"] == 0
    assert attachment_review["acknowledgment_history"]["destination_relation_counts"]["initial_acknowledgment"] == 1
    assert attachment_review["acknowledgment_history"]["latest_event"] == "acknowledge"
    assert attachment_review["acknowledgment_history"]["latest_destination_relation"] == "initial_acknowledgment"
    assert "first visible ticket destination state" in attachment_review["acknowledgment_history"]["latest_destination_relation_summary"]
    assert attachment_review["acknowledgment_history"]["destination_history_pattern"]["verdict"] == "no_destination_change_recorded"
    assert attachment_review["review_json_path"].endswith("ATTACHMENT_READINESS_REVIEW.json")
    assert attachment_review["review_txt_path"].endswith("ATTACHMENT_READINESS_REVIEW.txt")
    attachment_review_txt = Path(result["paths"]["attachment_review_txt"]).read_text(encoding="utf-8")
    assert "Runtime attachment review: board-pc-drill" in attachment_review_txt
    assert "same_destination_reuse_count: 0" in attachment_review_txt
    assert "destination_history_pattern: no_destination_change_recorded" in attachment_review_txt
    ticket_comment_txt = Path(result["paths"]["ticket_comment_txt"]).read_text(encoding="utf-8")
    assert "attachment_acknowledged: True" in ticket_comment_txt
    assert "current: True" in ticket_comment_txt
    assert "acknowledgment_history_count: 1" in ticket_comment_txt
    assert "reacknowledgment_count: 0" in ticket_comment_txt
    assert "acknowledgment_history_summary:" in ticket_comment_txt
    assert "- latest_event: acknowledge" in ticket_comment_txt
    assert "- latest_destination_relation: initial_acknowledgment" in ticket_comment_txt
    assert "ticket_reference: TICKET-2048" in ticket_comment_txt
    assert "ticket_destination_summary:" in ticket_comment_txt
    assert "attachment_action_verdict:" in ticket_comment_txt
    assert "- status: current_no_action" in ticket_comment_txt
    assert "- status: stored_destination_ready" in ticket_comment_txt
    assert "- destination_display: TICKET-2048 | https://tickets.example/TICKET-2048" in ticket_comment_txt
    assert "attachment_fingerprint_verdict:" in ticket_comment_txt
    assert "- status: match" in ticket_comment_txt
    assert "attachment_timeline_summary:" in ticket_comment_txt
    assert "- status: current_after_ack" in ticket_comment_txt
    assert "attach_now_minimal:" in ticket_comment_txt
    assert "attachment_fingerprints_current:" in ticket_comment_txt
    assert "attachment_fingerprints_acknowledged:" in ticket_comment_txt
    handoff_md = Path(result["paths"]["handoff_md"]).read_text(encoding="utf-8")
    assert "Ticket destination: `TICKET-2048 | https://tickets.example/TICKET-2048`" in handoff_md
    assert "Ticket destination status: `stored_destination_ready`" in handoff_md
    assert "Acknowledgment history count: `1`" in handoff_md
    assert "Acknowledgment history summary: `1 acknowledgment event(s) recorded; latest event=acknowledge; destination relation=initial_acknowledgment; latest change=n/a`" in handoff_md
    assert "Latest destination relation: `initial_acknowledgment`" in handoff_md
    assert "Attachment action verdict: `current_no_action`" in handoff_md
    assert "Ticket destination summary: `reference_and_url`" in handoff_md
    assert "Attached by: `orri`" in handoff_md
    assert "Fingerprint verdict: `match`" in handoff_md
    assert "Attachment timeline: `current_after_ack`" in handoff_md
    assert "Attachment timeline points:" in handoff_md
    assert "Attach now (minimal):" in handoff_md
    assert "Current paired fingerprints:" in handoff_md
    assert "Acknowledged paired fingerprints:" in handoff_md


def test_acknowledgment_warns_when_paired_artifacts_change_after_upload(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
    )
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        attached_at="2026-04-14T00:00:00+00:00",
        ticket_status="attachments_uploaded",
        note="Initial upload done.",
    )

    for key in ["paired_bundle", "paired_summary_json", "paired_summary_md"]:
        path = Path(workspace[key])
        future_epoch = runtime_maintenance.parse_iso8601("2026-04-14T01:00:00+00:00").timestamp()
        os.utime(path, (future_epoch, future_epoch))

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    assert handoff["attachment_readiness"]["acknowledged"] is True
    assert handoff["attachment_readiness"]["acknowledgment_current"] is False
    assert handoff["attachment_readiness"]["reattach_required"] is True
    drift = handoff["attachment_readiness"]["acknowledgment_drift"]
    assert drift["stale_after_regeneration"] is True
    assert drift["drift_verdict"] == "timestamp_only"
    assert "timestamps changed after upload, but fingerprints still match" in drift["drift_summary"]
    assert {item["key"] for item in drift["changed_after_ack"]} == {"paired_bundle", "paired_summary_json", "paired_summary_md"}
    assert {item["drift_kind"] for item in drift["changed_after_ack"]} == {"timestamp_only"}
    assert any("ticket acknowledgment predates regenerated paired artifacts" in warning for warning in drift["warnings"])
    assert any("timestamp-only drift detected" in warning for warning in drift["warnings"])
    timeline = handoff["attachment_readiness"]["attachment_timeline"]
    assert timeline["verdict"] == "regenerated_after_ack"
    assert "regenerated after the recorded upload acknowledgment" in timeline["summary"]
    assert timeline["summary_after_attach"]
    assert timeline["seconds_between_attach_and_latest_regeneration"] == 3600
    assert {item["key"] for item in handoff["attachment_readiness"]["reattach_targets"]} == {"paired_bundle", "handoff_manifest_md", "paired_summary_md", "paired_summary_json"}

    ticket_comment = json.loads((Path(workspace["base"]) / "DRILL_TICKET_COMMENT.json").read_text(encoding="utf-8"))
    assert ticket_comment["attachment_readiness"]["acknowledgment_current"] is False
    assert ticket_comment["attachment_readiness"]["acknowledgment_drift"]["stale_after_regeneration"] is True
    assert ticket_comment["attachment_readiness"]["reattach_required"] is True
    assert ticket_comment["attachment_readiness"]["reacknowledge_destination_ready"] is False
    assert ticket_comment["attachment_readiness"]["acknowledgment_drift"]["drift_verdict"] == "timestamp_only"
    destination_summary = ticket_comment["attachment_readiness"]["destination_summary"]
    assert destination_summary["kind"] == "none"
    assert destination_summary["stored_destination_ready"] is False
    assert destination_summary["verdict"] == "destination_missing_for_reattach"
    assert "Re-attach is required" in destination_summary["verdict_text"]
    action_verdict = ticket_comment["attachment_readiness"]["action_verdict"]
    assert action_verdict["verdict"] == "reattach_and_reack_with_destination"
    assert "ticket reference or URL" in action_verdict["summary"]
    assert ticket_comment["attachment_readiness"]["reacknowledge_command"] == "app\\bin\\reacknowledge_drill_handoff.bat board-pc-drill"
    assert ticket_comment["attachment_readiness"]["reacknowledge_blocked_reason"] == "Stored ticket destination missing; re-acknowledge needs ticket reference or ticket URL."
    assert ticket_comment["attachment_readiness"]["reacknowledge_command_with_destination"] == "app\\bin\\reacknowledge_drill_handoff.bat board-pc-drill [attached-by] [ticket-status] [note] [ticket-reference] [ticket-url]"
    fingerprint_summary = ticket_comment["attachment_readiness"]["fingerprint_summary"]
    assert fingerprint_summary["snapshot_available"] is True
    assert fingerprint_summary["matches_current_acknowledgment"] is True
    assert fingerprint_summary["verdict"] == "match"
    assert "still match the current files" in fingerprint_summary["mismatch_summary"]
    assert fingerprint_summary["mismatch_keys"] == []
    assert fingerprint_summary["mismatches"] == []
    handoff_md = Path(workspace["base"]) / "DRILL_HANDOFF.md"
    handoff_text = handoff_md.read_text(encoding="utf-8")
    assert "Acknowledgment current: `no`" in handoff_text
    assert "Ticket destination status: `destination_missing_for_reattach`" in handoff_text
    assert "Attachment action summary: `reattach_and_reack_with_destination`" in handoff_text
    assert "Ticket destination summary: `none` — Re-attach is required, but no reusable ticket destination is stored yet." in handoff_text
    assert "Fingerprint verdict: `match`" in handoff_text
    assert "Fingerprint diff: All acknowledged paired artifact fingerprints still match the current files." in handoff_text
    assert "Acknowledgment drift summary: `timestamp_only`" in handoff_text
    assert "Attachment timeline: `regenerated_after_ack`" in handoff_text
    assert "Attachment timing note: latest paired regeneration happened 3600 seconds after the recorded upload acknowledgment" in handoff_text
    assert "Re-acknowledge blocked: Stored ticket destination missing; re-acknowledge needs ticket reference or ticket URL." in handoff_text
    assert "Re-acknowledge with destination: `app\\bin\\reacknowledge_drill_handoff.bat board-pc-drill [attached-by] [ticket-status] [note] [ticket-reference] [ticket-url]`" in handoff_text
    assert "Attach now (minimal):" in handoff_text


def test_acknowledgment_drift_distinguishes_real_fingerprint_change(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        attached_at="2026-04-14T00:00:00+00:00",
        ticket_status="attachments_uploaded",
        ticket_reference="TICKET-2048",
    )

    Path(workspace["paired_summary_json"]).write_text(json.dumps({"closed_loop_passed": False}, indent=2) + "\n", encoding="utf-8")
    future_epoch = runtime_maintenance.parse_iso8601("2026-04-14T01:00:00+00:00").timestamp()
    os.utime(Path(workspace["paired_summary_json"]), (future_epoch, future_epoch))

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")
    drift = handoff["attachment_readiness"]["acknowledgment_drift"]

    assert drift["stale_after_regeneration"] is True
    assert drift["drift_verdict"] == "fingerprint_changed"
    assert drift["fingerprint_changed_keys"] == ["paired_summary_json"]
    assert any(item["drift_kind"] == "fingerprint_changed" for item in drift["changed_after_ack"])
    assert any("fingerprint/content drift detected" in warning for warning in drift["warnings"])
    assert "acknowledged fingerprint snapshot" in drift["drift_summary"]


def test_reacknowledge_drill_handoff_reuses_stored_ticket_destination(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
    )
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        attached_at="2026-04-14T00:00:00+00:00",
        ticket_status="attachments_uploaded",
        ticket_reference="TICKET-2048",
        ticket_url="https://tickets.example/TICKET-2048",
        note="Initial upload done.",
    )

    for key in ["paired_bundle", "paired_summary_json", "paired_summary_md"]:
        path = Path(workspace[key])
        future_epoch = runtime_maintenance.parse_iso8601("2026-04-14T01:00:00+00:00").timestamp()
        os.utime(path, (future_epoch, future_epoch))

    result = runtime_maintenance.reacknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="field-tech",
        attached_at="2026-04-14T02:00:00+00:00",
        note="Re-attached refreshed paired artifacts.",
    )

    assert result["ticket_acknowledgment"]["attached_by"] == "field-tech"
    assert result["ticket_acknowledgment"]["ticket_reference"] == "TICKET-2048"
    assert result["ticket_acknowledgment"]["ticket_url"] == "https://tickets.example/TICKET-2048"
    assert result["ticket_acknowledgment"]["ticket_status"] == "attachments_uploaded"
    assert len(result["ticket_acknowledgment_history"]) == 2
    assert result["ticket_acknowledgment_history"][0]["event"] == "acknowledge"
    assert result["ticket_acknowledgment_history"][1]["event"] == "reacknowledge"
    assert result["ticket_acknowledgment_history"][1]["change_summary"] == "attached_by orri -> field-tech"
    assert result["handoff"]["attachment_readiness"]["acknowledgment_current"] is True
    assert result["handoff"]["attachment_readiness"]["reattach_required"] is False
    assert result["handoff"]["attachment_readiness"]["reacknowledge_destination_ready"] is True
    assert result["handoff"]["attachment_readiness"]["destination_summary"]["verdict"] == "stored_destination_ready"
    ticket_comment = json.loads((Path(workspace["base"]) / "DRILL_TICKET_COMMENT.json").read_text(encoding="utf-8"))
    assert ticket_comment["attachment_readiness"]["ticket_acknowledgment"]["ticket_reference"] == "TICKET-2048"
    assert ticket_comment["attachment_readiness"]["acknowledgment_current"] is True
    assert ticket_comment["acknowledgment_history"]["count"] == 2
    assert ticket_comment["acknowledgment_history"]["reacknowledge_count"] == 1
    assert ticket_comment["acknowledgment_history"]["destination_change_count"] == 0
    assert ticket_comment["acknowledgment_history"]["latest_event"] == "reacknowledge"
    assert ticket_comment["acknowledgment_history"]["latest_change_summary"] == "attached_by orri -> field-tech"
    assert ticket_comment["acknowledgment_history"]["latest_destination_relation"] == "same_destination_reused"
    assert "reused the same stored ticket destination" in ticket_comment["acknowledgment_history"]["latest_destination_relation_summary"]
    assert ticket_comment["acknowledgment_history"]["destination_history_pattern"]["verdict"] == "same_destination_reuse_only"
    attachment_review = json.loads((Path(workspace["base"]) / "ATTACHMENT_READINESS_REVIEW.json").read_text(encoding="utf-8"))
    assert attachment_review["acknowledgment_history"]["count"] == 2
    assert attachment_review["acknowledgment_history"]["reacknowledge_count"] == 1
    assert attachment_review["acknowledgment_history"]["destination_change_count"] == 0
    assert attachment_review["acknowledgment_history"]["same_destination_reuse_count"] == 1
    assert attachment_review["acknowledgment_history"]["latest_event"] == "reacknowledge"
    assert attachment_review["acknowledgment_history"]["latest_change_summary"] == "attached_by orri -> field-tech"
    assert attachment_review["acknowledgment_history"]["latest_destination_relation"] == "same_destination_reused"
    assert attachment_review["acknowledgment_history"]["destination_history_pattern"]["verdict"] == "same_destination_reuse_only"


def test_reacknowledge_records_destination_change_summary_when_ticket_target_changes(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        attached_at="2026-04-14T00:00:00+00:00",
        ticket_status="attachments_uploaded",
        ticket_reference="TICKET-2048",
        ticket_url="https://tickets.example/TICKET-2048",
    )

    for key in ["paired_bundle", "paired_summary_json", "paired_summary_md"]:
        path = Path(workspace[key])
        future_epoch = runtime_maintenance.parse_iso8601("2026-04-14T01:00:00+00:00").timestamp()
        os.utime(path, (future_epoch, future_epoch))

    result = runtime_maintenance.reacknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_at="2026-04-14T02:00:00+00:00",
        ticket_reference="TICKET-3099",
        ticket_url="https://tickets.example/TICKET-3099",
        ticket_status="reuploaded_after_refresh",
    )

    latest = result["ticket_acknowledgment_history"][-1]
    assert latest["destination_changed"] is True
    assert latest["ticket_destination_display"] == "TICKET-3099 | https://tickets.example/TICKET-3099"
    assert latest["previous_ticket_destination_display"] == "TICKET-2048 | https://tickets.example/TICKET-2048"
    assert latest["change_summary"] == (
        "destination TICKET-2048 | https://tickets.example/TICKET-2048 -> TICKET-3099 | https://tickets.example/TICKET-3099; "
        "ticket_status attachments_uploaded -> reuploaded_after_refresh"
    )
    ticket_comment = json.loads((Path(workspace["base"]) / "DRILL_TICKET_COMMENT.json").read_text(encoding="utf-8"))
    assert ticket_comment["acknowledgment_history"]["destination_change_count"] == 1
    assert "destination TICKET-2048 | https://tickets.example/TICKET-2048 -> TICKET-3099 | https://tickets.example/TICKET-3099" in ticket_comment["plain_text"]
    attachment_review = json.loads((Path(workspace["base"]) / "ATTACHMENT_READINESS_REVIEW.json").read_text(encoding="utf-8"))
    assert attachment_review["acknowledgment_history"]["destination_change_count"] == 1
    assert attachment_review["acknowledgment_history"]["latest_change_summary"].startswith("destination TICKET-2048")
    assert attachment_review["acknowledgment_history"]["latest_destination_relation"] == "destination_changed"
    assert attachment_review["acknowledgment_history"]["destination_history_pattern"]["verdict"] == "latest_is_only_destination_change"
    assert "changed the ticket destination from TICKET-2048 | https://tickets.example/TICKET-2048 to TICKET-3099 | https://tickets.example/TICKET-3099" in attachment_review["acknowledgment_history"]["latest_destination_relation_summary"]


def test_acknowledgment_history_pattern_marks_latest_as_one_of_multiple_destination_changes(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        attached_at="2026-04-14T00:00:00+00:00",
        ticket_status="attachments_uploaded",
        ticket_reference="TICKET-2048",
        ticket_url="https://tickets.example/TICKET-2048",
    )

    for attached_at, ref in [
        ("2026-04-14T01:00:00+00:00", "TICKET-3099"),
        ("2026-04-14T02:00:00+00:00", "TICKET-4100"),
    ]:
        for key in ["paired_bundle", "paired_summary_json", "paired_summary_md"]:
            path = Path(workspace[key])
            future_epoch = runtime_maintenance.parse_iso8601(attached_at).timestamp() - 60
            os.utime(path, (future_epoch, future_epoch))
        runtime_maintenance.reacknowledge_drill_handoff(
            root,
            label="board-pc-drill",
            attached_at=attached_at,
            ticket_reference=ref,
            ticket_url=f"https://tickets.example/{ref}",
            ticket_status=f"reuploaded_{ref.lower()}",
        )

    attachment_review = json.loads((Path(workspace["base"]) / "ATTACHMENT_READINESS_REVIEW.json").read_text(encoding="utf-8"))
    ack_history = attachment_review["acknowledgment_history"]
    assert ack_history["destination_change_count"] == 2
    assert ack_history["latest_destination_relation"] == "destination_changed"
    assert ack_history["destination_history_pattern"]["verdict"] == "latest_is_one_of_multiple_destination_changes"
    assert "2 destination-change events" in ack_history["destination_history_pattern"]["summary"]
    attachment_review_txt = Path(workspace["attachment_review_txt"]).read_text(encoding="utf-8")
    assert "destination_history_pattern: latest_is_one_of_multiple_destination_changes" in attachment_review_txt


def test_reacknowledge_requires_existing_acknowledgment_and_ticket_destination(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    try:
        runtime_maintenance.reacknowledge_drill_handoff(root, label="board-pc-drill")
        assert False, "expected ValueError when no initial acknowledgment exists"
    except ValueError as exc:
        assert "initial acknowledgment" in str(exc)

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        ticket_status="attachments_uploaded",
    )
    try:
        runtime_maintenance.reacknowledge_drill_handoff(root, label="board-pc-drill")
        assert False, "expected ValueError when no stored destination exists"
    except ValueError as exc:
        assert "ticket reference/url" in str(exc)


def test_attachment_review_summary_surfaces_minimal_attach_and_reack_guidance(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        service_ticket="TICKET-2048",
    )
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    runtime_maintenance.acknowledge_drill_handoff(
        root,
        label="board-pc-drill",
        attached_by="orri",
        attached_at="2026-04-14T00:00:00+00:00",
        ticket_status="attachments_uploaded",
        ticket_reference="TICKET-2048",
        ticket_url="https://tickets.example/TICKET-2048",
    )

    for key in ["paired_bundle", "paired_summary_json", "paired_summary_md"]:
        path = Path(workspace[key])
        future_epoch = runtime_maintenance.parse_iso8601("2026-04-14T01:00:00+00:00").timestamp()
        os.utime(path, (future_epoch, future_epoch))

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")
    review = runtime_maintenance.build_attachment_review_summary(
        label="board-pc-drill",
        recommendation=handoff["recommendation"],
        freshness=handoff["freshness"],
        artifacts=handoff["artifacts"],
        ticket_acknowledgment=handoff["ticket_acknowledgment"],
    )
    persisted_review = json.loads((Path(workspace["base"]) / "ATTACHMENT_READINESS_REVIEW.json").read_text(encoding="utf-8"))

    assert review["next_operator_step"] == "Re-attach the refreshed paired artifacts, then run reacknowledge_drill_handoff.bat."
    assert review["destination_summary"]["verdict"] == "stored_destination_ready"
    assert review["attachment_readiness"]["action_verdict"]["verdict"] == "reattach_and_reack_same_destination"
    assert review["fingerprint_summary"]["verdict"] == "match"
    assert review["attachment_timeline"]["verdict"] == "regenerated_after_ack"
    assert review["attachment_readiness"]["acknowledgment_drift"]["drift_verdict"] == "timestamp_only"
    assert "drift_status: timestamp_only" in review["plain_text"]
    assert "action_verdict: reattach_and_reack_same_destination" in review["plain_text"]
    assert "timeline_status: regenerated_after_ack" in review["plain_text"]
    assert "attach_timing: latest paired regeneration happened 3600 seconds after the recorded upload acknowledgment" in review["plain_text"]
    assert "attach_now_minimal:" in review["plain_text"]
    assert "reattach_now:" in review["plain_text"]
    assert "reacknowledge_helper: app\\bin\\reacknowledge_drill_handoff.bat board-pc-drill" in review["plain_text"]
    assert persisted_review["attachment_readiness"]["action_verdict"]["verdict"] == "reattach_and_reack_same_destination"
    assert persisted_review["attachment_timeline"]["verdict"] == "regenerated_after_ack"
    assert persisted_review["review_json_path"].endswith("ATTACHMENT_READINESS_REVIEW.json")
    assert persisted_review["review_txt_path"].endswith("ATTACHMENT_READINESS_REVIEW.txt")
    persisted_review_txt = Path(workspace["attachment_review_txt"]).read_text(encoding="utf-8")
    assert "same_destination_reuse_count: 0" in persisted_review_txt
    assert "next_step: Re-attach the refreshed paired artifacts, then run reacknowledge_drill_handoff.bat." in persisted_review_txt


def test_attachment_review_summary_highlights_missing_required_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root)
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]
    _mark_complete_drill_workspace(workspace)
    Path(workspace["paired_bundle"]).unlink()

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")
    review = runtime_maintenance.build_attachment_review_summary(
        label="board-pc-drill",
        recommendation=handoff["recommendation"],
        freshness=handoff["freshness"],
        artifacts=handoff["artifacts"],
        ticket_acknowledgment=handoff["ticket_acknowledgment"],
    )

    assert review["attachment_readiness"]["ready_to_attach"] is False
    assert any(item["key"] == "paired_bundle" for item in review["attachment_readiness"]["missing_required"])
    assert review["next_operator_step"] == "Finish the missing required artifacts before shipping."
    assert review["attachment_readiness"]["action_verdict"]["verdict"] == "blocked_missing_required"
    assert review["fingerprint_summary"]["verdict"] == "no_acknowledgment_recorded"
    assert review["attachment_readiness"]["acknowledgment_drift"]["drift_verdict"] == "no_acknowledgment_recorded"
    assert "missing_before_ship:" in review["plain_text"]
