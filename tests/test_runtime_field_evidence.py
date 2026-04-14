from __future__ import annotations

import importlib.util
import json
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
    for rel, content in [
        ("app/backend/.env", "BOARD_ID=BOARD-1\n"),
        ("app/frontend/build/index.html", "<html></html>\n"),
        ("app/agent/darts_agent.py", "print('agent')\n"),
        ("app/bin/runtime_maintenance.py", "print('runtime')\n"),
        ("app/bin/VERSION", version),
        ("config/backend.env.example", "DATABASE_URL=sqlite:///./data/db/darts.sqlite\n"),
        ("config/frontend.env.example", "REACT_APP_BACKEND_URL=http://localhost:8001\n"),
        ("config/VERSION", version),
        ("data/logs/backend.log", "boot ok\n"),
        ("data/db/darts.sqlite", "db\n"),
    ]:
        _write(root / rel, content)


def test_capture_and_compare_field_state_detects_clean_versioned_update(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")
    before_path = root / "data" / "field_state_before.json"
    after_path = root / "data" / "field_state_after.json"
    report_path = root / "data" / "field_report.md"

    drill_context = runtime_maintenance.build_drill_context(
        label="update-to-4.4.4",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
        drill_phase="before",
    )
    before = runtime_maintenance.collect_runtime_boundary_state(root, drill_context=drill_context)
    runtime_maintenance.write_json(before_path, before)

    _write(root / "app/bin/VERSION", "4.4.4")
    _write(root / "config/VERSION", "4.4.4")
    _write(root / "data/logs/update.log", "updated\n")
    _write(root / "data/update_manifest.json", json.dumps({"action": "install_update", "target_version": "4.4.4"}))
    _write(root / "data/rollback_manifest.json", json.dumps({"action": "rollback", "backup_path": "data/app_backups/one.zip"}))

    after = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(
            label="update-to-4.4.4",
            device_id="BOARD-17",
            operator="orri",
            service_ticket="TICKET-2048",
            drill_phase="before",
        ),
    )
    runtime_maintenance.write_json(after_path, after)

    comparison = runtime_maintenance.compare_runtime_boundary_state(before, after)
    runtime_maintenance.write_field_report_markdown(report_path, before, after, comparison, "update-to-4.4.4")

    assert comparison["version_changed"] is True
    assert comparison["config_boundary_stable"] is True
    changed_paths = {item["path"] for item in comparison["config_hash_changes"]}
    assert "config/VERSION" in changed_paths
    assert "app/bin/VERSION" in changed_paths
    assert comparison["unexpected_config_hash_changes"] == []
    assert comparison["data_boundary_present_before_and_after"] is True
    assert comparison["logs_boundary_present_before_and_after"] is True
    assert comparison["update_manifest_action_after"] == "install_update"
    assert comparison["rollback_manifest_action_after"] == "rollback"
    assert comparison["drill_context_matches"] is True
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "Runtime Field Report — update-to-4.4.4" in report_text
    assert "Device Id: `BOARD-17`" in report_text
    assert "Service Ticket: `TICKET-2048`" in report_text


def test_compare_field_state_flags_unexpected_config_example_drift(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")

    before = runtime_maintenance.collect_runtime_boundary_state(root)
    _write(root / "config/backend.env.example", "DATABASE_URL=broken\n")
    after = runtime_maintenance.collect_runtime_boundary_state(root)

    comparison = runtime_maintenance.compare_runtime_boundary_state(before, after)

    assert comparison["config_boundary_stable"] is False
    changed_paths = {item["path"] for item in comparison["config_hash_changes"]}
    assert "config/backend.env.example" in changed_paths


def test_build_support_bundle_collects_field_artifacts_and_logs(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")

    before = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(
            label="update-to-4.4.4",
            device_id="BOARD-17",
            operator="orri",
            service_ticket="TICKET-2048",
            drill_phase="before",
        ),
    )
    runtime_maintenance.write_json(root / "data" / "field_state_before.json", before)
    _write(root / "app/bin/VERSION", "4.4.4")
    _write(root / "config/VERSION", "4.4.4")
    after = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(
            label="update-to-4.4.4",
            device_id="BOARD-17",
            operator="orri",
            service_ticket="TICKET-2048",
            drill_phase="after",
        ),
    )
    runtime_maintenance.write_json(root / "data" / "field_state_after.json", after)
    comparison = runtime_maintenance.compare_runtime_boundary_state(before, after)
    runtime_maintenance.write_field_report_markdown(root / "data" / "field_report.md", before, after, comparison, "update-to-4.4.4")
    _write(root / "data" / "update_manifest.json", json.dumps({"action": "install_update", "target_version": "4.4.4"}))
    _write(root / "data" / "rollback_manifest.json", json.dumps({"action": "rollback", "backup_path": "data/app_backups/one.zip"}))
    runtime_maintenance.record_updater_run(root, exit_code=0, notes="update ok")
    _write(root / "data" / "logs" / "update.log", "updated\n")

    result = runtime_maintenance.build_support_bundle(
        root,
        label="update-to-4.4.4",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
        drill_phase="after",
    )

    assert Path(result["bundle_path"]).exists()
    assert result["files_written"] >= 6
    archived = set()
    with zipfile.ZipFile(result["bundle_path"]) as zf:
        archived = set(zf.namelist())
        assert "bundle_summary.json" in archived
        assert "field_state_before.json" in archived
        assert "field_state_after.json" in archived
        assert "field_report.md" in archived
        assert "update_manifest.json" in archived
        assert "rollback_manifest.json" in archived
        assert "last_updater_run.json" in archived
        assert "logs/update.log" in archived
        summary = json.loads(zf.read("bundle_summary.json").decode("utf-8"))
        assert summary["drill_context"]["device_id"] == "BOARD-17"
        assert summary["drill_context"]["service_ticket"] == "TICKET-2048"


def test_record_updater_run_flows_into_field_state_and_report(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")
    _write(root / "data" / "update_manifest.json", json.dumps({"action": "rollback", "backup_path": "data/app_backups/one.zip"}))
    _write(root / "data" / "update_result.json", json.dumps({"status": "rolled_back"}))
    _write(root / "data" / "logs" / "updater.log", "rollback ok\n")

    record = runtime_maintenance.record_updater_run(root, exit_code=0, notes="rollback drill")
    assert Path(record["record_path"]).exists()

    before = runtime_maintenance.collect_runtime_boundary_state(root)
    _write(root / "config/VERSION", "4.4.4")
    after = runtime_maintenance.collect_runtime_boundary_state(root)
    comparison = runtime_maintenance.compare_runtime_boundary_state(before, after)
    report_path = root / "data" / "field_report.md"
    runtime_maintenance.write_field_report_markdown(report_path, before, after, comparison, "rollback-drill")

    assert after["updater_artifacts"]["manifest_action"] == "rollback"
    assert after["updater_artifacts"]["exit_code"] == 0
    assert comparison["updater_manifest_action_after"] == "rollback"
    assert comparison["updater_exit_code_after"] == 0
    report_text = report_path.read_text(encoding="utf-8")
    assert "updater manifest action: `rollback`" in report_text
    assert "updater exit code: `0`" in report_text


def test_build_drill_leg_and_paired_summary_close_the_loop(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")

    update_before = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(label="board-pc-drill", device_id="BOARD-17", operator="orri", service_ticket="TICKET-2048", drill_phase="before"),
    )
    runtime_maintenance.write_json(root / "data" / "field_state_before.json", update_before)
    _write(root / "app/bin/VERSION", "4.4.4")
    _write(root / "config/VERSION", "4.4.4")
    _write(root / "data" / "update_manifest.json", json.dumps({"action": "install_update", "target_version": "4.4.4"}))
    _write(root / "data" / "update_result.json", json.dumps({"status": "updated"}))
    _write(root / "data" / "logs" / "updater.log", "update ok\n")
    runtime_maintenance.record_updater_run(root, exit_code=0, notes="update leg")
    update_after = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(label="board-pc-drill", device_id="BOARD-17", operator="orri", service_ticket="TICKET-2048", drill_phase="after"),
    )
    runtime_maintenance.write_json(root / "data" / "field_state_after.json", update_after)
    update_report = root / "data" / "field_report_update.md"
    runtime_maintenance.write_field_report_markdown(update_report, update_before, update_after, runtime_maintenance.compare_runtime_boundary_state(update_before, update_after), "board-pc-drill-update")
    update_leg = runtime_maintenance.build_drill_leg_summary(
        root,
        before_path=root / "data" / "field_state_before.json",
        after_path=root / "data" / "field_state_after.json",
        report_path=update_report,
        label="board-pc-drill",
        leg="update",
    )

    rollback_before = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(label="board-pc-drill", device_id="BOARD-17", operator="orri", service_ticket="TICKET-2048", drill_phase="before"),
    )
    runtime_maintenance.write_json(root / "data" / "field_state_before_rollback.json", rollback_before)
    _write(root / "app/bin/VERSION", "4.4.3")
    _write(root / "config/VERSION", "4.4.3")
    _write(root / "data" / "update_manifest.json", json.dumps({"action": "rollback", "backup_path": "data/app_backups/one.zip"}))
    _write(root / "data" / "update_result.json", json.dumps({"status": "rolled_back"}))
    runtime_maintenance.record_updater_run(root, exit_code=0, notes="rollback leg")
    rollback_after = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(label="board-pc-drill", device_id="BOARD-17", operator="orri", service_ticket="TICKET-2048", drill_phase="after"),
    )
    runtime_maintenance.write_json(root / "data" / "field_state_after_rollback.json", rollback_after)
    rollback_report = root / "data" / "field_report_rollback.md"
    runtime_maintenance.write_field_report_markdown(rollback_report, rollback_before, rollback_after, runtime_maintenance.compare_runtime_boundary_state(rollback_before, rollback_after), "board-pc-drill-rollback")
    rollback_leg = runtime_maintenance.build_drill_leg_summary(
        root,
        before_path=root / "data" / "field_state_before_rollback.json",
        after_path=root / "data" / "field_state_after_rollback.json",
        report_path=rollback_report,
        label="board-pc-drill",
        leg="rollback",
    )

    paired = runtime_maintenance.build_paired_drill_summary(
        root,
        update_leg_path=Path(update_leg["summary_path"]),
        rollback_leg_path=Path(rollback_leg["summary_path"]),
        label="board-pc-drill",
    )

    assert update_leg["status"]["passed"] is True
    assert rollback_leg["status"]["passed"] is True
    assert paired["rollback_restored_start_version"] is True
    assert paired["closed_loop_passed"] is True
    assert Path(paired["summary_json_path"]).exists()
    assert Path(paired["summary_md_path"]).exists()
    assert "Closed-loop passed: `yes`" in Path(paired["summary_md_path"]).read_text(encoding="utf-8")


def test_compare_field_state_flags_drill_context_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")

    before = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(label="update-to-4.4.4", device_id="BOARD-17", operator="orri", service_ticket="TICKET-2048", drill_phase="before"),
    )
    after = runtime_maintenance.collect_runtime_boundary_state(
        root,
        drill_context=runtime_maintenance.build_drill_context(label="update-to-4.4.4", device_id="BOARD-18", operator="orri", service_ticket="TICKET-2048", drill_phase="after"),
    )

    comparison = runtime_maintenance.compare_runtime_boundary_state(before, after)

    assert comparison["drill_context_matches"] is False
    mismatch_fields = {item["field"] for item in comparison["drill_context_mismatches"]}
    assert "device_id" in mismatch_fields
    assert "drill_phase" not in mismatch_fields


def test_initialize_drill_workspace_creates_checklist_and_leg_paths(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")

    payload = runtime_maintenance.initialize_drill_workspace(
        root,
        label="board-pc-drill",
        device_id="BOARD-17",
        operator="orri",
        service_ticket="TICKET-2048",
    )

    workspace = payload["workspace"]
    checklist_json = Path(workspace["checklist_json"])
    checklist_md = Path(workspace["checklist_md"])
    handoff_json = checklist_json.parent / "DRILL_HANDOFF.json"
    handoff_md = checklist_json.parent / "DRILL_HANDOFF.md"
    assert checklist_json.exists()
    assert checklist_md.exists()
    assert handoff_json.exists()
    assert handoff_md.exists()
    data = json.loads(checklist_json.read_text(encoding="utf-8"))
    assert data["drill_context"]["device_id"] == "BOARD-17"
    step_names = {item["name"] for item in data["steps"]}
    assert "update_before_capture" in step_names
    assert "rollback_after_capture" in step_names
    assert "paired_summary" in step_names
    assert "paired_bundle" in step_names
    assert Path(workspace["update_before"]).parent == checklist_json.parent


def test_refresh_drill_workspace_marks_artifacts_and_emits_handoff_manifest(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]

    _write(Path(workspace["update_before"]), json.dumps({"ok": True}))
    _write(Path(workspace["update_after"]), json.dumps({"ok": True}))
    _write(Path(workspace["update_leg_summary"]), json.dumps({"status": {"passed": True}}))
    _write(Path(workspace["update_bundle"]), "bundle")

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    checklist = json.loads(Path(workspace["checklist_json"]).read_text(encoding="utf-8"))
    steps = {item["name"]: item["done"] for item in checklist["steps"]}
    assert steps["update_before_capture"] is True
    assert steps["update_after_capture"] is True
    assert steps["update_leg_summary"] is True
    assert steps["update_bundle"] is True
    assert steps["rollback_before_capture"] is False
    assert handoff["next_step"] == "rollback_before_capture"
    assert handoff["recommendation"]["status"] == "needs_manual_review"
    assert Path(workspace["checklist_md"]).read_text(encoding="utf-8").count("[x]") >= 4


def test_refresh_drill_workspace_marks_green_closed_loop_as_ship(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]

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
        content = "ok"
        if key.endswith(".json") or key in {"update_leg_summary", "rollback_leg_summary"}:
            content = json.dumps({"status": {"passed": True}})
        _write(Path(workspace[key]), content)

    Path(workspace["paired_summary_json"]).write_text(json.dumps({
        "closed_loop_passed": True,
        "rollback_restored_start_version": True,
    }, indent=2) + "\n", encoding="utf-8")

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    assert handoff["complete"] is True
    assert handoff["recommendation"]["status"] == "ship"
    assert "rollback restored the starting version" in handoff["recommendation"]["summary"].lower()


def test_refresh_drill_workspace_marks_failed_pair_as_retry_rollback(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    _build_runtime_root(root, version="4.4.3")
    payload = runtime_maintenance.initialize_drill_workspace(root, label="board-pc-drill")
    workspace = payload["workspace"]

    Path(workspace["paired_summary_json"]).parent.mkdir(parents=True, exist_ok=True)
    Path(workspace["paired_summary_json"]).write_text(json.dumps({
        "closed_loop_passed": False,
        "rollback_restored_start_version": False,
    }, indent=2) + "\n", encoding="utf-8")
    _write(Path(workspace["paired_summary_md"]), "paired")

    handoff = runtime_maintenance.refresh_drill_workspace_status(root, label="board-pc-drill")

    assert handoff["recommendation"]["status"] == "retry_rollback"
    assert any("rollback did not restore the starting version" == reason for reason in handoff["recommendation"]["reasons"])
