#!/usr/bin/env python3
"""Lightweight local/device smoke test for the kiosk runtime.

Uses only the Python standard library so it can run on fresh Windows installs
without extra tooling. Intended for operator bring-up and quick sanity checks.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch_json(url: str) -> tuple[int, dict | list | str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except Exception:
            payload = body
        return exc.code, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--board-id", default="BOARD-1")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    board_id = urllib.parse.quote(args.board_id)

    checks = [
        ("health", f"{base}/api/health"),
        ("version", f"{base}/api/system/version"),
        ("boards", f"{base}/api/boards"),
        ("observer", f"{base}/api/kiosk/{board_id}/observer-status"),
    ]

    failures = 0
    print(f"[SMOKE] base_url={base} board_id={args.board_id}")
    for label, url in checks:
        try:
            status, payload = fetch_json(url)
        except Exception as exc:  # pragma: no cover - CLI path
            failures += 1
            print(f"[FAIL] {label:<10} request error: {exc}")
            continue

        if status >= 400:
            failures += 1
            print(f"[FAIL] {label:<10} HTTP {status}: {payload}")
            continue

        if label == "health":
            print(f"[ OK ] {label:<10} {payload}")
        elif label == "version":
            print(f"[ OK ] {label:<10} installed_version={payload.get('installed_version')}")
        elif label == "boards":
            board_ids = [item.get("board_id") for item in payload if isinstance(item, dict)]
            if args.board_id not in board_ids:
                failures += 1
                print(f"[FAIL] {label:<10} board {args.board_id} missing; found={board_ids}")
            else:
                print(f"[ OK ] {label:<10} boards={board_ids}")
        elif label == "observer":
            summary = {
                "mode": payload.get("autodarts_mode"),
                "running": payload.get("running"),
                "connected": payload.get("connected"),
                "last_error": payload.get("last_error"),
                "credits_remaining": payload.get("credits_remaining"),
                "pricing_mode": payload.get("pricing_mode"),
            }
            print(f"[ OK ] {label:<10} {summary}")

    if failures:
        print(f"[DONE] smoke test finished with {failures} failure(s)")
        return 1

    print("[DONE] smoke test passed")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI path
    raise SystemExit(main())
