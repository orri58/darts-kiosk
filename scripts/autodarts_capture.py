#!/usr/bin/env python3
"""Autodarts capture harness for field diagnostics.

Goal:
- capture WebSocket frames, SPA navigation, selected HTTP metadata, and basic context
- write newline-delimited JSON (jsonl) plus a summary.json for later analysis
- run locally on a board/test device with the real Chrome profile if desired

This tool is intentionally local-first and operator-friendly.
It does not send data anywhere.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import signal
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / "backend" / ".env"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_ROOT = DEFAULT_DATA_DIR / "autodarts_capture"
DEFAULT_AUTODARTS_URL = "https://play.autodarts.io"
MAX_RAW_TEXT = 65535
MAX_RESPONSE_BODY = 100_000
AUTODARTS_API_HOSTS = ("api.autodarts.io", "play.autodarts.io")


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def redacted_token_fingerprint(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
    return digest[:12]


def trim_text(value: Any, limit: int = MAX_RAW_TEXT) -> tuple[str, bool, int]:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    original_len = len(text)
    if original_len <= limit:
        return text, False, original_len
    return text[:limit], True, original_len


def safe_jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, dict):
            return {str(k): safe_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [safe_jsonable(v) for v in value]
        return str(value)


UUID_RE = re.compile(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", re.IGNORECASE)


def extract_channel(raw: str) -> str:
    patterns = [
        r"(autodarts\.matches\.[a-f0-9-]+\.\S+)",
        r"(autodarts\.lobbies\.[a-f0-9-]+\.\S+)",
        r"(autodarts\.tournaments\.[a-f0-9-]+\.\S+)",
        r"(autodarts\.boards\.\S+)",
        r"(autodarts\.\S+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            return match.group(1)
    if raw.startswith("[") or raw.startswith("42["):
        try:
            arr = json.loads(raw.lstrip("0123456789"))
            if isinstance(arr, list) and arr and isinstance(arr[0], str):
                return arr[0]
        except Exception:
            pass
    return "unknown"


def parse_payload(raw: str) -> tuple[Any | None, str]:
    try:
        return json.loads(raw), "json"
    except Exception:
        pass

    match = re.match(r"^\d+(.+)$", raw)
    if match:
        try:
            return json.loads(match.group(1)), "socketio"
        except Exception:
            pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1]), "embedded_json"
        except Exception:
            pass

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1]), "json_array"
        except Exception:
            pass

    return None, "text"


def nested_get(node: Any, *keys: str) -> Any:
    current = node
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extract_event(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("event", "type"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for container_key in ("data", "body", "match", "lobby", "game"):
            nested = payload.get(container_key)
            result = extract_event(nested)
            if result:
                return result
    if isinstance(payload, list):
        for item in payload:
            result = extract_event(item)
            if result:
                return result
    return None


def extract_variant(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        value = payload.get("variant")
        if isinstance(value, str) and value.strip():
            return value.strip()
        for nested in payload.values():
            found = extract_variant(nested)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_variant(item)
            if found:
                return found
    return None


def extract_bool(payload: Any, field_name: str) -> Optional[bool]:
    if isinstance(payload, dict):
        if payload.get(field_name) is True:
            return True
        for nested in payload.values():
            result = extract_bool(nested, field_name)
            if result is True:
                return True
    elif isinstance(payload, list):
        for item in payload:
            result = extract_bool(item, field_name)
            if result is True:
                return True
    return None


def extract_winner(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("winner", "matchWinner", "gameWinner"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("nickname", "name", "username"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        return nested_value.strip()
        for nested in payload.values():
            found = extract_winner(nested)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_winner(item)
            if found:
                return found
    return None


def extract_state(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("state", "matchState", "status"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for nested in payload.values():
            found = extract_state(nested)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_state(item)
            if found:
                return found
    return None


def extract_context_id(channel: str, payload: Any, root_name: str) -> Optional[str]:
    candidates: list[str] = []
    if channel:
        candidates.append(channel)
    if isinstance(payload, dict):
        for key in ("topic", "id", f"{root_name[:-1]}Id", f"{root_name[:-1]}_id", "matchId", "lobbyId", "tournamentId"):
            value = payload.get(key)
            if isinstance(value, str):
                candidates.append(value)
        for nested_key in ("data", root_name[:-1], "match", "lobby", "tournament", "board"):
            nested = payload.get(nested_key)
            if isinstance(nested, dict):
                for key in ("topic", "id", f"{root_name[:-1]}Id", f"{root_name[:-1]}_id"):
                    value = nested.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
    for candidate in candidates:
        match = re.search(rf"autodarts\.{root_name}\.([a-f0-9-]+)", candidate, re.IGNORECASE)
        if match:
            return match.group(1)
        match = UUID_RE.search(candidate)
        if match:
            return match.group(1)
    return None


def extract_players(payload: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    player_keys = {"players", "participants", "members", "teams", "opponents", "competitors"}

    def add_name(value: Any):
        if value is None:
            return
        text = str(value).strip()
        if not text:
            return
        key = text.lower()
        if key not in seen:
            seen.add(key)
            names.append(text)

    def walk(node: Any, in_player_context: bool = False, depth: int = 0):
        if depth > 8 or node is None:
            return
        if isinstance(node, dict):
            if in_player_context:
                for key in ("nickname", "displayName", "display_name", "name", "username", "label", "playerName"):
                    if key in node:
                        add_name(node.get(key))
                user = node.get("user")
                if isinstance(user, dict):
                    walk(user, True, depth + 1)
            for key, value in node.items():
                key_lower = str(key).lower()
                walk(value, in_player_context or key_lower in player_keys, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, in_player_context, depth + 1)
        elif in_player_context and isinstance(node, str):
            add_name(node)

    walk(payload)
    return names


@dataclass
class CaptureSummary:
    started_at: str
    finished_at: Optional[str] = None
    session_dir: str = ""
    board_id: str = ""
    autodarts_url: str = ""
    profile_dir: str = ""
    headless: bool = False
    duration_seconds_requested: int = 0
    websocket_frames_total: int = 0
    websocket_frames_received: int = 0
    websocket_frames_sent: int = 0
    http_requests_logged: int = 0
    http_responses_logged: int = 0
    console_events_logged: int = 0
    browser_events_logged: int = 0
    pages_seen: int = 0
    last_url: Optional[str] = None
    last_title: Optional[str] = None
    last_match_id: Optional[str] = None
    last_lobby_id: Optional[str] = None
    last_tournament_id: Optional[str] = None
    last_variant: Optional[str] = None
    last_players: list[str] = field(default_factory=list)
    last_winner: Optional[str] = None
    last_state: Optional[str] = None
    channels_seen: dict[str, int] = field(default_factory=dict)
    event_names_seen: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class JSONLWriter:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        self._lock = asyncio.Lock()

    async def write(self, event: dict[str, Any]):
        async with self._lock:
            self._fh.write(json.dumps(safe_jsonable(event), ensure_ascii=False) + "\n")
            self._fh.flush()

    def close(self):
        self._fh.close()


class AutodartsCapture:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_name = args.session_name or f"capture-{timestamp}"
        self.session_dir = args.output_dir / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.writer = JSONLWriter(self.session_dir / "capture.jsonl")
        self.summary = CaptureSummary(
            started_at=utc_now(),
            session_dir=str(self.session_dir),
            board_id=args.board_id or "",
            autodarts_url=args.url,
            profile_dir=str(args.profile_dir),
            headless=args.headless,
            duration_seconds_requested=args.duration_seconds,
        )
        self._stop_event = asyncio.Event()
        self._playwright = None
        self._context = None
        self._pages_seen: set[int] = set()
        self._event_counter = 0

    async def emit(self, event_type: str, **payload: Any):
        self._event_counter += 1
        event = {
            "ts": utc_now(),
            "seq": self._event_counter,
            "type": event_type,
            **payload,
        }
        await self.writer.write(event)

    def update_summary_from_ws(self, channel: str, payload: Any, direction: str):
        self.summary.websocket_frames_total += 1
        if direction == "received":
            self.summary.websocket_frames_received += 1
        elif direction == "sent":
            self.summary.websocket_frames_sent += 1
        if channel:
            self.summary.channels_seen[channel] = self.summary.channels_seen.get(channel, 0) + 1
        event_name = extract_event(payload)
        if event_name:
            self.summary.event_names_seen[event_name] = self.summary.event_names_seen.get(event_name, 0) + 1
        match_id = extract_context_id(channel, payload, "matches")
        lobby_id = extract_context_id(channel, payload, "lobbies")
        tournament_id = extract_context_id(channel, payload, "tournaments")
        variant = extract_variant(payload)
        players = extract_players(payload)
        winner = extract_winner(payload)
        state = extract_state(payload)
        if match_id:
            self.summary.last_match_id = match_id
        if lobby_id:
            self.summary.last_lobby_id = lobby_id
        if tournament_id:
            self.summary.last_tournament_id = tournament_id
        if variant:
            self.summary.last_variant = variant
        if players:
            self.summary.last_players = players
        if winner:
            self.summary.last_winner = winner
        if state:
            self.summary.last_state = state

    async def on_browser_bridge(self, source, payload: Any):
        self.summary.browser_events_logged += 1
        page = getattr(source, "page", None)
        page_url = None
        try:
            page_url = page.url if page else None
        except Exception:
            page_url = None
        if isinstance(payload, dict):
            href = payload.get("href")
            title = payload.get("title")
            if isinstance(href, str) and href:
                self.summary.last_url = href
            if isinstance(title, str) and title:
                self.summary.last_title = title
        await self.emit("browser_event", page_url=page_url, payload=payload)

    async def on_request(self, request):
        url = request.url
        if not any(host in url for host in AUTODARTS_API_HOSTS):
            return
        self.summary.http_requests_logged += 1
        headers = {}
        token_fp = None
        auth_present = False
        try:
            all_headers = await request.all_headers()
            auth_header = all_headers.get("authorization") or all_headers.get("Authorization")
            auth_present = bool(auth_header)
            if isinstance(auth_header, str) and auth_header.lower().startswith("bearer "):
                token_fp = redacted_token_fingerprint(auth_header[7:].strip())
            allowed = {"content-type", "accept", "origin", "referer", "user-agent"}
            headers = {k: v for k, v in all_headers.items() if k.lower() in allowed}
        except Exception:
            pass
        await self.emit(
            "http_request",
            url=url,
            method=request.method,
            resource_type=request.resource_type,
            is_navigation=request.is_navigation_request(),
            headers=headers,
            auth_present=auth_present,
            token_fingerprint=token_fp,
        )

    async def on_response(self, response):
        url = response.url
        if not any(host in url for host in AUTODARTS_API_HOSTS):
            return
        self.summary.http_responses_logged += 1
        content_type = None
        body_preview = None
        body_truncated = None
        body_original_len = None
        if self.args.capture_api_bodies:
            try:
                headers = await response.all_headers()
                content_type = headers.get("content-type")
                if content_type and "json" in content_type.lower():
                    text = await response.text()
                    body_preview, body_truncated, body_original_len = trim_text(text, MAX_RESPONSE_BODY)
                else:
                    body_preview = None
            except Exception:
                pass
        await self.emit(
            "http_response",
            url=url,
            status=response.status,
            ok=response.ok,
            content_type=content_type,
            body_preview=body_preview,
            body_truncated=body_truncated,
            body_original_len=body_original_len,
        )

    async def on_console(self, msg):
        self.summary.console_events_logged += 1
        try:
            text = msg.text
        except Exception:
            text = "<unavailable>"
        await self.emit("console", level=msg.type, text=text)

    async def on_page(self, page):
        page_id = id(page)
        if page_id in self._pages_seen:
            return
        self._pages_seen.add(page_id)
        self.summary.pages_seen = len(self._pages_seen)
        try:
            await page.expose_binding("__ocCapturePagePing", lambda source, payload=None: None)
        except Exception:
            pass
        page.on("console", lambda msg: asyncio.create_task(self.on_console(msg)))
        page.on("websocket", self._on_ws_created)
        page.on("framenavigated", lambda frame: asyncio.create_task(self._on_frame_navigated(frame)))
        page.on("load", lambda: asyncio.create_task(self._emit_page_state(page, "load")))
        page.on("domcontentloaded", lambda: asyncio.create_task(self._emit_page_state(page, "domcontentloaded")))
        await self._emit_page_state(page, "attached")

    async def _emit_page_state(self, page, phase: str):
        url = None
        title = None
        try:
            url = page.url
            title = await page.title()
        except Exception:
            pass
        if url:
            self.summary.last_url = url
        if title:
            self.summary.last_title = title
        await self.emit("page_state", phase=phase, url=url, title=title)

    async def _on_frame_navigated(self, frame):
        if frame.parent_frame is not None:
            return
        url = getattr(frame, "url", None)
        if url:
            self.summary.last_url = url
        await self.emit("navigation", url=url, frame_name=frame.name)

    def _on_ws_created(self, ws):
        ws_url = ws.url
        asyncio.create_task(self.emit("websocket_open", ws_url=ws_url))
        ws.on("framereceived", lambda payload: asyncio.create_task(self._handle_ws_frame(ws_url, payload, "received")))
        ws.on("framesent", lambda payload: asyncio.create_task(self._handle_ws_frame(ws_url, payload, "sent")))
        ws.on("close", lambda: asyncio.create_task(self.emit("websocket_close", ws_url=ws_url)))

    async def _handle_ws_frame(self, ws_url: str, payload: Any, direction: str):
        raw_text, truncated, original_len = trim_text(payload)
        channel = extract_channel(raw_text)
        parsed_payload, payload_type = parse_payload(raw_text)
        self.update_summary_from_ws(channel, parsed_payload, direction)
        await self.emit(
            "websocket_frame",
            ws_url=ws_url,
            direction=direction,
            channel=channel,
            payload_type=payload_type,
            event=extract_event(parsed_payload),
            state=extract_state(parsed_payload),
            variant=extract_variant(parsed_payload),
            finished=extract_bool(parsed_payload, "finished"),
            gameFinished=extract_bool(parsed_payload, "gameFinished"),
            winner=extract_winner(parsed_payload),
            match_id=extract_context_id(channel, parsed_payload, "matches"),
            lobby_id=extract_context_id(channel, parsed_payload, "lobbies"),
            tournament_id=extract_context_id(channel, parsed_payload, "tournaments"),
            players=extract_players(parsed_payload),
            raw_text=raw_text,
            raw_truncated=truncated,
            raw_original_len=original_len,
            payload=parsed_payload,
        )

    async def _write_meta(self):
        meta = {
            "started_at": self.summary.started_at,
            "board_id": self.args.board_id,
            "autodarts_url": self.args.url,
            "profile_dir": str(self.args.profile_dir),
            "output_dir": str(self.session_dir),
            "headless": self.args.headless,
            "duration_seconds": self.args.duration_seconds,
            "capture_api_bodies": self.args.capture_api_bodies,
            "python": sys.version,
            "argv": sys.argv,
        }
        (self.session_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    async def _write_summary(self):
        self.summary.finished_at = utc_now()
        (self.session_dir / "summary.json").write_text(
            json.dumps(asdict(self.summary), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    async def _open_browser(self):
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch_kwargs = {
            "user_data_dir": str(self.args.profile_dir),
            "headless": self.args.headless,
            "ignore_https_errors": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        try:
            self._context = await self._playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
            launch_mode = "chrome"
        except Exception as chrome_error:
            executable_path = self._find_playwright_chromium_executable()
            if not executable_path:
                raise RuntimeError(f"Chrome channel failed and no Playwright Chromium fallback found: {chrome_error}")
            self._context = await self._playwright.chromium.launch_persistent_context(
                executable_path=executable_path,
                **launch_kwargs,
            )
            launch_mode = f"playwright-chromium:{executable_path}"
        await self.emit("capture_started", launch_mode=launch_mode)

        await self._context.expose_binding("__ocCaptureEmit", self.on_browser_bridge)
        await self._context.add_init_script(
            """
            (() => {
              const safeEmit = (kind, payload = {}) => {
                try {
                  if (typeof window.__ocCaptureEmit === 'function') {
                    window.__ocCaptureEmit({
                      kind,
                      payload,
                      href: String(location.href || ''),
                      title: String(document.title || ''),
                      ts: new Date().toISOString(),
                    });
                  }
                } catch (_) {}
              };

              const wrapHistory = (name) => {
                const original = history[name];
                if (typeof original !== 'function') return;
                history[name] = function(...args) {
                  const result = original.apply(this, args);
                  safeEmit('spa_navigation', { method: name, target: args[2] ?? null });
                  return result;
                };
              };

              wrapHistory('pushState');
              wrapHistory('replaceState');
              window.addEventListener('popstate', () => safeEmit('spa_navigation', { method: 'popstate' }));
              window.addEventListener('hashchange', () => safeEmit('spa_navigation', { method: 'hashchange' }));

              const titleObserver = new MutationObserver(() => {
                safeEmit('title_change', { title: String(document.title || '') });
              });
              const watchTitle = () => {
                const titleNode = document.querySelector('title');
                if (titleNode) {
                  titleObserver.observe(titleNode, { childList: true, subtree: true, characterData: true });
                }
              };
              if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', watchTitle, { once: true });
              } else {
                watchTitle();
              }

              safeEmit('init_script_ready', { readyState: document.readyState });
            })();
            """
        )

        self._context.on("page", lambda page: asyncio.create_task(self.on_page(page)))
        self._context.on("request", lambda request: asyncio.create_task(self.on_request(request)))
        self._context.on("response", lambda response: asyncio.create_task(self.on_response(response)))

        for page in self._context.pages:
            await self.on_page(page)

        page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await page.goto(self.args.url, wait_until="domcontentloaded", timeout=30000)
        await self._emit_page_state(page, "goto_initial_url")

    def _find_playwright_chromium_executable(self) -> Optional[str]:
        explicit = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or os.environ.get("CHROMIUM_BIN")
        if explicit and Path(explicit).exists():
            return explicit
        cache_root = Path.home() / ".cache" / "ms-playwright"
        if cache_root.exists():
            for candidate in sorted(cache_root.glob("chromium-*/chrome-linux/chrome"), reverse=True):
                if candidate.exists():
                    return str(candidate)
            for candidate in sorted(cache_root.glob("chromium-*/*/chrome.exe"), reverse=True):
                if candidate.exists():
                    return str(candidate)
        return None

    async def run(self):
        await self._write_meta()
        await self.emit(
            "meta",
            board_id=self.args.board_id,
            profile_dir=str(self.args.profile_dir),
            output_dir=str(self.session_dir),
            capture_api_bodies=self.args.capture_api_bodies,
        )
        await self._open_browser()
        if self.args.duration_seconds > 0:
            await self.emit("timer", seconds=self.args.duration_seconds)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.args.duration_seconds)
            except asyncio.TimeoutError:
                await self.emit("capture_timeout", seconds=self.args.duration_seconds)
        else:
            await self.emit("capture_waiting", message="Press Ctrl+C to stop capture")
            await self._stop_event.wait()

    async def shutdown(self, reason: str = "manual_stop"):
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        await self.emit("capture_stopping", reason=reason)
        try:
            if self._context:
                await self._context.close()
        except Exception as exc:
            await self.emit("warning", stage="context_close", error=str(exc))
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            await self.emit("warning", stage="playwright_stop", error=str(exc))
        await self._write_summary()
        self.writer.close()


async def async_main(args: argparse.Namespace) -> int:
    capture = AutodartsCapture(args)

    loop = asyncio.get_running_loop()

    def _schedule_stop(signame: str):
        asyncio.create_task(capture.shutdown(reason=signame))

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _schedule_stop, sig.name)
        except NotImplementedError:
            signal.signal(sig, lambda *_: asyncio.create_task(capture.shutdown(reason=sig.name)))

    try:
        await capture.run()
    finally:
        await capture.shutdown(reason="normal_exit")
    print(f"Capture written to: {capture.session_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    env_values = load_env_file(DEFAULT_ENV_FILE)
    board_id = env_values.get("BOARD_ID", "BOARD-1")
    url = env_values.get("AUTODARTS_URL", DEFAULT_AUTODARTS_URL)
    profile_dir = DEFAULT_DATA_DIR / "chrome_profile" / board_id

    parser = argparse.ArgumentParser(description="Capture Autodarts WebSocket/API/navigation data into JSONL files.")
    parser.add_argument("--url", default=url, help="Autodarts URL to open")
    parser.add_argument("--board-id", default=board_id, help="Board ID label used for metadata/output")
    parser.add_argument("--profile-dir", type=Path, default=profile_dir, help="Chrome profile dir to use")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Root output directory for capture sessions")
    parser.add_argument("--session-name", default="", help="Optional explicit capture session directory name")
    parser.add_argument("--duration-seconds", type=int, default=0, help="Stop automatically after N seconds (0 = run until Ctrl+C)")
    parser.add_argument("--headless", action="store_true", help="Run without visible browser window")
    parser.add_argument("--capture-api-bodies", action="store_true", help="Also store JSON response previews from api.autodarts.io")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.profile_dir = Path(args.profile_dir)
    args.output_dir = Path(args.output_dir)
    args.profile_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
