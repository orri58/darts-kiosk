"""
SQLAlchemy Models for Darts Kiosk System
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum

from backend.database import Base


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STAFF = "staff"


class BoardStatus(str, enum.Enum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    IN_GAME = "in_game"
    OFFLINE = "offline"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    FINISHED = "finished"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PricingMode(str, enum.Enum):
    PER_GAME = "per_game"
    PER_TIME = "per_time"
    PER_PLAYER = "per_player"


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    pin_hash = Column(String(255), nullable=True)  # Quick PIN for staff
    role = Column(String(20), nullable=False, default=UserRole.STAFF.value)
    display_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Board(Base):
    __tablename__ = "boards"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    board_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g. "BOARD-1"
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
    autodarts_target_url = Column(String(500), nullable=True)
    agent_api_base_url = Column(String(500), nullable=True)
    agent_secret = Column(String(255), nullable=True)
    status = Column(String(20), default=BoardStatus.LOCKED.value)
    last_heartbeat_at = Column(DateTime, nullable=True)
    is_master = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    sessions = relationship("Session", back_populates="board")


class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    board_id = Column(String(36), ForeignKey("boards.id"), nullable=False, index=True)
    pricing_mode = Column(String(20), nullable=False)  # per_game, per_time, per_player
    game_type = Column(String(50), nullable=True)  # 301, 501, Cricket, etc.
    
    # Pricing data
    credits_total = Column(Integer, default=0)
    credits_remaining = Column(Integer, default=0)
    minutes_total = Column(Integer, default=0)
    price_per_unit = Column(Float, default=0.0)
    price_total = Column(Float, default=0.0)
    
    # Time tracking
    started_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Players
    players_count = Column(Integer, default=1)
    players = Column(JSON, default=list)  # List of player names
    
    # Status
    status = Column(String(20), default=SessionStatus.ACTIVE.value)
    ended_reason = Column(String(100), nullable=True)
    
    # Tracking
    unlocked_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    board = relationship("Board", back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)  # board, session, user, settings
    entity_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class TrustedPeer(Base):
    """Stores paired Master/Agent relationships after secure pairing"""
    __tablename__ = "trusted_peers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    board_id = Column(String(50), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "master" or "agent"
    ip = Column(String(50), nullable=False)
    port = Column(Integer, nullable=True)
    version = Column(String(20), nullable=True)
    fingerprint = Column(String(64), nullable=False)
    paired_token_hash = Column(String(255), nullable=False)
    paired_at = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow)
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSON, nullable=True)


class MatchResult(Base):
    """Public match result with expiring token for QR code sharing"""
    __tablename__ = "match_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    public_token = Column(String(64), unique=True, nullable=False, index=True)
    board_id = Column(String(50), nullable=False)
    board_name = Column(String(100), nullable=True)
    game_type = Column(String(50), nullable=False)
    players = Column(JSON, default=list)
    winner = Column(String(100), nullable=True)
    scores = Column(JSON, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    played_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Player(Base):
    """
    Guest-first player model. Guests have just a nickname.
    Registered players (Stammkunden) add a PIN and optionally a QR token.
    """
    __tablename__ = "players"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    nickname = Column(String(50), unique=True, nullable=False, index=True)
    nickname_lower = Column(String(50), unique=True, nullable=False, index=True)
    pin_hash = Column(String(255), nullable=True)  # None = guest
    qr_token = Column(String(64), unique=True, nullable=True, index=True)
    is_registered = Column(Boolean, default=False)
    games_played = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    last_played_at = Column(DateTime, nullable=True)


# Default palettes data
DEFAULT_PALETTES = [
    {
        "id": "industrial",
        "name": "Industrial",
        "colors": {
            "bg": "#09090b",
            "surface": "#18181b",
            "primary": "#f59e0b",
            "secondary": "#ffffff",
            "accent": "#ef4444",
            "text": "#e4e4e7"
        }
    },
    {
        "id": "midnight",
        "name": "Midnight",
        "colors": {
            "bg": "#0f172a",
            "surface": "#1e293b",
            "primary": "#3b82f6",
            "secondary": "#e2e8f0",
            "accent": "#8b5cf6",
            "text": "#f1f5f9"
        }
    },
    {
        "id": "forest",
        "name": "Forest",
        "colors": {
            "bg": "#0c0f0a",
            "surface": "#1a1f1a",
            "primary": "#22c55e",
            "secondary": "#d1fae5",
            "accent": "#f59e0b",
            "text": "#ecfdf5"
        }
    },
    {
        "id": "crimson",
        "name": "Crimson",
        "colors": {
            "bg": "#0a0506",
            "surface": "#1c1011",
            "primary": "#dc2626",
            "secondary": "#fecaca",
            "accent": "#f59e0b",
            "text": "#fef2f2"
        }
    },
    {
        "id": "ocean",
        "name": "Ocean",
        "colors": {
            "bg": "#0a1628",
            "surface": "#0f2847",
            "primary": "#06b6d4",
            "secondary": "#cffafe",
            "accent": "#f472b6",
            "text": "#e0f2fe"
        }
    },
    {
        "id": "sunset",
        "name": "Sunset",
        "colors": {
            "bg": "#1a0a0a",
            "surface": "#2d1414",
            "primary": "#f97316",
            "secondary": "#fef3c7",
            "accent": "#ec4899",
            "text": "#ffedd5"
        }
    },
    {
        "id": "slate",
        "name": "Slate",
        "colors": {
            "bg": "#0f1115",
            "surface": "#1c1f26",
            "primary": "#a1a1aa",
            "secondary": "#e4e4e7",
            "accent": "#f59e0b",
            "text": "#fafafa"
        }
    },
    {
        "id": "emerald",
        "name": "Emerald",
        "colors": {
            "bg": "#022c22",
            "surface": "#064e3b",
            "primary": "#10b981",
            "secondary": "#a7f3d0",
            "accent": "#fbbf24",
            "text": "#d1fae5"
        }
    }
]

DEFAULT_PRICING = {
    "mode": "per_game",
    "per_game": {
        "price_per_credit": 2.0,
        "default_credits": 3,
        "currency": "EUR"
    },
    "per_time": {
        "price_per_30_min": 5.0,
        "price_per_60_min": 8.0,
        "currency": "EUR"
    },
    "per_player": {
        "price_per_player": 1.5,
        "currency": "EUR"
    },
    "max_players": 4,
    "idle_timeout_minutes": 5,
    "allowed_game_types": ["301", "501", "Cricket", "Training"]
}

DEFAULT_STAMMKUNDE_DISPLAY = {
    "enabled": False,
    "period": "month",
    "interval_seconds": 6,
    "max_entries": 3,
    "nickname_max_length": 15,
}

DEFAULT_SOUND_CONFIG = {
    "enabled": False,
    "volume": 70,
    "sound_pack": "default",
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "rate_limit_ms": 1500,
}

DEFAULT_LANGUAGE = {
    "language": "de",
}

DEFAULT_BRANDING = {
    "cafe_name": "Dart Zone",
    "subtitle": "Darts & More",
    "logo_url": None,
    "palette_id": "industrial",
    "font_preset": "industrial",
    "background_style": "solid"
}

DEFAULT_KIOSK_TEXTS = {
    "locked_title": "GESPERRT",
    "locked_subtitle": "Bitte an der Theke freischalten lassen",
    "pricing_hint": "",
    "game_running": "SPIEL LÄUFT",
    "game_finished": "SPIEL BEENDET",
    "call_staff": "Personal rufen",
    "credits_label": "Spiele übrig",
    "time_label": "Zeit übrig",
    "staff_hint": "",
    "upsell_message": "Weitere Spiele an der Theke freischalten",
    "upsell_pricing": "",
}

DEFAULT_PWA_CONFIG = {
    "app_name": "Darts Kiosk",
    "short_name": "Darts",
    "theme_color": "#09090b",
    "background_color": "#09090b",
}

DEFAULT_LOCKSCREEN_QR = {
    "enabled": False,
    "label": "Leaderboard & Stats",
    "path": "/public/leaderboard",
}

DEFAULT_OVERLAY_CONFIG = {
    "enabled": True,
    "position": "bottom-left",
}

DEFAULT_POST_MATCH_DELAY = {
    "delay_ms": 5000,
}

DEFAULT_AUTODARTS_DESKTOP = {
    "exe_path": "C:\\Program Files\\Autodarts\\Autodarts.exe",
    "auto_start": False,
}
