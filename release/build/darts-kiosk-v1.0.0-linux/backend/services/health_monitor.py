"""
Health Monitoring Service
Tracks system health, automation status, and agent connectivity
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from collections import deque
import httpx

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR
SCREENSHOTS_DIR = DATA_DIR / 'autodarts_debug'


@dataclass
class AutomationMetrics:
    """Metrics for Autodarts automation"""
    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    last_error: Optional[str] = None
    last_error_screenshot: Optional[str] = None
    success_rate: float = 0.0
    
    def record_success(self):
        self.total_attempts += 1
        self.successful += 1
        self.last_success = datetime.now(timezone.utc).isoformat()
        self._update_rate()
    
    def record_failure(self, error: str, screenshot_path: Optional[str] = None):
        self.total_attempts += 1
        self.failed += 1
        self.last_failure = datetime.now(timezone.utc).isoformat()
        self.last_error = error
        self.last_error_screenshot = screenshot_path
        self._update_rate()
    
    def _update_rate(self):
        if self.total_attempts > 0:
            self.success_rate = round(self.successful / self.total_attempts * 100, 2)


@dataclass
class AgentHealth:
    """Health status of a board agent"""
    board_id: str
    agent_url: str
    is_online: bool = False
    last_heartbeat: Optional[str] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    consecutive_failures: int = 0


@dataclass
class SystemHealth:
    """Overall system health status"""
    status: str = "healthy"  # healthy, degraded, unhealthy
    uptime_seconds: int = 0
    start_time: str = ""
    database_ok: bool = True
    scheduler_running: bool = False
    backup_service_running: bool = False
    automation_metrics: AutomationMetrics = field(default_factory=AutomationMetrics)
    agent_status: Dict[str, AgentHealth] = field(default_factory=dict)
    recent_errors: List[dict] = field(default_factory=list)
    last_check: str = ""


class HealthMonitor:
    """Monitors system health and agent connectivity"""
    
    MAX_RECENT_ERRORS = 50
    AGENT_CHECK_INTERVAL = 30  # seconds
    AGENT_TIMEOUT = 10  # seconds
    
    def __init__(self):
        self._start_time = datetime.now(timezone.utc)
        self._automation_metrics = AutomationMetrics()
        self._agent_health: Dict[str, AgentHealth] = {}
        self._recent_errors: deque = deque(maxlen=self.MAX_RECENT_ERRORS)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._scheduler_running = False
        self._backup_running = False
    
    async def start(self):
        """Start health monitoring"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitor started")
    
    async def stop(self):
        """Stop health monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")
    
    async def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                await self._check_agents()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
            
            await asyncio.sleep(self.AGENT_CHECK_INTERVAL)
    
    async def _check_agents(self):
        """Check health of all registered agents"""
        from backend.database import AsyncSessionLocal
        from sqlalchemy import select
        from backend.models import Board
        
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Board).where(Board.agent_api_base_url != None)
                )
                boards = result.scalars().all()
                
                for board in boards:
                    if board.agent_api_base_url:
                        await self._check_single_agent(board.board_id, board.agent_api_base_url)
        except Exception as e:
            logger.error(f"Error checking agents: {e}")
    
    async def _check_single_agent(self, board_id: str, agent_url: str):
        """Check health of a single agent"""
        health = self._agent_health.get(board_id)
        if not health:
            health = AgentHealth(board_id=board_id, agent_url=agent_url)
            self._agent_health[board_id] = health
        
        try:
            start_time = datetime.now(timezone.utc)
            
            async with httpx.AsyncClient(timeout=self.AGENT_TIMEOUT) as client:
                response = await client.get(f"{agent_url}/api/agent/health")
                
            latency = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            if response.status_code == 200:
                health.is_online = True
                health.last_heartbeat = datetime.now(timezone.utc).isoformat()
                health.latency_ms = latency
                health.error = None
                health.consecutive_failures = 0
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            health.is_online = False
            health.error = str(e)
            health.consecutive_failures += 1
            
            if health.consecutive_failures >= 3:
                logger.warning(f"Agent {board_id} appears offline: {e}")
    
    def record_automation_success(self):
        """Record successful automation attempt"""
        self._automation_metrics.record_success()
    
    def record_automation_failure(self, error: str, screenshot_path: Optional[str] = None):
        """Record failed automation attempt"""
        self._automation_metrics.record_failure(error, screenshot_path)
        self._add_error("automation", error, screenshot_path)
    
    def _add_error(self, category: str, message: str, screenshot: Optional[str] = None):
        """Add an error to recent errors list"""
        self._recent_errors.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "message": message,
            "screenshot": screenshot
        })
    
    def set_scheduler_status(self, running: bool):
        """Update scheduler status"""
        self._scheduler_running = running
    
    def set_backup_status(self, running: bool):
        """Update backup service status"""
        self._backup_running = running
    
    def get_error_screenshots(self) -> List[dict]:
        """Get list of error screenshots"""
        screenshots = []
        
        if SCREENSHOTS_DIR.exists():
            for file in sorted(SCREENSHOTS_DIR.glob("error_*.png"), reverse=True)[:20]:
                stat = file.stat()
                screenshots.append({
                    "filename": file.name,
                    "path": f"/api/health/screenshot/{file.name}",
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                })
        
        return screenshots
    
    def get_health(self) -> SystemHealth:
        """Get current system health status"""
        now = datetime.now(timezone.utc)
        uptime = int((now - self._start_time).total_seconds())
        
        # Determine overall status
        status = "healthy"
        
        # Check automation success rate
        if self._automation_metrics.total_attempts > 0:
            if self._automation_metrics.success_rate < 50:
                status = "unhealthy"
            elif self._automation_metrics.success_rate < 80:
                status = "degraded"
        
        # Check agent health
        offline_agents = sum(1 for a in self._agent_health.values() if not a.is_online)
        if offline_agents > 0:
            if status == "healthy":
                status = "degraded"
        
        return SystemHealth(
            status=status,
            uptime_seconds=uptime,
            start_time=self._start_time.isoformat(),
            database_ok=True,  # TODO: Add actual DB check
            scheduler_running=self._scheduler_running,
            backup_service_running=self._backup_running,
            automation_metrics=self._automation_metrics,
            agent_status={k: asdict(v) for k, v in self._agent_health.items()},
            recent_errors=list(self._recent_errors),
            last_check=now.isoformat()
        )


# Global instance
health_monitor = HealthMonitor()


async def start_health_monitor():
    await health_monitor.start()


async def stop_health_monitor():
    await health_monitor.stop()
