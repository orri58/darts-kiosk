"""
Update Service — GitHub-based
Checks GitHub Releases for new versions, downloads assets,
triggers backup before update, persists update history to DB.
Includes a background scheduler that checks once per interval.
"""
import os
import asyncio
import logging
import platform
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR
from backend.services.version_service import read_app_version

GITHUB_REPO = os.environ.get('GITHUB_REPO', '').strip().strip('/')
GITHUB_API = "https://api.github.com"
DOWNLOADS_DIR = DATA_DIR / 'downloads'
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

UPDATE_CHECK_ENABLED = os.environ.get('UPDATE_CHECK_ENABLED', 'true').lower() in ('true', '1', 'yes')
UPDATE_CHECK_INTERVAL_HOURS = int(os.environ.get('UPDATE_CHECK_INTERVAL_HOURS', '24'))


@dataclass
class GitHubRelease:
    version: str
    tag: str
    name: str
    body: str = ""
    published_at: str = ""
    is_prerelease: bool = False
    html_url: str = ""
    assets: List[Dict] = field(default_factory=list)
    is_current: bool = False
    is_newer: bool = False


class UpdateService:
    """GitHub-based update system for Darts Kiosk."""

    CHECK_TIMEOUT = 15
    DOWNLOAD_TIMEOUT = 300

    def __init__(self):
        self._cached_releases: List[GitHubRelease] = []
        self._last_check: Optional[str] = None
        self._download_progress: Dict[str, Dict] = {}
        self._bg_task: Optional[asyncio.Task] = None
        self._bg_running = False
        # In-memory cache of last background check result
        self._notification_cache: Optional[Dict] = None

    def get_current_version(self) -> str:
        return read_app_version()

    def get_github_repo(self) -> str:
        return GITHUB_REPO

    @staticmethod
    def _parse_version(v: str) -> tuple:
        import re

        clean = v.lstrip('v').strip()
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$', clean)
        if match:
            return tuple(int(part) for part in match.groups())

        parts = []
        for p in clean.split('.'):
            m = re.match(r'^(\d+)', p)
            parts.append(int(m.group(1)) if m else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def _is_newer(self, version: str) -> bool:
        try:
            return self._parse_version(version) > self._parse_version(self.get_current_version())
        except Exception:
            return False

    def _github_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def check_for_updates(self) -> Dict:
        """Check GitHub for new releases."""
        current_version = self.get_current_version()
        if not GITHUB_REPO:
            return {
                "configured": False,
                "current_version": current_version,
                "message": "Kein GitHub-Repository konfiguriert. Setze GITHUB_REPO in .env (z.B. owner/darts-kiosk).",
                "releases": [],
                "last_check": self._last_check,
            }

        try:
            url = f"{GITHUB_API}/repos/{GITHUB_REPO}/releases"
            headers = self._github_headers()
            has_token = bool(os.environ.get("GITHUB_TOKEN", ""))

            logger.info(f"[UpdateCheck] Checking {GITHUB_REPO} (authenticated={has_token})")

            async with httpx.AsyncClient(timeout=self.CHECK_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params={"per_page": 15})

            if resp.status_code == 404:
                msg = f"Repository '{GITHUB_REPO}' nicht gefunden."
                if not has_token:
                    msg += " Falls private: GITHUB_TOKEN in .env setzen."
                logger.warning(f"[UpdateCheck] 404: {msg}")
                return {
                    "configured": True,
                    "current_version": current_version,
                    "message": msg,
                    "releases": [],
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }

            if resp.status_code == 401:
                logger.warning("[UpdateCheck] 401: Token ungueltig oder abgelaufen")
                return {
                    "configured": True,
                    "current_version": current_version,
                    "message": "GitHub-Token ungueltig oder abgelaufen. Bitte GITHUB_TOKEN in .env pruefen.",
                    "releases": [],
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }

            if resp.status_code == 403:
                return {
                    "configured": True,
                    "current_version": current_version,
                    "message": "GitHub API Rate-Limit erreicht. Versuche es spaeter erneut oder setze GITHUB_TOKEN.",
                    "releases": [],
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }

            resp.raise_for_status()
            data = resp.json()

            releases = []
            for r in data:
                tag = r.get("tag_name", "")
                version = tag.lstrip("v")

                # Build asset list with BOTH browser URL and API URL
                release_assets = []
                for a in r.get("assets", []):
                    release_assets.append({
                        "name": a["name"],
                        "size": a["size"],
                        "download_url": a["browser_download_url"],
                        "api_url": a.get("url", ""),  # API endpoint for authenticated download
                        "asset_id": a.get("id", 0),
                        "content_type": a.get("content_type", ""),
                    })

                rel = GitHubRelease(
                    version=version,
                    tag=tag,
                    name=r.get("name", tag),
                    body=r.get("body", ""),
                    published_at=r.get("published_at", ""),
                    is_prerelease=r.get("prerelease", False),
                    html_url=r.get("html_url", ""),
                    assets=release_assets,
                    is_current=(version == current_version or tag == f"v{current_version}"),
                    is_newer=self._is_newer(version),
                )
                releases.append(rel)

                logger.info(
                    f"[UpdateCheck] Release {tag}: "
                    f"assets={[a['name'] for a in release_assets]}, "
                    f"is_newer={rel.is_newer}, is_current={rel.is_current}"
                )

            self._cached_releases = releases
            self._last_check = datetime.now(timezone.utc).isoformat()

            newest = next((r for r in releases if r.is_newer and not r.is_prerelease), None)

            if newest:
                logger.info(f"[UpdateCheck] Update verfuegbar: v{newest.version} (aktuell: v{current_version})")
            else:
                logger.info(f"[UpdateCheck] Kein Update verfuegbar (aktuell: v{current_version})")

            return {
                "configured": True,
                "current_version": current_version,
                "update_available": newest is not None,
                "latest_version": newest.version if newest else current_version,
                "latest_name": newest.name if newest else None,
                "latest_url": newest.html_url if newest else None,
                "latest_body": newest.body if newest else None,
                "latest_assets": newest.assets if newest else [],
                "releases": [
                    {
                        "version": r.version,
                        "tag": r.tag,
                        "name": r.name,
                        "body": r.body,
                        "published_at": r.published_at,
                        "is_prerelease": r.is_prerelease,
                        "is_current": r.is_current,
                        "is_newer": r.is_newer,
                        "html_url": r.html_url,
                        "assets": r.assets,
                    }
                    for r in releases
                ],
                "last_check": self._last_check,
                "message": None,
            }

        except httpx.TimeoutException:
            return {
                "configured": True,
                "current_version": current_version,
                "message": "GitHub-API Timeout. Pruefe die Internetverbindung.",
                "releases": [],
                "last_check": self._last_check,
            }
        except Exception as e:
            logger.error(f"GitHub update check failed: {e}")
            return {
                "configured": True,
                "current_version": current_version,
                "message": f"Fehler: {str(e)}",
                "releases": [],
                "last_check": self._last_check,
            }

    def _detect_platform_asset(self, assets: List[Dict]) -> Optional[Dict]:
        """Auto-detect the best asset for this platform."""
        system = platform.system().lower()
        keywords = []
        if system == "windows":
            keywords = ["windows", "win"]
        elif system == "linux":
            keywords = ["linux"]

        for asset in assets:
            name = asset["name"].lower()
            for kw in keywords:
                if kw in name:
                    return asset

        # Fallback: source package
        for asset in assets:
            if "source" in asset["name"].lower():
                return asset

        return assets[0] if assets else None

    async def download_asset(self, asset_url: str, asset_name: str, download_id: str) -> Dict:
        """
        Download a release asset with progress tracking.

        For PRIVATE repos: Uses the GitHub API URL with Accept: application/octet-stream.
        The browser_download_url returns 404 for private repos even with a token,
        because it requires browser cookie authentication, not API token auth.

        For PUBLIC repos: Uses browser_download_url directly (works without token).
        """
        self._download_progress[download_id] = {
            "status": "downloading",
            "asset_name": asset_name,
            "bytes_downloaded": 0,
            "total_bytes": 0,
            "percent": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        download_path = DOWNLOADS_DIR / asset_name
        has_token = bool(os.environ.get("GITHUB_TOKEN", ""))

        # Determine the correct download URL and headers
        # For private repos: use the API URL with octet-stream accept header
        # For public repos: browser_download_url works fine
        actual_url, download_headers = self._resolve_download_url(asset_url, asset_name, has_token)

        logger.info(f"[Download] Starting: {asset_name}")
        logger.info(f"[Download]   original_url: {asset_url}")
        logger.info(f"[Download]   resolved_url: {actual_url}")
        logger.info(f"[Download]   authenticated: {has_token}")
        logger.info(f"[Download]   target: {download_path}")

        try:
            async with httpx.AsyncClient(timeout=self.DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
                async with client.stream("GET", actual_url, headers=download_headers) as resp:
                    if resp.status_code == 404:
                        raise httpx.HTTPStatusError(
                            f"404 Not Found — Asset nicht erreichbar. "
                            f"{'Pruefe GITHUB_TOKEN fuer private Repos.' if not has_token else 'Token hat keinen Zugriff auf dieses Asset.'}",
                            request=resp.request, response=resp,
                        )
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0))
                    self._download_progress[download_id]["total_bytes"] = total

                    downloaded = 0
                    with open(download_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            percent = int((downloaded / total * 100)) if total > 0 else 0
                            self._download_progress[download_id].update({
                                "bytes_downloaded": downloaded,
                                "percent": percent,
                            })

            validation_error = self._validate_downloaded_asset(download_path, asset_name)
            if validation_error:
                raise ValueError(validation_error)

            self._download_progress[download_id].update({
                "status": "completed",
                "percent": 100,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "file_path": str(download_path),
            })

            logger.info(f"[Download] Complete: {asset_name} ({downloaded} bytes)")
            return self._download_progress[download_id]

        except Exception as e:
            self._download_progress[download_id].update({
                "status": "failed",
                "error": str(e),
            })
            logger.error(f"[Download] Failed for {asset_name}: {e}")
            # Clean up partial download
            if download_path.exists():
                download_path.unlink()
            return self._download_progress[download_id]

    def _resolve_download_url(self, asset_url: str, asset_name: str, has_token: bool) -> tuple:
        """
        Resolve the correct download URL for a GitHub release asset.

        Private repos: browser_download_url returns 404 with token auth.
        Must use the API endpoint with Accept: application/octet-stream instead.

        Returns: (url, headers)
        """
        headers = self._github_headers()

        if has_token:
            # Try to find the API URL from cached releases
            api_url = self._find_api_url_for_asset(asset_name)
            if api_url:
                # Use API URL with octet-stream header for binary download
                headers["Accept"] = "application/octet-stream"
                logger.info(f"[Download] Using API URL for authenticated download: {api_url}")
                return api_url, headers

            # Fallback: construct API URL from browser URL
            # browser_download_url: https://github.com/{owner}/{repo}/releases/download/{tag}/{filename}
            # We need: https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset_id}
            # But without the asset_id, try the browser URL with token (works for some cases)
            logger.info(f"[Download] No API URL cached, using browser URL with auth: {asset_url}")
            return asset_url, headers

        # Public repo: browser URL works without auth. If UI accidentally sends the
        # GitHub API asset URL, remap it back to the public browser download URL.
        if "api.github.com/repos/" in asset_url and "/releases/assets/" in asset_url:
            public_url = self._find_browser_download_url_for_asset(asset_name)
            if public_url:
                logger.info(f"[Download] Rewriting public API asset URL to browser download URL: {public_url}")
                return public_url, headers

        return asset_url, headers

    def _find_api_url_for_asset(self, asset_name: str) -> Optional[str]:
        """Find the API URL for an asset from the cached releases."""
        for release in self._cached_releases:
            for asset in release.assets:
                if asset.get("name") == asset_name and asset.get("api_url"):
                    return asset["api_url"]
        return None

    def _find_browser_download_url_for_asset(self, asset_name: str) -> Optional[str]:
        """Find the public browser download URL for an asset from the cached releases."""
        for release in self._cached_releases:
            for asset in release.assets:
                if asset.get("name") == asset_name and asset.get("download_url"):
                    return asset["download_url"]
        return None

    def _validate_downloaded_asset(self, download_path: Path, asset_name: str) -> Optional[str]:
        """Lightweight validation to catch HTML/JSON error pages saved as assets."""
        if not download_path.exists():
            return "Download-Datei fehlt nach dem Download"

        suffix = download_path.suffix.lower()
        try:
            with open(download_path, "rb") as f:
                head = f.read(8)
        except Exception as e:
            return f"Download-Datei konnte nicht geprüft werden: {e}"

        if suffix == ".zip" and not head.startswith(b"PK"):
            return f"Download ist keine gültige ZIP-Datei: {asset_name}"
        if suffix == ".gz" and head[:2] != b"\x1f\x8b":
            return f"Download ist kein gültiges GZip-Archiv: {asset_name}"
        return None

    def get_download_progress(self, download_id: str) -> Optional[Dict]:
        return self._download_progress.get(download_id)

    def list_downloaded_assets(self) -> List[Dict]:
        """List all downloaded release assets."""
        assets = []
        if DOWNLOADS_DIR.exists():
            for f in sorted(DOWNLOADS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file():
                    stat = f.stat()
                    assets.append({
                        "name": f.name,
                        "filename": f.name,
                        "path": str(f),
                        "size": stat.st_size,
                        "size_bytes": stat.st_size,
                        "downloaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    })
        return assets

    def delete_downloaded_asset(self, filename: str) -> bool:
        """Delete a downloaded asset."""
        path = DOWNLOADS_DIR / filename
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    async def prepare_update(self, target_version: str) -> Dict:
        """Create backup and prepare update instructions."""
        from backend.services.backup_service import backup_service
        backup_info = None
        try:
            backup_info = backup_service.create_backup()
            logger.info(f"Pre-update backup created: {backup_info.filename if backup_info else 'failed'}")
        except Exception as e:
            logger.warning(f"Pre-update backup failed: {e}")

        release = next((r for r in self._cached_releases if r.version == target_version), None)

        # Auto-detect platform asset
        recommended_asset = None
        download_links = []
        has_token = bool(os.environ.get("GITHUB_TOKEN", ""))

        if release and release.assets:
            recommended_asset = self._detect_platform_asset(release.assets)
            for asset in release.assets:
                label = asset["name"]
                if "windows" in label.lower():
                    label = f"Windows: {asset['name']}"
                elif "linux" in label.lower():
                    label = f"Linux: {asset['name']}"
                elif "source" in label.lower():
                    label = f"Source: {asset['name']}"

                # For private repos: prefer api_url over browser_download_url
                # browser_download_url returns 404 for private repo assets
                effective_url = asset.get("download_url", "")
                if has_token and asset.get("api_url"):
                    effective_url = asset["api_url"]

                download_links.append({
                    "label": label,
                    "name": asset["name"],
                    "url": effective_url,
                    "size": asset["size"],
                })

        # Same logic for recommended_asset
        rec_url = ""
        if recommended_asset:
            rec_url = recommended_asset.get("download_url", "")
            if has_token and recommended_asset.get("api_url"):
                rec_url = recommended_asset["api_url"]

        return {
            "backup_created": backup_info is not None,
            "backup_filename": backup_info.filename if backup_info else None,
            "target_version": target_version,
            "changelog": release.body if release else "",
            "release_url": release.html_url if release else f"https://github.com/{GITHUB_REPO}/releases",
            "recommended_asset": {
                "name": recommended_asset["name"],
                "url": rec_url,
                "size": recommended_asset["size"],
            } if recommended_asset else None,
            "download_links": download_links,
            "manual_steps": [
                "1. Backup wurde automatisch erstellt" if backup_info else "1. Backup manuell erstellen",
                f"2. Release-Paket v{target_version} herunterladen",
                "3. Services stoppen (stop.bat / systemctl stop darts-kiosk)",
                "4. Dateien ersetzen (backend/, frontend/build/)",
                "5. Services neu starten",
                "6. Version im Admin-Panel pruefen",
            ],
            "rollback_info": {
                "backup_filename": backup_info.filename if backup_info else None,
                "instruction": "Bei Problemen: Backup wiederherstellen unter System > Backups",
            },
        }

    async def get_update_history(self, db_session) -> List[Dict]:
        """Load update history from the DB settings table."""
        from sqlalchemy import select
        from backend.models import Settings
        result = await db_session.execute(
            select(Settings).where(Settings.key == "update_history")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value
        return []

    async def record_update_event(self, db_session, event: Dict):
        """Persist an update event to the DB."""
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified
        from backend.models import Settings

        event["timestamp"] = datetime.now(timezone.utc).isoformat()

        result = await db_session.execute(
            select(Settings).where(Settings.key == "update_history")
        )
        setting = result.scalar_one_or_none()
        if setting:
            history = list(setting.value or [])
            history.append(event)
            # Keep last 50 entries
            if len(history) > 50:
                history = history[-50:]
            setting.value = history
            flag_modified(setting, "value")
        else:
            setting = Settings(key="update_history", value=[event])
            db_session.add(setting)

        await db_session.flush()

    # ------------------------------------------------------------------
    # Background Update Checker
    # ------------------------------------------------------------------
    async def start_background_checker(self):
        """Start the periodic background update check."""
        if not UPDATE_CHECK_ENABLED:
            logger.info("Background update check is disabled (UPDATE_CHECK_ENABLED=false)")
            return
        if not GITHUB_REPO:
            logger.info("Background update check skipped: no GITHUB_REPO configured")
            return
        if self._bg_running:
            return

        self._bg_running = True
        self._bg_task = asyncio.create_task(self._bg_check_loop())
        logger.info(
            f"Background update checker started (interval={UPDATE_CHECK_INTERVAL_HOURS}h, repo={GITHUB_REPO})"
        )

    async def stop_background_checker(self):
        """Stop the periodic background update check."""
        self._bg_running = False
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
        logger.info("Background update checker stopped")

    async def _bg_check_loop(self):
        """Run the check loop. First check after 60s, then every INTERVAL hours."""
        await asyncio.sleep(60)
        while self._bg_running:
            await self._run_background_check()
            await asyncio.sleep(UPDATE_CHECK_INTERVAL_HOURS * 3600)

    async def _run_background_check(self):
        """Perform a single background check and persist the result."""
        try:
            result = await self.check_for_updates()
            current_version = self.get_current_version()

            notification = {
                "update_available": result.get("update_available", False),
                "current_version": current_version,
                "latest_version": result.get("latest_version", current_version),
                "latest_name": result.get("latest_name"),
                "latest_body": result.get("latest_body"),
                "latest_url": result.get("latest_url"),
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "configured": result.get("configured", False),
                "error": result.get("message"),
            }
            self._notification_cache = notification

            # Persist to DB
            try:
                from backend.database import AsyncSessionLocal
                async with AsyncSessionLocal() as db:
                    await self._persist_notification(db, notification)
                    await db.commit()
            except Exception as e:
                logger.error(f"Failed to persist update notification: {e}")

            if notification["update_available"]:
                logger.info(f"Background check: update available v{notification['latest_version']}")
            else:
                logger.info("Background check: system is up to date")

        except Exception as e:
            logger.error(f"Background update check failed: {e}")

    async def _persist_notification(self, db_session, notification: Dict):
        """Save notification cache to DB settings."""
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified
        from backend.models import Settings

        result = await db_session.execute(
            select(Settings).where(Settings.key == "update_check_cache")
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = notification
            flag_modified(setting, "value")
        else:
            setting = Settings(key="update_check_cache", value=notification)
            db_session.add(setting)

    async def get_notification(self, db_session) -> Optional[Dict]:
        """Get the cached update notification (in-memory first, then DB)."""
        if self._notification_cache:
            return self._notification_cache

        from sqlalchemy import select
        from backend.models import Settings
        result = await db_session.execute(
            select(Settings).where(Settings.key == "update_check_cache")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            self._notification_cache = setting.value
            return setting.value
        return None

    async def dismiss_notification(self, db_session, version: str):
        """Mark a notification as permanently dismissed for a specific version."""
        await self._update_notification_field(db_session, "dismissed_version", version)

    async def snooze_notification(self, db_session, version: str, hours: int = 48):
        """Snooze the notification for `hours`. Banner reappears after that."""
        from datetime import timedelta
        snooze_until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        await self._update_notification_field(db_session, "snoozed_version", version)
        await self._update_notification_field(db_session, "snooze_until", snooze_until)

    async def _update_notification_field(self, db_session, field: str, value):
        """Helper: set a single field on the update_check_cache setting."""
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified
        from backend.models import Settings

        result = await db_session.execute(
            select(Settings).where(Settings.key == "update_check_cache")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            setting.value[field] = value
            flag_modified(setting, "value")

        if self._notification_cache:
            self._notification_cache[field] = value


update_service = UpdateService()
