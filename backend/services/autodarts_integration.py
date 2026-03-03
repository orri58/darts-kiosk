"""
Autodarts Integration Service
Service layer for Autodarts browser automation.
Designed to be swappable for event-based integration later.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    """Configuration for a dart game"""
    game_type: str  # "301", "501", "Cricket", "Training"
    players: List[str]
    board_id: str
    session_id: str


@dataclass
class GameStatus:
    """Status of a dart game"""
    is_running: bool
    is_finished: bool
    winner: Optional[str] = None
    scores: Optional[dict] = None
    error: Optional[str] = None


class AutodartsIntegration(ABC):
    """
    Abstract base class for Autodarts integration.
    Allows swapping between different integration methods.
    """
    
    @abstractmethod
    async def start_game(self, config: GameConfig) -> bool:
        """Start a new game with the given configuration"""
        pass
    
    @abstractmethod
    async def get_game_status(self) -> GameStatus:
        """Get the current game status"""
        pass
    
    @abstractmethod
    async def stop_game(self) -> bool:
        """Stop the current game"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if Autodarts is available"""
        pass


class PlaywrightAutodartsIntegration(AutodartsIntegration):
    """
    Playwright-based Autodarts integration.
    Uses browser automation to control Autodarts.
    
    NOTE: This is a placeholder implementation.
    Full implementation requires Playwright browser instance
    running on the local Board-PC with Autodarts access.
    """
    
    def __init__(self, autodarts_url: str = "https://play.autodarts.io"):
        self.autodarts_url = autodarts_url
        self._browser = None
        self._page = None
        self._current_config: Optional[GameConfig] = None
    
    async def is_available(self) -> bool:
        """Check if Autodarts web interface is reachable"""
        # In production, this would check if the browser can reach Autodarts
        logger.info("Checking Autodarts availability...")
        return True
    
    async def start_game(self, config: GameConfig) -> bool:
        """
        Start a game via Playwright browser automation.
        
        Steps:
        1. Navigate to Autodarts play page
        2. Select game type (301/501/Cricket/etc.)
        3. Enter player names
        4. Click Start
        
        Returns True if game started successfully.
        """
        self._current_config = config
        logger.info(f"Starting game: {config.game_type} with players: {config.players}")
        
        # Placeholder: In production, this would be actual Playwright code
        # Example implementation:
        #
        # from playwright.async_api import async_playwright
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=False)
        #     page = await browser.new_page()
        #     await page.goto(self.autodarts_url)
        #     
        #     # Wait for page load
        #     await page.wait_for_selector('[data-testid="game-select"]')
        #     
        #     # Select game type
        #     await page.click(f'[data-game-type="{config.game_type}"]')
        #     
        #     # Add players
        #     for i, player in enumerate(config.players):
        #         await page.fill(f'[data-player-{i}]', player)
        #     
        #     # Start game
        #     await page.click('[data-testid="start-game"]')
        #     
        #     # Wait for game to start
        #     await page.wait_for_selector('[data-testid="game-board"]')
        #     
        #     self._browser = browser
        #     self._page = page
        
        return True
    
    async def get_game_status(self) -> GameStatus:
        """
        Get current game status by inspecting DOM.
        
        Looks for:
        - Game running indicators
        - Match finished markers
        - Winner display
        - Score elements
        """
        if not self._current_config:
            return GameStatus(is_running=False, is_finished=False)
        
        # Placeholder: In production, would check actual DOM
        # Example:
        #
        # if self._page:
        #     finished_el = await self._page.query_selector('[data-match-finished]')
        #     if finished_el:
        #         winner_el = await self._page.query_selector('[data-winner-name]')
        #         winner = await winner_el.text_content() if winner_el else None
        #         return GameStatus(is_running=False, is_finished=True, winner=winner)
        #     
        #     running_el = await self._page.query_selector('[data-game-active]')
        #     if running_el:
        #         return GameStatus(is_running=True, is_finished=False)
        
        return GameStatus(is_running=True, is_finished=False)
    
    async def stop_game(self) -> bool:
        """Stop the current game and close browser"""
        logger.info("Stopping Autodarts game...")
        
        # Placeholder: In production, would close browser
        # if self._browser:
        #     await self._browser.close()
        #     self._browser = None
        #     self._page = None
        
        self._current_config = None
        return True
    
    async def wait_for_game_end(self, timeout_seconds: int = 3600) -> GameStatus:
        """
        Wait for the game to end (blocking).
        Polls the DOM for match-finished markers.
        
        Args:
            timeout_seconds: Maximum time to wait (default 1 hour)
        
        Returns:
            GameStatus with final game state
        """
        import asyncio
        
        poll_interval = 5  # Check every 5 seconds
        elapsed = 0
        
        while elapsed < timeout_seconds:
            status = await self.get_game_status()
            if status.is_finished:
                logger.info(f"Game finished! Winner: {status.winner}")
                return status
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        # Timeout reached
        return GameStatus(
            is_running=False, 
            is_finished=True, 
            error="Timeout waiting for game end"
        )


class MockAutodartsIntegration(AutodartsIntegration):
    """
    Mock implementation for testing without actual Autodarts.
    Simulates game flow for development/testing.
    """
    
    def __init__(self):
        self._game_running = False
        self._config: Optional[GameConfig] = None
    
    async def is_available(self) -> bool:
        return True
    
    async def start_game(self, config: GameConfig) -> bool:
        logger.info(f"[MOCK] Starting game: {config.game_type}")
        self._game_running = True
        self._config = config
        return True
    
    async def get_game_status(self) -> GameStatus:
        return GameStatus(
            is_running=self._game_running, 
            is_finished=not self._game_running
        )
    
    async def stop_game(self) -> bool:
        self._game_running = False
        self._config = None
        return True


# Factory function to get the appropriate integration
def get_autodarts_integration(use_mock: bool = False) -> AutodartsIntegration:
    """
    Factory function to get Autodarts integration instance.
    
    Args:
        use_mock: If True, returns mock implementation for testing
    
    Returns:
        AutodartsIntegration instance
    """
    if use_mock:
        return MockAutodartsIntegration()
    return PlaywrightAutodartsIntegration()


# Example usage:
# 
# integration = get_autodarts_integration()
# 
# config = GameConfig(
#     game_type="501",
#     players=["Max", "Lisa"],
#     board_id="BOARD-1",
#     session_id="abc123"
# )
# 
# if await integration.is_available():
#     await integration.start_game(config)
#     
#     # Poll for game end or use callback
#     status = await integration.wait_for_game_end()
#     
#     if status.is_finished:
#         # Game ended - update session
#         pass
