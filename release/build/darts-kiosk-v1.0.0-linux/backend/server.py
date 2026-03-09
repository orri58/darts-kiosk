"""
Main FastAPI Application - Darts Kiosk + Admin Control System
Refactored: routes split into routers/, schemas in schemas.py, deps in dependencies.py
"""
import sys
from pathlib import Path

# Ensure 'from backend.xxx' works regardless of working directory
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from datetime import datetime, timezone
import os
import logging
import logging.handlers
import json

# Load environment
ROOT_DIR = Path(__file__).parent
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

# Load secrets from file if available
from backend.services.setup_wizard import load_secrets_to_env, is_setup_complete
load_secrets_to_env()

from backend.database import get_db, init_db, Base, async_engine, AsyncSessionLocal
from backend.models import (
    User, Board, UserRole, BoardStatus,
    DEFAULT_PALETTES, DEFAULT_PRICING, DEFAULT_BRANDING
)
from backend.dependencies import hash_password, get_or_create_setting, MODE

# Services
from backend.services.scheduler import start_scheduler, stop_scheduler
from backend.services.backup_service import start_backup_service, stop_backup_service
from backend.services.health_monitor import health_monitor, start_health_monitor, stop_health_monitor
from backend.services.ws_manager import board_ws
from backend.services.mdns_service import mdns_service

# Routers
from backend.routers import auth, boards, kiosk, settings, admin, backups, updates, agent, discovery, matches, stats, players

# Configuration
from backend.database import DATA_DIR
LOGS_DIR = DATA_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# JSON Logging with rotation
LOG_FILE = LOGS_DIR / 'app.log'


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,
    backupCount=5
)
file_handler.setFormatter(JsonFormatter())

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Security: LAN-only access
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

if CORS_ORIGINS != ['*']:
    lan_patterns = [
        'http://localhost:*',
        'http://127.0.0.1:*',
        'http://192.168.*.*:*',
        'http://10.*.*.*:*',
        'http://172.16.*.*:*',
    ]
    CORS_ORIGINS.extend([p for p in lan_patterns if p not in CORS_ORIGINS])


# ===== Lifespan =====

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN.value))
        if not result.scalar_one_or_none():
            admin_user = User(
                username="admin",
                password_hash=hash_password("admin123"),
                pin_hash=hash_password("1234"),
                role=UserRole.ADMIN.value,
                display_name="Administrator"
            )
            db.add(admin_user)
            logger.info("Created default admin user: admin / admin123")

        result = await db.execute(select(User).where(User.username == "wirt"))
        if not result.scalar_one_or_none():
            staff = User(
                username="wirt",
                password_hash=hash_password("wirt123"),
                pin_hash=hash_password("0000"),
                role=UserRole.STAFF.value,
                display_name="Wirt"
            )
            db.add(staff)
            logger.info("Created default staff user: wirt / wirt123")

        result = await db.execute(select(Board).where(Board.board_id == "BOARD-1"))
        if not result.scalar_one_or_none():
            board1 = Board(
                board_id="BOARD-1",
                name="Dartboard 1",
                location="Main Floor",
                status=BoardStatus.LOCKED.value,
                is_master=(MODE == "MASTER")
            )
            db.add(board1)
            logger.info("Created BOARD-1")

        result = await db.execute(select(Board).where(Board.board_id == "BOARD-2"))
        if not result.scalar_one_or_none():
            board2 = Board(
                board_id="BOARD-2",
                name="Dartboard 2",
                location="Back Room",
                status=BoardStatus.LOCKED.value
            )
            db.add(board2)
            logger.info("Created BOARD-2")

        await get_or_create_setting(db, "branding", DEFAULT_BRANDING)
        await get_or_create_setting(db, "pricing", DEFAULT_PRICING)
        await get_or_create_setting(db, "palettes", DEFAULT_PALETTES)

        await db.commit()

    await start_scheduler()
    health_monitor.set_scheduler_status(True)

    await start_backup_service()
    health_monitor.set_backup_status(True)

    await start_health_monitor()

    # Start mDNS
    try:
        if MODE == "MASTER":
            mdns_service.start_discovery()
            logger.info("mDNS discovery started (MASTER mode)")
        else:
            mdns_service.advertise()
            logger.info("mDNS advertisement started (AGENT mode)")
    except Exception as exc:
        logger.warning(f"mDNS start failed (non-critical): {exc}")

    # Start background update checker
    from backend.services.update_service import update_service as _update_svc
    await _update_svc.start_background_checker()

    logger.info(f"Darts Kiosk System started in {MODE} mode")
    logger.info(f"Setup complete: {is_setup_complete()}")
    logger.info(f"Autodarts mode: {os.environ.get('AUTODARTS_MODE', 'observer')}")
    yield
    # Shutdown: close all observers first
    from backend.services.autodarts_observer import observer_manager
    await observer_manager.close_all()
    from backend.services.update_service import update_service as _update_svc
    await _update_svc.stop_background_checker()
    mdns_service.stop()
    await stop_health_monitor()
    await stop_backup_service()
    await stop_scheduler()
    logger.info("Shutting down...")


# ===== App Setup =====

app = FastAPI(title="Darts Kiosk System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ALLOWED_HOSTS != ['*']:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


# ===== Include all routers under /api =====

from fastapi import APIRouter
api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(boards.router)
api_router.include_router(kiosk.router)
api_router.include_router(settings.router)
api_router.include_router(admin.router)
api_router.include_router(backups.router)
api_router.include_router(updates.router)
api_router.include_router(agent.router)
api_router.include_router(discovery.router)
api_router.include_router(matches.router)
api_router.include_router(stats.router)
api_router.include_router(players.router)

app.include_router(api_router)


# ===== Utility endpoint: LAN base URL =====

@app.get("/api/system/base-url")
async def get_base_url(request: Request):
    """Return the best base URL for generating public links (QR codes etc)."""
    import socket
    # Prefer X-Forwarded-Host header (reverse proxy)
    host_header = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    scheme = request.headers.get("x-forwarded-proto", "http")

    # If host looks like a real external URL, use it
    if host_header and "localhost" not in host_header and "127.0.0.1" not in host_header:
        return {"base_url": f"{scheme}://{host_header}"}

    # Otherwise detect LAN IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            finally:
                s.close()
    except Exception:
        local_ip = "127.0.0.1"

    port = os.environ.get("PORT", "8001")
    return {"base_url": f"http://{local_ip}:{port}"}


# ===== WebSocket Endpoint for Real-Time Board Status =====

@app.websocket("/api/ws/boards")
async def ws_boards(ws: WebSocket):
    """WebSocket endpoint for live board status updates"""
    await board_ws.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await board_ws.disconnect(ws)
