"""
mDNS Service – Zeroconf advertisement (agent) and discovery (master).
Service type: _darts-kiosk._tcp.local.
Enhanced: periodic stale cleanup, re-scan, heartbeat stats.
"""
import asyncio
import logging
import os
import hashlib
import socket
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, field, asdict

from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, ServiceStateChange

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_darts-kiosk._tcp.local."
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
MODE = os.environ.get('MODE', 'MASTER')
LOCAL_BOARD_ID = os.environ.get('LOCAL_BOARD_ID', 'BOARD-1')
API_PORT = int(os.environ.get('API_PORT', '8001'))
STALE_TIMEOUT = int(os.environ.get('MDNS_STALE_TIMEOUT', '120'))
CLEANUP_INTERVAL = int(os.environ.get('MDNS_CLEANUP_INTERVAL', '30'))


def _compute_fingerprint(board_id: str) -> str:
    raw = f"{board_id}:{socket.gethostname()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class DiscoveredAgent:
    board_id: str
    ip: str
    port: int
    version: str
    role: str
    api_path: str
    fingerprint: str
    first_seen: str
    last_seen: str
    is_paired: bool = False
    seen_count: int = 1
    is_stale: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class MDNSService:
    """Handles both mDNS registration (agent) and browsing (master)."""

    def __init__(self):
        self._zeroconf: Optional[Zeroconf] = None
        self._browser: Optional[ServiceBrowser] = None
        self._service_info: Optional[ServiceInfo] = None
        self._discovered: Dict[str, DiscoveredAgent] = {}
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._discovery_stats = {
            "total_discovered": 0,
            "total_removed": 0,
            "last_scan": None,
            "scan_count": 0,
        }

    # ------------------------------------------------------------------
    # Agent: advertise
    # ------------------------------------------------------------------
    def advertise(self, board_id: str = None, port: int = None):
        board_id = board_id or LOCAL_BOARD_ID
        port = port or API_PORT
        fp = _compute_fingerprint(board_id)

        hostname = socket.gethostname()
        service_name = f"darts-kiosk-{board_id}.{SERVICE_TYPE}"

        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "127.0.0.1"

        properties = {
            b"board_id": board_id.encode(),
            b"role": b"agent",
            b"version": APP_VERSION.encode(),
            b"api": b"/api/agent",
            b"fingerprint": fp.encode(),
        }

        self._service_info = ServiceInfo(
            SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties=properties,
            server=f"{hostname}.local.",
        )

        if not self._zeroconf:
            self._zeroconf = Zeroconf()

        self._zeroconf.register_service(self._service_info)
        self._running = True
        logger.info(f"mDNS: advertising {board_id} on {local_ip}:{port} (fp={fp})")

    # ------------------------------------------------------------------
    # Master: discover
    # ------------------------------------------------------------------
    def start_discovery(self):
        if not self._zeroconf:
            self._zeroconf = Zeroconf()

        self._browser = ServiceBrowser(
            self._zeroconf, SERVICE_TYPE, handlers=[self._on_state_change]
        )
        self._running = True
        self._discovery_stats["last_scan"] = datetime.now(timezone.utc).isoformat()
        self._discovery_stats["scan_count"] += 1
        logger.info("mDNS: discovery started")

        # Start periodic stale cleanup
        self._start_cleanup_loop()

    def restart_discovery(self):
        """Stop and restart the browser to force a re-scan."""
        if self._browser:
            try:
                self._browser.cancel()
            except Exception:
                pass
            self._browser = None

        if self._zeroconf:
            self._browser = ServiceBrowser(
                self._zeroconf, SERVICE_TYPE, handlers=[self._on_state_change]
            )
            self._discovery_stats["last_scan"] = datetime.now(timezone.utc).isoformat()
            self._discovery_stats["scan_count"] += 1
            logger.info("mDNS: discovery restarted (re-scan)")

    def _start_cleanup_loop(self):
        """Start background task for periodic stale agent cleanup."""
        if self._cleanup_task and not self._cleanup_task.done():
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._cleanup_task = loop.create_task(self._cleanup_loop())
        except RuntimeError:
            pass

    async def _cleanup_loop(self):
        while self._running:
            try:
                self.remove_stale(max_age_seconds=STALE_TIMEOUT)
            except Exception as e:
                logger.error(f"mDNS cleanup error: {e}")
            await asyncio.sleep(CLEANUP_INTERVAL)

    def _on_state_change(self, zeroconf: Zeroconf, service_type: str,
                         name: str, state_change: ServiceStateChange):
        if state_change == ServiceStateChange.Added:
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(self._handle_add, zeroconf, service_type, name)
            except RuntimeError:
                self._handle_add(zeroconf, service_type, name)
        elif state_change == ServiceStateChange.Removed:
            self._handle_remove(name)

    def _handle_add(self, zeroconf: Zeroconf, service_type: str, name: str):
        info = zeroconf.get_service_info(service_type, name)
        if not info:
            return

        props = {k.decode(): v.decode() if isinstance(v, bytes) else v
                 for k, v in (info.properties or {}).items()}

        board_id = props.get("board_id", "unknown")
        ip = info.parsed_addresses()[0] if info.parsed_addresses() else "unknown"
        now = datetime.now(timezone.utc).isoformat()

        if board_id in self._discovered:
            agent = self._discovered[board_id]
            agent.ip = ip
            agent.port = info.port
            agent.version = props.get("version", "?")
            agent.last_seen = now
            agent.seen_count += 1
            agent.is_stale = False
        else:
            self._discovered[board_id] = DiscoveredAgent(
                board_id=board_id,
                ip=ip,
                port=info.port,
                version=props.get("version", "?"),
                role=props.get("role", "agent"),
                api_path=props.get("api", "/api/agent"),
                fingerprint=props.get("fingerprint", ""),
                first_seen=now,
                last_seen=now,
            )
            self._discovery_stats["total_discovered"] += 1
            logger.info(f"mDNS: discovered agent {board_id} at {ip}:{info.port}")

    def _handle_remove(self, name: str):
        for bid, agent in list(self._discovered.items()):
            if bid.lower() in name.lower():
                agent.is_stale = True
                logger.info(f"mDNS: agent {bid} signaled removal")
                break

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def get_discovered_agents(self) -> list:
        return [a.to_dict() for a in self._discovered.values()]

    def get_agent(self, board_id: str) -> Optional[DiscoveredAgent]:
        return self._discovered.get(board_id)

    def mark_paired(self, board_id: str):
        if board_id in self._discovered:
            self._discovered[board_id].is_paired = True

    def remove_stale(self, max_age_seconds: int = None):
        """Remove agents not seen within max_age_seconds."""
        if max_age_seconds is None:
            max_age_seconds = STALE_TIMEOUT
        now = datetime.now(timezone.utc)
        stale = []
        for bid, agent in self._discovered.items():
            last = datetime.fromisoformat(agent.last_seen)
            age = (now - last).total_seconds()
            if age > max_age_seconds:
                stale.append(bid)
            elif age > max_age_seconds * 0.7:
                agent.is_stale = True
        for bid in stale:
            del self._discovered[bid]
            self._discovery_stats["total_removed"] += 1
            logger.info(f"mDNS: removed stale agent {bid}")

    def get_discovery_stats(self) -> dict:
        return {
            **self._discovery_stats,
            "active_agents": len(self._discovered),
            "stale_agents": sum(1 for a in self._discovered.values() if a.is_stale),
            "paired_agents": sum(1 for a in self._discovered.values() if a.is_paired),
            "stale_timeout_seconds": STALE_TIMEOUT,
            "cleanup_interval_seconds": CLEANUP_INTERVAL,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def stop(self):
        self._running = False

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

        if self._service_info and self._zeroconf:
            try:
                self._zeroconf.unregister_service(self._service_info)
            except Exception:
                pass

        if self._browser:
            try:
                self._browser.cancel()
            except Exception:
                pass

        if self._zeroconf:
            try:
                self._zeroconf.close()
            except Exception:
                pass

        logger.info("mDNS: service stopped")

    @property
    def is_running(self) -> bool:
        return self._running


mdns_service = MDNSService()
