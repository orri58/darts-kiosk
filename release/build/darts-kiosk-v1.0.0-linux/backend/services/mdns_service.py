"""
mDNS Service – Zeroconf advertisement (agent) and discovery (master).
Service type: _darts-kiosk._tcp.local.
"""
import asyncio
import logging
import os
import hashlib
import socket
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass, field, asdict

from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, ServiceStateChange

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_darts-kiosk._tcp.local."
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
MODE = os.environ.get('MODE', 'MASTER')
LOCAL_BOARD_ID = os.environ.get('LOCAL_BOARD_ID', 'BOARD-1')
API_PORT = int(os.environ.get('API_PORT', '8001'))


def _compute_fingerprint(board_id: str) -> str:
    """Deterministic fingerprint from board_id + hostname (public, not secret)."""
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

    # ------------------------------------------------------------------
    # Agent: advertise
    # ------------------------------------------------------------------
    def advertise(self, board_id: str = None, port: int = None):
        """Register this agent on the LAN via mDNS."""
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
        """Browse the LAN for agent services."""
        if not self._zeroconf:
            self._zeroconf = Zeroconf()

        self._browser = ServiceBrowser(
            self._zeroconf, SERVICE_TYPE, handlers=[self._on_state_change]
        )
        self._running = True
        logger.info("mDNS: discovery started")

    def _on_state_change(self, zeroconf: Zeroconf, service_type: str,
                         name: str, state_change: ServiceStateChange):
        if state_change == ServiceStateChange.Added:
            asyncio.get_event_loop().call_soon_threadsafe(
                self._handle_add, zeroconf, service_type, name
            )
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
            # Update existing
            self._discovered[board_id].ip = ip
            self._discovered[board_id].port = info.port
            self._discovered[board_id].version = props.get("version", "?")
            self._discovered[board_id].last_seen = now
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
            logger.info(f"mDNS: discovered agent {board_id} at {ip}:{info.port}")

    def _handle_remove(self, name: str):
        # Extract board_id from service name
        for bid, agent in list(self._discovered.items()):
            if bid.lower() in name.lower():
                logger.info(f"mDNS: agent {bid} removed from network")
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

    def remove_stale(self, max_age_seconds: int = 300):
        """Remove agents not seen within max_age_seconds."""
        now = datetime.now(timezone.utc)
        stale = []
        for bid, agent in self._discovered.items():
            last = datetime.fromisoformat(agent.last_seen)
            if (now - last).total_seconds() > max_age_seconds:
                stale.append(bid)
        for bid in stale:
            del self._discovered[bid]
            logger.info(f"mDNS: removed stale agent {bid}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def stop(self):
        if self._service_info and self._zeroconf:
            try:
                self._zeroconf.unregister_service(self._service_info)
            except Exception:
                pass

        if self._zeroconf:
            try:
                self._zeroconf.close()
            except Exception:
                pass

        self._running = False
        logger.info("mDNS: service stopped")

    @property
    def is_running(self) -> bool:
        return self._running


mdns_service = MDNSService()
