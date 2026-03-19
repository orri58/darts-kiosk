"""
Agent Client — HTTP client for the local Windows Agent v3.4.0

The backend uses this client to communicate with the local agent process.
All calls have strict timeouts (3s). On timeout or error, returns None
so the caller can fall back to existing direct services.

Usage:
    from backend.services.agent_client import agent_client

    status = await agent_client.get_status()
    if status is None:
        # Agent offline — use fallback
"""
import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration from environment
_AGENT_HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
_AGENT_PORT = os.environ.get("AGENT_PORT", "8002")
_AGENT_SECRET = os.environ.get("AGENT_SECRET", "")
_AGENT_TIMEOUT = 3.0  # seconds — hard limit per user requirement


def _agent_url() -> str:
    return f"http://{_AGENT_HOST}:{_AGENT_PORT}"


async def _request(method: str, path: str, body: Optional[dict] = None) -> Optional[dict]:
    """Make an HTTP request to the local agent. Returns None on any failure."""
    import httpx

    url = f"{_agent_url()}{path}"
    headers = {"X-Agent-Secret": _AGENT_SECRET}

    try:
        async with httpx.AsyncClient(timeout=_AGENT_TIMEOUT) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            else:
                resp = await client.post(url, headers=headers, json=body or {})

            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(
                    f"[AGENT_CLIENT] {method} {path} returned {resp.status_code}: "
                    f"{resp.text[:200]}"
                )
                return None
    except Exception as e:
        logger.debug(f"[AGENT_CLIENT] {method} {path} failed: {type(e).__name__}: {e}")
        return None


class AgentClient:
    """Async client for the local Windows Agent."""

    async def get_status(self) -> Optional[dict]:
        """Get agent status. No auth required for this endpoint."""
        import httpx
        url = f"{_agent_url()}/status"
        try:
            async with httpx.AsyncClient(timeout=_AGENT_TIMEOUT) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    def is_configured(self) -> bool:
        """Check if agent communication is configured."""
        return bool(_AGENT_SECRET)

    async def ensure_autodarts(self, exe_path: str = "") -> Optional[dict]:
        return await _request("POST", "/autodarts/ensure", {"exe_path": exe_path})

    async def restart_autodarts(self, exe_path: str = "") -> Optional[dict]:
        return await _request("POST", "/autodarts/restart", {"exe_path": exe_path})

    async def restart_backend(self) -> Optional[dict]:
        return await _request("POST", "/system/restart-backend")

    async def reboot_os(self) -> Optional[dict]:
        return await _request("POST", "/system/reboot")

    async def shutdown_os(self) -> Optional[dict]:
        return await _request("POST", "/system/shutdown")

    async def switch_shell(self, target: str) -> Optional[dict]:
        return await _request("POST", "/kiosk/shell/switch", {"target": target})

    async def set_task_manager(self, enabled: bool) -> Optional[dict]:
        return await _request("POST", "/kiosk/taskmanager/set", {"enabled": enabled})


agent_client = AgentClient()
