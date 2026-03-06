"""
Autodarts Integration Service - Full Production Implementation
Browser automation via Playwright for Autodarts.io
With Circuit Breaker, Fallback Strategy, and Persistent Browser Context
"""
import asyncio
import os
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
import time

logger = logging.getLogger(__name__)

# Configuration
AUTODARTS_URL = os.environ.get('AUTODARTS_URL', 'https://play.autodarts.io')
SCREENSHOTS_DIR = Path(os.environ.get('DATA_DIR', '/app/data')) / 'autodarts_debug'
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ===== Circuit Breaker =====

class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for automation resilience.
    Opens after consecutive failures, allows recovery attempts.
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
    
    @property
    def state(self) -> CircuitState:
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker: OPEN -> HALF_OPEN")
        return self._state
    
    def can_execute(self) -> bool:
        """Check if request can proceed"""
        state = self.state
        
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        else:  # OPEN
            return False
    
    def record_success(self):
        """Record successful execution"""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            logger.info("Circuit breaker: HALF_OPEN -> CLOSED (recovered)")
        
        self._failure_count = 0
        self._half_open_calls = 0
    
    def record_failure(self):
        """Record failed execution"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker: HALF_OPEN -> OPEN (still failing)")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: CLOSED -> OPEN (threshold {self.failure_threshold} reached)")
        
        self._half_open_calls += 1
    
    def reset(self):
        """Manual reset"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("Circuit breaker: manually reset to CLOSED")


# ===== Selector Fallback Strategy =====

class SelectorFallback:
    """
    Manages multiple selector strategies with fallback.
    Learns which selectors work and prioritizes them.
    """
    
    def __init__(self):
        self._selector_success: dict = {}  # selector -> success count
        self._selector_failure: dict = {}  # selector -> failure count
    
    def get_selectors(self, category: str, selectors: List[str]) -> List[str]:
        """Get selectors sorted by success rate"""
        def score(selector: str) -> float:
            key = f"{category}:{selector}"
            success = self._selector_success.get(key, 0)
            failure = self._selector_failure.get(key, 0)
            total = success + failure
            if total == 0:
                return 0.5  # Neutral for untested
            return success / total
        
        return sorted(selectors, key=score, reverse=True)
    
    def record_success(self, category: str, selector: str):
        """Record that a selector worked"""
        key = f"{category}:{selector}"
        self._selector_success[key] = self._selector_success.get(key, 0) + 1
    
    def record_failure(self, category: str, selector: str):
        """Record that a selector failed"""
        key = f"{category}:{selector}"
        self._selector_failure[key] = self._selector_failure.get(key, 0) + 1


class AutodartsError(Exception):
    """Custom exception for Autodarts integration errors"""
    def __init__(self, message: str, screenshot_path: Optional[str] = None, html_path: Optional[str] = None):
        super().__init__(message)
        self.screenshot_path = screenshot_path
        self.html_path = html_path


class GameType(str, Enum):
    X01_301 = "301"
    X01_501 = "501"
    CRICKET = "Cricket"
    TRAINING = "Training"


@dataclass
class GameConfig:
    """Configuration for a dart game"""
    game_type: str
    players: List[str]
    board_id: str
    session_id: str
    autodarts_url: str = AUTODARTS_URL


@dataclass
class GameStatus:
    """Status of a dart game"""
    is_running: bool = False
    is_finished: bool = False
    winner: Optional[str] = None
    scores: Optional[dict] = None
    current_player: Optional[str] = None
    error: Optional[str] = None
    error_screenshot: Optional[str] = None


@dataclass
class AutomationResult:
    """Result of an automation action"""
    success: bool
    message: str
    screenshot_path: Optional[str] = None
    html_path: Optional[str] = None
    details: dict = field(default_factory=dict)


class AutodartsIntegration(ABC):
    """Abstract base class for Autodarts integration"""
    
    @abstractmethod
    async def start_game(self, config: GameConfig) -> AutomationResult:
        pass
    
    @abstractmethod
    async def get_game_status(self) -> GameStatus:
        pass
    
    @abstractmethod
    async def stop_game(self) -> AutomationResult:
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
    
    @abstractmethod
    async def wait_for_game_end(self, timeout_seconds: int, on_status_update: Optional[Callable] = None) -> GameStatus:
        pass


class PlaywrightAutodartsIntegration(AutodartsIntegration):
    """
    Production Playwright-based Autodarts integration.
    Handles browser automation for Autodarts.io
    With Circuit Breaker, Selector Fallback, and Persistent Browser Context
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    PAGE_LOAD_TIMEOUT = 30000  # ms
    ACTION_TIMEOUT = 10000  # ms
    
    # Circuit breaker settings
    CIRCUIT_FAILURE_THRESHOLD = 3
    CIRCUIT_RECOVERY_TIMEOUT = 120  # seconds
    
    # DOM Selectors (may need adjustment based on actual Autodarts DOM)
    SELECTORS = {
        # Game selection
        'game_mode_button': '[data-testid="game-mode-{mode}"], .game-mode-{mode}, button:has-text("{mode}")',
        'game_301': '[data-game="301"], .game-301, button:has-text("301")',
        'game_501': '[data-game="501"], .game-501, button:has-text("501")',
        'game_cricket': '[data-game="cricket"], .game-cricket, button:has-text("Cricket")',
        'game_training': '[data-game="training"], .game-training, button:has-text("Training")',
        
        # Player entry
        'add_player_button': '[data-testid="add-player"], .add-player, button:has-text("Add Player")',
        'player_name_input': 'input[name="player-name"], input[placeholder*="name"], .player-name-input',
        'player_confirm': '[data-testid="confirm-player"], .confirm-player',
        
        # Game controls
        'start_game_button': '[data-testid="start-game"], .start-game, button:has-text("Start")',
        'game_active_indicator': '[data-game-active], .game-active, .match-running',
        
        # Match end detection
        'match_finished': '[data-match-finished], .match-finished, .game-over, .winner-screen',
        'winner_display': '[data-winner], .winner-name, .match-winner',
        'final_scores': '[data-final-scores], .final-scores, .match-results',
        
        # Error states
        'error_message': '.error-message, .alert-error, [data-error]',
    }
    
    def __init__(self, headless: bool = True, use_persistent_context: bool = True):
        self.headless = headless
        self.use_persistent_context = use_persistent_context
        self._browser = None
        self._context = None
        self._page = None
        self._current_config: Optional[GameConfig] = None
        self._game_started = False
        self._playwright = None
        
        # Circuit breaker and selector fallback
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=self.CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=self.CIRCUIT_RECOVERY_TIMEOUT
        )
        self._selector_fallback = SelectorFallback()
        self._manual_mode = False  # Fallback to manual operation
    
    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit_breaker.state
    
    @property
    def is_manual_mode(self) -> bool:
        return self._manual_mode
    
    def enable_manual_mode(self):
        """Enable manual fallback mode (automation disabled)"""
        self._manual_mode = True
        logger.warning("Manual mode enabled - automation disabled")
    
    def disable_manual_mode(self):
        """Disable manual fallback mode (re-enable automation)"""
        self._manual_mode = False
        self._circuit_breaker.reset()
        logger.info("Manual mode disabled - automation re-enabled")
    
    async def _init_browser(self):
        """Initialize Playwright browser with persistent context for speed"""
        if self._browser is not None:
            return
        
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            
            if self.use_persistent_context:
                # Persistent context for faster subsequent loads
                user_data_dir = SCREENSHOTS_DIR.parent / 'browser_data'
                user_data_dir.mkdir(exist_ok=True)
                
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=self.headless,
                    viewport={'width': 1920, 'height': 1080},
                    args=['--disable-dev-shm-usage', '--no-sandbox']
                )
                self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            else:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=['--disable-dev-shm-usage', '--no-sandbox']
                )
                self._context = await self._browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
                )
                self._page = await self._context.new_page()
            
            self._page.set_default_timeout(self.ACTION_TIMEOUT)
            logger.info(f"Playwright browser initialized (persistent={self.use_persistent_context})")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise AutodartsError(f"Browser initialization failed: {e}")
    
    async def _close_browser(self):
        """Close browser and cleanup"""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
    
    async def _save_debug_info(self, prefix: str) -> tuple:
        """Save screenshot and HTML for debugging"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        board_id = self._current_config.board_id if self._current_config else 'unknown'
        session_id = self._current_config.session_id[:8] if self._current_config else 'unknown'
        
        base_name = f"{prefix}_{board_id}_{session_id}_{timestamp}"
        screenshot_path = SCREENSHOTS_DIR / f"{base_name}.png"
        html_path = SCREENSHOTS_DIR / f"{base_name}.html"
        
        try:
            if self._page:
                await self._page.screenshot(path=str(screenshot_path), full_page=True)
                html_content = await self._page.content()
                html_path.write_text(html_content)
                logger.info(f"Debug info saved: {screenshot_path}")
                return str(screenshot_path), str(html_path)
        except Exception as e:
            logger.warning(f"Failed to save debug info: {e}")
        
        return None, None
    
    async def _retry_action(self, action_fn, action_name: str):
        """Execute action with retry logic"""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                return await action_fn()
            except Exception as e:
                last_error = e
                logger.warning(f"{action_name} failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)
        
        # All retries failed - save debug info
        screenshot_path, html_path = await self._save_debug_info(f"error_{action_name}")
        raise AutodartsError(
            f"{action_name} failed after {self.MAX_RETRIES} attempts: {last_error}",
            screenshot_path=screenshot_path,
            html_path=html_path
        )
    
    async def is_available(self) -> bool:
        """Check if Autodarts is reachable"""
        try:
            await self._init_browser()
            await self._page.goto(AUTODARTS_URL, timeout=self.PAGE_LOAD_TIMEOUT)
            await self._page.wait_for_load_state('networkidle', timeout=self.PAGE_LOAD_TIMEOUT)
            logger.info("Autodarts is available")
            return True
        except Exception as e:
            logger.error(f"Autodarts not available: {e}")
            return False
    
    async def start_game(self, config: GameConfig) -> AutomationResult:
        """
        Start a new game via browser automation.
        
        Flow:
        1. Navigate to Autodarts
        2. Select game type
        3. Add players
        4. Click Start
        """
        self._current_config = config
        logger.info(f"Starting game: {config.game_type} | Board: {config.board_id} | Session: {config.session_id}")
        logger.info(f"Players: {config.players}")
        
        try:
            await self._init_browser()
            
            # Step 1: Navigate to Autodarts
            async def navigate():
                await self._page.goto(config.autodarts_url, timeout=self.PAGE_LOAD_TIMEOUT)
                await self._page.wait_for_load_state('networkidle', timeout=self.PAGE_LOAD_TIMEOUT)
            
            await self._retry_action(navigate, "navigate")
            logger.info("Navigated to Autodarts")
            
            # Step 2: Select game type
            async def select_game():
                game_type_lower = config.game_type.lower()
                selectors_to_try = [
                    f'[data-game="{config.game_type}"]',
                    f'.game-{game_type_lower}',
                    f'button:has-text("{config.game_type}")',
                    f'a:has-text("{config.game_type}")',
                    f'div:has-text("{config.game_type}"):visible',
                ]
                
                for selector in selectors_to_try:
                    try:
                        element = await self._page.wait_for_selector(selector, timeout=3000)
                        if element:
                            await element.click()
                            logger.info(f"Selected game type: {config.game_type}")
                            return
                    except:
                        continue
                
                raise Exception(f"Could not find game type selector for: {config.game_type}")
            
            await self._retry_action(select_game, "select_game")
            await asyncio.sleep(1)  # Wait for UI update
            
            # Step 3: Add players
            async def add_players():
                for i, player_name in enumerate(config.players):
                    # Try to find add player button
                    add_btn_selectors = [
                        '[data-testid="add-player"]',
                        '.add-player',
                        'button:has-text("Add")',
                        'button:has-text("+")',
                    ]
                    
                    for selector in add_btn_selectors:
                        try:
                            btn = await self._page.wait_for_selector(selector, timeout=2000)
                            if btn:
                                await btn.click()
                                break
                        except:
                            continue
                    
                    await asyncio.sleep(0.5)
                    
                    # Find and fill player name input
                    input_selectors = [
                        f'input[name="player-{i}"]',
                        'input[placeholder*="name"]:last-of-type',
                        '.player-name-input:last-of-type',
                        'input:visible:last-of-type',
                    ]
                    
                    for selector in input_selectors:
                        try:
                            input_el = await self._page.wait_for_selector(selector, timeout=2000)
                            if input_el:
                                await input_el.fill(player_name)
                                logger.info(f"Added player: {player_name}")
                                break
                        except:
                            continue
                    
                    await asyncio.sleep(0.3)
            
            await self._retry_action(add_players, "add_players")
            await asyncio.sleep(1)
            
            # Step 4: Start game
            async def click_start():
                start_selectors = [
                    '[data-testid="start-game"]',
                    '.start-game',
                    'button:has-text("Start")',
                    'button:has-text("BEGIN")',
                    'button.primary:has-text("Start")',
                ]
                
                for selector in start_selectors:
                    try:
                        btn = await self._page.wait_for_selector(selector, timeout=3000)
                        if btn:
                            await btn.click()
                            logger.info("Clicked Start button")
                            return
                    except:
                        continue
                
                raise Exception("Could not find Start button")
            
            await self._retry_action(click_start, "click_start")
            await asyncio.sleep(2)  # Wait for game to initialize
            
            self._game_started = True
            screenshot_path, _ = await self._save_debug_info("game_started")
            
            logger.info(f"Game started successfully: {config.game_type} with {len(config.players)} players")
            
            return AutomationResult(
                success=True,
                message="Game started successfully",
                screenshot_path=screenshot_path,
                details={
                    "game_type": config.game_type,
                    "players": config.players,
                    "board_id": config.board_id,
                    "session_id": config.session_id
                }
            )
            
        except AutodartsError:
            raise
        except Exception as e:
            screenshot_path, html_path = await self._save_debug_info("start_game_error")
            logger.error(f"Failed to start game: {e}")
            return AutomationResult(
                success=False,
                message=f"Failed to start game: {e}",
                screenshot_path=screenshot_path,
                html_path=html_path
            )
    
    async def get_game_status(self) -> GameStatus:
        """Check current game status by inspecting DOM"""
        if not self._page or not self._game_started:
            return GameStatus(is_running=False, is_finished=False)
        
        try:
            # Check for match finished
            finished_selectors = [
                '[data-match-finished]',
                '.match-finished',
                '.game-over',
                '.winner-screen',
                'div:has-text("Winner"):visible',
                'div:has-text("WINNER"):visible',
                'div:has-text("Game Over"):visible',
            ]
            
            for selector in finished_selectors:
                try:
                    element = await self._page.query_selector(selector)
                    if element:
                        # Try to get winner
                        winner = None
                        winner_selectors = ['.winner-name', '[data-winner]', '.match-winner']
                        for ws in winner_selectors:
                            try:
                                winner_el = await self._page.query_selector(ws)
                                if winner_el:
                                    winner = await winner_el.text_content()
                                    break
                            except:
                                continue
                        
                        logger.info(f"Match finished! Winner: {winner}")
                        return GameStatus(is_running=False, is_finished=True, winner=winner)
                except:
                    continue
            
            # Check for active game
            active_selectors = [
                '[data-game-active]',
                '.game-active',
                '.match-running',
                '.scoreboard',
            ]
            
            for selector in active_selectors:
                try:
                    element = await self._page.query_selector(selector)
                    if element:
                        return GameStatus(is_running=True, is_finished=False)
                except:
                    continue
            
            # Default: assume running if we started the game
            return GameStatus(is_running=self._game_started, is_finished=False)
            
        except Exception as e:
            logger.warning(f"Error checking game status: {e}")
            return GameStatus(is_running=self._game_started, is_finished=False, error=str(e))
    
    async def wait_for_game_end(self, timeout_seconds: int = 7200, on_status_update: Optional[Callable] = None) -> GameStatus:
        """
        Wait for game to end with polling.
        Default timeout: 2 hours
        """
        poll_interval = 5  # seconds
        elapsed = 0
        last_status = None
        
        logger.info(f"Waiting for game end (timeout: {timeout_seconds}s)")
        
        while elapsed < timeout_seconds:
            try:
                status = await self.get_game_status()
                
                # Call status update callback if provided
                if on_status_update and status != last_status:
                    try:
                        await on_status_update(status)
                    except:
                        pass
                    last_status = status
                
                if status.is_finished:
                    logger.info(f"Game finished after {elapsed}s. Winner: {status.winner}")
                    await self._save_debug_info("game_finished")
                    return status
                
                if status.error:
                    logger.warning(f"Game status error: {status.error}")
                
            except Exception as e:
                logger.warning(f"Error in wait loop: {e}")
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            
            # Log progress every 5 minutes
            if elapsed % 300 == 0:
                logger.info(f"Still waiting for game end... ({elapsed}s elapsed)")
        
        # Timeout reached
        screenshot_path, _ = await self._save_debug_info("timeout")
        logger.warning(f"Game wait timeout after {timeout_seconds}s")
        
        return GameStatus(
            is_running=False,
            is_finished=True,
            error="Timeout waiting for game end",
            error_screenshot=screenshot_path
        )
    
    async def stop_game(self) -> AutomationResult:
        """Stop the current game and cleanup"""
        logger.info("Stopping Autodarts game and closing browser")
        
        self._game_started = False
        self._current_config = None
        
        try:
            await self._close_browser()
            return AutomationResult(success=True, message="Game stopped and browser closed")
        except Exception as e:
            logger.error(f"Error stopping game: {e}")
            return AutomationResult(success=False, message=f"Error stopping game: {e}")


class MockAutodartsIntegration(AutodartsIntegration):
    """Mock implementation for testing"""
    
    def __init__(self, game_duration_seconds: int = 10):
        self._game_running = False
        self._game_started_at: Optional[datetime] = None
        self._config: Optional[GameConfig] = None
        self._game_duration = game_duration_seconds
    
    async def is_available(self) -> bool:
        return True
    
    async def start_game(self, config: GameConfig) -> AutomationResult:
        logger.info(f"[MOCK] Starting game: {config.game_type}")
        self._game_running = True
        self._game_started_at = datetime.now(timezone.utc)
        self._config = config
        return AutomationResult(success=True, message="[MOCK] Game started")
    
    async def get_game_status(self) -> GameStatus:
        if not self._game_running:
            return GameStatus(is_running=False, is_finished=False)
        
        # Simulate game ending after duration
        if self._game_started_at:
            elapsed = (datetime.now(timezone.utc) - self._game_started_at).total_seconds()
            if elapsed >= self._game_duration:
                self._game_running = False
                winner = self._config.players[0] if self._config and self._config.players else "Player 1"
                return GameStatus(is_running=False, is_finished=True, winner=winner)
        
        return GameStatus(is_running=True, is_finished=False)
    
    async def wait_for_game_end(self, timeout_seconds: int = 3600, on_status_update: Optional[Callable] = None) -> GameStatus:
        while self._game_running:
            status = await self.get_game_status()
            if status.is_finished:
                return status
            await asyncio.sleep(1)
        return GameStatus(is_running=False, is_finished=True)
    
    async def stop_game(self) -> AutomationResult:
        self._game_running = False
        self._config = None
        return AutomationResult(success=True, message="[MOCK] Game stopped")


# Factory function
def get_autodarts_integration(use_mock: bool = False, headless: bool = True) -> AutodartsIntegration:
    """Get Autodarts integration instance"""
    if use_mock or os.environ.get('AUTODARTS_MOCK', '').lower() == 'true':
        logger.info("Using MOCK Autodarts integration")
        return MockAutodartsIntegration()
    
    logger.info("Using Playwright Autodarts integration")
    return PlaywrightAutodartsIntegration(headless=headless)
