#!/usr/bin/env python3
"""Runtime package maintenance helper for Windows board devices.

Safe by default:
- validates expected runtime layout
- prepares required writable directories
- applies retention cleanup for logs/backups/downloads/support bundles
- supports dry-run mode for operator confidence

This script is additive and only targets the runtime-shaped package layout.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import hashlib
import sys
import time
import zipfile
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


RUNTIME_APP_DIRS = [
    "backend",
    "frontend/build",
    "agent",
    "bin",
]

RUNTIME_PROTECTED_PATHS = [
    "config",
    "data",
    "logs",
]

FRESHNESS_WARNING_HOURS = 8
FRESHNESS_STALE_HOURS = 24

WRITABLE_DIR_KEYS = [
    "data",
    "data/db",
    "data/logs",
    "data/backups",
    "data/app_backups",
    "data/downloads",
    "data/assets",
    "data/chrome_profile",
    "data/kiosk_ui_profile",
]


@dataclass
class RetentionPolicy:
    logs_keep: int = 8
    logs_max_mb: int = 50
    app_backups_keep: int = 2
    downloads_keep: int = 3
    downloads_max_age_days: int = 14
    support_bundles_keep: int = 2
    support_bundles_max_age_days: int = 7


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ensure_dir(path: Path, dry_run: bool, created: list[str]) -> None:
    if path.exists():
        return
    created.append(str(path))
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def human_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def file_age_days(path: Path, now: float) -> float:
    return max(0.0, (now - path.stat().st_mtime) / 86400.0)


def iter_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    return sorted((p for p in path.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)


def prune_keep_newest(files: list[Path], keep: int, dry_run: bool, removed: list[str]) -> None:
    for path in files[keep:]:
        removed.append(str(path))
        if not dry_run:
            path.unlink(missing_ok=True)


def prune_old(files: Iterable[Path], max_age_days: int, dry_run: bool, removed: list[str], now: float) -> None:
    for path in files:
        if file_age_days(path, now) > max_age_days:
            removed.append(str(path))
            if not dry_run:
                path.unlink(missing_ok=True)


def cap_total_size(files: list[Path], max_mb: int, dry_run: bool, removed: list[str]) -> None:
    budget = max_mb * 1024 * 1024
    total = sum(p.stat().st_size for p in files)
    if total <= budget:
        return
    for path in reversed(files):
        if total <= budget:
            break
        total -= path.stat().st_size
        removed.append(str(path))
        if not dry_run:
            path.unlink(missing_ok=True)


def validate_layout(root: Path) -> list[str]:
    required = [
        root / "app" / "backend",
        root / "app" / "frontend" / "build",
        root / "app" / "agent",
        root / "app" / "bin",
        root / "config" / "backend.env.example",
        root / "config" / "frontend.env.example",
        root / "config" / "VERSION",
        root / "data",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    return missing


def check_writable_paths(root: Path, dry_run: bool = False) -> dict[str, list[str]]:
    checked: list[str] = []
    ok: list[str] = []
    failed: list[str] = []
    created: list[str] = []

    for rel in WRITABLE_DIR_KEYS:
        path = root / rel
        checked.append(rel)
        if not path.exists():
            created.append(rel)
            if not dry_run:
                path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test.tmp"
        try:
            if not dry_run:
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
            ok.append(rel)
        except Exception:
            failed.append(rel)
    return {
        "checked": checked,
        "ok": ok,
        "failed": failed,
        "created": created,
    }


def normalize_rel_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_drill_context(
    *,
    label: str | None = None,
    operator: str | None = None,
    device_id: str | None = None,
    service_ticket: str | None = None,
    drill_phase: str | None = None,
    notes: str | None = None,
) -> dict[str, str]:
    context: dict[str, str] = {}
    for key, value in {
        "label": label,
        "operator": operator,
        "device_id": device_id,
        "service_ticket": service_ticket,
        "drill_phase": drill_phase,
        "notes": notes,
    }.items():
        cleaned = (value or "").strip()
        if cleaned:
            context[key] = cleaned
    return context


def summarize_updater_artifacts(root: Path) -> dict:
    run_record_path = root / "data" / "last_updater_run.json"
    update_result_path = root / "data" / "update_result.json"
    log_candidates = [
        root / "logs" / "updater.log",
        root / "data" / "logs" / "updater.log",
    ]

    result: dict[str, object] = {
        "run_record": {"path": str(run_record_path), "exists": run_record_path.exists()},
        "update_result": {"path": str(update_result_path), "exists": update_result_path.exists()},
        "log": {"path": None, "exists": False, "size_bytes": 0},
        "manifest_action": None,
        "exit_code": None,
        "ok": None,
    }

    for candidate in log_candidates:
        if candidate.exists() and candidate.is_file():
            result["log"] = {
                "path": str(candidate),
                "exists": True,
                "size_bytes": candidate.stat().st_size,
            }
            break

    if run_record_path.exists() and run_record_path.is_file():
        try:
            run_record = json.loads(run_record_path.read_text(encoding="utf-8"))
            result["run_record"]["data"] = run_record
            result["manifest_action"] = run_record.get("manifest_action")
            result["exit_code"] = run_record.get("exit_code")
            result["ok"] = run_record.get("ok")
        except Exception as exc:  # pragma: no cover - defensive
            result["run_record"]["error"] = str(exc)

    if update_result_path.exists() and update_result_path.is_file():
        try:
            update_result = json.loads(update_result_path.read_text(encoding="utf-8"))
            result["update_result"]["data"] = update_result
            if result["ok"] is None:
                status = str(update_result.get("status") or "").strip().lower()
                if status:
                    result["ok"] = status in {"ok", "success", "updated", "rolled_back", "rollback_success"}
        except Exception as exc:  # pragma: no cover - defensive
            result["update_result"]["error"] = str(exc)

    return result


def record_updater_run(
    root: Path,
    *,
    manifest_path: Path | None = None,
    exit_code: int,
    update_result_path: Path | None = None,
    log_path: Path | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict:
    manifest_file = (manifest_path or (root / "data" / "update_manifest.json")).expanduser().resolve()
    update_result_file = (update_result_path or (root / "data" / "update_result.json")).expanduser().resolve()
    log_file = (log_path.expanduser().resolve() if log_path else None)
    if log_file is None:
        for candidate in [root / "logs" / "updater.log", root / "data" / "logs" / "updater.log"]:
            if candidate.exists() and candidate.is_file():
                log_file = candidate.resolve()
                break

    manifest_data = None
    manifest_error = None
    if manifest_file.exists() and manifest_file.is_file():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            manifest_error = str(exc)

    update_result_data = None
    update_result_error = None
    if update_result_file.exists() and update_result_file.is_file():
        try:
            update_result_data = json.loads(update_result_file.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            update_result_error = str(exc)

    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_file),
        "manifest_exists": manifest_file.exists(),
        "manifest_action": manifest_data.get("action") if isinstance(manifest_data, dict) else None,
        "target_version": manifest_data.get("target_version") if isinstance(manifest_data, dict) else None,
        "backup_path": manifest_data.get("backup_path") if isinstance(manifest_data, dict) else None,
        "exit_code": exit_code,
        "ok": exit_code == 0,
        "update_result_path": str(update_result_file),
        "update_result_exists": update_result_file.exists(),
        "update_result": update_result_data,
        "log_path": str(log_file) if log_file else None,
        "log_exists": bool(log_file and log_file.exists()),
        "log_size_bytes": log_file.stat().st_size if log_file and log_file.exists() else 0,
        "notes": notes,
    }
    if manifest_error:
        payload["manifest_error"] = manifest_error
    if update_result_error:
        payload["update_result_error"] = update_result_error

    record_path = root / "data" / "last_updater_run.json"
    if not dry_run:
        write_json(record_path, payload)
    return {"record_path": str(record_path), "record": payload}


def collect_runtime_boundary_state(root: Path, drill_context: dict[str, str] | None = None) -> dict:
    config_version_path = root / "config" / "VERSION"
    app_version_path = root / "app" / "bin" / "VERSION"
    update_manifest_path = root / "data" / "update_manifest.json"
    rollback_manifest_path = root / "data" / "rollback_manifest.json"

    def summarize_tree(path: Path) -> dict:
        result = {
            "path": str(path),
            "exists": path.exists(),
            "file_count": 0,
            "dir_count": 0,
            "total_bytes": 0,
            "sample_files": [],
        }
        if not path.exists():
            return result
        files: list[str] = []
        for item in sorted(path.rglob("*")):
            rel = item.relative_to(path).as_posix()
            if item.is_dir():
                result["dir_count"] += 1
                continue
            result["file_count"] += 1
            result["total_bytes"] += item.stat().st_size
            if len(files) < 12:
                files.append(rel)
        result["sample_files"] = files
        return result

    def summarize_manifest(path: Path) -> dict:
        result = {"path": str(path), "exists": path.exists(), "action": None, "target_version": None, "backup_path": None}
        if not path.exists():
            return result
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            result["error"] = str(exc)
            return result
        result["action"] = data.get("action")
        result["target_version"] = data.get("target_version")
        result["backup_path"] = data.get("backup_path")
        return result

    state = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root.resolve()),
        "config_version": config_version_path.read_text(encoding="utf-8", errors="ignore").strip() if config_version_path.exists() else None,
        "app_bin_version": app_version_path.read_text(encoding="utf-8", errors="ignore").strip() if app_version_path.exists() else None,
        "app": summarize_tree(root / "app"),
        "config": summarize_tree(root / "config"),
        "data": summarize_tree(root / "data"),
        "logs": summarize_tree(root / "data" / "logs"),
        "update_manifest": summarize_manifest(update_manifest_path),
        "rollback_manifest": summarize_manifest(rollback_manifest_path),
        "updater_artifacts": summarize_updater_artifacts(root),
    }
    if drill_context:
        state["drill_context"] = dict(drill_context)

    tracked_hashes: dict[str, str] = {}
    for rel in [
        "config/VERSION",
        "app/bin/VERSION",
        "config/backend.env.example",
        "config/frontend.env.example",
    ]:
        candidate = root / rel
        if candidate.exists() and candidate.is_file():
            tracked_hashes[rel] = sha256_file(candidate)
    state["tracked_hashes"] = tracked_hashes
    return state


def compare_runtime_boundary_state(before: dict, after: dict) -> dict:
    def metric(section: str, key: str) -> tuple[int | None, int | None, int | None]:
        before_value = before.get(section, {}).get(key)
        after_value = after.get(section, {}).get(key)
        delta = None
        if isinstance(before_value, int) and isinstance(after_value, int):
            delta = after_value - before_value
        return before_value, after_value, delta

    hash_changes = []
    expected_version_paths = {"config/VERSION", "app/bin/VERSION"}
    unexpected_hash_changes = []
    tracked = sorted(set(before.get("tracked_hashes", {})) | set(after.get("tracked_hashes", {})))
    for rel in tracked:
        before_hash = before.get("tracked_hashes", {}).get(rel)
        after_hash = after.get("tracked_hashes", {}).get(rel)
        if before_hash != after_hash:
            item = {"path": rel, "before": before_hash, "after": after_hash}
            hash_changes.append(item)
            if rel not in expected_version_paths:
                unexpected_hash_changes.append(item)

    config_files = metric("config", "file_count")
    data_files = metric("data", "file_count")
    log_files = metric("logs", "file_count")
    app_files = metric("app", "file_count")
    before_context = before.get("drill_context", {}) if isinstance(before.get("drill_context"), dict) else {}
    after_context = after.get("drill_context", {}) if isinstance(after.get("drill_context"), dict) else {}
    context_mismatches = []
    for key in sorted(set(before_context) | set(after_context)):
        before_value = before_context.get(key)
        after_value = after_context.get(key)
        if key == "drill_phase" and before_value == "before" and after_value == "after":
            continue
        if before_value != after_value:
            context_mismatches.append({"field": key, "before": before_value, "after": after_value})

    return {
        "before_version": before.get("config_version"),
        "after_version": after.get("config_version"),
        "before_app_bin_version": before.get("app_bin_version"),
        "after_app_bin_version": after.get("app_bin_version"),
        "version_changed": before.get("config_version") != after.get("config_version"),
        "app_bin_version_changed": before.get("app_bin_version") != after.get("app_bin_version"),
        "config_files": {"before": config_files[0], "after": config_files[1], "delta": config_files[2]},
        "data_files": {"before": data_files[0], "after": data_files[1], "delta": data_files[2]},
        "log_files": {"before": log_files[0], "after": log_files[1], "delta": log_files[2]},
        "app_files": {"before": app_files[0], "after": app_files[1], "delta": app_files[2]},
        "config_hash_changes": hash_changes,
        "unexpected_config_hash_changes": unexpected_hash_changes,
        "config_boundary_stable": not unexpected_hash_changes,
        "data_boundary_present_before_and_after": bool(before.get("data", {}).get("exists")) and bool(after.get("data", {}).get("exists")),
        "logs_boundary_present_before_and_after": bool(before.get("logs", {}).get("exists")) and bool(after.get("logs", {}).get("exists")),
        "update_manifest_action_after": after.get("update_manifest", {}).get("action"),
        "rollback_manifest_action_after": after.get("rollback_manifest", {}).get("action"),
        "updater_exit_code_after": after.get("updater_artifacts", {}).get("exit_code"),
        "updater_ok_after": after.get("updater_artifacts", {}).get("ok"),
        "updater_manifest_action_after": after.get("updater_artifacts", {}).get("manifest_action"),
        "updater_log_present_after": bool(after.get("updater_artifacts", {}).get("log", {}).get("exists")),
        "update_result_present_after": bool(after.get("updater_artifacts", {}).get("update_result", {}).get("exists")),
        "drill_context_before": before_context,
        "drill_context_after": after_context,
        "drill_context_matches": not context_mismatches,
        "drill_context_mismatches": context_mismatches,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_field_report_markdown(path: Path, before: dict, after: dict, comparison: dict, label: str) -> None:
    drill_context = comparison.get("drill_context_after") or comparison.get("drill_context_before") or {}
    lines = [
        f"# Runtime Field Report — {label}",
        "",
        f"- Captured before: `{before.get('captured_at')}`",
        f"- Captured after: `{after.get('captured_at')}`",
        f"- Runtime root: `{after.get('root')}`",
        f"- Version before → after: `{comparison.get('before_version')}` → `{comparison.get('after_version')}`",
        f"- app/bin VERSION before → after: `{comparison.get('before_app_bin_version')}` → `{comparison.get('after_app_bin_version')}`",
        f"- Config boundary stable: `{'yes' if comparison.get('config_boundary_stable') else 'no'}`",
        f"- Data boundary present before/after: `{'yes' if comparison.get('data_boundary_present_before_and_after') else 'no'}`",
        f"- Logs boundary present before/after: `{'yes' if comparison.get('logs_boundary_present_before_and_after') else 'no'}`",
        "",
        "## Drill metadata",
        "",
    ]
    if drill_context:
        for key in ["label", "device_id", "operator", "service_ticket", "drill_phase", "notes"]:
            if drill_context.get(key):
                lines.append(f"- {key.replace('_', ' ').title()}: `{drill_context[key]}`")
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## File-count deltas",
        "",
        f"- app/: {comparison['app_files']['before']} → {comparison['app_files']['after']} (delta {comparison['app_files']['delta']})",
        f"- config/: {comparison['config_files']['before']} → {comparison['config_files']['after']} (delta {comparison['config_files']['delta']})",
        f"- data/: {comparison['data_files']['before']} → {comparison['data_files']['after']} (delta {comparison['data_files']['delta']})",
        f"- data/logs/: {comparison['log_files']['before']} → {comparison['log_files']['after']} (delta {comparison['log_files']['delta']})",
        "",
        "## Manifest status after capture",
        "",
        f"- update_manifest action: `{comparison.get('update_manifest_action_after')}`",
        f"- rollback_manifest action: `{comparison.get('rollback_manifest_action_after')}`",
        f"- updater manifest action: `{comparison.get('updater_manifest_action_after')}`",
        f"- updater exit code: `{comparison.get('updater_exit_code_after')}`",
        f"- updater marked ok: `{'yes' if comparison.get('updater_ok_after') else 'no' if comparison.get('updater_ok_after') is False else 'unknown'}`",
        f"- update_result.json present: `{'yes' if comparison.get('update_result_present_after') else 'no'}`",
        f"- updater log present: `{'yes' if comparison.get('updater_log_present_after') else 'no'}`",
        "",
        "## Config hash changes",
        "",
    ])
    if comparison["config_hash_changes"]:
        for item in comparison["config_hash_changes"]:
            lines.append(f"- `{item['path']}` changed")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Unexpected config drift")
    lines.append("")
    if comparison["unexpected_config_hash_changes"]:
        for item in comparison["unexpected_config_hash_changes"]:
            lines.append(f"- `{item['path']}` changed unexpectedly")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Drill context mismatches")
    lines.append("")
    if comparison["drill_context_mismatches"]:
        for item in comparison["drill_context_mismatches"]:
            lines.append(f"- `{item['field']}` before=`{item['before']}` after=`{item['after']}`")
    else:
        lines.append("- none")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def sanitize_label(label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in label.strip())
    return safe.strip("-") or "board-pc-drill"


def get_drill_workspace(root: Path, label: str) -> dict[str, Path]:
    safe = sanitize_label(label)
    base = (root / "data" / "support" / "drills" / safe).resolve()
    return {
        "label": Path(safe),
        "base": base,
        "checklist_json": base / "drill-checklist.json",
        "checklist_md": base / "DRILL_CHECKLIST.md",
        "update_before": base / "field_state_update_before.json",
        "update_after": base / "field_state_update_after.json",
        "update_report": base / "field_report_update.md",
        "update_bundle": base / f"runtime-support-bundle-update-{safe}.zip",
        "update_leg_summary": base / f"drill-leg-update-{safe}.json",
        "rollback_before": base / "field_state_rollback_before.json",
        "rollback_after": base / "field_state_rollback_after.json",
        "rollback_report": base / "field_report_rollback.md",
        "rollback_bundle": base / f"runtime-support-bundle-rollback-{safe}.zip",
        "rollback_leg_summary": base / f"drill-leg-rollback-{safe}.json",
        "paired_summary_json": base / f"paired-drill-summary-{safe}.json",
        "paired_summary_md": base / f"paired-drill-summary-{safe}.md",
        "paired_bundle": base / f"runtime-support-bundle-paired-{safe}.zip",
        "attachment_review_json": base / "ATTACHMENT_READINESS_REVIEW.json",
        "attachment_review_txt": base / "ATTACHMENT_READINESS_REVIEW.txt",
    }


def describe_artifact(path: Path) -> dict[str, object]:
    exists = path.exists() and path.is_file()
    payload: dict[str, object] = {
        "path": str(path.resolve()),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "sha256": sha256_file(path) if exists else None,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if exists else None,
    }
    if exists and path.suffix.lower() == ".json":
        try:
            payload["json"] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            payload["json_error"] = str(exc)
    return payload


def parse_iso8601(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_acknowledgment_history_entry(
    *,
    acknowledgment: dict[str, object],
    sequence: int,
    event: str,
    previous_acknowledgment: dict[str, object] | None = None,
) -> dict[str, object]:
    previous = copy.deepcopy(previous_acknowledgment or {})
    previous_reference = str(previous.get("ticket_reference") or "").strip() or None
    previous_url = str(previous.get("ticket_url") or "").strip() or None
    current_reference = str(acknowledgment.get("ticket_reference") or "").strip() or None
    current_url = str(acknowledgment.get("ticket_url") or "").strip() or None
    previous_destination = " | ".join(item for item in [previous_reference, previous_url] if item) or None
    current_destination = " | ".join(item for item in [current_reference, current_url] if item) or None
    change_bits: list[str] = []
    if previous_destination != current_destination:
        change_bits.append(
            f"destination {previous_destination or '-'} -> {current_destination or '-'}"
        )
    previous_by = str(previous.get("attached_by") or "").strip() or None
    current_by = str(acknowledgment.get("attached_by") or "").strip() or None
    if previous_by != current_by:
        change_bits.append(f"attached_by {previous_by or '-'} -> {current_by or '-'}")
    previous_status = str(previous.get("ticket_status") or "").strip() or None
    current_status = str(acknowledgment.get("ticket_status") or "").strip() or None
    if previous_status != current_status:
        change_bits.append(f"ticket_status {previous_status or '-'} -> {current_status or '-'}")
    return {
        "sequence": sequence,
        "event": event,
        "attached_by": acknowledgment.get("attached_by"),
        "attached_at": acknowledgment.get("attached_at"),
        "ticket_status": acknowledgment.get("ticket_status"),
        "ticket_reference": acknowledgment.get("ticket_reference"),
        "ticket_url": acknowledgment.get("ticket_url"),
        "ticket_destination_display": current_destination,
        "note": acknowledgment.get("note"),
        "paired_artifact_snapshot": copy.deepcopy(acknowledgment.get("paired_artifact_snapshot") or {}),
        "previous_attached_at": previous.get("attached_at"),
        "previous_ticket_status": previous.get("ticket_status"),
        "previous_ticket_reference": previous_reference,
        "previous_ticket_url": previous_url,
        "previous_ticket_destination_display": previous_destination,
        "destination_changed": previous_destination != current_destination,
        "change_summary": "; ".join(change_bits) if change_bits else "no operator-visible destination/status/assignee change",
    }


def artifact_timestamp(artifact: dict[str, object]) -> datetime | None:
    return parse_iso8601(artifact.get("modified_at"))


def evaluate_drill_artifact_freshness(*, artifacts: dict[str, dict[str, object]], paired_json: dict[str, object]) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    warnings: list[str] = []
    stale_artifacts: list[str] = []
    misaligned_artifacts: list[str] = []
    checked_artifacts: dict[str, dict[str, object]] = {}

    def record_age(name: str) -> None:
        artifact = artifacts[name]
        ts = artifact_timestamp(artifact)
        info: dict[str, object] = {
            "exists": artifact.get("exists") is True,
            "modified_at": artifact.get("modified_at"),
            "age_hours": None,
            "freshness": "missing" if artifact.get("exists") is not True else "unknown",
        }
        if ts is not None:
            age_hours = round(max(0.0, (now - ts).total_seconds() / 3600.0), 2)
            info["age_hours"] = age_hours
            if age_hours >= FRESHNESS_STALE_HOURS:
                info["freshness"] = "stale"
                stale_artifacts.append(name)
                warnings.append(f"{name} is older than {FRESHNESS_STALE_HOURS}h")
            elif age_hours >= FRESHNESS_WARNING_HOURS:
                info["freshness"] = "aging"
                warnings.append(f"{name} is older than {FRESHNESS_WARNING_HOURS}h")
            else:
                info["freshness"] = "fresh"
        checked_artifacts[name] = info

    for name in [
        "update_before", "update_after", "update_leg_summary", "update_bundle",
        "rollback_before", "rollback_after", "rollback_leg_summary", "rollback_bundle",
        "paired_summary_json", "paired_summary_md", "paired_bundle",
    ]:
        record_age(name)

    def compare_order(older: str, newer: str, description: str) -> None:
        older_ts = artifact_timestamp(artifacts[older])
        newer_ts = artifact_timestamp(artifacts[newer])
        if older_ts is None or newer_ts is None:
            return
        if newer_ts < older_ts:
            misaligned_artifacts.append(f"{newer}<{older}")
            warnings.append(description)

    compare_order("update_after", "update_leg_summary", "update leg summary predates update-after evidence")
    compare_order("update_leg_summary", "update_bundle", "update bundle predates update leg summary")
    compare_order("rollback_after", "rollback_leg_summary", "rollback leg summary predates rollback-after evidence")
    compare_order("rollback_leg_summary", "rollback_bundle", "rollback bundle predates rollback leg summary")
    compare_order("update_leg_summary", "paired_summary_json", "paired summary predates update leg summary")
    compare_order("rollback_leg_summary", "paired_summary_json", "paired summary predates rollback leg summary")
    compare_order("paired_summary_json", "paired_bundle", "paired bundle predates paired summary")

    paired_created = parse_iso8601(paired_json.get("created_at"))
    if paired_created is not None:
        checked_artifacts["paired_summary_payload"] = {
            "exists": True,
            "modified_at": paired_json.get("created_at"),
            "age_hours": round(max(0.0, (now - paired_created).total_seconds() / 3600.0), 2),
            "freshness": "fresh" if max(0.0, (now - paired_created).total_seconds() / 3600.0) < FRESHNESS_WARNING_HOURS else "aging",
        }

    return {
        "checked_artifacts": checked_artifacts,
        "warning_threshold_hours": FRESHNESS_WARNING_HOURS,
        "stale_threshold_hours": FRESHNESS_STALE_HOURS,
        "warnings": warnings,
        "stale_artifacts": stale_artifacts,
        "misaligned_artifacts": misaligned_artifacts,
        "ok": not stale_artifacts and not misaligned_artifacts,
    }


def build_drill_workspace_checklist_payload(root: Path, paths: dict[str, Path], label: str, drill_context: dict[str, str]) -> dict:
    return {
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(root.resolve()),
        "drill_context": drill_context,
        "workspace": {key: str(value) for key, value in paths.items() if key != "label"},
        "steps": [
            {"name": "update_before_capture", "artifact": str(paths["update_before"]), "done": False},
            {"name": "update_after_capture", "artifact": str(paths["update_after"]), "done": False},
            {"name": "update_leg_summary", "artifact": str(paths["update_leg_summary"]), "done": False},
            {"name": "update_bundle", "artifact": str(paths["update_bundle"]), "done": False},
            {"name": "rollback_before_capture", "artifact": str(paths["rollback_before"]), "done": False},
            {"name": "rollback_after_capture", "artifact": str(paths["rollback_after"]), "done": False},
            {"name": "rollback_leg_summary", "artifact": str(paths["rollback_leg_summary"]), "done": False},
            {"name": "rollback_bundle", "artifact": str(paths["rollback_bundle"]), "done": False},
            {"name": "paired_summary", "artifact": str(paths["paired_summary_json"]), "done": False},
            {"name": "paired_bundle", "artifact": str(paths["paired_bundle"]), "done": False},
        ],
    }


def render_drill_checklist_markdown(root: Path, paths: dict[str, Path], label: str, drill_context: dict[str, str], steps: list[dict[str, object]], next_step: str) -> str:
    checklist_lines = [
        f"# Runtime Drill Checklist — {label}",
        "",
        f"- Runtime root: `{root.resolve()}`",
        f"- Workspace: `{paths['base']}`",
        "",
        "## Drill metadata",
        "",
    ]
    if drill_context:
        for key in ["device_id", "operator", "service_ticket", "notes"]:
            if drill_context.get(key):
                checklist_lines.append(f"- {key.replace('_', ' ').title()}: `{drill_context[key]}`")
    else:
        checklist_lines.append("- none")
    checklist_lines.extend([
        "",
        "## Expected artifacts",
        "",
        f"- Update before: `{paths['update_before']}`",
        f"- Update after: `{paths['update_after']}`",
        f"- Update report: `{paths['update_report']}`",
        f"- Update bundle: `{paths['update_bundle']}`",
        f"- Rollback before: `{paths['rollback_before']}`",
        f"- Rollback after: `{paths['rollback_after']}`",
        f"- Rollback report: `{paths['rollback_report']}`",
        f"- Rollback bundle: `{paths['rollback_bundle']}`",
        f"- Paired summary: `{paths['paired_summary_md']}`",
        f"- Paired bundle: `{paths['paired_bundle']}`",
        "",
        "## Status",
        "",
    ])
    labels = {
        "update_before_capture": "Capture update-before state",
        "update_after_capture": "Capture update-after state",
        "update_leg_summary": "Build update leg summary",
        "update_bundle": "Build update support bundle",
        "rollback_before_capture": "Capture rollback-before state",
        "rollback_after_capture": "Capture rollback-after state",
        "rollback_leg_summary": "Build rollback leg summary",
        "rollback_bundle": "Build rollback support bundle",
        "paired_summary": "Build paired summary",
        "paired_bundle": "Build paired support bundle",
    }
    for step in steps:
        checklist_lines.append(f"- [{'x' if step['done'] else ' '}] {labels.get(str(step['name']), str(step['name']))}")
    checklist_lines.extend([
        "",
        f"Next suggested operator step: `{next_step}`",
        "",
        "This folder is the wave-14 operator lane: one drill label, one self-refreshing checklist, one handoff manifest.",
    ])
    return "\n".join(checklist_lines) + "\n"


def merge_drill_context(base: dict[str, str] | None = None, overrides: dict[str, str] | None = None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for source in [base or {}, overrides or {}]:
        for key, value in source.items():
            cleaned = str(value or "").strip()
            if cleaned:
                merged[key] = cleaned
    return merged


def snapshot_paired_artifacts(artifacts: dict[str, dict[str, object]]) -> dict[str, object]:
    monitored_keys = ["paired_bundle", "paired_summary_json", "paired_summary_md"]
    snapshot_items: list[dict[str, object]] = []
    for key in monitored_keys:
        artifact = artifacts.get(key) or {}
        snapshot_items.append({
            "key": key,
            "path": artifact.get("path"),
            "exists": bool(artifact.get("exists")),
            "size_bytes": artifact.get("size_bytes") if artifact.get("exists") else 0,
            "modified_at": artifact.get("modified_at") if artifact.get("exists") else None,
            "sha256": artifact.get("sha256") if artifact.get("exists") else None,
            "sha256_short": (str(artifact.get("sha256"))[:12] if artifact.get("sha256") else None),
        })
    return {
        "monitored_keys": monitored_keys,
        "items": snapshot_items,
    }


def build_attachment_fingerprint_summary(
    *,
    ticket_acknowledgment: dict[str, object] | None,
    artifacts: dict[str, dict[str, object]],
) -> dict[str, object]:
    current_snapshot = snapshot_paired_artifacts(artifacts)
    acknowledgment = copy.deepcopy(ticket_acknowledgment or {})
    acknowledged_snapshot = copy.deepcopy(acknowledgment.get("paired_artifact_snapshot") or {})
    current_by_key = {str(item.get("key")): item for item in current_snapshot.get("items") or [] if item.get("key")}
    acknowledged_by_key = {str(item.get("key")): item for item in acknowledged_snapshot.get("items") or [] if item.get("key")}
    compared_keys = sorted(set(current_by_key) | set(acknowledged_by_key))
    mismatches: list[dict[str, object]] = []
    mismatch_keys: list[str] = []
    for key in compared_keys:
        current_item = current_by_key.get(key) or {}
        acknowledged_item = acknowledged_by_key.get(key) or {}
        current_sha = current_item.get("sha256")
        acknowledged_sha = acknowledged_item.get("sha256")
        if current_sha and acknowledged_sha and current_sha == acknowledged_sha:
            continue
        if not current_item and not acknowledged_item:
            continue
        mismatch_keys.append(key)
        mismatches.append({
            "key": key,
            "current_sha256": current_sha,
            "current_sha256_short": current_item.get("sha256_short"),
            "acknowledged_sha256": acknowledged_sha,
            "acknowledged_sha256_short": acknowledged_item.get("sha256_short"),
            "current_exists": current_item.get("exists"),
            "acknowledged_exists": acknowledged_item.get("exists"),
            "change_summary": (
                f"{key}: current {current_item.get('sha256_short') or '-'} vs acknowledged {acknowledged_item.get('sha256_short') or '-'}"
            ),
        })
    snapshot_available = bool(acknowledged_snapshot.get("items"))
    acknowledgment_recorded = bool(acknowledgment.get("acknowledged"))
    matches_current_acknowledgment = acknowledgment_recorded and snapshot_available and not mismatches
    warnings: list[str] = []
    verdict = "no_acknowledgment_recorded"
    verdict_text = "No upload acknowledgment recorded yet."
    mismatch_summary = "No fingerprint differences detected."
    if not acknowledgment_recorded:
        mismatch_summary = "No upload acknowledgment recorded yet, so there is no acknowledged fingerprint snapshot to compare."
    elif acknowledgment.get("acknowledged") and not snapshot_available:
        warnings.append("acknowledgment predates artifact fingerprint snapshots; only current fingerprints are available")
        verdict = "snapshot_missing"
        verdict_text = "Upload acknowledged, but that acknowledgment predates fingerprint snapshots."
        mismatch_summary = "No acknowledged fingerprint snapshot is available for comparison yet."
    elif mismatches:
        mismatch_summary = "Changed paired entries: " + ", ".join(mismatch_keys)
        warnings.append(
            "current paired artifact fingerprints differ from the last acknowledged snapshot: "
            + ", ".join(mismatch_keys)
        )
        verdict = "mismatch"
        verdict_text = "Acknowledged artifact set no longer matches the current paired files."
    elif matches_current_acknowledgment:
        verdict = "match"
        verdict_text = "Acknowledged artifact set matches the current paired files."
        mismatch_summary = "All acknowledged paired artifact fingerprints still match the current files."
    elif acknowledgment.get("acknowledged"):
        verdict = "acknowledged_without_snapshot"
        verdict_text = "Upload acknowledged, but fingerprint comparison is incomplete."
        mismatch_summary = "Upload acknowledgment exists, but fingerprint comparison is incomplete."
    return {
        "current": current_snapshot,
        "acknowledged": acknowledged_snapshot,
        "snapshot_available": snapshot_available,
        "matches_current_acknowledgment": matches_current_acknowledgment,
        "mismatches": mismatches,
        "mismatch_keys": mismatch_keys,
        "mismatch_summary": mismatch_summary,
        "warnings": warnings,
        "verdict": verdict,
        "verdict_text": verdict_text,
    }


def derive_acknowledgment_drift(
    *,
    ticket_acknowledgment: dict[str, object] | None,
    artifacts: dict[str, dict[str, object]],
) -> dict[str, object]:
    acknowledgment = copy.deepcopy(ticket_acknowledgment or {})
    acknowledged = bool(acknowledgment.get("acknowledged"))
    attached_at = parse_iso8601(acknowledgment.get("attached_at"))
    monitored_keys = ["paired_bundle", "paired_summary_json", "paired_summary_md"]
    changed_after_ack: list[dict[str, object]] = []
    acknowledged_snapshot = copy.deepcopy(acknowledgment.get("paired_artifact_snapshot") or {})
    acknowledged_by_key = {
        str(item.get("key")): item
        for item in acknowledged_snapshot.get("items") or []
        if item.get("key")
    }
    timestamp_only_keys: list[str] = []
    fingerprint_changed_keys: list[str] = []
    snapshot_missing_keys: list[str] = []

    if acknowledged and attached_at is not None:
        for key in monitored_keys:
            artifact = artifacts.get(key) or {}
            modified_at = artifact_timestamp(artifact)
            if modified_at is None or modified_at <= attached_at:
                continue
            acknowledged_item = acknowledged_by_key.get(key) or {}
            current_sha = artifact.get("sha256")
            acknowledged_sha = acknowledged_item.get("sha256")
            drift_kind = "timestamp_only"
            if current_sha and acknowledged_sha:
                if current_sha != acknowledged_sha:
                    drift_kind = "fingerprint_changed"
                    fingerprint_changed_keys.append(key)
                else:
                    timestamp_only_keys.append(key)
            else:
                drift_kind = "snapshot_missing"
                snapshot_missing_keys.append(key)
            changed_after_ack.append(
                {
                    "key": key,
                    "path": artifact.get("path"),
                    "modified_at": artifact.get("modified_at"),
                    "attached_at": acknowledgment.get("attached_at"),
                    "drift_kind": drift_kind,
                    "current_sha256": current_sha,
                    "current_sha256_short": (str(current_sha)[:12] if current_sha else None),
                    "acknowledged_sha256": acknowledged_sha,
                    "acknowledged_sha256_short": (str(acknowledged_sha)[:12] if acknowledged_sha else None),
                }
            )

    stale_after_regeneration = bool(changed_after_ack)
    if stale_after_regeneration and fingerprint_changed_keys:
        drift_verdict = "fingerprint_changed"
        drift_summary = "Regenerated paired artifacts differ from the acknowledged fingerprint snapshot."
    elif stale_after_regeneration and timestamp_only_keys and not snapshot_missing_keys:
        drift_verdict = "timestamp_only"
        drift_summary = "Paired artifact timestamps changed after upload, but fingerprints still match the acknowledged snapshot."
    elif stale_after_regeneration and snapshot_missing_keys and not fingerprint_changed_keys:
        drift_verdict = "timestamp_changed_snapshot_missing"
        drift_summary = "Paired artifact timestamps changed after upload, but acknowledged fingerprint snapshots are incomplete."
    elif stale_after_regeneration:
        drift_verdict = "mixed"
        drift_summary = "Some paired artifacts changed after upload; see per-entry drift kinds for timestamp-only vs fingerprint-changed details."
    elif acknowledged:
        drift_verdict = "current"
        drift_summary = "Acknowledgment is still current relative to the paired artifacts."
    else:
        drift_verdict = "no_acknowledgment_recorded"
        drift_summary = "No upload acknowledgment recorded yet."

    warnings: list[str] = []
    if stale_after_regeneration:
        changed_keys = ", ".join(item["key"] for item in changed_after_ack)
        warnings.append(
            f"ticket acknowledgment predates regenerated paired artifacts: {changed_keys}"
        )
        if timestamp_only_keys:
            warnings.append(
                "timestamp-only drift detected for: " + ", ".join(timestamp_only_keys)
            )
        if fingerprint_changed_keys:
            warnings.append(
                "fingerprint/content drift detected for: " + ", ".join(fingerprint_changed_keys)
            )
        if snapshot_missing_keys:
            warnings.append(
                "acknowledged fingerprint snapshot missing for: " + ", ".join(snapshot_missing_keys)
            )

    return {
        "acknowledged": acknowledged,
        "attached_at": acknowledgment.get("attached_at"),
        "stale_after_regeneration": stale_after_regeneration,
        "current": acknowledged and not stale_after_regeneration,
        "monitored_keys": monitored_keys,
        "changed_after_ack": changed_after_ack,
        "timestamp_only_keys": timestamp_only_keys,
        "fingerprint_changed_keys": fingerprint_changed_keys,
        "snapshot_missing_keys": snapshot_missing_keys,
        "drift_verdict": drift_verdict,
        "drift_summary": drift_summary,
        "warnings": warnings,
    }


def build_attachment_destination_summary(
    *,
    ticket_acknowledgment: dict[str, object] | None,
    reattach_required: bool,
    reusable_destination: bool,
) -> dict[str, object]:
    acknowledgment = copy.deepcopy(ticket_acknowledgment or {})
    ticket_reference = str(acknowledgment.get("ticket_reference") or "").strip() or None
    ticket_url = str(acknowledgment.get("ticket_url") or "").strip() or None

    destination_kind = "none"
    destination_display = "No stored ticket destination."
    if ticket_reference and ticket_url:
        destination_kind = "reference_and_url"
        destination_display = f"{ticket_reference} | {ticket_url}"
    elif ticket_reference:
        destination_kind = "reference_only"
        destination_display = ticket_reference
    elif ticket_url:
        destination_kind = "url_only"
        destination_display = ticket_url

    if acknowledgment.get("acknowledged") and reusable_destination:
        verdict = "stored_destination_ready"
        verdict_text = "Stored ticket destination is available for direct re-acknowledge reuse."
    elif acknowledgment.get("acknowledged") and reattach_required:
        verdict = "destination_missing_for_reattach"
        verdict_text = "Re-attach is required, but no reusable ticket destination is stored yet."
    elif acknowledgment.get("acknowledged"):
        verdict = "acknowledged_destination_missing"
        verdict_text = "Upload is acknowledged, but no reusable ticket destination is stored."
    else:
        verdict = "no_acknowledgment_recorded"
        verdict_text = "No upload acknowledgment recorded yet, so no ticket destination is on record."

    return {
        "kind": destination_kind,
        "display": destination_display,
        "ticket_reference": ticket_reference,
        "ticket_url": ticket_url,
        "stored_destination_ready": reusable_destination,
        "verdict": verdict,
        "verdict_text": verdict_text,
    }


def build_attachment_timeline(
    *,
    ticket_acknowledgment: dict[str, object] | None,
    artifacts: dict[str, dict[str, object]],
    acknowledgment_drift: dict[str, object],
) -> dict[str, object]:
    acknowledgment = copy.deepcopy(ticket_acknowledgment or {})
    paired_summary_json = artifacts.get("paired_summary_json") or {}
    paired_bundle = artifacts.get("paired_bundle") or {}
    paired_summary_md = artifacts.get("paired_summary_md") or {}

    latest_regenerated_candidates = [
        artifact_timestamp(paired_bundle),
        artifact_timestamp(paired_summary_json),
        artifact_timestamp(paired_summary_md),
    ]
    latest_regenerated_at = max((value for value in latest_regenerated_candidates if value is not None), default=None)
    attached_at = parse_iso8601(acknowledgment.get("attached_at"))
    paired_summary_built_at = artifact_timestamp(paired_summary_json)
    paired_bundle_built_at = artifact_timestamp(paired_bundle)

    verdict = "awaiting_acknowledgment"
    summary = "Paired evidence exists but no upload acknowledgment is recorded yet."
    if acknowledgment.get("acknowledged") and acknowledgment_drift.get("stale_after_regeneration"):
        verdict = "regenerated_after_ack"
        summary = "Paired artifacts were regenerated after the recorded upload acknowledgment; review/re-attach is required."
    elif acknowledgment.get("acknowledged"):
        verdict = "current_after_ack"
        summary = "Recorded upload acknowledgment is still current for the visible paired artifacts."

    if not paired_summary_json.get("exists") and not paired_bundle.get("exists"):
        verdict = "artifacts_not_ready"
        summary = "Paired summary/bundle artifacts are not ready yet."

    return {
        "paired_summary_built_at": paired_summary_json.get("modified_at"),
        "paired_bundle_built_at": paired_bundle.get("modified_at"),
        "attached_at": acknowledgment.get("attached_at"),
        "latest_regenerated_at": latest_regenerated_at.isoformat() if latest_regenerated_at is not None else None,
        "summary_after_attach": None,
        "seconds_between_summary_and_bundle": (
            int(round((paired_bundle_built_at - paired_summary_built_at).total_seconds()))
            if paired_summary_built_at is not None and paired_bundle_built_at is not None else None
        ),
        "seconds_between_attach_and_latest_regeneration": (
            int(round((latest_regenerated_at - attached_at).total_seconds()))
            if latest_regenerated_at is not None and attached_at is not None else None
        ),
        "verdict": verdict,
        "summary": summary,
    }


def build_attachment_action_verdict(
    *,
    ready_to_attach: bool,
    acknowledged: bool,
    acknowledgment_current: bool,
    reattach_required: bool,
    reusable_destination: bool,
    missing_required: list[dict[str, object]],
    attach_now_minimal: list[dict[str, object]],
) -> dict[str, object]:
    minimal_keys = [str(item.get("key")) for item in attach_now_minimal if item.get("key")]
    missing_keys = [str(item.get("key")) for item in missing_required if item.get("key")]

    if missing_required:
        verdict = "blocked_missing_required"
        summary = "Required paired handoff artifacts are still missing; do not attach or acknowledge yet."
        operator_action = "Finish the missing required artifacts before shipping."
    elif reattach_required and reusable_destination:
        verdict = "reattach_and_reack_same_destination"
        summary = "Paired artifacts changed after upload; re-attach the refreshed set and re-acknowledge the same stored ticket destination."
        operator_action = "Re-attach the refreshed paired artifacts, then run reacknowledge_drill_handoff.bat."
    elif reattach_required:
        verdict = "reattach_and_reack_with_destination"
        summary = "Paired artifacts changed after upload; re-attach the refreshed set and re-acknowledge with ticket reference or URL."
        operator_action = "Re-attach the refreshed paired artifacts, then re-acknowledge with ticket reference/URL."
    elif ready_to_attach and not acknowledged:
        verdict = "attach_and_acknowledge"
        summary = "Paired handoff artifacts are ready; attach the minimal set and record the upload acknowledgment."
        operator_action = "Attach the paired bundle + handoff manifest, then run acknowledge_drill_handoff.bat."
    elif acknowledged and acknowledgment_current:
        verdict = "current_no_action"
        summary = "Current paired artifacts still match the recorded upload acknowledgment; no re-attach is needed."
        operator_action = "No re-attach needed; keep the recorded acknowledgment as-is."
    elif acknowledged:
        verdict = "acknowledged_review_state"
        summary = "An upload acknowledgment exists, but the current paired artifact state still needs manual review."
        operator_action = "Review the current paired artifacts before deciding whether a new attach/re-ack step is needed."
    else:
        verdict = "awaiting_handoff_readiness"
        summary = "Handoff is not ready yet; finish the paired drill artifacts before any attach/ack step."
        operator_action = "Finish the paired drill outputs and refresh the handoff state."

    return {
        "verdict": verdict,
        "summary": summary,
        "operator_action": operator_action,
        "attach_now_minimal_keys": minimal_keys,
        "missing_required_keys": missing_keys,
        "same_destination_reack_only": bool(reattach_required and reusable_destination),
    }


def build_attachment_readiness(
    *,
    label: str,
    recommendation: dict[str, object],
    freshness: dict[str, object],
    artifacts: dict[str, dict[str, object]],
    ticket_acknowledgment: dict[str, object] | None = None,
) -> dict[str, object]:
    recommended_order = [
        ("paired_bundle", True),
        ("handoff_manifest_md", True),
        ("ticket_comment_txt", False),
        ("paired_summary_md", False),
        ("paired_summary_json", False),
        ("update_bundle", False),
        ("rollback_bundle", False),
    ]
    attach_now: list[dict[str, object]] = []
    missing_required: list[dict[str, object]] = []
    missing_optional: list[dict[str, object]] = []

    for key, required in recommended_order:
        artifact = artifacts.get(key) or {}
        item = {
            "key": key,
            "path": artifact.get("path"),
            "exists": bool(artifact.get("exists")),
            "required": required,
        }
        if item["exists"]:
            attach_now.append(item)
        elif required:
            missing_required.append(item)
        else:
            missing_optional.append(item)

    acknowledgment = copy.deepcopy(ticket_acknowledgment or {})
    acknowledgment_drift = derive_acknowledgment_drift(
        ticket_acknowledgment=acknowledgment,
        artifacts=artifacts,
    )
    fingerprint_summary = build_attachment_fingerprint_summary(
        ticket_acknowledgment=acknowledgment,
        artifacts=artifacts,
    )
    ready_to_attach = (
        recommendation.get("status") == "ship"
        and freshness.get("ok") is True
        and not missing_required
    )
    reattach_required = bool(acknowledgment.get("acknowledged")) and bool(acknowledgment_drift.get("stale_after_regeneration"))
    reattach_targets = [
        item
        for item in attach_now
        if item["key"] in {"paired_bundle", "handoff_manifest_md", "paired_summary_md", "paired_summary_json"}
    ]
    attach_now_minimal = [
        item
        for item in attach_now
        if item["key"] in {"paired_bundle", "handoff_manifest_md"}
    ]
    reattach_reason = None
    if reattach_required:
        changed_keys = [str(item.get("key")) for item in acknowledgment_drift.get("changed_after_ack") or [] if item.get("key")]
        drift_summary = str(acknowledgment_drift.get("drift_summary") or "").strip()
        if changed_keys and drift_summary:
            reattach_reason = (
                "paired artifacts changed after the recorded ticket upload: "
                + ", ".join(changed_keys)
                + f" ({drift_summary})"
            )
        elif changed_keys:
            reattach_reason = "paired artifacts changed after the recorded ticket upload: " + ", ".join(changed_keys)
        elif drift_summary:
            reattach_reason = drift_summary
        else:
            reattach_reason = "paired artifacts changed after the recorded ticket upload"
    reusable_destination = bool((acknowledgment.get("ticket_reference") or acknowledgment.get("ticket_url")))
    reacknowledge_command = None
    if acknowledgment.get("acknowledged"):
        reacknowledge_command = f"app\\bin\\reacknowledge_drill_handoff.bat {label}"
    reacknowledge_command_with_destination = (
        f"app\\bin\\reacknowledge_drill_handoff.bat {label} [attached-by] [ticket-status] [note] [ticket-reference] [ticket-url]"
        if acknowledgment.get("acknowledged") else None
    )
    reacknowledge_blocked_reason = None
    if reattach_required and not reusable_destination:
        reacknowledge_blocked_reason = "Stored ticket destination missing; re-acknowledge needs ticket reference or ticket URL."
    destination_summary = build_attachment_destination_summary(
        ticket_acknowledgment=acknowledgment,
        reattach_required=reattach_required,
        reusable_destination=reusable_destination,
    )
    attachment_timeline = build_attachment_timeline(
        ticket_acknowledgment=acknowledgment,
        artifacts=artifacts,
        acknowledgment_drift=acknowledgment_drift,
    )
    if attachment_timeline.get("attached_at") and attachment_timeline.get("latest_regenerated_at"):
        delta_seconds = attachment_timeline.get("seconds_between_attach_and_latest_regeneration")
        if isinstance(delta_seconds, int):
            if delta_seconds > 0:
                attachment_timeline["summary_after_attach"] = f"latest paired regeneration happened {delta_seconds} seconds after the recorded upload acknowledgment"
            elif delta_seconds == 0:
                attachment_timeline["summary_after_attach"] = "latest paired regeneration timestamp matches the recorded upload acknowledgment"
            else:
                attachment_timeline["summary_after_attach"] = f"latest paired regeneration predates the recorded upload acknowledgment by {abs(delta_seconds)} seconds"
    elif attachment_timeline.get("attached_at"):
        attachment_timeline["summary_after_attach"] = "upload acknowledgment is recorded, but no paired regeneration timestamp is available yet"

    action_verdict = build_attachment_action_verdict(
        ready_to_attach=ready_to_attach,
        acknowledged=bool(acknowledgment.get("acknowledged")),
        acknowledgment_current=bool(acknowledgment_drift.get("current")),
        reattach_required=reattach_required,
        reusable_destination=reusable_destination,
        missing_required=missing_required,
        attach_now_minimal=attach_now_minimal,
    )

    return {
        "ready_to_attach": ready_to_attach,
        "acknowledged": bool(acknowledgment.get("acknowledged")),
        "acknowledgment_current": bool(acknowledgment_drift.get("current")),
        "acknowledgment_drift": acknowledgment_drift,
        "fingerprint_summary": fingerprint_summary,
        "attachment_timeline": attachment_timeline,
        "reattach_required": reattach_required,
        "reattach_reason": reattach_reason,
        "reattach_targets": reattach_targets,
        "reacknowledge_ready": bool(acknowledgment.get("acknowledged")),
        "reacknowledge_destination_ready": reusable_destination,
        "reacknowledge_command": reacknowledge_command,
        "reacknowledge_command_with_destination": reacknowledge_command_with_destination,
        "reacknowledge_blocked_reason": reacknowledge_blocked_reason,
        "destination_summary": destination_summary,
        "action_verdict": action_verdict,
        "attach_now": attach_now,
        "attach_now_minimal": attach_now_minimal,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "required_keys": [key for key, required in recommended_order if required],
        "ticket_acknowledgment": acknowledgment,
    }


def summarize_acknowledgment_history(ticket_acknowledgment_history: list[dict[str, object]] | None = None) -> dict[str, object]:
    history = [copy.deepcopy(item) for item in (ticket_acknowledgment_history or []) if isinstance(item, dict)]
    latest = copy.deepcopy(history[-1]) if history else None
    initial = copy.deepcopy(history[0]) if history else None
    reacknowledge_count = sum(1 for item in history if str(item.get("event") or "") == "reacknowledge")
    destination_change_count = sum(1 for item in history if item.get("destination_changed") is True)
    latest_change_summary = str(latest.get("change_summary") or "").strip() if latest else None

    destination_relation_counts = {
        "initial_acknowledgment": 0,
        "same_destination_reused": 0,
        "destination_changed": 0,
        "destination_first_recorded_on_reack": 0,
        "destination_cleared": 0,
        "no_destination_to_compare": 0,
        "unknown": 0,
    }

    latest_destination_relation = None
    latest_destination_relation_summary = None
    latest_destination_display = str(latest.get("ticket_destination_display") or "").strip() if latest else None
    previous_destination_display = str(latest.get("previous_ticket_destination_display") or "").strip() if latest else None
    if latest:
        latest_event = str(latest.get("event") or "").strip() or None
        destination_changed = latest.get("destination_changed") is True
        if latest_event == "acknowledge":
            latest_destination_relation = "initial_acknowledgment"
            latest_destination_relation_summary = "Initial upload acknowledgment recorded the first visible ticket destination state."
        elif destination_changed:
            latest_destination_relation = "destination_changed"
            latest_destination_relation_summary = (
                f"Latest re-ack changed the ticket destination from {previous_destination_display or '-'} to {latest_destination_display or '-'}"
            )
        elif previous_destination_display and latest_destination_display and previous_destination_display == latest_destination_display:
            latest_destination_relation = "same_destination_reused"
            latest_destination_relation_summary = (
                f"Latest re-ack reused the same stored ticket destination: {latest_destination_display}"
            )
        elif latest_destination_display and not previous_destination_display:
            latest_destination_relation = "destination_first_recorded_on_reack"
            latest_destination_relation_summary = (
                f"Latest re-ack recorded a ticket destination for the first time: {latest_destination_display}"
            )
        elif not latest_destination_display and previous_destination_display:
            latest_destination_relation = "destination_cleared"
            latest_destination_relation_summary = (
                f"Latest re-ack no longer shows the previously recorded ticket destination: {previous_destination_display}"
            )
        elif latest_event == "reacknowledge":
            latest_destination_relation = "no_destination_to_compare"
            latest_destination_relation_summary = "Latest re-ack has no ticket destination context to compare."
        else:
            latest_destination_relation = "unknown"
            latest_destination_relation_summary = "Latest acknowledgment destination relation is not classified."

    for item in history:
        item_event = str(item.get("event") or "").strip() or None
        item_destination = str(item.get("ticket_destination_display") or "").strip() or None
        item_previous_destination = str(item.get("previous_ticket_destination_display") or "").strip() or None
        item_destination_changed = item.get("destination_changed") is True
        if item_event == "acknowledge":
            relation = "initial_acknowledgment"
        elif item_destination_changed:
            relation = "destination_changed"
        elif item_previous_destination and item_destination and item_previous_destination == item_destination:
            relation = "same_destination_reused"
        elif item_destination and not item_previous_destination:
            relation = "destination_first_recorded_on_reack"
        elif not item_destination and item_previous_destination:
            relation = "destination_cleared"
        elif item_event == "reacknowledge":
            relation = "no_destination_to_compare"
        else:
            relation = "unknown"
        destination_relation_counts[relation] = destination_relation_counts.get(relation, 0) + 1

    latest_is_only_destination_change = bool(destination_change_count == 1 and latest_destination_relation == "destination_changed")
    if not history:
        destination_history_pattern = {
            "verdict": "no_history",
            "summary": "No acknowledgment history recorded yet.",
            "latest_is_only_destination_change": False,
        }
    elif destination_change_count == 0 and destination_relation_counts.get("same_destination_reused", 0) > 0:
        destination_history_pattern = {
            "verdict": "same_destination_reuse_only",
            "summary": "Visible acknowledgment history only shows same-destination reuse; no ticket-destination change is recorded.",
            "latest_is_only_destination_change": False,
        }
    elif latest_is_only_destination_change:
        destination_history_pattern = {
            "verdict": "latest_is_only_destination_change",
            "summary": "The latest visible acknowledgment is the only recorded ticket-destination change in the current history.",
            "latest_is_only_destination_change": True,
        }
    elif destination_change_count > 1 and latest_destination_relation == "destination_changed":
        destination_history_pattern = {
            "verdict": "latest_is_one_of_multiple_destination_changes",
            "summary": f"The latest visible acknowledgment changed ticket destination again; {destination_change_count} destination-change events are recorded in the current history.",
            "latest_is_only_destination_change": False,
        }
    elif destination_change_count > 0:
        destination_history_pattern = {
            "verdict": "historical_destination_change_present",
            "summary": f"Ticket-destination change exists in the current history ({destination_change_count} event(s)), but the latest visible acknowledgment is not itself a destination-change event.",
            "latest_is_only_destination_change": False,
        }
    else:
        destination_history_pattern = {
            "verdict": "no_destination_change_recorded",
            "summary": "No ticket-destination change is recorded in the current acknowledgment history.",
            "latest_is_only_destination_change": False,
        }

    return {
        "count": len(history),
        "reacknowledge_count": reacknowledge_count,
        "has_reacknowledgment": reacknowledge_count > 0,
        "destination_change_count": destination_change_count,
        "destination_relation_counts": destination_relation_counts,
        "same_destination_reuse_count": destination_relation_counts.get("same_destination_reused", 0),
        "latest_event": latest.get("event") if latest else None,
        "latest_attached_at": latest.get("attached_at") if latest else None,
        "initial_attached_at": initial.get("attached_at") if initial else None,
        "latest_change_summary": latest_change_summary or None,
        "latest_destination_relation": latest_destination_relation,
        "latest_destination_relation_summary": latest_destination_relation_summary,
        "destination_history_pattern": destination_history_pattern,
        "latest_destination_display": latest_destination_display or None,
        "previous_destination_display": previous_destination_display or None,
        "history": history,
        "summary": (
            f"{len(history)} acknowledgment event(s) recorded; latest event={latest.get('event')}; destination relation={latest_destination_relation or 'n/a'}; latest change={latest_change_summary or 'n/a'}"
            if latest else
            "No acknowledgment history recorded yet."
        ),
    }


def build_attachment_review_summary(
    *,
    label: str,
    recommendation: dict[str, object],
    freshness: dict[str, object],
    artifacts: dict[str, dict[str, object]],
    ticket_acknowledgment: dict[str, object] | None = None,
    ticket_acknowledgment_history: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    attachment_readiness = build_attachment_readiness(
        label=label,
        recommendation=recommendation,
        freshness=freshness,
        artifacts=artifacts,
        ticket_acknowledgment=ticket_acknowledgment,
    )
    destination_summary = attachment_readiness.get("destination_summary") or {}
    fingerprint_summary = attachment_readiness.get("fingerprint_summary") or {}
    attachment_timeline = attachment_readiness.get("attachment_timeline") or {}
    action_verdict = attachment_readiness.get("action_verdict") or {}
    acknowledgment = attachment_readiness.get("ticket_acknowledgment") or {}
    acknowledgment_history = summarize_acknowledgment_history(ticket_acknowledgment_history)

    next_operator_step = str(action_verdict.get("operator_action") or "attach paired bundle + handoff manifest")

    plain_lines = [
        f"Runtime attachment review: {label}",
        f"- recommendation: {recommendation.get('status')}",
        f"- attachment_ready: {attachment_readiness.get('ready_to_attach')}",
        f"- attachment_acknowledged: {attachment_readiness.get('acknowledged')}",
        f"- acknowledgment_current: {attachment_readiness.get('acknowledgment_current')}",
        f"- destination_status: {destination_summary.get('verdict')}",
        f"- destination_display: {destination_summary.get('display')}",
        f"- action_verdict: {action_verdict.get('verdict')}",
        f"- action_summary: {action_verdict.get('summary')}",
        f"- fingerprint_status: {fingerprint_summary.get('verdict')}",
        f"- fingerprint_diff: {fingerprint_summary.get('mismatch_summary')}",
        f"- drift_status: {(attachment_readiness.get('acknowledgment_drift') or {}).get('drift_verdict')}",
        f"- drift_summary: {(attachment_readiness.get('acknowledgment_drift') or {}).get('drift_summary')}",
        f"- timeline_status: {attachment_timeline.get('verdict')}",
        f"- timeline_summary: {attachment_timeline.get('summary')}",
        f"- acknowledgment_history_count: {acknowledgment_history.get('count')}",
        f"- reacknowledgment_count: {acknowledgment_history.get('reacknowledge_count')}",
        f"- destination_change_count: {acknowledgment_history.get('destination_change_count')}",
        f"- same_destination_reuse_count: {acknowledgment_history.get('same_destination_reuse_count')}",
        f"- latest_ack_event: {acknowledgment_history.get('latest_event')}",
        f"- latest_ack_change: {acknowledgment_history.get('latest_change_summary') or '-'}",
        f"- latest_destination_relation: {acknowledgment_history.get('latest_destination_relation') or '-'}",
        f"- latest_destination_relation_summary: {acknowledgment_history.get('latest_destination_relation_summary') or '-'}",
        f"- destination_history_pattern: {(acknowledgment_history.get('destination_history_pattern') or {}).get('verdict') or '-'}",
        f"- destination_history_pattern_summary: {(acknowledgment_history.get('destination_history_pattern') or {}).get('summary') or '-'}",
        f"- next_step: {next_operator_step}",
    ]

    if acknowledgment.get("acknowledged"):
        plain_lines.extend([
            f"- attached_by: {acknowledgment.get('attached_by') or '-'}",
            f"- attached_at: {acknowledgment.get('attached_at') or '-'}",
            f"- ticket_status: {acknowledgment.get('ticket_status') or '-'}",
        ])
    plain_lines.extend([
        f"- paired_summary_built_at: {attachment_timeline.get('paired_summary_built_at') or '-'}",
        f"- paired_bundle_built_at: {attachment_timeline.get('paired_bundle_built_at') or '-'}",
        f"- latest_regenerated_at: {attachment_timeline.get('latest_regenerated_at') or '-'}",
    ])
    if attachment_timeline.get("summary_after_attach"):
        plain_lines.append(f"- attach_timing: {attachment_timeline.get('summary_after_attach')}")
    if attachment_readiness.get("attach_now_minimal"):
        plain_lines.append("attach_now_minimal:")
        plain_lines.extend(
            f"- {item['key']}: {item['path']}" for item in attachment_readiness["attach_now_minimal"]
        )
    if attachment_readiness.get("reattach_required"):
        plain_lines.append("reattach_now:")
        plain_lines.append(f"- reason: {attachment_readiness.get('reattach_reason') or '-'}")
        for item in attachment_readiness.get("reattach_targets") or []:
            plain_lines.append(f"- {item['key']}: {item['path']}")
        if attachment_readiness.get("reacknowledge_command"):
            plain_lines.append(f"- reacknowledge_helper: {attachment_readiness['reacknowledge_command']}")
        if attachment_readiness.get("reacknowledge_blocked_reason"):
            plain_lines.append(f"- blocked_reason: {attachment_readiness['reacknowledge_blocked_reason']}")
        if attachment_readiness.get("reacknowledge_command_with_destination"):
            plain_lines.append(f"- reacknowledge_with_destination: {attachment_readiness['reacknowledge_command_with_destination']}")
    if attachment_readiness.get("missing_required"):
        plain_lines.append("missing_before_ship:")
        plain_lines.extend(f"- {item['key']}" for item in attachment_readiness["missing_required"])

    return {
        "label": label,
        "recommendation_status": recommendation.get("status"),
        "freshness_ok": freshness.get("ok"),
        "next_operator_step": next_operator_step,
        "destination_summary": destination_summary,
        "fingerprint_summary": fingerprint_summary,
        "attachment_timeline": attachment_timeline,
        "acknowledgment_history": acknowledgment_history,
        "attachment_readiness": attachment_readiness,
        "plain_text": "\n".join(plain_lines) + "\n",
    }


def persist_attachment_review_summary(
    root: Path,
    *,
    label: str,
    recommendation: dict[str, object],
    freshness: dict[str, object],
    artifacts: dict[str, dict[str, object]],
    ticket_acknowledgment: dict[str, object] | None = None,
    ticket_acknowledgment_history: list[dict[str, object]] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    workspace = get_drill_workspace(root, label)
    review = build_attachment_review_summary(
        label=label,
        recommendation=recommendation,
        freshness=freshness,
        artifacts=artifacts,
        ticket_acknowledgment=ticket_acknowledgment,
        ticket_acknowledgment_history=ticket_acknowledgment_history,
    )
    review_payload = copy.deepcopy(review)
    review_payload["exported_at"] = datetime.now(timezone.utc).isoformat()
    review_payload["review_json_path"] = str(workspace["attachment_review_json"].resolve())
    review_payload["review_txt_path"] = str(workspace["attachment_review_txt"].resolve())
    review_payload["contract"] = {
        "schema": "runtime_attachment_review_v1",
        "detail_level": "reviewer_safe",
    }
    if not dry_run:
        write_json(workspace["attachment_review_json"], review_payload)
        workspace["attachment_review_txt"].write_text(review["plain_text"], encoding="utf-8")
    return review_payload


def build_ticket_comment_payload(
    *,
    label: str,
    drill_context: dict[str, str],
    recommendation: dict[str, object],
    freshness: dict[str, object],
    artifacts: dict[str, dict[str, object]],
    handoff_manifest: dict[str, object],
    ticket_acknowledgment: dict[str, object] | None = None,
    ticket_acknowledgment_history: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    attachment_readiness = build_attachment_readiness(
        label=label,
        recommendation=recommendation,
        freshness=freshness,
        artifacts=artifacts,
        ticket_acknowledgment=ticket_acknowledgment,
    )
    attachment_candidates: list[dict[str, object]] = []
    for key in ["paired_bundle", "handoff_manifest_md", "ticket_comment_txt", "paired_summary_md", "paired_summary_json", "update_bundle", "rollback_bundle"]:
        artifact = artifacts.get(key) or {}
        if artifact.get("exists"):
            attachment_candidates.append({
                "key": key,
                "path": artifact.get("path"),
                "size_bytes": artifact.get("size_bytes"),
                "modified_at": artifact.get("modified_at"),
            })

    headline = f"[{str(recommendation.get('status') or 'needs_manual_review').upper()}] Runtime closed-loop drill {label}"
    if drill_context.get("device_id"):
        headline += f" on {drill_context['device_id']}"

    summary_bits = [
        f"recommendation={recommendation.get('status')}",
        f"closed_loop_passed={handoff_manifest.get('closed_loop_passed')}",
        f"rollback_restored={handoff_manifest.get('rollback_restored_start_version')}",
        f"freshness_ok={freshness.get('ok')}",
        f"checklist_complete={handoff_manifest.get('complete')}",
    ]
    if drill_context.get("service_ticket"):
        summary_bits.append(f"ticket={drill_context['service_ticket']}")

    reasons = [str(item) for item in (recommendation.get("reasons") or []) if str(item).strip()]
    warnings = [str(item) for item in (freshness.get("warnings") or []) if str(item).strip()]
    ticket_ack = attachment_readiness.get("ticket_acknowledgment") or {}
    acknowledgment_history = summarize_acknowledgment_history(ticket_acknowledgment_history)

    plain_lines = [
        headline,
        " ".join(summary_bits),
        f"operator_action: {recommendation.get('operator_action')}",
        f"attachment_ready: {attachment_readiness['ready_to_attach']}",
        f"attachment_acknowledged: {attachment_readiness['acknowledged']}",
        f"acknowledgment_history_count: {acknowledgment_history.get('count')}",
        f"reacknowledgment_count: {acknowledgment_history.get('reacknowledge_count')}",
        f"latest_destination_relation: {acknowledgment_history.get('latest_destination_relation') or '-'}",
    ]
    if drill_context.get("notes"):
        plain_lines.extend([
            "operator_notes:",
            f"- {drill_context['notes']}",
        ])
    destination_summary = attachment_readiness.get("destination_summary") or {}
    attachment_timeline = attachment_readiness.get("attachment_timeline") or {}
    action_verdict = attachment_readiness.get("action_verdict") or {}
    plain_lines.extend([
        "ticket_destination_summary:",
        f"- status: {destination_summary.get('verdict')}",
        f"- summary: {destination_summary.get('verdict_text')}",
        f"- stored_destination_ready: {destination_summary.get('stored_destination_ready')}",
        f"- destination_kind: {destination_summary.get('kind')}",
        f"- destination_display: {destination_summary.get('display')}",
        "attachment_action_verdict:",
        f"- status: {action_verdict.get('verdict')}",
        f"- summary: {action_verdict.get('summary')}",
        f"- operator_action: {action_verdict.get('operator_action')}",
    ])
    if ticket_ack.get("acknowledged"):
        plain_lines.extend([
            "ticket_attachment_acknowledgment:",
            f"- attached_by: {ticket_ack.get('attached_by') or '-'}",
            f"- attached_at: {ticket_ack.get('attached_at') or '-'}",
            f"- ticket_status: {ticket_ack.get('ticket_status') or '-'}",
            f"- ticket_reference: {ticket_ack.get('ticket_reference') or '-'}",
            f"- ticket_url: {ticket_ack.get('ticket_url') or '-'}",
            f"- note: {ticket_ack.get('note') or '-'}",
            f"- current: {attachment_readiness.get('acknowledgment_current')}",
        ])
    plain_lines.extend([
        "acknowledgment_history_summary:",
        f"- count: {acknowledgment_history.get('count')}",
        f"- reacknowledgments: {acknowledgment_history.get('reacknowledge_count')}",
        f"- destination_changes: {acknowledgment_history.get('destination_change_count')}",
        f"- destination_history_pattern: {(acknowledgment_history.get('destination_history_pattern') or {}).get('verdict') or '-'}",
        f"- destination_history_pattern_summary: {(acknowledgment_history.get('destination_history_pattern') or {}).get('summary') or '-'}",
        f"- latest_event: {acknowledgment_history.get('latest_event') or '-'}",
        f"- latest_change: {acknowledgment_history.get('latest_change_summary') or '-'}",
        f"- latest_destination_relation: {acknowledgment_history.get('latest_destination_relation') or '-'}",
        f"- latest_destination_relation_summary: {acknowledgment_history.get('latest_destination_relation_summary') or '-'}",
        f"- summary: {acknowledgment_history.get('summary')}",
    ])
    ack_drift = attachment_readiness.get("acknowledgment_drift") or {}
    plain_lines.extend([
        "acknowledgment_drift_summary:",
        f"- status: {ack_drift.get('drift_verdict')}",
        f"- summary: {ack_drift.get('drift_summary')}",
    ])
    plain_lines.extend([
        "attachment_timeline_summary:",
        f"- status: {attachment_timeline.get('verdict')}",
        f"- summary: {attachment_timeline.get('summary')}",
        f"- paired_summary_built_at: {attachment_timeline.get('paired_summary_built_at') or '-'}",
        f"- paired_bundle_built_at: {attachment_timeline.get('paired_bundle_built_at') or '-'}",
        f"- latest_regenerated_at: {attachment_timeline.get('latest_regenerated_at') or '-'}",
        f"- attached_at: {attachment_timeline.get('attached_at') or '-'}",
    ])
    if attachment_timeline.get("summary_after_attach"):
        plain_lines.append(f"- attach_timing: {attachment_timeline.get('summary_after_attach')}")
    if ack_drift.get("warnings"):
        plain_lines.append("acknowledgment_drift_warnings:")
        plain_lines.extend(f"- {warning}" for warning in ack_drift["warnings"])
    if attachment_readiness.get("reattach_required"):
        plain_lines.extend([
            "reattach_now:",
            f"- required: {attachment_readiness.get('reattach_required')}",
            f"- reason: {attachment_readiness.get('reattach_reason') or '-'}",
            f"- stored_destination_ready: {attachment_readiness.get('reacknowledge_destination_ready')}",
        ])
        if attachment_readiness.get("reacknowledge_blocked_reason"):
            plain_lines.append(f"- blocked_reason: {attachment_readiness['reacknowledge_blocked_reason']}")
        targets = attachment_readiness.get("reattach_targets") or []
        if targets:
            plain_lines.extend(f"- {item['key']}: {item['path']}" for item in targets)
        if attachment_readiness.get("reacknowledge_command"):
            plain_lines.append(f"- reacknowledge_helper: {attachment_readiness['reacknowledge_command']}")
        if attachment_readiness.get("reacknowledge_blocked_reason") and attachment_readiness.get("reacknowledge_command_with_destination"):
            plain_lines.append(f"- reacknowledge_with_destination: {attachment_readiness['reacknowledge_command_with_destination']}")
    fingerprint_summary = attachment_readiness.get("fingerprint_summary") or {}
    plain_lines.extend([
        "attachment_fingerprint_verdict:",
        f"- status: {fingerprint_summary.get('verdict')}",
        f"- summary: {fingerprint_summary.get('verdict_text')}",
        f"- diff: {fingerprint_summary.get('mismatch_summary')}",
    ])
    if fingerprint_summary.get("warnings"):
        plain_lines.append("attachment_fingerprint_warnings:")
        plain_lines.extend(f"- {warning}" for warning in fingerprint_summary["warnings"])
    plain_lines.append("attachment_fingerprints_current:")
    current_fingerprints = (fingerprint_summary.get("current") or {}).get("items") or []
    if current_fingerprints:
        plain_lines.extend(
            f"- {item['key']}: sha256={item.get('sha256_short') or '-'} size={item.get('size_bytes')} modified_at={item.get('modified_at') or '-'}"
            for item in current_fingerprints
        )
    else:
        plain_lines.append("- none")
    if ticket_ack.get("acknowledged"):
        plain_lines.append("attachment_fingerprints_acknowledged:")
        acknowledged_fingerprints = (fingerprint_summary.get("acknowledged") or {}).get("items") or []
        if acknowledged_fingerprints:
            plain_lines.extend(
                f"- {item['key']}: sha256={item.get('sha256_short') or '-'} size={item.get('size_bytes')} modified_at={item.get('modified_at') or '-'}"
                for item in acknowledged_fingerprints
            )
        else:
            plain_lines.append("- unavailable")
    if reasons:
        plain_lines.append("reasons:")
        plain_lines.extend(f"- {reason}" for reason in reasons)
    if warnings:
        plain_lines.append("freshness_warnings:")
        plain_lines.extend(f"- {warning}" for warning in warnings)
    plain_lines.append("attachments:")
    if attachment_candidates:
        plain_lines.extend(f"- {item['key']}: {item['path']}" for item in attachment_candidates)
    else:
        plain_lines.append("- none ready yet")
    plain_lines.append("attach_now_minimal:")
    if attachment_readiness["attach_now_minimal"]:
        plain_lines.extend(f"- {item['key']}: {item['path']}" for item in attachment_readiness["attach_now_minimal"])
    else:
        plain_lines.append("- none")
    plain_lines.append("attach_now:")
    if attachment_readiness["attach_now"]:
        plain_lines.extend(f"- {item['key']}: {item['path']}" for item in attachment_readiness["attach_now"])
    else:
        plain_lines.append("- none")
    plain_lines.append("missing_before_ship:")
    if attachment_readiness["missing_required"]:
        plain_lines.extend(f"- {item['key']}" for item in attachment_readiness["missing_required"])
    else:
        plain_lines.append("- none")
    plain_lines.append(f"handoff_manifest: {artifacts['handoff_manifest_md']['path']}")

    md_lines = [
        f"# Runtime Drill Ticket Comment — {label}",
        "",
        headline,
        "",
        f"- Recommendation: `{recommendation.get('status')}`",
        f"- Closed-loop passed: `{handoff_manifest.get('closed_loop_passed')}`",
        f"- Rollback restored start version: `{handoff_manifest.get('rollback_restored_start_version')}`",
        f"- Freshness OK: `{'yes' if freshness.get('ok') else 'no'}`",
        f"- Checklist complete: `{'yes' if handoff_manifest.get('complete') else 'no'}`",
        f"- Attachment ready: `{'yes' if attachment_readiness['ready_to_attach'] else 'no'}`",
        f"- Attachment acknowledged: `{'yes' if attachment_readiness['acknowledged'] else 'no'}`",
        f"- Acknowledgment current: `{'yes' if attachment_readiness['acknowledgment_current'] else 'no'}`",
        f"- Acknowledgment history count: `{acknowledgment_history.get('count')}`",
        f"- Re-acknowledgments recorded: `{acknowledgment_history.get('reacknowledge_count')}`",
        f"- Destination changes recorded: `{acknowledgment_history.get('destination_change_count')}`",
        f"- Destination history pattern: `{(acknowledgment_history.get('destination_history_pattern') or {}).get('verdict') or '-'}` — {(acknowledgment_history.get('destination_history_pattern') or {}).get('summary') or '-'}",
        f"- Latest acknowledgment change: {acknowledgment_history.get('latest_change_summary') or '-'}",
        f"- Latest destination relation: `{acknowledgment_history.get('latest_destination_relation') or '-'}` — {acknowledgment_history.get('latest_destination_relation_summary') or '-'}",
        f"- Ticket destination: `{destination_summary.get('display') or '-'}`",
        f"- Ticket destination status: `{destination_summary.get('verdict')}` — {destination_summary.get('verdict_text')}",
        f"- Attachment action verdict: `{action_verdict.get('verdict')}` — {action_verdict.get('summary')}",
        f"- Acknowledgment history summary: `{acknowledgment_history.get('summary')}`",
    ]
    for key in ["device_id", "operator", "service_ticket"]:
        if drill_context.get(key):
            md_lines.append(f"- {key.replace('_', ' ').title()}: `{drill_context[key]}`")
    if drill_context.get("notes"):
        md_lines.append(f"- Operator notes: {drill_context['notes']}")
    if ticket_ack.get("acknowledged"):
        md_lines.extend([
            f"- Attached by: `{ticket_ack.get('attached_by') or '-'}`",
            f"- Attached at: `{ticket_ack.get('attached_at') or '-'}`",
            f"- Ticket status: `{ticket_ack.get('ticket_status') or '-'}`",
            f"- Ticket reference: `{ticket_ack.get('ticket_reference') or '-'}`",
            f"- Ticket URL: `{ticket_ack.get('ticket_url') or '-'}`",
            f"- Acknowledgment current: `{'yes' if attachment_readiness['acknowledgment_current'] else 'no'}`",
        ])
        if ticket_ack.get("note"):
            md_lines.append(f"- Attachment note: {ticket_ack['note']}")
    ack_drift = attachment_readiness.get("acknowledgment_drift") or {}
    md_lines.extend([
        "",
        "## Acknowledgment drift summary",
        "",
        f"- Status: `{ack_drift.get('drift_verdict')}`",
        f"- Summary: {ack_drift.get('drift_summary')}",
    ])
    md_lines.extend([
        "",
        "## Attachment timeline",
        "",
        f"- Status: `{attachment_timeline.get('verdict')}`",
        f"- Summary: {attachment_timeline.get('summary')}",
        f"- Paired summary built at: `{attachment_timeline.get('paired_summary_built_at') or '-'}`",
        f"- Paired bundle built at: `{attachment_timeline.get('paired_bundle_built_at') or '-'}`",
        f"- Latest regenerated at: `{attachment_timeline.get('latest_regenerated_at') or '-'}`",
        f"- Attached at: `{attachment_timeline.get('attached_at') or '-'}`",
    ])
    if attachment_timeline.get("summary_after_attach"):
        md_lines.append(f"- Attach timing: {attachment_timeline.get('summary_after_attach')}")
    if ack_drift.get("warnings"):
        md_lines.extend(["", "## Acknowledgment drift warnings", ""])
        md_lines.extend(f"- {warning}" for warning in ack_drift["warnings"])
    if attachment_readiness.get("reattach_required"):
        md_lines.extend(["", "## Re-attach now", ""])
        md_lines.append(f"- Required: `{'yes' if attachment_readiness['reattach_required'] else 'no'}`")
        md_lines.append(f"- Reason: {attachment_readiness.get('reattach_reason') or '-'}")
        md_lines.append(f"- Stored destination ready: `{'yes' if attachment_readiness.get('reacknowledge_destination_ready') else 'no'}`")
        if attachment_readiness.get("reacknowledge_blocked_reason"):
            md_lines.append(f"- Blocked reason: {attachment_readiness['reacknowledge_blocked_reason']}")
        targets = attachment_readiness.get("reattach_targets") or []
        if targets:
            md_lines.extend(f"- `{item['key']}` — `{item['path']}`" for item in targets)
        if attachment_readiness.get("reacknowledge_command"):
            md_lines.append(f"- Re-acknowledge helper: `{attachment_readiness['reacknowledge_command']}`")
        if attachment_readiness.get("reacknowledge_blocked_reason") and attachment_readiness.get("reacknowledge_command_with_destination"):
            md_lines.append(f"- Re-acknowledge with destination: `{attachment_readiness['reacknowledge_command_with_destination']}`")
    fingerprint_summary = attachment_readiness.get("fingerprint_summary") or {}
    md_lines.extend([
        "",
        "## Attachment fingerprint verdict",
        "",
        f"- Status: `{fingerprint_summary.get('verdict')}`",
        f"- Summary: {fingerprint_summary.get('verdict_text')}",
        f"- Diff: {fingerprint_summary.get('mismatch_summary')}",
    ])
    if fingerprint_summary.get("warnings"):
        md_lines.extend(["", "## Attachment fingerprint warnings", ""])
        md_lines.extend(f"- {warning}" for warning in fingerprint_summary["warnings"])
    md_lines.extend(["", "## Attachment fingerprints (current)", ""])
    current_fingerprints = (fingerprint_summary.get("current") or {}).get("items") or []
    if current_fingerprints:
        md_lines.extend(
            f"- `{item['key']}` — sha256 `{item.get('sha256_short') or '-'}` — `{item.get('size_bytes')}` bytes — `{item.get('modified_at') or '-'}`"
            for item in current_fingerprints
        )
    else:
        md_lines.append("- none")
    if ticket_ack.get("acknowledged"):
        md_lines.extend(["", "## Attachment fingerprints (acknowledged snapshot)", ""])
        acknowledged_fingerprints = (fingerprint_summary.get("acknowledged") or {}).get("items") or []
        if acknowledged_fingerprints:
            md_lines.extend(
                f"- `{item['key']}` — sha256 `{item.get('sha256_short') or '-'}` — `{item.get('size_bytes')}` bytes — `{item.get('modified_at') or '-'}`"
                for item in acknowledged_fingerprints
            )
        else:
            md_lines.append("- unavailable")
    md_lines.extend(["", "## Operator action", "", str(recommendation.get("operator_action") or "")])
    if reasons:
        md_lines.extend(["", "## Reasons", ""])
        md_lines.extend(f"- {reason}" for reason in reasons)
    if warnings:
        md_lines.extend(["", "## Freshness warnings", ""])
        md_lines.extend(f"- {warning}" for warning in warnings)
    md_lines.extend(["", "## Suggested attachments", ""])
    if attachment_candidates:
        md_lines.extend(f"- `{item['key']}` — `{item['path']}`" for item in attachment_candidates)
    else:
        md_lines.append("- none ready yet")
    md_lines.extend(["", "## Attach now (minimal)", ""])
    if attachment_readiness["attach_now_minimal"]:
        md_lines.extend(f"- `{item['key']}` — `{item['path']}`" for item in attachment_readiness["attach_now_minimal"])
    else:
        md_lines.append("- none")
    md_lines.extend(["", "## Attach now (full)", ""])
    if attachment_readiness["attach_now"]:
        md_lines.extend(f"- `{item['key']}` — `{item['path']}`" for item in attachment_readiness["attach_now"])
    else:
        md_lines.append("- none")
    md_lines.extend(["", "## Missing before ship", ""])
    if attachment_readiness["missing_required"]:
        md_lines.extend(f"- `{item['key']}`" for item in attachment_readiness["missing_required"])
    else:
        md_lines.append("- none")
    md_lines.extend(["", "## Source handoff docs", "", f"- `{artifacts['handoff_manifest_md']['path']}`", f"- `{artifacts['handoff_manifest_json']['path']}`", ""])

    return {
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "headline": headline,
        "recommendation": copy.deepcopy(recommendation),
        "drill_context": copy.deepcopy(drill_context),
        "freshness": {
            "ok": freshness.get("ok"),
            "warnings": warnings,
        },
        "acknowledgment_history": acknowledgment_history,
        "attachment_readiness": attachment_readiness,
        "attachments": attachment_candidates,
        "handoff_manifest_paths": {
            "markdown": artifacts["handoff_manifest_md"]["path"],
            "json": artifacts["handoff_manifest_json"]["path"],
        },
        "plain_text": "\n".join(plain_lines) + "\n",
        "markdown": "\n".join(md_lines) + "\n",
    }


def build_handoff_recommendation(*, complete: bool, next_step: str, paired_json: dict[str, object], artifacts: dict[str, dict[str, object]], freshness: dict[str, object]) -> dict[str, object]:
    closed_loop_passed = paired_json.get("closed_loop_passed") is True
    rollback_restored = paired_json.get("rollback_restored_start_version") is True

    freshness_warnings = list(freshness.get("warnings") or [])
    freshness_ok = freshness.get("ok") is True

    if not freshness_ok and artifacts["paired_summary_json"]["exists"]:
        reasons = list(freshness_warnings) or ["paired drill artifacts are stale or timestamp-misaligned"]
        return {
            "status": "needs_manual_review",
            "summary": "Closed-loop evidence exists, but artifact freshness/timestamp alignment needs review.",
            "reasons": reasons,
            "operator_action": "Refresh the paired summary/bundle or confirm the older artifacts are still the intended handoff set before shipping.",
        }

    if closed_loop_passed and rollback_restored and complete:
        return {
            "status": "ship",
            "summary": "Closed-loop drill passed and rollback restored the starting version.",
            "reasons": [
                "update and rollback leg summaries both passed",
                "paired summary confirms rollback restored the starting version",
                "all expected drill artifacts are present",
            ],
            "operator_action": "Attach the paired support bundle and handoff manifest to the service ticket.",
        }

    if artifacts["paired_summary_json"]["exists"] and (not closed_loop_passed or not rollback_restored):
        reasons: list[str] = []
        if not closed_loop_passed:
            reasons.append("paired summary did not pass the closed loop")
        if not rollback_restored:
            reasons.append("rollback did not restore the starting version")
        return {
            "status": "retry_rollback",
            "summary": "Closed-loop evidence exists, but rollback recovery is not yet clean.",
            "reasons": reasons,
            "operator_action": "Review the paired summary and rollback evidence before attempting another rollback or escalation.",
        }

    reasons = []
    if not complete:
        reasons.append(f"missing required artifact for next step: {next_step}")
    if not artifacts["paired_summary_json"]["exists"]:
        reasons.append("paired summary not built yet")
    if not artifacts["paired_bundle"]["exists"]:
        reasons.append("paired support bundle not built yet")
    return {
        "status": "needs_manual_review",
        "summary": "Drill handoff is still incomplete or awaiting final closed-loop evidence.",
        "reasons": reasons,
        "operator_action": "Finish the next missing step and refresh the paired summary/bundle before handing off.",
    }


def refresh_drill_workspace_status(root: Path, *, label: str, dry_run: bool = False) -> dict:
    paths = get_drill_workspace(root, label)
    checklist_path = paths["checklist_json"]
    if checklist_path.exists():
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        drill_context = checklist.get("drill_context") or {}
        created_at = checklist.get("created_at")
    else:
        drill_context = build_drill_context(label=label)
        checklist = build_drill_workspace_checklist_payload(root, paths, label, drill_context)
        created_at = checklist.get("created_at")
    drill_context = merge_drill_context(build_drill_context(label=label), drill_context)
    ticket_acknowledgment = copy.deepcopy(checklist.get("ticket_acknowledgment") or {})
    ticket_acknowledgment_history = [
        copy.deepcopy(item)
        for item in (checklist.get("ticket_acknowledgment_history") or [])
        if isinstance(item, dict)
    ]

    artifacts = {
        "update_before": describe_artifact(paths["update_before"]),
        "update_after": describe_artifact(paths["update_after"]),
        "update_report": describe_artifact(paths["update_report"]),
        "update_leg_summary": describe_artifact(paths["update_leg_summary"]),
        "update_bundle": describe_artifact(paths["update_bundle"]),
        "rollback_before": describe_artifact(paths["rollback_before"]),
        "rollback_after": describe_artifact(paths["rollback_after"]),
        "rollback_report": describe_artifact(paths["rollback_report"]),
        "rollback_leg_summary": describe_artifact(paths["rollback_leg_summary"]),
        "rollback_bundle": describe_artifact(paths["rollback_bundle"]),
        "paired_summary_json": describe_artifact(paths["paired_summary_json"]),
        "paired_summary_md": describe_artifact(paths["paired_summary_md"]),
        "paired_bundle": describe_artifact(paths["paired_bundle"]),
    }
    step_done = {
        "update_before_capture": artifacts["update_before"]["exists"],
        "update_after_capture": artifacts["update_after"]["exists"],
        "update_leg_summary": artifacts["update_leg_summary"]["exists"],
        "update_bundle": artifacts["update_bundle"]["exists"],
        "rollback_before_capture": artifacts["rollback_before"]["exists"],
        "rollback_after_capture": artifacts["rollback_after"]["exists"],
        "rollback_leg_summary": artifacts["rollback_leg_summary"]["exists"],
        "rollback_bundle": artifacts["rollback_bundle"]["exists"],
        "paired_summary": artifacts["paired_summary_json"]["exists"] and artifacts["paired_summary_md"]["exists"],
        "paired_bundle": artifacts["paired_bundle"]["exists"],
    }
    steps: list[dict[str, object]] = []
    for step in checklist.get("steps") or []:
        updated = dict(step)
        updated["done"] = bool(step_done.get(str(step.get("name")), step.get("done")))
        steps.append(updated)
    if not steps:
        for name, done in step_done.items():
            steps.append({"name": name, "artifact": "", "done": bool(done)})

    next_step = "complete"
    for step in steps:
        if not step["done"]:
            next_step = str(step["name"])
            break

    paired_json = artifacts["paired_summary_json"].get("json") if isinstance(artifacts["paired_summary_json"].get("json"), dict) else {}
    complete = all(step["done"] for step in steps)
    freshness = evaluate_drill_artifact_freshness(artifacts=artifacts, paired_json=paired_json)
    recommendation = build_handoff_recommendation(
        complete=complete,
        next_step=next_step,
        paired_json=paired_json,
        artifacts=artifacts,
        freshness=freshness,
    )
    handoff_manifest = {
        "label": label,
        "created_at": created_at,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(root.resolve()),
        "workspace": {key: str(value) for key, value in paths.items() if key != "label"},
        "drill_context": drill_context,
        "steps": steps,
        "complete": complete,
        "next_step": next_step,
        "closed_loop_passed": paired_json.get("closed_loop_passed"),
        "rollback_restored_start_version": paired_json.get("rollback_restored_start_version"),
        "freshness": freshness,
        "recommendation": recommendation,
        "artifacts": artifacts,
    }
    handoff_json_path = paths["base"] / "DRILL_HANDOFF.json"
    handoff_md_path = paths["base"] / "DRILL_HANDOFF.md"
    ticket_comment_txt_path = paths["base"] / "DRILL_TICKET_COMMENT.txt"
    ticket_comment_md_path = paths["base"] / "DRILL_TICKET_COMMENT.md"
    ticket_comment_json_path = paths["base"] / "DRILL_TICKET_COMMENT.json"
    attachment_review_json_path = paths["attachment_review_json"]
    handoff_manifest["support_exports"] = {
        "ticket_comment_txt": str(ticket_comment_txt_path.resolve()),
        "ticket_comment_md": str(ticket_comment_md_path.resolve()),
        "ticket_comment_json": str(ticket_comment_json_path.resolve()),
        "attachment_review_json": str(attachment_review_json_path.resolve()),
        "attachment_review_txt": str(paths["attachment_review_txt"].resolve()),
    }
    handoff_manifest["artifacts"] = {
        **artifacts,
        "handoff_manifest_json": {"path": str(handoff_json_path.resolve()), "exists": True},
        "handoff_manifest_md": {"path": str(handoff_md_path.resolve()), "exists": True},
        "ticket_comment_txt": {"path": str(ticket_comment_txt_path.resolve()), "exists": True},
        "ticket_comment_md": {"path": str(ticket_comment_md_path.resolve()), "exists": True},
        "ticket_comment_json": {"path": str(ticket_comment_json_path.resolve()), "exists": True},
        "attachment_review_json": {"path": str(attachment_review_json_path.resolve()), "exists": True},
        "attachment_review_txt": {"path": str(paths["attachment_review_txt"].resolve()), "exists": True},
    }
    ticket_comment = build_ticket_comment_payload(
        label=label,
        drill_context=drill_context,
        recommendation=recommendation,
        freshness=freshness,
        artifacts=handoff_manifest["artifacts"],
        handoff_manifest=handoff_manifest,
        ticket_acknowledgment=ticket_acknowledgment,
        ticket_acknowledgment_history=ticket_acknowledgment_history,
    )
    attachment_review = persist_attachment_review_summary(
        root,
        label=label,
        recommendation=recommendation,
        freshness=freshness,
        artifacts=handoff_manifest["artifacts"],
        ticket_acknowledgment=ticket_acknowledgment,
        ticket_acknowledgment_history=ticket_acknowledgment_history,
        dry_run=dry_run,
    )
    handoff_manifest["ticket_acknowledgment"] = ticket_comment["attachment_readiness"].get("ticket_acknowledgment") or {}
    handoff_manifest["ticket_acknowledgment_history"] = attachment_review.get("acknowledgment_history") or summarize_acknowledgment_history(ticket_acknowledgment_history)
    handoff_manifest["attachment_readiness"] = ticket_comment["attachment_readiness"]
    handoff_manifest["attachment_review"] = attachment_review
    handoff_md = [
        f"# Runtime Drill Handoff Manifest — {label}",
        "",
        f"- Refreshed: `{handoff_manifest['refreshed_at']}`",
        f"- Workspace: `{paths['base']}`",
        f"- Checklist complete: `{'yes' if handoff_manifest['complete'] else 'no'}`",
        f"- Next step: `{next_step}`",
        f"- Closed-loop passed: `{handoff_manifest['closed_loop_passed']}`",
        f"- Rollback restored start version: `{handoff_manifest['rollback_restored_start_version']}`",
        f"- Freshness OK: `{'yes' if freshness.get('ok') else 'no'}`",
        f"- Recommendation: `{recommendation['status']}`",
        f"- Attachment ready: `{'yes' if ticket_comment['attachment_readiness']['ready_to_attach'] else 'no'}`",
        f"- Attachment acknowledged: `{'yes' if ticket_comment['attachment_readiness']['acknowledged'] else 'no'}`",
        f"- Acknowledgment current: `{'yes' if ticket_comment['attachment_readiness']['acknowledgment_current'] else 'no'}`",
        f"- Ticket destination: `{(ticket_comment['attachment_readiness'].get('destination_summary') or {}).get('display') or '-'}`",
        f"- Ticket destination status: `{(ticket_comment['attachment_readiness'].get('destination_summary') or {}).get('verdict')}` — {(ticket_comment['attachment_readiness'].get('destination_summary') or {}).get('verdict_text')}",
        f"- Acknowledgment history count: `{(handoff_manifest.get('ticket_acknowledgment_history') or {}).get('count')}`",
        "",
        "## Drill context",
        "",
    ]
    for key in ["device_id", "operator", "service_ticket"]:
        if drill_context.get(key):
            handoff_md.append(f"- {key.replace('_', ' ').title()}: `{drill_context[key]}`")
    if drill_context.get("notes"):
        handoff_md.append(f"- Operator notes: {drill_context['notes']}")
    destination_summary = ticket_comment["attachment_readiness"].get("destination_summary") or {}
    action_verdict = ticket_comment["attachment_readiness"].get("action_verdict") or {}
    handoff_md.append(f"- Ticket destination kind: `{destination_summary.get('kind') or '-'}`")
    handoff_md.append(f"- Attachment action verdict: `{action_verdict.get('verdict') or '-'}`")
    if ticket_acknowledgment.get("acknowledged"):
        handoff_md.append(f"- Attached by: `{ticket_acknowledgment.get('attached_by') or '-'}`")
        handoff_md.append(f"- Attached at: `{ticket_acknowledgment.get('attached_at') or '-'}`")
        handoff_md.append(f"- Ticket status: `{ticket_acknowledgment.get('ticket_status') or '-'}`")
        handoff_md.append(f"- Acknowledgment current: `{'yes' if ticket_comment['attachment_readiness']['acknowledgment_current'] else 'no'}`")
        if ticket_acknowledgment.get("note"):
            handoff_md.append(f"- Attachment note: {ticket_acknowledgment['note']}")
    ack_history = handoff_manifest.get("ticket_acknowledgment_history") or {}
    handoff_md.append(f"- Acknowledgment history summary: `{ack_history.get('summary')}`")
    handoff_md.append(
        f"- Latest destination relation: `{ack_history.get('latest_destination_relation') or '-'}` — {ack_history.get('latest_destination_relation_summary') or '-'}"
    )
    handoff_md.append(
        f"- Destination history pattern: `{(ack_history.get('destination_history_pattern') or {}).get('verdict') or '-'}` — {(ack_history.get('destination_history_pattern') or {}).get('summary') or '-'}"
    )
    if ack_history.get("has_reacknowledgment"):
        handoff_md.append(f"- Re-acknowledgments recorded: `{ack_history.get('reacknowledge_count')}`")
        handoff_md.append(f"- Destination changes recorded: `{ack_history.get('destination_change_count')}`")
        handoff_md.append(f"- Latest acknowledgment change: {ack_history.get('latest_change_summary') or '-'}")
    handoff_md.extend([
        "",
        "## Recommendation",
        "",
        recommendation["summary"],
        "",
        f"- Operator action: `{recommendation['operator_action']}`",
    ])
    if recommendation["reasons"]:
        handoff_md.extend(["- Reasons:"])
        for reason in recommendation["reasons"]:
            handoff_md.append(f"  - {reason}")
    handoff_md.extend([
        "",
        "## Step status",
        "",
    ])
    for step in steps:
        handoff_md.append(f"- [{'OK' if step['done'] else 'TODO'}] {step['name']}")
    handoff_md.extend(["", "## Freshness / timestamp checks", ""])
    if freshness.get("warnings"):
        for warning in freshness["warnings"]:
            handoff_md.append(f"- WARN: {warning}")
    else:
        handoff_md.append("- no freshness or ordering warnings")
    handoff_md.extend(["", "## Attachment readiness", ""])
    ack_drift = ticket_comment["attachment_readiness"].get("acknowledgment_drift") or {}
    attachment_timeline = ticket_comment["attachment_readiness"].get("attachment_timeline") or {}
    fingerprint_summary = ticket_comment["attachment_readiness"].get("fingerprint_summary") or {}
    handoff_md.append(
        f"- Ticket destination summary: `{destination_summary.get('kind')}` — {destination_summary.get('verdict_text')}"
    )
    handoff_md.append(
        f"- Attachment action summary: `{action_verdict.get('verdict')}` — {action_verdict.get('summary')}"
    )
    handoff_md.append(
        f"- Fingerprint verdict: `{fingerprint_summary.get('verdict')}` — {fingerprint_summary.get('verdict_text')}"
    )
    handoff_md.append(f"- Fingerprint diff: {fingerprint_summary.get('mismatch_summary')}")
    if ticket_comment["attachment_readiness"]["attach_now_minimal"]:
        handoff_md.append("- Attach now (minimal):")
        for item in ticket_comment["attachment_readiness"]["attach_now_minimal"]:
            handoff_md.append(f"  - {item['key']}: `{item['path']}`")
    else:
        handoff_md.append("- Attach now (minimal): none")
    if ticket_comment["attachment_readiness"]["attach_now"]:
        handoff_md.append("- Attach now (full):")
        for item in ticket_comment["attachment_readiness"]["attach_now"]:
            handoff_md.append(f"  - {item['key']}: `{item['path']}`")
    else:
        handoff_md.append("- Attach now (full): none")
    if ticket_comment["attachment_readiness"]["missing_required"]:
        handoff_md.append("- Missing before ship:")
        for item in ticket_comment["attachment_readiness"]["missing_required"]:
            handoff_md.append(f"  - {item['key']}")
    else:
        handoff_md.append("- Missing before ship: none")
    handoff_md.append(
        f"- Acknowledgment drift summary: `{ack_drift.get('drift_verdict')}` — {ack_drift.get('drift_summary')}"
    )
    handoff_md.append(
        f"- Attachment timeline: `{attachment_timeline.get('verdict')}` — {attachment_timeline.get('summary')}"
    )
    handoff_md.append(
        f"- Attachment timeline points: summary `{attachment_timeline.get('paired_summary_built_at') or '-'}` | bundle `{attachment_timeline.get('paired_bundle_built_at') or '-'}` | attached `{attachment_timeline.get('attached_at') or '-'}` | latest regeneration `{attachment_timeline.get('latest_regenerated_at') or '-'}`"
    )
    if attachment_timeline.get("summary_after_attach"):
        handoff_md.append(f"- Attachment timing note: {attachment_timeline.get('summary_after_attach')}")
    if ack_drift.get("warnings"):
        handoff_md.append("- Acknowledgment drift warnings:")
        for warning in ack_drift["warnings"]:
            handoff_md.append(f"  - {warning}")
    if ticket_comment["attachment_readiness"].get("reacknowledge_blocked_reason"):
        handoff_md.append(f"- Re-acknowledge blocked: {ticket_comment['attachment_readiness']['reacknowledge_blocked_reason']}")
    if ticket_comment["attachment_readiness"].get("reacknowledge_blocked_reason") and ticket_comment["attachment_readiness"].get("reacknowledge_command_with_destination"):
        handoff_md.append(
            f"- Re-acknowledge with destination: `{ticket_comment['attachment_readiness']['reacknowledge_command_with_destination']}`"
        )
    if fingerprint_summary.get("warnings"):
        handoff_md.append("- Attachment fingerprint warnings:")
        for warning in fingerprint_summary["warnings"]:
            handoff_md.append(f"  - {warning}")
    current_fingerprints = (fingerprint_summary.get("current") or {}).get("items") or []
    if current_fingerprints:
        handoff_md.append("- Current paired fingerprints:")
        for item in current_fingerprints:
            handoff_md.append(
                f"  - {item['key']}: sha256 {item.get('sha256_short') or '-'} | {item.get('size_bytes')} bytes | {item.get('modified_at') or '-'}"
            )
    acknowledged_fingerprints = (fingerprint_summary.get("acknowledged") or {}).get("items") or []
    if ticket_comment["attachment_readiness"]["acknowledged"]:
        handoff_md.append("- Acknowledged paired fingerprints:")
        if acknowledged_fingerprints:
            for item in acknowledged_fingerprints:
                handoff_md.append(
                    f"  - {item['key']}: sha256 {item.get('sha256_short') or '-'} | {item.get('size_bytes')} bytes | {item.get('modified_at') or '-'}"
                )
        else:
            handoff_md.append("  - unavailable")
    handoff_md.extend(["", "## Key artifacts", ""])
    for key in ["update_leg_summary", "update_bundle", "rollback_leg_summary", "rollback_bundle", "paired_summary_json", "paired_bundle"]:
        artifact = artifacts[key]
        handoff_md.append(f"- {key}: `{'present' if artifact['exists'] else 'missing'}` — `{artifact['path']}`")
    handoff_md.append("")

    checklist = {
        "label": label,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(root.resolve()),
        "drill_context": drill_context,
        "workspace": {key: str(value) for key, value in paths.items() if key != "label"},
        "steps": steps,
        "handoff_manifest_json": str((paths['base'] / 'DRILL_HANDOFF.json').resolve()),
        "handoff_manifest_md": str((paths['base'] / 'DRILL_HANDOFF.md').resolve()),
        "next_step": next_step,
        "complete": handoff_manifest["complete"],
        "ticket_acknowledgment": handoff_manifest["ticket_acknowledgment"],
        "ticket_acknowledgment_history": handoff_manifest["ticket_acknowledgment_history"],
    }
    if not dry_run:
        paths["base"].mkdir(parents=True, exist_ok=True)
        write_json(paths["checklist_json"], checklist)
        paths["checklist_md"].write_text(render_drill_checklist_markdown(root, paths, label, drill_context, steps, next_step), encoding="utf-8")
        write_json(handoff_json_path, handoff_manifest)
        handoff_md_path.write_text("\n".join(handoff_md) + "\n", encoding="utf-8")
        write_json(ticket_comment_json_path, ticket_comment)
        ticket_comment_txt_path.write_text(str(ticket_comment["plain_text"]), encoding="utf-8")
        ticket_comment_md_path.write_text(str(ticket_comment["markdown"]), encoding="utf-8")
    return handoff_manifest


def initialize_drill_workspace(
    root: Path,
    *,
    label: str,
    operator: str | None = None,
    device_id: str | None = None,
    service_ticket: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict:
    paths = get_drill_workspace(root, label)
    drill_context = build_drill_context(
        label=label,
        operator=operator,
        device_id=device_id,
        service_ticket=service_ticket,
        notes=notes,
    )
    checklist = build_drill_workspace_checklist_payload(root, paths, label, drill_context)
    result = {
        "label": label,
        "workspace": {key: str(value) for key, value in paths.items() if key != "label"},
        "drill_context": drill_context,
        "dry_run": dry_run,
    }
    if not dry_run:
        paths["base"].mkdir(parents=True, exist_ok=True)
        write_json(paths["checklist_json"], checklist)
        refresh_drill_workspace_status(root, label=label, dry_run=False)
    return result


def default_support_bundle_name(label: str) -> str:
    safe = sanitize_label(label)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    return f"runtime-support-bundle-{safe}-{ts}.zip"


def summarize_drill_leg_status(comparison: dict) -> dict:
    checks = [
        {"name": "config_boundary_stable", "ok": bool(comparison.get("config_boundary_stable"))},
        {"name": "data_boundary_present", "ok": bool(comparison.get("data_boundary_present_before_and_after"))},
        {"name": "logs_boundary_present", "ok": bool(comparison.get("logs_boundary_present_before_and_after"))},
        {"name": "drill_context_matches", "ok": bool(comparison.get("drill_context_matches"))},
        {
            "name": "updater_run_recorded",
            "ok": comparison.get("updater_manifest_action_after") in {"install_update", "rollback"}
                and comparison.get("updater_exit_code_after") is not None,
        },
        {"name": "updater_ok", "ok": comparison.get("updater_ok_after") is True},
        {"name": "update_result_present", "ok": bool(comparison.get("update_result_present_after"))},
        {"name": "updater_log_present", "ok": bool(comparison.get("updater_log_present_after"))},
    ]
    return {
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
    }


def build_drill_leg_summary(
    root: Path,
    *,
    before_path: Path,
    after_path: Path,
    report_path: Path | None = None,
    summary_path: Path | None = None,
    label: str = "board-pc-drill",
    leg: str,
    dry_run: bool = False,
) -> dict:
    before_state = json.loads(before_path.read_text(encoding="utf-8"))
    after_state = json.loads(after_path.read_text(encoding="utf-8"))
    comparison = compare_runtime_boundary_state(before_state, after_state)
    status = summarize_drill_leg_status(comparison)
    payload = {
        "label": label,
        "leg": leg,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(root.resolve()),
        "before_path": str(before_path.resolve()),
        "after_path": str(after_path.resolve()),
        "report_path": str(report_path.resolve()) if report_path else None,
        "drill_context": copy.deepcopy(comparison.get("drill_context_after") or comparison.get("drill_context_before") or {}),
        "comparison": comparison,
        "status": status,
    }
    target = summary_path or (root / "data" / "support" / f"drill-leg-{leg}-{sanitize_label(label)}.json")
    payload["summary_path"] = str(target.resolve())
    if not dry_run:
        write_json(target.resolve(), payload)
    return payload


def write_paired_drill_markdown(path: Path, payload: dict) -> None:
    lines = [
        f"# Runtime Paired Drill Summary — {payload['label']}",
        "",
        f"- Created: `{payload['created_at']}`",
        f"- Runtime root: `{payload['runtime_root']}`",
        f"- Update leg passed: `{'yes' if payload['update_leg']['status']['passed'] else 'no'}`",
        f"- Rollback leg passed: `{'yes' if payload['rollback_leg']['status']['passed'] else 'no'}`",
        f"- Closed-loop passed: `{'yes' if payload['closed_loop_passed'] else 'no'}`",
        "",
    ]
    final_version = payload.get("final_version_after_rollback")
    restored_version = payload.get("rollback_restored_start_version")
    if final_version is not None or restored_version is not None:
        lines.extend([
            "## Version loop",
            "",
            f"- Start version before update: `{payload.get('start_version_before_update')}`",
            f"- Version after update leg: `{payload.get('version_after_update')}`",
            f"- Final version after rollback leg: `{final_version}`",
            f"- Rollback restored start version: `{'yes' if restored_version else 'no'}`",
            "",
        ])
    for leg_key, title in (("update_leg", "Update leg"), ("rollback_leg", "Rollback leg")):
        leg = payload[leg_key]
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"- Summary file: `{leg.get('summary_path')}`")
        lines.append(f"- Updater action: `{leg['comparison'].get('updater_manifest_action_after')}`")
        lines.append(f"- Updater exit code: `{leg['comparison'].get('updater_exit_code_after')}`")
        lines.append(f"- Passed: `{'yes' if leg['status']['passed'] else 'no'}`")
        lines.append("")
        for check in leg['status']['checks']:
            lines.append(f"- [{'OK' if check['ok'] else 'FAIL'}] {check['name']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_paired_drill_summary(
    root: Path,
    *,
    update_leg_path: Path,
    rollback_leg_path: Path,
    label: str = "board-pc-drill",
    summary_json_path: Path | None = None,
    summary_md_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    update_leg = json.loads(update_leg_path.read_text(encoding="utf-8"))
    rollback_leg = json.loads(rollback_leg_path.read_text(encoding="utf-8"))
    start_version = update_leg.get("comparison", {}).get("before_version")
    version_after_update = update_leg.get("comparison", {}).get("after_version")
    final_version = rollback_leg.get("comparison", {}).get("after_version")
    payload = {
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(root.resolve()),
        "update_leg": update_leg,
        "rollback_leg": rollback_leg,
        "start_version_before_update": start_version,
        "version_after_update": version_after_update,
        "final_version_after_rollback": final_version,
        "rollback_restored_start_version": start_version is not None and final_version == start_version,
        "closed_loop_passed": bool(update_leg.get("status", {}).get("passed")) and bool(rollback_leg.get("status", {}).get("passed")) and (start_version is not None and final_version == start_version),
    }
    safe_label = sanitize_label(label)
    json_target = (summary_json_path or (root / "data" / "support" / f"paired-drill-summary-{safe_label}.json")).resolve()
    md_target = (summary_md_path or (root / "data" / "support" / f"paired-drill-summary-{safe_label}.md")).resolve()
    payload["summary_json_path"] = str(json_target)
    payload["summary_md_path"] = str(md_target)
    if not dry_run:
        write_json(json_target, payload)
        write_paired_drill_markdown(md_target, payload)
    return payload


def acknowledge_drill_handoff(
    root: Path,
    *,
    label: str = "board-pc-drill",
    attached_by: str | None = None,
    attached_at: str | None = None,
    ticket_status: str | None = None,
    ticket_reference: str | None = None,
    ticket_url: str | None = None,
    note: str | None = None,
    event: str = "acknowledge",
    dry_run: bool = False,
) -> dict:
    workspace = get_drill_workspace(root, label)
    checklist_path = workspace["checklist_json"]
    if checklist_path.exists():
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    else:
        checklist = build_drill_workspace_checklist_payload(root, workspace, label, build_drill_context(label=label))

    previous_acknowledgment = copy.deepcopy(checklist.get("ticket_acknowledgment") or {})
    prior_history = [
        copy.deepcopy(item)
        for item in (checklist.get("ticket_acknowledgment_history") or [])
        if isinstance(item, dict)
    ]

    artifacts = {
        "paired_bundle": describe_artifact(workspace["paired_bundle"]),
        "paired_summary_json": describe_artifact(workspace["paired_summary_json"]),
        "paired_summary_md": describe_artifact(workspace["paired_summary_md"]),
    }
    acknowledgment = {
        "acknowledged": True,
        "attached_by": (attached_by or "").strip() or None,
        "attached_at": (attached_at or "").strip() or datetime.now(timezone.utc).isoformat(),
        "ticket_status": (ticket_status or "").strip() or None,
        "ticket_reference": (ticket_reference or "").strip() or None,
        "ticket_url": (ticket_url or "").strip() or None,
        "note": (note or "").strip() or None,
        "paired_artifact_snapshot": snapshot_paired_artifacts(artifacts),
    }
    history_entry = build_acknowledgment_history_entry(
        acknowledgment=acknowledgment,
        sequence=len(prior_history) + 1,
        event=event,
        previous_acknowledgment=previous_acknowledgment,
    )
    checklist["ticket_acknowledgment"] = acknowledgment
    checklist["ticket_acknowledgment_history"] = [*prior_history, history_entry]
    if not dry_run:
        workspace["base"].mkdir(parents=True, exist_ok=True)
        write_json(checklist_path, checklist)
    handoff = refresh_drill_workspace_status(root, label=label, dry_run=dry_run)
    return {
        "label": label,
        "dry_run": dry_run,
        "ticket_acknowledgment": acknowledgment,
        "ticket_acknowledgment_history": checklist["ticket_acknowledgment_history"],
        "handoff": handoff,
        "paths": {
            "handoff_json": str((workspace["base"] / "DRILL_HANDOFF.json").resolve()),
            "handoff_md": str((workspace["base"] / "DRILL_HANDOFF.md").resolve()),
            "ticket_comment_txt": str((workspace["base"] / "DRILL_TICKET_COMMENT.txt").resolve()),
            "ticket_comment_md": str((workspace["base"] / "DRILL_TICKET_COMMENT.md").resolve()),
            "ticket_comment_json": str((workspace["base"] / "DRILL_TICKET_COMMENT.json").resolve()),
            "attachment_review_json": str(workspace["attachment_review_json"].resolve()),
            "attachment_review_txt": str(workspace["attachment_review_txt"].resolve()),
        },
    }


def reacknowledge_drill_handoff(
    root: Path,
    *,
    label: str = "board-pc-drill",
    attached_by: str | None = None,
    attached_at: str | None = None,
    ticket_status: str | None = None,
    ticket_reference: str | None = None,
    ticket_url: str | None = None,
    note: str | None = None,
    dry_run: bool = False,
) -> dict:
    workspace = get_drill_workspace(root, label)
    checklist_path = workspace["checklist_json"]
    if checklist_path.exists():
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    else:
        checklist = build_drill_workspace_checklist_payload(root, workspace, label, build_drill_context(label=label))

    previous = copy.deepcopy(checklist.get("ticket_acknowledgment") or {})
    if not previous.get("acknowledged"):
        raise ValueError("cannot re-acknowledge before an initial acknowledgment exists")

    resolved_reference = (ticket_reference or "").strip() or previous.get("ticket_reference")
    resolved_url = (ticket_url or "").strip() or previous.get("ticket_url")
    resolved_by = (attached_by or "").strip() or previous.get("attached_by")
    resolved_status = (ticket_status or "").strip() or previous.get("ticket_status")
    if not resolved_reference and not resolved_url:
        raise ValueError("cannot re-acknowledge without a stored or provided ticket reference/url")

    resolved_note = (note or "").strip()
    prior_note = str(previous.get("note") or "").strip()
    if resolved_note and prior_note and resolved_note != prior_note:
        merged_note = f"{prior_note} | re-acknowledged: {resolved_note}"
    elif resolved_note:
        merged_note = resolved_note
    else:
        merged_note = prior_note or "re-attached refreshed paired artifacts"

    return acknowledge_drill_handoff(
        root,
        label=label,
        attached_by=str(resolved_by or "").strip() or None,
        attached_at=attached_at,
        ticket_status=str(resolved_status or "").strip() or None,
        ticket_reference=str(resolved_reference or "").strip() or None,
        ticket_url=str(resolved_url or "").strip() or None,
        note=merged_note,
        event="reacknowledge",
        dry_run=dry_run,
    )


def finalize_drill_handoff(
    root: Path,
    *,
    label: str = "board-pc-drill",
    update_leg_path: Path | None = None,
    rollback_leg_path: Path | None = None,
    summary_json_path: Path | None = None,
    summary_md_path: Path | None = None,
    bundle_path: Path | None = None,
    before: Path | None = None,
    after: Path | None = None,
    report: Path | None = None,
    manifest: Path | None = None,
    rollback_manifest: Path | None = None,
    include_logs: bool = True,
    include_downloads: bool = False,
    operator: str | None = None,
    device_id: str | None = None,
    service_ticket: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict:
    workspace = get_drill_workspace(root, label)
    checklist_path = workspace["checklist_json"]
    if checklist_path.exists():
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    else:
        checklist = build_drill_workspace_checklist_payload(root, workspace, label, build_drill_context(label=label))
    drill_context = merge_drill_context(
        checklist.get("drill_context") if isinstance(checklist, dict) else {},
        build_drill_context(
            label=label,
            operator=operator,
            device_id=device_id,
            service_ticket=service_ticket,
            drill_phase="finalize",
            notes=notes,
        ),
    )
    checklist["drill_context"] = drill_context
    if not dry_run:
        workspace["base"].mkdir(parents=True, exist_ok=True)
        write_json(checklist_path, checklist)
    paired = build_paired_drill_summary(
        root,
        update_leg_path=(update_leg_path or workspace["update_leg_summary"]).resolve(),
        rollback_leg_path=(rollback_leg_path or workspace["rollback_leg_summary"]).resolve(),
        label=label,
        summary_json_path=(summary_json_path or workspace["paired_summary_json"]).resolve(),
        summary_md_path=(summary_md_path or workspace["paired_summary_md"]).resolve(),
        dry_run=dry_run,
    )
    bundle = build_support_bundle(
        root,
        bundle_path=(bundle_path or workspace["paired_bundle"]).resolve(),
        label=label,
        before=(before or workspace["update_before"]).resolve(),
        after=(after or workspace["rollback_after"]).resolve(),
        report=(report or workspace["paired_summary_md"]).resolve(),
        manifest=manifest.resolve() if manifest else None,
        rollback_manifest=rollback_manifest.resolve() if rollback_manifest else None,
        include_logs=include_logs,
        include_downloads=include_downloads,
        operator=drill_context.get("operator"),
        device_id=drill_context.get("device_id"),
        service_ticket=drill_context.get("service_ticket"),
        drill_phase=drill_context.get("drill_phase") or "finalize",
        notes=drill_context.get("notes"),
        dry_run=dry_run,
    )
    handoff = refresh_drill_workspace_status(root, label=label, dry_run=dry_run)
    return {
        "label": label,
        "dry_run": dry_run,
        "summary": paired,
        "bundle": bundle,
        "handoff": handoff,
        "paths": {
            "paired_summary_json": str((summary_json_path or workspace["paired_summary_json"]).resolve()),
            "paired_summary_md": str((summary_md_path or workspace["paired_summary_md"]).resolve()),
            "paired_bundle": str((bundle_path or workspace["paired_bundle"]).resolve()),
            "handoff_json": str((workspace["base"] / "DRILL_HANDOFF.json").resolve()),
            "handoff_md": str((workspace["base"] / "DRILL_HANDOFF.md").resolve()),
            "ticket_comment_txt": str((workspace["base"] / "DRILL_TICKET_COMMENT.txt").resolve()),
            "ticket_comment_md": str((workspace["base"] / "DRILL_TICKET_COMMENT.md").resolve()),
            "ticket_comment_json": str((workspace["base"] / "DRILL_TICKET_COMMENT.json").resolve()),
            "attachment_review_json": str(workspace["attachment_review_json"].resolve()),
            "attachment_review_txt": str(workspace["attachment_review_txt"].resolve()),
        },
    }


def collect_support_bundle_candidates(
    root: Path,
    *,
    label: str = "board-pc-drill",
    before: Path | None = None,
    after: Path | None = None,
    report: Path | None = None,
    manifest: Path | None = None,
    rollback_manifest: Path | None = None,
    include_logs: bool = True,
    include_downloads: bool = False,
) -> list[dict[str, str | int]]:
    candidates: list[tuple[Path, str]] = []

    safe_label = sanitize_label(label)
    drill_workspace = get_drill_workspace(root, label)
    explicit = [
        (before or (root / "data" / "field_state_before.json"), "field_state_before.json"),
        (after or (root / "data" / "field_state_after.json"), "field_state_after.json"),
        (report or (root / "data" / "field_report.md"), "field_report.md"),
        (manifest or (root / "data" / "update_manifest.json"), "update_manifest.json"),
        (rollback_manifest or (root / "data" / "rollback_manifest.json"), "rollback_manifest.json"),
        (root / "data" / "last_updater_run.json", "last_updater_run.json"),
        (root / "data" / "update_result.json", "update_result.json"),
        (root / "data" / "support" / f"paired-drill-summary-{safe_label}.json", f"support/paired-drill-summary-{safe_label}.json"),
        (root / "data" / "support" / f"paired-drill-summary-{safe_label}.md", f"support/paired-drill-summary-{safe_label}.md"),
        (root / "data" / "support" / f"drill-leg-update-{safe_label}.json", f"support/drill-leg-update-{safe_label}.json"),
        (root / "data" / "support" / f"drill-leg-rollback-{safe_label}.json", f"support/drill-leg-rollback-{safe_label}.json"),
        (drill_workspace["checklist_json"], f"support/drills/{safe_label}/drill-checklist.json"),
        (drill_workspace["checklist_md"], f"support/drills/{safe_label}/DRILL_CHECKLIST.md"),
        (drill_workspace["base"] / "DRILL_HANDOFF.json", f"support/drills/{safe_label}/DRILL_HANDOFF.json"),
        (drill_workspace["base"] / "DRILL_HANDOFF.md", f"support/drills/{safe_label}/DRILL_HANDOFF.md"),
        (drill_workspace["base"] / "DRILL_TICKET_COMMENT.json", f"support/drills/{safe_label}/DRILL_TICKET_COMMENT.json"),
        (drill_workspace["base"] / "DRILL_TICKET_COMMENT.md", f"support/drills/{safe_label}/DRILL_TICKET_COMMENT.md"),
        (drill_workspace["base"] / "DRILL_TICKET_COMMENT.txt", f"support/drills/{safe_label}/DRILL_TICKET_COMMENT.txt"),
        (drill_workspace["attachment_review_json"], f"support/drills/{safe_label}/ATTACHMENT_READINESS_REVIEW.json"),
        (drill_workspace["attachment_review_txt"], f"support/drills/{safe_label}/ATTACHMENT_READINESS_REVIEW.txt"),
        (drill_workspace["update_leg_summary"], f"support/drills/{safe_label}/{drill_workspace['update_leg_summary'].name}"),
        (drill_workspace["rollback_leg_summary"], f"support/drills/{safe_label}/{drill_workspace['rollback_leg_summary'].name}"),
        (drill_workspace["paired_summary_json"], f"support/drills/{safe_label}/{drill_workspace['paired_summary_json'].name}"),
        (drill_workspace["paired_summary_md"], f"support/drills/{safe_label}/{drill_workspace['paired_summary_md'].name}"),
    ]
    for key in ["update_before", "update_after", "update_report", "update_bundle", "rollback_before", "rollback_after", "rollback_report", "rollback_bundle", "paired_bundle"]:
        candidates.append((drill_workspace[key], f"support/drills/{safe_label}/{drill_workspace[key].name}"))
    candidates.extend(explicit)

    if include_logs:
        for path in iter_files(root / "data" / "logs")[:10]:
            candidates.append((path, f"logs/{path.name}"))
    if include_downloads:
        for path in iter_files(root / "data" / "downloads")[:5]:
            candidates.append((path, f"downloads/{path.name}"))

    seen: set[str] = set()
    result: list[dict[str, str | int]] = []
    for source, archive_name in candidates:
        key = str(source.resolve()) if source.exists() else str(source)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "source": str(source),
                "archive_name": archive_name.replace("\\", "/"),
                "exists": source.exists() and source.is_file(),
                "size_bytes": source.stat().st_size if source.exists() and source.is_file() else 0,
            }
        )
    return result


def build_support_bundle(
    root: Path,
    *,
    bundle_path: Path | None = None,
    label: str = "board-pc-drill",
    before: Path | None = None,
    after: Path | None = None,
    report: Path | None = None,
    manifest: Path | None = None,
    rollback_manifest: Path | None = None,
    include_logs: bool = True,
    include_downloads: bool = False,
    operator: str | None = None,
    device_id: str | None = None,
    service_ticket: str | None = None,
    drill_phase: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict:
    target = (bundle_path or (root / "data" / "support" / default_support_bundle_name(label))).expanduser().resolve()
    if not dry_run:
        refresh_drill_workspace_status(root, label=label, dry_run=False)
    candidates = collect_support_bundle_candidates(
        root,
        label=label,
        before=before,
        after=after,
        report=report,
        manifest=manifest,
        rollback_manifest=rollback_manifest,
        include_logs=include_logs,
        include_downloads=include_downloads,
    )
    included = [item for item in candidates if item["exists"]]
    missing = [item for item in candidates if not item["exists"]]
    result = {
        "bundle_path": str(target),
        "bundle_parent": str(target.parent),
        "bundle_parent_exists": target.parent.exists(),
        "label": label,
        "dry_run": dry_run,
        "included": included,
        "missing": missing,
        "files_written": 0,
        "bytes_written": 0,
        "drill_context": build_drill_context(
            label=label,
            operator=operator,
            device_id=device_id,
            service_ticket=service_ticket,
            drill_phase=drill_phase,
            notes=notes,
        ),
    }

    if dry_run:
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        summary = {
            "label": label,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runtime_root": str(root.resolve()),
            "drill_context": result["drill_context"],
            "included": included,
            "missing": missing,
        }
        zf.writestr("bundle_summary.json", json.dumps(summary, indent=2) + "\n")
        result["files_written"] += 1
        result["bytes_written"] += len(json.dumps(summary))
        for item in included:
            source = Path(str(item["source"]))
            archive_name = str(item["archive_name"])
            zf.write(source, archive_name)
            result["files_written"] += 1
            result["bytes_written"] += int(item["size_bytes"])
    result["bundle_parent_exists"] = True
    return result


def default_app_backup_name(root: Path, target_version: str | None = None) -> str:
    current_version = (root / "config" / "VERSION").read_text(encoding="utf-8", errors="ignore").strip() or "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    suffix = f"-to-{target_version}" if target_version else ""
    return f"runtime-app-{current_version}{suffix}-{ts}.zip"


def build_runtime_update_manifest(
    root: Path,
    staging_dir: Path,
    target_version: str,
    backup_path: str | None = None,
    current_version: str | None = None,
    health_check_url: str = "http://localhost:8001/api/health",
    version_check_url: str = "http://localhost:8001/api/system/version",
) -> dict:
    backup = backup_path or f"data/app_backups/{default_app_backup_name(root, target_version=target_version)}"
    current = current_version or (root / "config" / "VERSION").read_text(encoding="utf-8", errors="ignore").strip() or "unknown"
    return {
        "action": "install_update",
        "project_root": str(root),
        "staging_dir": str(staging_dir),
        "backup_path": backup,
        "target_version": target_version,
        "current_version": current,
        "health_check_url": health_check_url,
        "version_check_url": version_check_url,
        "protected_paths": list(RUNTIME_PROTECTED_PATHS),
    }


def build_runtime_rollback_manifest(
    root: Path,
    backup_path: Path,
    health_check_url: str = "http://localhost:8001/api/health",
    version_check_url: str = "http://localhost:8001/api/system/version",
) -> dict:
    return {
        "action": "rollback",
        "project_root": str(root),
        "backup_path": str(backup_path),
        "health_check_url": health_check_url,
        "version_check_url": version_check_url,
        "protected_paths": list(RUNTIME_PROTECTED_PATHS),
    }


def inspect_runtime_app_payload(payload: Path) -> dict:
    payload = payload.expanduser().resolve()
    result = {
        "payload": str(payload),
        "payload_exists": payload.exists(),
        "payload_kind": None,
        "top_level_entries": [],
        "unexpected_top_level": [],
        "app_entries": [],
        "missing_app_entries": [],
    }
    if not payload.exists():
        return result

    entries: list[str] = []
    payload_kind = "directory"
    if payload.is_dir():
        for path in sorted(payload.rglob("*")):
            rel = path.relative_to(payload).as_posix()
            if path.is_dir():
                rel += "/"
            entries.append(rel)
    else:
        payload_kind = "zip" if payload.suffix.lower() == ".zip" else "file"
        if payload_kind != "zip":
            result["payload_kind"] = payload_kind
            result["unexpected_top_level"] = [payload.name]
            result["missing_app_entries"] = [f"app/{rel}" for rel in RUNTIME_APP_DIRS]
            return result
        with zipfile.ZipFile(payload) as zf:
            for info in zf.infolist():
                rel = info.filename.replace("\\", "/")
                if not rel:
                    continue
                if info.is_dir() and not rel.endswith("/"):
                    rel += "/"
                entries.append(rel)

    result["payload_kind"] = payload_kind
    normalized = [item.strip("/") for item in entries if item.strip("/")]
    top_level = sorted({item.split("/", 1)[0] for item in normalized})
    result["top_level_entries"] = top_level
    result["unexpected_top_level"] = [item for item in top_level if item != "app"]

    app_entries: list[str] = []
    for rel in RUNTIME_APP_DIRS:
        prefix = f"app/{rel.strip('/')}"
        if any(item == prefix or item.startswith(prefix + "/") for item in normalized):
            app_entries.append(prefix)
    result["app_entries"] = app_entries
    result["missing_app_entries"] = [f"app/{rel}" for rel in RUNTIME_APP_DIRS if f"app/{rel}" not in app_entries]
    return result


def validate_update_payload(root: Path, manifest_path: Path | None = None) -> dict:
    manifest = manifest_path or (root / "data" / "update_manifest.json")
    result = {
        "manifest_path": str(manifest),
        "manifest_present": manifest.exists(),
        "action": None,
        "project_root": None,
        "project_root_matches_root": False,
        "staging_dir": None,
        "staging_exists": False,
        "backup_path": None,
        "backup_parent_exists": False,
        "backup_exists": False,
        "backup_payload": None,
        "target_version": None,
        "top_level_entries": [],
        "unexpected_top_level": [],
        "missing_app_entries": [],
        "protected_paths": [],
        "protected_paths_outside_runtime_roots": [],
        "missing_required_protected_paths": [],
        "unexpected_protected_paths": [],
    }
    if not manifest.exists():
        return result

    data = json.loads(manifest.read_text(encoding="utf-8"))
    result["action"] = data.get("action")
    result["project_root"] = data.get("project_root")
    result["project_root_matches_root"] = bool(data.get("project_root")) and Path(data.get("project_root")).resolve() == root.resolve()
    result["backup_path"] = data.get("backup_path")
    result["target_version"] = data.get("target_version")
    result["protected_paths"] = [normalize_rel_path(item) for item in data.get("protected_paths", []) if str(item).strip()]
    if result["backup_path"]:
        backup_path = Path(result["backup_path"]).expanduser().resolve()
        result["backup_parent_exists"] = backup_path.parent.exists()
        result["backup_exists"] = backup_path.exists()
        if result["backup_exists"]:
            result["backup_payload"] = inspect_runtime_app_payload(backup_path)

    staging_dir = Path(data.get("staging_dir", "")) if data.get("staging_dir") else None
    if staging_dir:
        result["staging_dir"] = str(staging_dir)
        result["staging_exists"] = staging_dir.exists()
    if result["action"] == "rollback":
        result["missing_required_protected_paths"] = [
            path for path in RUNTIME_PROTECTED_PATHS if path not in result["protected_paths"]
        ]
        return result
    if not staging_dir or not staging_dir.exists():
        return result

    top_level = sorted({p.relative_to(staging_dir).parts[0] for p in staging_dir.iterdir()})
    result["top_level_entries"] = top_level
    result["unexpected_top_level"] = [item for item in top_level if item != "app"]

    missing_app_entries: list[str] = []
    for rel in RUNTIME_APP_DIRS:
        if not (staging_dir / "app" / rel).exists():
            missing_app_entries.append(f"app/{rel}")
    result["missing_app_entries"] = missing_app_entries

    outside_runtime_roots: list[str] = []
    unexpected_protected_paths: list[str] = []
    for protected in result["protected_paths"]:
        if protected and protected not in RUNTIME_PROTECTED_PATHS:
            unexpected_protected_paths.append(protected)
        if protected and not (
            protected == "config"
            or protected.startswith("config/")
            or protected == "data"
            or protected.startswith("data/")
            or protected == "logs"
            or protected.startswith("logs/")
        ):
            outside_runtime_roots.append(protected)
    result["protected_paths_outside_runtime_roots"] = outside_runtime_roots
    result["unexpected_protected_paths"] = unexpected_protected_paths
    result["missing_required_protected_paths"] = [
        path for path in RUNTIME_PROTECTED_PATHS if path not in result["protected_paths"]
    ]
    return result


def stage_runtime_zip(root: Path, runtime_zip: Path, output_dir: Path | None = None, dry_run: bool = False) -> dict:
    zip_path = runtime_zip.expanduser().resolve()
    target_dir = (output_dir or (root / "data" / "downloads" / f"staged-{zip_path.stem}")).expanduser().resolve()
    result = {
        "runtime_zip": str(zip_path),
        "runtime_zip_exists": zip_path.exists(),
        "output_dir": str(target_dir),
        "top_level_entries": [],
        "selected_runtime_root": None,
        "runtime_root_candidates": [],
        "selected_runtime_has_app": False,
        "staged_app_entries": [],
        "missing_app_entries": [],
        "dry_run": dry_run,
    }
    if not zip_path.exists():
        return result

    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name and not name.endswith("/")]
        top_level = sorted({Path(name).parts[0] for name in names if Path(name).parts})
        result["top_level_entries"] = top_level

        runtime_root_candidates: list[str] = []
        if any(name.startswith("app/") for name in names):
            runtime_root_candidates.append(".")
        for entry in top_level:
            prefix = f"{entry}/"
            if any(name.startswith(prefix + "app/") for name in names):
                runtime_root_candidates.append(entry)
        result["runtime_root_candidates"] = runtime_root_candidates

        if not runtime_root_candidates:
            return result

        selected_root = "."
        if "." not in runtime_root_candidates:
            selected_root = runtime_root_candidates[0]
        result["selected_runtime_root"] = selected_root
        app_prefix = "app/" if selected_root == "." else f"{selected_root}/app/"
        result["selected_runtime_has_app"] = any(name.startswith(app_prefix) for name in names)
        if not result["selected_runtime_has_app"]:
            return result

        staged_entries: list[str] = []
        for rel in RUNTIME_APP_DIRS:
            if any(name.startswith(app_prefix + rel.rstrip("/") + "/") or name == app_prefix + rel.rstrip("/") for name in names):
                staged_entries.append(f"app/{rel}")
        result["staged_app_entries"] = staged_entries
        result["missing_app_entries"] = [f"app/{rel}" for rel in RUNTIME_APP_DIRS if f"app/{rel}" not in staged_entries]
        if result["missing_app_entries"]:
            return result

        if dry_run:
            return result

        if target_dir.exists():
            shutil.rmtree(target_dir)
        (target_dir / "app").mkdir(parents=True, exist_ok=True)

        for member in zf.infolist():
            member_name = member.filename.replace("\\", "/")
            if not member_name or member_name.endswith("/"):
                continue
            if not member_name.startswith(app_prefix):
                continue
            rel_name = member_name[len(app_prefix):]
            if not rel_name:
                continue
            destination = target_dir / "app" / rel_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    return result


def create_app_backup(root: Path, backup_path: Path | None = None, source_dir: Path | None = None, dry_run: bool = False) -> dict:
    app_dir = (source_dir or (root / "app")).expanduser().resolve()
    target = (backup_path or (root / "data" / "app_backups" / default_app_backup_name(root))).expanduser().resolve()
    result = {
        "source_dir": str(app_dir),
        "source_exists": app_dir.exists(),
        "backup_path": str(target),
        "backup_parent": str(target.parent),
        "backup_parent_exists": target.parent.exists(),
        "app_entries": [],
        "missing_app_entries": [],
        "dry_run": dry_run,
        "files_written": 0,
        "bytes_written": 0,
    }
    if not app_dir.exists():
        return result

    for rel in RUNTIME_APP_DIRS:
        candidate = app_dir / rel
        if candidate.exists():
            result["app_entries"].append(f"app/{rel}")
        else:
            result["missing_app_entries"].append(f"app/{rel}")
    if result["missing_app_entries"]:
        return result

    if dry_run:
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in sorted(app_dir.rglob("*")):
            if src.is_dir():
                continue
            rel = src.relative_to(app_dir)
            arcname = Path("app") / rel
            zf.write(src, arcname.as_posix())
            result["files_written"] += 1
            result["bytes_written"] += src.stat().st_size
    result["backup_parent_exists"] = True
    return result


def validate_rehearsal(root: Path, manifest_path: Path | None = None, dry_run: bool = False) -> dict:
    missing = validate_layout(root)
    writable = check_writable_paths(root, dry_run=dry_run)
    update = validate_update_payload(root, manifest_path)
    checklist = [
        {"name": "runtime_layout", "ok": not missing},
        {"name": "writable_paths", "ok": not writable["failed"]},
        {"name": "update_manifest_present", "ok": update["manifest_present"]},
        {"name": "update_staging_exists", "ok": update["action"] == "install_update" and update["staging_exists"]},
        {"name": "update_app_only_top_level", "ok": update["action"] == "install_update" and update["manifest_present"] and not update["unexpected_top_level"]},
        {"name": "update_app_shape_complete", "ok": update["action"] == "install_update" and update["manifest_present"] and not update["missing_app_entries"]},
        {"name": "update_project_root_matches", "ok": update["manifest_present"] and update["project_root_matches_root"]},
        {"name": "update_protected_paths_complete", "ok": update["manifest_present"] and not update["missing_required_protected_paths"] and not update["unexpected_protected_paths"] and not update["protected_paths_outside_runtime_roots"]},
        {"name": "backup_parent_exists", "ok": update["manifest_present"] and update["backup_parent_exists"]},
        {"name": "rollback_backup_shape_complete", "ok": update["action"] != "rollback" or (bool(update["backup_payload"]) and not update["backup_payload"]["unexpected_top_level"] and not update["backup_payload"]["missing_app_entries"])},
    ]
    return {
        "root": str(root),
        "missing": missing,
        "writable": writable,
        "update": update,
        "checklist": checklist,
    }


def load_policy(root: Path) -> RetentionPolicy:
    env = parse_env_file(root / "app" / "backend" / ".env")
    policy = RetentionPolicy()
    mapping = {
        "RUNTIME_LOGS_KEEP": ("logs_keep", int),
        "RUNTIME_LOGS_MAX_MB": ("logs_max_mb", int),
        "RUNTIME_APP_BACKUPS_KEEP": ("app_backups_keep", int),
        "RUNTIME_DOWNLOADS_KEEP": ("downloads_keep", int),
        "RUNTIME_DOWNLOADS_MAX_AGE_DAYS": ("downloads_max_age_days", int),
        "RUNTIME_SUPPORT_BUNDLES_KEEP": ("support_bundles_keep", int),
        "RUNTIME_SUPPORT_BUNDLES_MAX_AGE_DAYS": ("support_bundles_max_age_days", int),
    }
    for key, (attr, caster) in mapping.items():
        if key in env:
            try:
                setattr(policy, attr, caster(env[key]))
            except ValueError:
                pass
    return policy


def run_cleanup(root: Path, policy: RetentionPolicy, dry_run: bool) -> dict:
    created: list[str] = []
    removed: list[str] = []
    now = time.time()

    logs_dir = root / "data" / "logs"
    backups_dir = root / "data" / "app_backups"
    downloads_dir = root / "data" / "downloads"
    support_dir = downloads_dir / "support"
    writable_dirs = [
        root / "data",
        root / "data" / "db",
        logs_dir,
        root / "data" / "backups",
        backups_dir,
        downloads_dir,
        root / "data" / "assets",
        root / "data" / "chrome_profile",
        root / "data" / "kiosk_ui_profile",
        support_dir,
    ]

    for path in writable_dirs:
        ensure_dir(path, dry_run, created)

    log_files = [p for p in iter_files(logs_dir) if p.suffix.lower() in {".log", ".txt"}]
    prune_keep_newest(log_files, policy.logs_keep, dry_run, removed)
    remaining_log_files = [p for p in iter_files(logs_dir) if p.exists() and p.suffix.lower() in {".log", ".txt"}]
    cap_total_size(remaining_log_files, policy.logs_max_mb, dry_run, removed)

    backup_files = [p for p in iter_files(backups_dir) if p.suffix.lower() in {".zip", ".bak"}]
    prune_keep_newest(backup_files, policy.app_backups_keep, dry_run, removed)

    download_files = [p for p in iter_files(downloads_dir) if p.parent == downloads_dir and p.suffix.lower() in {".zip", ".json", ".msi", ".exe"}]
    prune_keep_newest(download_files, policy.downloads_keep, dry_run, removed)
    prune_old(download_files, policy.downloads_max_age_days, dry_run, removed, now)

    support_files = [p for p in support_dir.rglob("*") if p.is_file()]
    support_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    prune_keep_newest(support_files, policy.support_bundles_keep, dry_run, removed)
    prune_old(support_files, policy.support_bundles_max_age_days, dry_run, removed, now)

    return {
        "dry_run": dry_run,
        "created_dirs": created,
        "removed_paths": removed,
        "policy": policy.__dict__,
    }


def prepare_closed_loop_rehearsal(
    root: Path,
    runtime_zip: Path,
    target_version: str,
    output_dir: Path | None = None,
    backup_path: Path | None = None,
    update_manifest_path: Path | None = None,
    rollback_manifest_path: Path | None = None,
    current_version: str | None = None,
    health_check_url: str = "http://localhost:8001/api/health",
    version_check_url: str = "http://localhost:8001/api/system/version",
    dry_run: bool = False,
) -> dict:
    resolved_update_manifest = (update_manifest_path or (root / "data" / "update_manifest.json")).resolve()
    resolved_rollback_manifest = (rollback_manifest_path or (root / "data" / "rollback_manifest.json")).resolve()
    chosen_backup = (backup_path or (root / "data" / "app_backups" / default_app_backup_name(root, target_version=target_version))).expanduser().resolve()

    backup_result = create_app_backup(root=root, backup_path=chosen_backup, source_dir=(root / "app"), dry_run=dry_run)
    stage_result = stage_runtime_zip(root=root, runtime_zip=runtime_zip, output_dir=output_dir, dry_run=dry_run)
    update_manifest = build_runtime_update_manifest(
        root=root,
        staging_dir=Path(stage_result["output_dir"]),
        target_version=target_version,
        backup_path=str(chosen_backup),
        current_version=current_version,
        health_check_url=health_check_url,
        version_check_url=version_check_url,
    )
    rollback_manifest = build_runtime_rollback_manifest(
        root=root,
        backup_path=chosen_backup,
        health_check_url=health_check_url,
        version_check_url=version_check_url,
    )

    update_validation = None
    rollback_validation = None
    rehearsal_result = None
    if not dry_run and backup_result["source_exists"] and not backup_result["missing_app_entries"] and stage_result["runtime_zip_exists"] and stage_result["selected_runtime_root"] and not stage_result["missing_app_entries"]:
        resolved_update_manifest.parent.mkdir(parents=True, exist_ok=True)
        resolved_update_manifest.write_text(json.dumps(update_manifest, indent=2) + "\n", encoding="utf-8")
        resolved_rollback_manifest.parent.mkdir(parents=True, exist_ok=True)
        resolved_rollback_manifest.write_text(json.dumps(rollback_manifest, indent=2) + "\n", encoding="utf-8")
        update_validation = validate_update_payload(root, resolved_update_manifest)
        rollback_validation = validate_update_payload(root, resolved_rollback_manifest)
        rehearsal_result = validate_rehearsal(root, resolved_update_manifest)

    return {
        "backup": backup_result,
        "stage": stage_result,
        "update_manifest_path": str(resolved_update_manifest),
        "rollback_manifest_path": str(resolved_rollback_manifest),
        "update_manifest": update_manifest,
        "rollback_manifest": rollback_manifest,
        "update_validation": update_validation,
        "rollback_validation": rollback_validation,
        "rehearsal": rehearsal_result,
        "next_steps": [
            f"Run update with: app\\bin\\update_runtime.bat (uses {resolved_update_manifest.relative_to(root).as_posix().replace('/', '\\\\')})",
            f"If rollback is needed, swap in {resolved_rollback_manifest.relative_to(root).as_posix().replace('/', '\\\\')} as data\\update_manifest.json or point updater to it directly.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime maintenance helper")
    parser.add_argument(
        "command",
        choices=[
            "validate",
            "cleanup",
            "report",
            "validate-update",
            "rehearsal",
            "prepare-update-manifest",
            "prepare-rollback-manifest",
            "stage-runtime-zip",
            "create-app-backup",
            "prepare-runtime-update",
            "prepare-closed-loop-rehearsal",
            "capture-field-state",
            "compare-field-state",
            "build-drill-leg-summary",
            "build-paired-drill-summary",
            "show-attachment-readiness",
            "finalize-drill-handoff",
            "acknowledge-drill-handoff",
            "reacknowledge-drill-handoff",
            "build-support-bundle",
            "record-updater-run",
            "init-drill-workspace",
        ],
    )
    parser.add_argument("--root", default=Path(__file__).resolve().parents[2], type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--staging-dir", type=Path)
    parser.add_argument("--target-version")
    parser.add_argument("--backup-path")
    parser.add_argument("--current-version")
    parser.add_argument("--runtime-zip", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--health-check-url", default="http://localhost:8001/api/health")
    parser.add_argument("--version-check-url", default="http://localhost:8001/api/system/version")
    parser.add_argument("--rollback-manifest", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--label", default="board-pc-drill")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--summary-md", type=Path)
    parser.add_argument("--leg", choices=["update", "rollback"])
    parser.add_argument("--update-leg", type=Path)
    parser.add_argument("--rollback-leg", type=Path)
    parser.add_argument("--include-downloads", action="store_true")
    parser.add_argument("--no-logs", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--device-id")
    parser.add_argument("--service-ticket")
    parser.add_argument("--drill-phase")
    parser.add_argument("--notes")
    parser.add_argument("--attached-by")
    parser.add_argument("--attached-at")
    parser.add_argument("--ticket-status")
    parser.add_argument("--ticket-reference")
    parser.add_argument("--ticket-url")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--update-result", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    missing = validate_layout(root)
    policy = load_policy(root)

    if args.command == "validate":
        writable = check_writable_paths(root, dry_run=args.dry_run)
        result = {
            "root": str(root),
            "missing": missing,
            "policy": policy.__dict__,
            "backend_env_present": (root / "app" / "backend" / ".env").exists(),
            "venv_present": (root / "app" / ".venv" / "Scripts" / "activate.bat").exists(),
            "writable": writable,
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Runtime root: {root}")
            print(f"Missing required paths: {len(missing)}")
            for item in missing:
                print(f"  - {item}")
            print(f"Backend .env present: {'yes' if result['backend_env_present'] else 'no'}")
            print(f"Virtualenv present: {'yes' if result['venv_present'] else 'no'}")
            print(f"Writable paths OK: {len(writable['ok'])}/{len(writable['checked'])}")
            for item in writable['failed']:
                print(f"  ! not writable: {item}")
        return 1 if (missing or writable["failed"]) else 0

    if args.command == "validate-update":
        result = validate_update_payload(root, args.manifest)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Update manifest present: {'yes' if result['manifest_present'] else 'no'}")
            if result['manifest_present']:
                print(f"Action: {result['action']}")
                if result['action'] == 'install_update':
                    print(f"Staging exists: {'yes' if result['staging_exists'] else 'no'}")
                    print(f"Top-level staging entries: {', '.join(result['top_level_entries']) or '-'}")
                    for item in result['unexpected_top_level']:
                        print(f"  ! unexpected top-level entry: {item}")
                if result['project_root']:
                    print(f"Project root matches runtime root: {'yes' if result['project_root_matches_root'] else 'no'}")
                if result['backup_path']:
                    print(f"Backup parent exists: {'yes' if result['backup_parent_exists'] else 'no'}")
                    print(f"Backup exists: {'yes' if result['backup_exists'] else 'no'}")
                for item in result['missing_app_entries']:
                    print(f"  ! missing staged path: {item}")
                for item in result['missing_required_protected_paths']:
                    print(f"  ! missing protected path: {item}")
                for item in result['unexpected_protected_paths']:
                    print(f"  ! unexpected protected path: {item}")
                for item in result['protected_paths_outside_runtime_roots']:
                    print(f"  ! protected path outside runtime roots: {item}")
                if result['backup_payload']:
                    for item in result['backup_payload']['unexpected_top_level']:
                        print(f"  ! unexpected backup top-level entry: {item}")
                    for item in result['backup_payload']['missing_app_entries']:
                        print(f"  ! missing backup path: {item}")
        bad = (
            not result['manifest_present']
            or not result['project_root_matches_root']
            or bool(result['missing_required_protected_paths'])
            or bool(result['unexpected_protected_paths'])
            or bool(result['protected_paths_outside_runtime_roots'])
            or not result['backup_parent_exists']
            or (result['action'] == 'install_update' and (not result['staging_exists'] or bool(result['unexpected_top_level']) or bool(result['missing_app_entries'])))
            or (result['action'] == 'rollback' and (not result['backup_exists'] or not result['backup_payload'] or bool(result['backup_payload']['unexpected_top_level']) or bool(result['backup_payload']['missing_app_entries'])))
        )
        return 1 if bad else 0

    if args.command == "rehearsal":
        result = validate_rehearsal(root, args.manifest, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Board-PC rehearsal preflight: {root}")
            for item in result['checklist']:
                print(f"  [{'OK' if item['ok'] else 'FAIL'}] {item['name']}")
            if result['missing']:
                print("Missing runtime paths:")
                for item in result['missing']:
                    print(f"  - {item}")
            if result['writable']['failed']:
                print("Not writable:")
                for item in result['writable']['failed']:
                    print(f"  - {item}")
            if result['update']['unexpected_top_level']:
                print("Unexpected staged top-level entries:")
                for item in result['update']['unexpected_top_level']:
                    print(f"  - {item}")
            if result['update']['missing_app_entries']:
                print("Missing staged app entries:")
                for item in result['update']['missing_app_entries']:
                    print(f"  - {item}")
            if result['update']['missing_required_protected_paths']:
                print("Missing protected paths:")
                for item in result['update']['missing_required_protected_paths']:
                    print(f"  - {item}")
            if result['update']['unexpected_protected_paths']:
                print("Unexpected protected paths:")
                for item in result['update']['unexpected_protected_paths']:
                    print(f"  - {item}")
            if result['update']['backup_payload'] and result['update']['backup_payload']['unexpected_top_level']:
                print("Unexpected backup top-level entries:")
                for item in result['update']['backup_payload']['unexpected_top_level']:
                    print(f"  - {item}")
            if result['update']['backup_payload'] and result['update']['backup_payload']['missing_app_entries']:
                print("Missing backup app entries:")
                for item in result['update']['backup_payload']['missing_app_entries']:
                    print(f"  - {item}")
        failures = [item for item in result['checklist'] if not item['ok']]
        return 1 if failures else 0

    if args.command == "stage-runtime-zip":
        if not args.runtime_zip:
            print("--runtime-zip is required", file=sys.stderr)
            return 2
        result = stage_runtime_zip(root=root, runtime_zip=args.runtime_zip, output_dir=args.output_dir, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Runtime zip present: {'yes' if result['runtime_zip_exists'] else 'no'}")
            print(f"Staging output dir: {result['output_dir']}")
            print(f"Zip top-level entries: {', '.join(result['top_level_entries']) or '-'}")
            print(f"Selected runtime root: {result['selected_runtime_root'] or '-'}")
            if result['staged_app_entries']:
                print(f"Staged app entries: {', '.join(result['staged_app_entries'])}")
            for item in result['missing_app_entries']:
                print(f"  ! missing runtime zip path: {item}")
            if not args.dry_run and not result['missing_app_entries'] and result['runtime_zip_exists']:
                print("Runtime zip unpacked into app-only staging directory.")
        bad = (
            not result['runtime_zip_exists']
            or not result['selected_runtime_root']
            or not result['selected_runtime_has_app']
            or bool(result['missing_app_entries'])
        )
        return 1 if bad else 0

    if args.command == "create-app-backup":
        backup_target = Path(args.backup_path) if args.backup_path else None
        result = create_app_backup(root=root, backup_path=backup_target, source_dir=(root / 'app'), dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"App source exists: {'yes' if result['source_exists'] else 'no'}")
            print(f"Backup path: {result['backup_path']}")
            print(f"Backup parent exists: {'yes' if result['backup_parent_exists'] else 'no'}")
            if result['app_entries']:
                print(f"App entries: {', '.join(result['app_entries'])}")
            for item in result['missing_app_entries']:
                print(f"  ! missing app path: {item}")
            if not args.dry_run and not result['missing_app_entries'] and result['source_exists']:
                print(f"Files written: {result['files_written']}")
                print(f"Payload size: {human_mb(result['bytes_written'])}")
        bad = (not result['source_exists'] or bool(result['missing_app_entries']))
        return 1 if bad else 0

    if args.command == "prepare-update-manifest":
        if not args.staging_dir:
            print("--staging-dir is required", file=sys.stderr)
            return 2
        if not args.target_version:
            print("--target-version is required", file=sys.stderr)
            return 2

        manifest_path = (args.manifest or (root / "data" / "update_manifest.json")).resolve()
        staging_dir = args.staging_dir.resolve()
        manifest_data = build_runtime_update_manifest(
            root=root,
            staging_dir=staging_dir,
            target_version=args.target_version,
            backup_path=args.backup_path,
            current_version=args.current_version,
            health_check_url=args.health_check_url,
            version_check_url=args.version_check_url,
        )

        if args.dry_run:
            print(json.dumps(manifest_data, indent=2))
            return 0

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
        validation = validate_update_payload(root, manifest_path)
        bad = (
            not validation['manifest_present']
            or not validation['staging_exists']
            or bool(validation['unexpected_top_level'])
            or bool(validation['missing_app_entries'])
            or not validation['project_root_matches_root']
            or bool(validation['missing_required_protected_paths'])
            or bool(validation['unexpected_protected_paths'])
            or bool(validation['protected_paths_outside_runtime_roots'])
            or not validation['backup_parent_exists']
        )
        if args.json:
            print(json.dumps({"manifest": manifest_data, "validation": validation}, indent=2))
        else:
            print(f"Runtime update manifest written: {manifest_path}")
            print(f"Staging dir: {staging_dir}")
            print(f"Target version: {args.target_version}")
            print(f"Protected paths: {', '.join(manifest_data['protected_paths'])}")
            print(f"Backup path: {manifest_data['backup_path']}")
        return 1 if bad else 0

    if args.command == "prepare-rollback-manifest":
        if not args.backup_path:
            print("--backup-path is required", file=sys.stderr)
            return 2
        manifest_path = (args.manifest or (root / "data" / "update_manifest.json")).resolve()
        backup_path = Path(args.backup_path).expanduser().resolve()
        manifest_data = build_runtime_rollback_manifest(
            root=root,
            backup_path=backup_path,
            health_check_url=args.health_check_url,
            version_check_url=args.version_check_url,
        )
        if args.dry_run:
            print(json.dumps(manifest_data, indent=2))
            return 0
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
        validation = validate_update_payload(root, manifest_path)
        bad = (
            not validation['manifest_present']
            or not validation['project_root_matches_root']
            or bool(validation['missing_required_protected_paths'])
            or bool(validation['unexpected_protected_paths'])
            or bool(validation['protected_paths_outside_runtime_roots'])
            or not validation['backup_parent_exists']
            or not validation['backup_exists']
        )
        if args.json:
            print(json.dumps({"manifest": manifest_data, "validation": validation}, indent=2))
        else:
            print(f"Runtime rollback manifest written: {manifest_path}")
            print(f"Backup path: {manifest_data['backup_path']}")
            print(f"Protected paths: {', '.join(manifest_data['protected_paths'])}")
        return 1 if bad else 0

    if args.command == "prepare-runtime-update":
        if not args.runtime_zip:
            print("--runtime-zip is required", file=sys.stderr)
            return 2
        if not args.target_version:
            print("--target-version is required", file=sys.stderr)
            return 2
        manifest_path = (args.manifest or (root / 'data' / 'update_manifest.json')).resolve()
        stage_result = stage_runtime_zip(root=root, runtime_zip=args.runtime_zip, output_dir=args.output_dir, dry_run=args.dry_run)
        if stage_result['missing_app_entries'] or not stage_result['runtime_zip_exists'] or not stage_result['selected_runtime_root']:
            payload = {"stage": stage_result}
            print(json.dumps(payload, indent=2) if args.json or args.dry_run else json.dumps(payload, indent=2))
            return 1
        manifest_data = build_runtime_update_manifest(
            root=root,
            staging_dir=Path(stage_result['output_dir']),
            target_version=args.target_version,
            backup_path=args.backup_path,
            current_version=args.current_version,
            health_check_url=args.health_check_url,
            version_check_url=args.version_check_url,
        )
        rehearsal_result = None
        validation = None
        if not args.dry_run:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding='utf-8')
            validation = validate_update_payload(root, manifest_path)
            rehearsal_result = validate_rehearsal(root, manifest_path)
        payload = {
            "stage": stage_result,
            "manifest": manifest_data,
            "validation": validation,
            "rehearsal": rehearsal_result,
        }
        print(json.dumps(payload, indent=2))
        bad = False
        if validation is not None:
            bad = (
                not validation['manifest_present']
                or not validation['staging_exists']
                or bool(validation['unexpected_top_level'])
                or bool(validation['missing_app_entries'])
                or not validation['project_root_matches_root']
                or bool(validation['missing_required_protected_paths'])
                or bool(validation['unexpected_protected_paths'])
                or bool(validation['protected_paths_outside_runtime_roots'])
                or not validation['backup_parent_exists']
                or any(not item['ok'] for item in (rehearsal_result or {}).get('checklist', []))
            )
        return 1 if bad else 0

    if args.command == "prepare-closed-loop-rehearsal":
        if not args.runtime_zip:
            print("--runtime-zip is required", file=sys.stderr)
            return 2
        if not args.target_version:
            print("--target-version is required", file=sys.stderr)
            return 2
        payload = prepare_closed_loop_rehearsal(
            root=root,
            runtime_zip=args.runtime_zip,
            target_version=args.target_version,
            output_dir=args.output_dir,
            backup_path=Path(args.backup_path) if args.backup_path else None,
            update_manifest_path=args.manifest,
            rollback_manifest_path=args.rollback_manifest,
            current_version=args.current_version,
            health_check_url=args.health_check_url,
            version_check_url=args.version_check_url,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        bad = (
            not payload['backup']['source_exists']
            or bool(payload['backup']['missing_app_entries'])
            or not payload['stage']['runtime_zip_exists']
            or not payload['stage']['selected_runtime_root']
            or bool(payload['stage']['missing_app_entries'])
            or (payload['update_validation'] is not None and (
                not payload['update_validation']['manifest_present']
                or not payload['update_validation']['staging_exists']
                or bool(payload['update_validation']['unexpected_top_level'])
                or bool(payload['update_validation']['missing_app_entries'])
                or not payload['update_validation']['project_root_matches_root']
                or bool(payload['update_validation']['missing_required_protected_paths'])
                or bool(payload['update_validation']['unexpected_protected_paths'])
                or bool(payload['update_validation']['protected_paths_outside_runtime_roots'])
                or not payload['update_validation']['backup_parent_exists']
            ))
            or (payload['rollback_validation'] is not None and (
                not payload['rollback_validation']['manifest_present']
                or not payload['rollback_validation']['project_root_matches_root']
                or not payload['rollback_validation']['backup_exists']
                or not payload['rollback_validation']['backup_payload']
                or bool(payload['rollback_validation']['backup_payload']['unexpected_top_level'])
                or bool(payload['rollback_validation']['backup_payload']['missing_app_entries'])
            ))
            or (payload['rehearsal'] is not None and any(not item['ok'] for item in payload['rehearsal']['checklist']))
        )
        return 1 if bad else 0

    if args.command == "init-drill-workspace":
        payload = initialize_drill_workspace(
            root,
            label=args.label,
            operator=args.operator,
            device_id=args.device_id,
            service_ticket=args.service_ticket,
            notes=args.notes,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "capture-field-state":
        state_path = (args.state or (root / "data" / "field_state.json")).resolve()
        payload = collect_runtime_boundary_state(
            root,
            drill_context=build_drill_context(
                label=args.label,
                operator=args.operator,
                device_id=args.device_id,
                service_ticket=args.service_ticket,
                drill_phase=args.drill_phase,
                notes=args.notes,
            ),
        )
        if args.dry_run:
            print(json.dumps(payload, indent=2))
            return 0
        write_json(state_path, payload)
        if "data/support/drills/" in state_path.as_posix():
            refresh_drill_workspace_status(root, label=args.label, dry_run=False)
        if args.json:
            print(json.dumps({"state_path": str(state_path), "state": payload}, indent=2))
        else:
            print(f"Field state written: {state_path}")
            print(f"Version: {payload['config_version']}")
            print(f"Config files: {payload['config']['file_count']}")
            print(f"Data files: {payload['data']['file_count']}")
            print(f"Log files: {payload['logs']['file_count']}")
            if payload.get("drill_context"):
                print(f"Drill metadata: {json.dumps(payload['drill_context'], ensure_ascii=False)}")
        return 0

    if args.command == "compare-field-state":
        before_path = (args.before or (root / "data" / "field_state_before.json")).resolve()
        after_path = (args.after or (root / "data" / "field_state_after.json")).resolve()
        if not before_path.exists() or not after_path.exists():
            print(json.dumps({"before_exists": before_path.exists(), "after_exists": after_path.exists()}, indent=2), file=sys.stderr)
            return 2
        before_state = json.loads(before_path.read_text(encoding="utf-8"))
        after_state = json.loads(after_path.read_text(encoding="utf-8"))
        comparison = compare_runtime_boundary_state(before_state, after_state)
        payload = {
            "label": args.label,
            "before_path": str(before_path),
            "after_path": str(after_path),
            "comparison": comparison,
        }
        if args.report and not args.dry_run:
            report_path = args.report.resolve()
            write_field_report_markdown(report_path, before_state, after_state, comparison, args.label)
            payload["report_path"] = str(report_path)
        if args.json or True:
            print(json.dumps(payload, indent=2))
        bad = (
            not comparison["data_boundary_present_before_and_after"]
            or not comparison["logs_boundary_present_before_and_after"]
            or not comparison["config_boundary_stable"]
            or not comparison["drill_context_matches"]
        )
        return 1 if bad else 0

    if args.command == "build-drill-leg-summary":
        if not args.before or not args.after:
            print("--before and --after are required", file=sys.stderr)
            return 2
        if not args.leg:
            print("--leg is required", file=sys.stderr)
            return 2
        payload = build_drill_leg_summary(
            root,
            before_path=args.before.resolve(),
            after_path=args.after.resolve(),
            report_path=args.report.resolve() if args.report else None,
            summary_path=args.summary.resolve() if args.summary else None,
            label=args.label,
            leg=args.leg,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        if not args.dry_run:
            refresh_drill_workspace_status(root, label=args.label, dry_run=False)
        return 0 if payload["status"]["passed"] else 1

    if args.command == "build-paired-drill-summary":
        if not args.update_leg or not args.rollback_leg:
            print("--update-leg and --rollback-leg are required", file=sys.stderr)
            return 2
        payload = build_paired_drill_summary(
            root,
            update_leg_path=args.update_leg.resolve(),
            rollback_leg_path=args.rollback_leg.resolve(),
            label=args.label,
            summary_json_path=args.summary.resolve() if args.summary else None,
            summary_md_path=args.summary_md.resolve() if args.summary_md else None,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        if not args.dry_run:
            refresh_drill_workspace_status(root, label=args.label, dry_run=False)
        return 0 if payload["closed_loop_passed"] else 1

    if args.command == "show-attachment-readiness":
        handoff = refresh_drill_workspace_status(root, label=args.label, dry_run=args.dry_run)
        raw_history = handoff.get("ticket_acknowledgment_history") or {}
        payload = build_attachment_review_summary(
            label=args.label,
            recommendation=handoff.get("recommendation") or {},
            freshness=handoff.get("freshness") or {},
            artifacts=handoff.get("artifacts") or {},
            ticket_acknowledgment=handoff.get("ticket_acknowledgment") or {},
            ticket_acknowledgment_history=raw_history.get("history") if isinstance(raw_history, dict) else None,
        )
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(payload["plain_text"], end="")
        readiness = payload.get("attachment_readiness") or {}
        blocked = bool(readiness.get("missing_required"))
        return 1 if blocked else 0

    if args.command == "acknowledge-drill-handoff":
        payload = acknowledge_drill_handoff(
            root,
            label=args.label,
            attached_by=args.attached_by or args.operator,
            attached_at=args.attached_at,
            ticket_status=args.ticket_status,
            ticket_reference=args.ticket_reference,
            ticket_url=args.ticket_url,
            note=args.notes,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "reacknowledge-drill-handoff":
        try:
            payload = reacknowledge_drill_handoff(
                root,
                label=args.label,
                attached_by=args.attached_by or args.operator,
                attached_at=args.attached_at,
                ticket_status=args.ticket_status,
                ticket_reference=args.ticket_reference,
                ticket_url=args.ticket_url,
                note=args.notes,
                dry_run=args.dry_run,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "finalize-drill-handoff":
        payload = finalize_drill_handoff(
            root,
            label=args.label,
            update_leg_path=args.update_leg.resolve() if args.update_leg else None,
            rollback_leg_path=args.rollback_leg.resolve() if args.rollback_leg else None,
            summary_json_path=args.summary.resolve() if args.summary else None,
            summary_md_path=args.summary_md.resolve() if args.summary_md else None,
            bundle_path=args.bundle.resolve() if args.bundle else None,
            before=args.before.resolve() if args.before else None,
            after=args.after.resolve() if args.after else None,
            report=args.report.resolve() if args.report else None,
            manifest=args.manifest.resolve() if args.manifest else None,
            rollback_manifest=args.rollback_manifest.resolve() if args.rollback_manifest else None,
            include_logs=not args.no_logs,
            include_downloads=args.include_downloads,
            operator=args.operator,
            device_id=args.device_id,
            service_ticket=args.service_ticket,
            notes=args.notes,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        handoff = payload["handoff"]
        return 0 if handoff.get("recommendation", {}).get("status") == "ship" else 1

    if args.command == "build-support-bundle":
        payload = build_support_bundle(
            root,
            bundle_path=args.bundle,
            label=args.label,
            before=args.before,
            after=args.after,
            report=args.report,
            manifest=args.manifest,
            rollback_manifest=args.rollback_manifest,
            include_logs=not args.no_logs,
            include_downloads=args.include_downloads,
            operator=args.operator,
            device_id=args.device_id,
            service_ticket=args.service_ticket,
            drill_phase=args.drill_phase,
            notes=args.notes,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        if not args.dry_run:
            refresh_drill_workspace_status(root, label=args.label, dry_run=False)
        bad = not payload["included"]
        return 1 if bad else 0

    if args.command == "record-updater-run":
        if args.exit_code is None:
            print("--exit-code is required", file=sys.stderr)
            return 2
        payload = record_updater_run(
            root,
            manifest_path=args.manifest,
            exit_code=args.exit_code,
            update_result_path=args.update_result,
            log_path=args.log_path,
            notes=args.notes,
            dry_run=args.dry_run,
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "report":
        result = {
            "root": str(root),
            "missing": missing,
            "policy": policy.__dict__,
            "logs": human_mb(sum(p.stat().st_size for p in iter_files(root / 'data' / 'logs'))),
            "downloads": len(list(iter_files(root / 'data' / 'downloads'))),
            "app_backups": len(list(iter_files(root / 'data' / 'app_backups'))),
        }
        print(json.dumps(result, indent=2) if args.json else result)
        return 0

    result = run_cleanup(root, policy, args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Runtime cleanup ({'dry-run' if args.dry_run else 'apply'})")
        print(f"Created dirs: {len(result['created_dirs'])}")
        print(f"Removed paths: {len(result['removed_paths'])}")
        for item in result['removed_paths'][:40]:
            print(f"  - {item}")
        if len(result['removed_paths']) > 40:
            print(f"  ... +{len(result['removed_paths']) - 40} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
