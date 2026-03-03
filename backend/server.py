"""
Main FastAPI Application - Darts Kiosk + Admin Control System
Enterprise Hardened Version with Setup Wizard, Backups, Health Monitoring
"""
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
import os
import uuid
import logging
import logging.handlers
import hashlib
import hmac
import jwt
import bcrypt
import json
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Load secrets from file if available
from services.setup_wizard import load_secrets_to_env
load_secrets_to_env()

from database import get_db, init_db, Base, async_engine
from models import (
    User, Board, Session, AuditLog, Settings,
    UserRole, BoardStatus, SessionStatus, PricingMode,
    DEFAULT_PALETTES, DEFAULT_PRICING, DEFAULT_BRANDING
)
from services.scheduler import scheduler, start_scheduler, stop_scheduler
from services.backup_service import backup_service, start_backup_service, stop_backup_service
from services.health_monitor import health_monitor, start_health_monitor, stop_health_monitor
from services.update_service import update_service
from services.setup_wizard import (
    is_setup_complete, check_setup_status, complete_setup,
    SetupConfig, SetupStatus
)

# Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'darts-kiosk-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
MODE = os.environ.get('MODE', 'MASTER')  # MASTER or AGENT
AGENT_SECRET = os.environ.get('AGENT_SECRET', 'agent-secret-key')
DATA_DIR = Path(os.environ.get('DATA_DIR', '/app/data'))
ASSETS_DIR = DATA_DIR / 'assets'
LOGS_DIR = DATA_DIR / 'logs'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
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

# Setup logging with rotation
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
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

# Restrict CORS to LAN if not wildcard
if CORS_ORIGINS != ['*']:
    # Add common LAN patterns
    lan_patterns = [
        'http://localhost:*',
        'http://127.0.0.1:*',
        'http://192.168.*.*:*',
        'http://10.*.*.*:*',
        'http://172.16.*.*:*',
    ]
    CORS_ORIGINS.extend([p for p in lan_patterns if p not in CORS_ORIGINS])


# ===== Pydantic Schemas =====

class LoginRequest(BaseModel):
    username: str
    password: str

class PinLoginRequest(BaseModel):
    pin: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "staff"
    display_name: Optional[str] = None
    pin: Optional[str] = None

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    pin: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    display_name: Optional[str]
    is_active: bool
    created_at: datetime

class BoardCreate(BaseModel):
    board_id: str
    name: str
    location: Optional[str] = None
    autodarts_target_url: Optional[str] = None
    agent_api_base_url: Optional[str] = None

class BoardUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    autodarts_target_url: Optional[str] = None
    agent_api_base_url: Optional[str] = None
    status: Optional[str] = None

class BoardResponse(BaseModel):
    id: str
    board_id: str
    name: str
    location: Optional[str]
    status: str
    last_heartbeat_at: Optional[datetime]
    is_master: bool
    created_at: datetime

class UnlockRequest(BaseModel):
    pricing_mode: str = "per_game"
    game_type: Optional[str] = None
    credits: Optional[int] = None
    minutes: Optional[int] = None
    players_count: int = 1
    price_total: float = 0.0

class ExtendRequest(BaseModel):
    credits: Optional[int] = None
    minutes: Optional[int] = None

class StartGameRequest(BaseModel):
    game_type: str
    players: List[str]

class SessionResponse(BaseModel):
    id: str
    board_id: str
    pricing_mode: str
    game_type: Optional[str]
    credits_total: int
    credits_remaining: int
    minutes_total: int
    price_total: float
    started_at: datetime
    expires_at: Optional[datetime]
    ended_at: Optional[datetime]
    players_count: int
    players: List[str]
    status: str

class AgentStatusResponse(BaseModel):
    board_id: str
    status: str
    current_session: Optional[SessionResponse]
    mode: str

class SettingsUpdate(BaseModel):
    value: dict

class AuditLogResponse(BaseModel):
    id: str
    username: Optional[str]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    details: Optional[dict]
    created_at: datetime

class RevenueResponse(BaseModel):
    date: str
    total: float
    session_count: int
    by_board: dict


# ===== Helper Functions =====

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_agent_secret(request: Request) -> bool:
    auth_header = request.headers.get("X-Agent-Secret", "")
    return hmac.compare_digest(auth_header, AGENT_SECRET)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def log_audit(db: AsyncSession, user: Optional[User], action: str, 
                    entity_type: str = None, entity_id: str = None, 
                    details: dict = None, ip: str = None):
    log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip
    )
    db.add(log)
    await db.flush()


async def get_or_create_setting(db: AsyncSession, key: str, default_value: dict) -> dict:
    result = await db.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = Settings(key=key, value=default_value)
        db.add(setting)
        await db.flush()
    return setting.value


async def get_active_session_for_board(db: AsyncSession, board_db_id: str) -> Optional[Session]:
    result = await db.execute(
        select(Session)
        .where(Session.board_id == board_db_id)
        .where(Session.status == SessionStatus.ACTIVE.value)
        .order_by(Session.started_at.desc())
    )
    return result.scalar_one_or_none()


# ===== Lifespan & App Setup =====

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    await init_db()
    
    # Seed default data
    async with async_engine.begin() as conn:
        from sqlalchemy.orm import Session as SyncSession
        
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        # Check for existing admin user
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN.value))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                pin_hash=hash_password("1234"),
                role=UserRole.ADMIN.value,
                display_name="Administrator"
            )
            db.add(admin)
            logger.info("Created default admin user: admin / admin123")
        
        # Create default staff user
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
        
        # Seed default boards
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
        
        # Seed default settings
        await get_or_create_setting(db, "branding", DEFAULT_BRANDING)
        await get_or_create_setting(db, "pricing", DEFAULT_PRICING)
        await get_or_create_setting(db, "palettes", DEFAULT_PALETTES)
        
        await db.commit()
    
    # Start background services
    await start_scheduler()
    health_monitor.set_scheduler_status(True)
    
    await start_backup_service()
    health_monitor.set_backup_status(True)
    
    await start_health_monitor()
    
    logger.info(f"Darts Kiosk System started in {MODE} mode")
    logger.info(f"Setup complete: {is_setup_complete()}")
    yield
    # Shutdown
    await stop_health_monitor()
    await stop_backup_service()
    await stop_scheduler()
    logger.info("Shutting down...")


app = FastAPI(title="Darts Kiosk System", lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# CORS - Restrict to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts (optional, enable in production)
if ALLOWED_HOSTS != ['*']:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


# ===== Auth Routes =====

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")
    
    token = create_token(user.id, user.username, user.role)
    await log_audit(db, user, "login", "user", user.id)
    
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name
        }
    )


@api_router.post("/auth/pin-login", response_model=TokenResponse)
async def pin_login(data: PinLoginRequest, db: AsyncSession = Depends(get_db)):
    """Quick PIN login for staff"""
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()
    
    for user in users:
        if user.pin_hash and verify_password(data.pin, user.pin_hash):
            token = create_token(user.id, user.username, user.role)
            await log_audit(db, user, "pin_login", "user", user.id)
            return TokenResponse(
                access_token=token,
                user={
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "display_name": user.display_name
                }
            )
    
    raise HTTPException(status_code=401, detail="Invalid PIN")


@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at
    )


# ===== User Management Routes (Admin Only) =====

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [UserResponse(
        id=u.id, username=u.username, role=u.role,
        display_name=u.display_name, is_active=u.is_active, created_at=u.created_at
    ) for u in users]


@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    # Check if username exists
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        pin_hash=hash_password(data.pin) if data.pin else None,
        role=data.role,
        display_name=data.display_name
    )
    db.add(user)
    await db.flush()
    await log_audit(db, admin, "create_user", "user", user.id, {"username": data.username})
    
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name, is_active=user.is_active, created_at=user.created_at
    )


@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.pin is not None:
        user.pin_hash = hash_password(data.pin)
    
    await db.flush()
    await log_audit(db, admin, "update_user", "user", user_id)
    
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name, is_active=user.is_active, created_at=user.created_at
    )


@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    await db.execute(delete(User).where(User.id == user_id))
    await log_audit(db, admin, "delete_user", "user", user_id, {"username": user.username})
    return {"message": "User deleted"}


# ===== Board Routes =====

@api_router.get("/boards", response_model=List[BoardResponse])
async def list_boards(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).order_by(Board.board_id))
    boards = result.scalars().all()
    return [BoardResponse(
        id=b.id, board_id=b.board_id, name=b.name, location=b.location,
        status=b.status, last_heartbeat_at=b.last_heartbeat_at,
        is_master=b.is_master, created_at=b.created_at
    ) for b in boards]


@api_router.get("/boards/{board_id}")
async def get_board(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Get active session
    session = await get_active_session_for_board(db, board.id)
    
    return {
        "board": BoardResponse(
            id=board.id, board_id=board.board_id, name=board.name, location=board.location,
            status=board.status, last_heartbeat_at=board.last_heartbeat_at,
            is_master=board.is_master, created_at=board.created_at
        ),
        "active_session": SessionResponse(
            id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
            game_type=session.game_type, credits_total=session.credits_total,
            credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
            price_total=session.price_total, started_at=session.started_at,
            expires_at=session.expires_at, ended_at=session.ended_at,
            players_count=session.players_count, players=session.players or [],
            status=session.status
        ) if session else None
    }


@api_router.post("/boards", response_model=BoardResponse)
async def create_board(data: BoardCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == data.board_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Board ID already exists")
    
    board = Board(
        board_id=data.board_id,
        name=data.name,
        location=data.location,
        autodarts_target_url=data.autodarts_target_url,
        agent_api_base_url=data.agent_api_base_url,
        agent_secret=str(uuid.uuid4())[:16],
        status=BoardStatus.LOCKED.value
    )
    db.add(board)
    await db.flush()
    await log_audit(db, admin, "create_board", "board", board.id, {"board_id": data.board_id})
    
    return BoardResponse(
        id=board.id, board_id=board.board_id, name=board.name, location=board.location,
        status=board.status, last_heartbeat_at=board.last_heartbeat_at,
        is_master=board.is_master, created_at=board.created_at
    )


@api_router.put("/boards/{board_id}", response_model=BoardResponse)
async def update_board(board_id: str, data: BoardUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    if data.name is not None:
        board.name = data.name
    if data.location is not None:
        board.location = data.location
    if data.autodarts_target_url is not None:
        board.autodarts_target_url = data.autodarts_target_url
    if data.agent_api_base_url is not None:
        board.agent_api_base_url = data.agent_api_base_url
    if data.status is not None:
        board.status = data.status
    
    await db.flush()
    await log_audit(db, admin, "update_board", "board", board.id)
    
    return BoardResponse(
        id=board.id, board_id=board.board_id, name=board.name, location=board.location,
        status=board.status, last_heartbeat_at=board.last_heartbeat_at,
        is_master=board.is_master, created_at=board.created_at
    )


@api_router.delete("/boards/{board_id}")
async def delete_board(board_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    await db.execute(delete(Board).where(Board.id == board.id))
    await log_audit(db, admin, "delete_board", "board", board.id, {"board_id": board_id})
    return {"message": "Board deleted"}


# ===== Session Routes =====

@api_router.post("/boards/{board_id}/unlock", response_model=SessionResponse)
async def unlock_board(board_id: str, data: UnlockRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Check for existing active session
    existing = await get_active_session_for_board(db, board.id)
    if existing:
        raise HTTPException(status_code=400, detail="Board already has an active session")
    
    # Calculate expires_at for per_time mode
    expires_at = None
    if data.pricing_mode == PricingMode.PER_TIME.value and data.minutes:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=data.minutes)
    
    session = Session(
        board_id=board.id,
        pricing_mode=data.pricing_mode,
        game_type=data.game_type,
        credits_total=data.credits or 0,
        credits_remaining=data.credits or 0,
        minutes_total=data.minutes or 0,
        price_total=data.price_total,
        players_count=data.players_count,
        expires_at=expires_at,
        unlocked_by_user_id=user.id,
        status=SessionStatus.ACTIVE.value
    )
    db.add(session)
    
    board.status = BoardStatus.UNLOCKED.value
    await db.flush()
    
    await log_audit(db, user, "unlock_board", "session", session.id, {
        "board_id": board_id,
        "pricing_mode": data.pricing_mode,
        "price_total": data.price_total
    })
    
    return SessionResponse(
        id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
        game_type=session.game_type, credits_total=session.credits_total,
        credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
        price_total=session.price_total, started_at=session.started_at,
        expires_at=session.expires_at, ended_at=session.ended_at,
        players_count=session.players_count, players=session.players or [],
        status=session.status
    )


@api_router.post("/boards/{board_id}/extend", response_model=SessionResponse)
async def extend_session(board_id: str, data: ExtendRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    session = await get_active_session_for_board(db, board.id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session to extend")
    
    if data.credits:
        session.credits_remaining += data.credits
        session.credits_total += data.credits
    
    if data.minutes:
        session.minutes_total += data.minutes
        if session.expires_at:
            session.expires_at = session.expires_at + timedelta(minutes=data.minutes)
        else:
            session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=data.minutes)
    
    await db.flush()
    await log_audit(db, user, "extend_session", "session", session.id, {
        "board_id": board_id,
        "credits": data.credits,
        "minutes": data.minutes
    })
    
    return SessionResponse(
        id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
        game_type=session.game_type, credits_total=session.credits_total,
        credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
        price_total=session.price_total, started_at=session.started_at,
        expires_at=session.expires_at, ended_at=session.ended_at,
        players_count=session.players_count, players=session.players or [],
        status=session.status
    )


@api_router.post("/boards/{board_id}/lock")
async def lock_board(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    session = await get_active_session_for_board(db, board.id)
    if session:
        session.status = SessionStatus.CANCELLED.value
        session.ended_at = datetime.now(timezone.utc)
        session.ended_reason = "manual_lock"
    
    board.status = BoardStatus.LOCKED.value
    await db.flush()
    
    await log_audit(db, user, "lock_board", "board", board.id, {"board_id": board_id})
    return {"message": "Board locked", "board_id": board_id}


@api_router.get("/boards/{board_id}/session")
async def get_board_session(board_id: str, db: AsyncSession = Depends(get_db)):
    """Get current session for kiosk (no auth required for kiosk display)"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    session = await get_active_session_for_board(db, board.id)
    
    return {
        "board_status": board.status,
        "session": SessionResponse(
            id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
            game_type=session.game_type, credits_total=session.credits_total,
            credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
            price_total=session.price_total, started_at=session.started_at,
            expires_at=session.expires_at, ended_at=session.ended_at,
            players_count=session.players_count, players=session.players or [],
            status=session.status
        ) if session else None
    }


# ===== Kiosk Actions (called from kiosk UI) =====

@api_router.post("/kiosk/{board_id}/start-game")
async def kiosk_start_game(board_id: str, data: StartGameRequest, db: AsyncSession = Depends(get_db)):
    """Called when customer starts a game on kiosk"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    session = await get_active_session_for_board(db, board.id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session - board must be unlocked first")
    
    # Check credits for per_game mode
    if session.pricing_mode == PricingMode.PER_GAME.value:
        if session.credits_remaining <= 0:
            raise HTTPException(status_code=400, detail="No credits remaining")
    
    # Check time for per_time mode
    if session.pricing_mode == PricingMode.PER_TIME.value:
        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
            raise HTTPException(status_code=400, detail="Session time expired")
    
    # Update session
    session.game_type = data.game_type
    session.players = data.players
    session.players_count = len(data.players)
    board.status = BoardStatus.IN_GAME.value
    
    await db.flush()
    
    return {
        "message": "Game started",
        "game_type": data.game_type,
        "players": data.players,
        "session_id": session.id
    }


@api_router.post("/kiosk/{board_id}/end-game")
async def kiosk_end_game(board_id: str, db: AsyncSession = Depends(get_db)):
    """Called when a game ends (from autodarts integration or manual)"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    session = await get_active_session_for_board(db, board.id)
    if not session:
        return {"message": "No active session"}
    
    should_lock = False
    
    # Decrement credits for per_game mode
    if session.pricing_mode == PricingMode.PER_GAME.value:
        session.credits_remaining = max(0, session.credits_remaining - 1)
        if session.credits_remaining <= 0:
            should_lock = True
    
    # Check time for per_time mode
    if session.pricing_mode == PricingMode.PER_TIME.value:
        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
            should_lock = True
    
    if should_lock:
        session.status = SessionStatus.FINISHED.value
        session.ended_at = datetime.now(timezone.utc)
        session.ended_reason = "credits_exhausted" if session.pricing_mode == PricingMode.PER_GAME.value else "time_expired"
        board.status = BoardStatus.LOCKED.value
    else:
        board.status = BoardStatus.UNLOCKED.value
    
    await db.flush()
    
    return {
        "message": "Game ended",
        "should_lock": should_lock,
        "credits_remaining": session.credits_remaining,
        "board_status": board.status
    }


@api_router.post("/kiosk/{board_id}/call-staff")
async def kiosk_call_staff(board_id: str, db: AsyncSession = Depends(get_db)):
    """Customer requests staff assistance"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    await log_audit(db, None, "call_staff", "board", board.id, {"board_id": board_id})
    return {"message": "Staff notified", "board_id": board_id}


# ===== Settings Routes =====

@api_router.get("/settings/branding")
async def get_branding(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "branding", DEFAULT_BRANDING)


@api_router.put("/settings/branding")
async def update_branding(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "branding"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="branding", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_branding", "settings", "branding")
    return setting.value


@api_router.get("/settings/pricing")
async def get_pricing(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "pricing", DEFAULT_PRICING)


@api_router.put("/settings/pricing")
async def update_pricing(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "pricing"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="pricing", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_pricing", "settings", "pricing")
    return setting.value


@api_router.get("/settings/palettes")
async def get_palettes(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "palettes", DEFAULT_PALETTES)


@api_router.put("/settings/palettes")
async def update_palettes(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "palettes"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="palettes", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_palettes", "settings", "palettes")
    return setting.value


# ===== Asset Upload =====

@api_router.post("/assets/upload")
async def upload_asset(file: UploadFile = File(...), admin: User = Depends(require_admin)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
    allowed_types = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Save file
    ext = file.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = ASSETS_DIR / filename
    
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"filename": filename, "url": f"/api/assets/{filename}"}


@api_router.get("/assets/{filename}")
async def get_asset(filename: str):
    filepath = ASSETS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(filepath)


# ===== Logs & Revenue =====

@api_router.get("/logs/audit", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        query = query.where(AuditLog.action == action)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    return [AuditLogResponse(
        id=l.id, username=l.username, action=l.action, entity_type=l.entity_type,
        entity_id=l.entity_id, details=l.details, created_at=l.created_at
    ) for l in logs]


@api_router.get("/logs/sessions")
async def get_session_logs(
    limit: int = 100,
    board_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Session).order_by(Session.started_at.desc()).limit(limit)
    if board_id:
        result = await db.execute(select(Board).where(Board.board_id == board_id))
        board = result.scalar_one_or_none()
        if board:
            query = query.where(Session.board_id == board.id)
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    return [SessionResponse(
        id=s.id, board_id=s.board_id, pricing_mode=s.pricing_mode,
        game_type=s.game_type, credits_total=s.credits_total,
        credits_remaining=s.credits_remaining, minutes_total=s.minutes_total,
        price_total=s.price_total, started_at=s.started_at,
        expires_at=s.expires_at, ended_at=s.ended_at,
        players_count=s.players_count, players=s.players or [],
        status=s.status
    ) for s in sessions]


@api_router.get("/revenue/summary")
async def get_revenue_summary(
    days: int = 7,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get revenue summary for the last N days"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = await db.execute(
        select(Session)
        .where(Session.started_at >= start_date)
        .where(Session.status.in_([SessionStatus.FINISHED.value, SessionStatus.EXPIRED.value, SessionStatus.CANCELLED.value]))
    )
    sessions = result.scalars().all()
    
    # Group by date
    by_date = {}
    for s in sessions:
        date_str = s.started_at.strftime("%Y-%m-%d")
        if date_str not in by_date:
            by_date[date_str] = {"total": 0.0, "count": 0, "by_board": {}}
        by_date[date_str]["total"] += s.price_total
        by_date[date_str]["count"] += 1
    
    return {
        "period_days": days,
        "total_revenue": sum(d["total"] for d in by_date.values()),
        "total_sessions": sum(d["count"] for d in by_date.values()),
        "by_date": by_date
    }


# ===== Agent API (for Master-Agent communication) =====

@api_router.get("/agent/health")
async def agent_health():
    return {"status": "ok", "mode": MODE, "timestamp": datetime.now(timezone.utc).isoformat()}


@api_router.get("/agent/status")
async def agent_status(request: Request, db: AsyncSession = Depends(get_db)):
    # For local agent, return local board status
    local_board_id = os.environ.get('LOCAL_BOARD_ID', 'BOARD-1')
    result = await db.execute(select(Board).where(Board.board_id == local_board_id))
    board = result.scalar_one_or_none()
    
    if not board:
        return {"error": "Local board not configured"}
    
    session = await get_active_session_for_board(db, board.id)
    
    return AgentStatusResponse(
        board_id=board.board_id,
        status=board.status,
        current_session=SessionResponse(
            id=session.id, board_id=session.board_id, pricing_mode=session.pricing_mode,
            game_type=session.game_type, credits_total=session.credits_total,
            credits_remaining=session.credits_remaining, minutes_total=session.minutes_total,
            price_total=session.price_total, started_at=session.started_at,
            expires_at=session.expires_at, ended_at=session.ended_at,
            players_count=session.players_count, players=session.players or [],
            status=session.status
        ) if session else None,
        mode=MODE
    )


# ===== Root & Health =====

@api_router.get("/")
async def root():
    return {"message": "Darts Kiosk System API", "mode": MODE}


@api_router.get("/health")
async def health():
    return {"status": "healthy", "mode": MODE}


# ===== Setup Wizard Routes =====

@api_router.get("/setup/status")
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Check if first-run setup is needed"""
    return await check_setup_status(db)


@api_router.post("/setup/complete")
async def complete_first_setup(config: SetupConfig, db: AsyncSession = Depends(get_db)):
    """Complete first-run setup with secure credentials"""
    # Validate
    if len(config.admin_password) < 8:
        raise HTTPException(status_code=400, detail="Admin password must be at least 8 characters")
    if len(config.staff_pin) != 4 or not config.staff_pin.isdigit():
        raise HTTPException(status_code=400, detail="Staff PIN must be exactly 4 digits")
    
    results = await complete_setup(db, config)
    return {
        "success": True,
        "results": results,
        "restart_required": results.get("secrets_generated", False),
        "message": "Setup complete. Please restart the server if new secrets were generated."
    }


# ===== Health Monitoring Routes =====

@api_router.get("/health/detailed")
async def get_detailed_health(admin: User = Depends(require_admin)):
    """Get detailed system health status"""
    from dataclasses import asdict
    health_data = health_monitor.get_health()
    return asdict(health_data)


@api_router.get("/health/screenshot/{filename}")
async def get_error_screenshot(filename: str, admin: User = Depends(require_admin)):
    """Get an error screenshot"""
    screenshots_dir = DATA_DIR / 'autodarts_debug'
    filepath = screenshots_dir / filename
    
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    
    # Security check - prevent path traversal
    if not str(filepath.resolve()).startswith(str(screenshots_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(filepath, media_type="image/png")


@api_router.get("/health/screenshots")
async def list_error_screenshots(admin: User = Depends(require_admin)):
    """List all error screenshots"""
    return health_monitor.get_error_screenshots()


# ===== Backup Routes =====

@api_router.get("/backups")
async def list_backups(admin: User = Depends(require_admin)):
    """List all available backups"""
    backups = backup_service.list_backups()
    return {
        "backups": [
            {
                "filename": b.filename,
                "size_bytes": b.size_bytes,
                "size_mb": round(b.size_bytes / (1024 * 1024), 2),
                "created_at": b.created_at.isoformat(),
                "compressed": b.compressed
            }
            for b in backups
        ],
        "stats": backup_service.get_backup_stats()
    }


@api_router.post("/backups/create")
async def create_backup(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Create a new backup immediately"""
    backup = backup_service.create_backup()
    if not backup:
        raise HTTPException(status_code=500, detail="Backup creation failed")
    
    await log_audit(db, admin, "create_backup", "backup", backup.filename)
    
    return {
        "success": True,
        "backup": {
            "filename": backup.filename,
            "size_bytes": backup.size_bytes,
            "created_at": backup.created_at.isoformat()
        }
    }


@api_router.get("/backups/download/{filename}")
async def download_backup(filename: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Download a backup file"""
    backup_path = backup_service.get_backup_path(filename)
    
    if not backup_path:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    await log_audit(db, admin, "download_backup", "backup", filename)
    
    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename=filename
    )


@api_router.post("/backups/restore/{filename}")
async def restore_backup(filename: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Restore database from a backup (requires restart)"""
    success = backup_service.restore_backup(filename)
    
    if not success:
        raise HTTPException(status_code=500, detail="Restore failed")
    
    await log_audit(db, admin, "restore_backup", "backup", filename)
    
    return {
        "success": True,
        "message": "Database restored. Please restart the server.",
        "restart_required": True
    }


@api_router.delete("/backups/{filename}")
async def delete_backup(filename: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Delete a backup file"""
    success = backup_service.delete_backup(filename)
    
    if not success:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    await log_audit(db, admin, "delete_backup", "backup", filename)
    
    return {"success": True, "message": "Backup deleted"}


# ===== Update Routes =====

@api_router.get("/updates/status")
async def get_update_status(admin: User = Depends(require_admin)):
    """Get current version and available updates"""
    return {
        "current_version": update_service.get_current_version(),
        "available_versions": [
            {
                "version": v.version,
                "tag": v.tag,
                "is_current": v.is_current,
                "is_stable": v.is_stable
            }
            for v in update_service.get_available_versions()
        ],
        "update_history": update_service.get_update_history(10)
    }


@api_router.post("/updates/agent/{board_id}")
async def update_agent(board_id: str, target_version: str = "latest", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Update a specific agent to a new version"""
    # Get board agent URL
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    
    if not board or not board.agent_api_base_url:
        raise HTTPException(status_code=404, detail="Board or agent URL not found")
    
    update_result = await update_service.update_agent(board_id, board.agent_api_base_url, target_version)
    
    await log_audit(db, admin, "update_agent", "board", board_id, {
        "target_version": target_version,
        "success": update_result.success
    })
    
    return {
        "success": update_result.success,
        "message": update_result.message,
        "details": {
            "board_id": update_result.board_id,
            "old_version": update_result.old_version,
            "new_version": update_result.new_version
        }
    }


@api_router.post("/updates/all-agents")
async def update_all_agents(target_version: str = "latest", admin: User = Depends(require_admin)):
    """Update all registered agents"""
    results = await update_service.update_all_agents(target_version)
    
    return {
        "total": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [
            {
                "board_id": r.board_id,
                "success": r.success,
                "message": r.message
            }
            for r in results
        ]
    }


@api_router.post("/updates/local")
async def update_local(target_version: str = "latest", admin: User = Depends(require_admin)):
    """Get instructions for local update"""
    return update_service.trigger_local_update(target_version)


@api_router.post("/updates/rollback/{board_id}")
async def rollback_agent(board_id: str, target_version: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Rollback an agent to a previous version"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    
    if not board or not board.agent_api_base_url:
        raise HTTPException(status_code=404, detail="Board or agent URL not found")
    
    rollback_result = await update_service.rollback_agent(board_id, board.agent_api_base_url, target_version)
    
    return {
        "success": rollback_result.success,
        "message": rollback_result.message
    }


# ===== Agent Update Endpoint (called by master) =====

@api_router.post("/agent/update")
async def agent_receive_update(request: Request, data: dict):
    """Receive update command from master (agent endpoint)"""
    # Verify agent secret
    if not verify_agent_secret(request):
        raise HTTPException(status_code=403, detail="Invalid agent secret")
    
    target_version = data.get("target_version", "latest")
    
    # In production, this would trigger docker pull + restart
    logger.info(f"Received update command: {target_version}")
    
    return {
        "success": True,
        "message": f"Update to {target_version} initiated",
        "note": "Container will restart shortly"
    }


# Include router
app.include_router(api_router)
