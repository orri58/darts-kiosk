"""
Update Service
Handles Docker image updates for master and agents
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)

# Configuration
CURRENT_VERSION = os.environ.get('APP_VERSION', '1.0.0')
IMAGE_NAME = os.environ.get('DOCKER_IMAGE', 'darts-kiosk')
REGISTRY_URL = os.environ.get('DOCKER_REGISTRY', '')


@dataclass
class VersionInfo:
    version: str
    tag: str
    released_at: Optional[str] = None
    is_current: bool = False
    is_stable: bool = False
    changelog: Optional[str] = None


@dataclass
class UpdateResult:
    success: bool
    board_id: str
    old_version: str
    new_version: str
    message: str
    timestamp: str


class UpdateService:
    """Manages Docker image updates for the system"""
    
    AGENT_TIMEOUT = 60  # seconds for update operations
    
    def __init__(self):
        self._update_history: List[UpdateResult] = []
        self._available_versions: List[VersionInfo] = []
    
    def get_current_version(self) -> str:
        """Get current running version"""
        return CURRENT_VERSION
    
    def get_available_versions(self) -> List[VersionInfo]:
        """Get list of available versions"""
        # In production, this would query a Docker registry
        # For now, return mock data
        return [
            VersionInfo(
                version="1.0.0",
                tag="stable",
                is_current=(CURRENT_VERSION == "1.0.0"),
                is_stable=True
            ),
            VersionInfo(
                version="1.0.1",
                tag="latest",
                is_current=(CURRENT_VERSION == "1.0.1"),
                is_stable=False
            )
        ]
    
    async def check_for_updates(self) -> Optional[VersionInfo]:
        """Check if updates are available"""
        versions = self.get_available_versions()
        
        for v in versions:
            if not v.is_current and v.is_stable:
                return v
        
        return None
    
    async def update_agent(self, board_id: str, agent_url: str, target_version: str = "latest") -> UpdateResult:
        """Send update command to an agent"""
        old_version = CURRENT_VERSION
        
        try:
            async with httpx.AsyncClient(timeout=self.AGENT_TIMEOUT) as client:
                # Trigger update on agent
                response = await client.post(
                    f"{agent_url}/api/agent/update",
                    json={"target_version": target_version},
                    headers={"X-Agent-Secret": os.environ.get('AGENT_SECRET', '')}
                )
                
                if response.status_code == 200:
                    result = UpdateResult(
                        success=True,
                        board_id=board_id,
                        old_version=old_version,
                        new_version=target_version,
                        message="Update initiated successfully",
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
                else:
                    result = UpdateResult(
                        success=False,
                        board_id=board_id,
                        old_version=old_version,
                        new_version=target_version,
                        message=f"Update failed: HTTP {response.status_code}",
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
                    
        except Exception as e:
            result = UpdateResult(
                success=False,
                board_id=board_id,
                old_version=old_version,
                new_version=target_version,
                message=f"Update failed: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        self._update_history.append(result)
        logger.info(f"Update agent {board_id}: {result.message}")
        
        return result
    
    async def update_all_agents(self, target_version: str = "latest") -> List[UpdateResult]:
        """Update all registered agents"""
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Board
        
        results = []
        
        try:
            async with AsyncSessionLocal() as db:
                query = select(Board).where(Board.agent_api_base_url != None)
                board_result = await db.execute(query)
                boards = board_result.scalars().all()
                
                for board in boards:
                    if board.agent_api_base_url:
                        result = await self.update_agent(
                            board.board_id,
                            board.agent_api_base_url,
                            target_version
                        )
                        results.append(result)
        except Exception as e:
            logger.error(f"Error updating agents: {e}")
        
        return results
    
    def get_update_history(self, limit: int = 50) -> List[Dict]:
        """Get update history"""
        return [
            {
                "success": r.success,
                "board_id": r.board_id,
                "old_version": r.old_version,
                "new_version": r.new_version,
                "message": r.message,
                "timestamp": r.timestamp
            }
            for r in self._update_history[-limit:]
        ]
    
    async def rollback_agent(self, board_id: str, agent_url: str, target_version: str) -> UpdateResult:
        """Rollback an agent to a previous version"""
        return await self.update_agent(board_id, agent_url, target_version)
    
    def trigger_local_update(self, target_version: str = "latest") -> dict:
        """
        Trigger local update (for current machine).
        Returns instructions for the update process.
        """
        return {
            "action": "manual_required",
            "current_version": CURRENT_VERSION,
            "target_version": target_version,
            "instructions": [
                f"docker pull {IMAGE_NAME}:{target_version}",
                "docker-compose down",
                "docker-compose up -d"
            ],
            "note": "Automatic local updates require container orchestration (e.g., Watchtower)"
        }


# Global instance
update_service = UpdateService()
