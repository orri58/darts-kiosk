"""
Update Service — GitHub-based
Checks GitHub Releases for new versions, provides update instructions,
and triggers backup before update.
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dataclasses import dataclass, field
import httpx

logger = logging.getLogger(__name__)

CURRENT_VERSION = os.environ.get('APP_VERSION', '1.0.0')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')  # e.g. "owner/darts-kiosk"
GITHUB_API = "https://api.github.com"


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


@dataclass
class UpdateResult:
    success: bool
    message: str
    timestamp: str = ""


class UpdateService:
    """GitHub-based update system for Darts Kiosk."""

    CHECK_TIMEOUT = 15

    def __init__(self):
        self._cached_releases: List[GitHubRelease] = []
        self._last_check: Optional[str] = None
        self._update_history: List[Dict] = []

    def get_current_version(self) -> str:
        return CURRENT_VERSION

    def get_github_repo(self) -> str:
        return GITHUB_REPO

    @staticmethod
    def _parse_version(v: str) -> tuple:
        """Parse version string like '1.2.3' into comparable tuple."""
        clean = v.lstrip('v').strip()
        parts = []
        for p in clean.split('.'):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def _is_newer(self, version: str) -> bool:
        try:
            return self._parse_version(version) > self._parse_version(CURRENT_VERSION)
        except Exception:
            return False

    async def check_for_updates(self) -> Dict:
        """Check GitHub for new releases."""
        if not GITHUB_REPO:
            return {
                "configured": False,
                "current_version": CURRENT_VERSION,
                "message": "Kein GitHub-Repository konfiguriert. Setze GITHUB_REPO in .env (z.B. owner/darts-kiosk).",
                "releases": [],
                "last_check": self._last_check,
            }

        try:
            url = f"{GITHUB_API}/repos/{GITHUB_REPO}/releases"
            headers = {"Accept": "application/vnd.github+json"}
            token = os.environ.get("GITHUB_TOKEN", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            async with httpx.AsyncClient(timeout=self.CHECK_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params={"per_page": 10})

            if resp.status_code == 404:
                return {
                    "configured": True,
                    "current_version": CURRENT_VERSION,
                    "message": f"Repository '{GITHUB_REPO}' nicht gefunden.",
                    "releases": [],
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }

            if resp.status_code == 403:
                return {
                    "configured": True,
                    "current_version": CURRENT_VERSION,
                    "message": "GitHub API Rate-Limit erreicht. Versuche es später erneut oder setze GITHUB_TOKEN.",
                    "releases": [],
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }

            resp.raise_for_status()
            data = resp.json()

            releases = []
            for r in data:
                tag = r.get("tag_name", "")
                version = tag.lstrip("v")
                rel = GitHubRelease(
                    version=version,
                    tag=tag,
                    name=r.get("name", tag),
                    body=r.get("body", "")[:500],
                    published_at=r.get("published_at", ""),
                    is_prerelease=r.get("prerelease", False),
                    html_url=r.get("html_url", ""),
                    assets=[
                        {"name": a["name"], "size": a["size"], "download_url": a["browser_download_url"]}
                        for a in r.get("assets", [])
                    ],
                    is_current=(version == CURRENT_VERSION or tag == f"v{CURRENT_VERSION}"),
                    is_newer=self._is_newer(version),
                )
                releases.append(rel)

            self._cached_releases = releases
            self._last_check = datetime.now(timezone.utc).isoformat()

            newest = next((r for r in releases if r.is_newer and not r.is_prerelease), None)

            return {
                "configured": True,
                "current_version": CURRENT_VERSION,
                "update_available": newest is not None,
                "latest_version": newest.version if newest else CURRENT_VERSION,
                "latest_name": newest.name if newest else None,
                "latest_url": newest.html_url if newest else None,
                "latest_body": newest.body if newest else None,
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
                "current_version": CURRENT_VERSION,
                "message": "GitHub-API Timeout. Prüfe die Internetverbindung.",
                "releases": [],
                "last_check": self._last_check,
            }
        except Exception as e:
            logger.error(f"GitHub update check failed: {e}")
            return {
                "configured": True,
                "current_version": CURRENT_VERSION,
                "message": f"Fehler: {str(e)}",
                "releases": [],
                "last_check": self._last_check,
            }

    async def prepare_update(self, target_version: str) -> Dict:
        """
        Prepare for an update: create backup, return instructions.
        """
        from backend.services.backup_service import backup_service
        backup_path = None
        try:
            backup_path = await backup_service.create_backup()
            logger.info(f"Pre-update backup created: {backup_path}")
        except Exception as e:
            logger.warning(f"Pre-update backup failed: {e}")

        self._update_history.append({
            "action": "prepare_update",
            "target_version": target_version,
            "backup_path": str(backup_path) if backup_path else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        release = next((r for r in self._cached_releases if r.version == target_version), None)

        instructions = []
        if release and release.assets:
            # Find matching asset for the platform
            for asset in release.assets:
                if "windows" in asset["name"].lower():
                    instructions.append(f"Windows: {asset['download_url']}")
                elif "linux" in asset["name"].lower():
                    instructions.append(f"Linux: {asset['download_url']}")
                elif "source" in asset["name"].lower():
                    instructions.append(f"Source: {asset['download_url']}")

        return {
            "backup_created": backup_path is not None,
            "backup_path": str(backup_path) if backup_path else None,
            "target_version": target_version,
            "release_url": release.html_url if release else f"https://github.com/{GITHUB_REPO}/releases",
            "download_links": instructions,
            "manual_steps": [
                "1. Backup wurde automatisch erstellt" if backup_path else "1. Backup manuell erstellen",
                "2. Neues Release-Paket herunterladen",
                "3. Services stoppen",
                "4. Dateien ersetzen (backend/, frontend/)",
                "5. Services neu starten",
                "6. Funktionalität prüfen",
            ],
        }

    def get_update_history(self, limit: int = 20) -> List[Dict]:
        return self._update_history[-limit:]


update_service = UpdateService()
